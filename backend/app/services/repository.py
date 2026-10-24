"""Data access: packaged historical snapshot or live Elexon with a bounded TTL cache."""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import time as _time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from app.config import Settings
from app.domain.models import ActualRecord, DataQualityReport, ForecastRecord
from app.domain.vintage import VintageIndex
from app.services.elexon import ElexonClient, UpstreamError
from app.services.normalize import normalize_actuals, normalize_forecasts

log = logging.getLogger("winddesk.data")

MAX_LEAD_DAYS = 2


@dataclass(frozen=True)
class RetrievalWindow:
    publish_from: datetime
    publish_to: datetime
    settlement_from: date
    settlement_to: date


def retrieval_window(settings: Settings) -> RetrievalWindow:
    """Ranges needed for every decision in scope, plus later revisions.

    Publish window starts 3 days before the first decision (WINDFOR horizon is
    ~3 days) and ends after the last possible delivery day so the revision
    explorer can show post-cutoff vintages.
    """
    last_delivery = settings.decision_end + timedelta(days=MAX_LEAD_DAYS)
    return RetrievalWindow(
        publish_from=datetime.combine(settings.decision_start - timedelta(days=2), time(0), UTC),
        publish_to=datetime.combine(last_delivery + timedelta(days=1), time(0), UTC),
        settlement_from=settings.decision_start,
        settlement_to=last_delivery + timedelta(days=1),
    )


@dataclass
class Provenance:
    source: str  # snapshot | live | fixture
    label: str
    retrieved_at: datetime | None
    loaded_at: datetime
    endpoints: list[str]
    quality: dict[str, dict[str, int]]
    warnings: list[str] = field(default_factory=list)
    manifest: dict[str, Any] | None = None


@dataclass
class Dataset:
    forecasts: list[ForecastRecord]
    actuals: list[ActualRecord]
    provenance: Provenance
    index: VintageIndex = field(init=False)
    actuals_by_start: dict[datetime, ActualRecord] = field(init=False)

    def __post_init__(self) -> None:
        self.index = VintageIndex(self.forecasts)
        self.actuals_by_start = {a.start_time: a for a in self.actuals}


def build_dataset(
    raw_forecasts: list[dict[str, Any]],
    raw_actuals: list[dict[str, Any]],
    *,
    source: str,
    label: str,
    retrieved_at: datetime | None,
    endpoints: list[str],
    manifest: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> Dataset:
    forecasts, fq = normalize_forecasts(raw_forecasts)
    actuals, aq = normalize_actuals(raw_actuals)
    return Dataset(
        forecasts,
        actuals,
        Provenance(
            source=source,
            label=label,
            retrieved_at=retrieved_at,
            loaded_at=datetime.now(UTC),
            endpoints=endpoints,
            quality={"forecasts": fq.as_dict(), "actuals": aq.as_dict()},
            warnings=list(warnings or []),
            manifest=manifest,
        ),
    )


def _read_json_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path} does not contain a JSON array")
    return data


def load_snapshot(snapshot_dir: Path) -> Dataset:
    manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    source = manifest.get("source_kind", "snapshot")
    return build_dataset(
        _read_json_gz(snapshot_dir / "raw" / "windfor.json.gz"),
        _read_json_gz(snapshot_dir / "raw" / "fuelhh_wind.json.gz"),
        source=source,
        label=manifest.get("label", "Elexon historical snapshot"),
        retrieved_at=datetime.fromisoformat(manifest["retrieved_at"]) if manifest.get("retrieved_at") else None,
        endpoints=[q["url"] for q in manifest.get("queries", [])],
        manifest=manifest,
    )


async def fetch_live(
    client: ElexonClient, window: RetrievalWindow
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    forecasts, actuals = await asyncio.gather(
        client.fetch_windfor(window.publish_from, window.publish_to),
        client.fetch_fuelhh_wind(window.settlement_from, window.settlement_to),
    )
    return forecasts, actuals


class DataRepository:
    """Serves a :class:`Dataset`.

    * ``snapshot`` mode: loads the packaged snapshot once (read-only filesystem safe).
    * ``live`` mode: fetches Elexon, caches for ``ttl`` seconds (single entry, so
      memory is bounded), coalesces concurrent refreshes behind one lock, and
      falls back to the snapshot with a visible warning if upstream fails.
    """

    def __init__(self, settings: Settings, client: ElexonClient | None = None) -> None:
        self._settings = settings
        self._client = client or ElexonClient(
            settings.elexon_base_url, settings.http_timeout_s, settings.http_max_retries
        )
        self._lock = asyncio.Lock()
        self._snapshot: Dataset | None = None
        self._live: Dataset | None = None
        self._live_expires = 0.0

    def snapshot(self) -> Dataset:
        if self._snapshot is None:
            self._snapshot = load_snapshot(self._settings.snapshot_dir)
        return self._snapshot

    async def get(self) -> Dataset:
        if self._settings.data_source != "live":
            return self.snapshot()
        if self._live is not None and _time.monotonic() < self._live_expires:
            return self._live
        async with self._lock:
            if self._live is not None and _time.monotonic() < self._live_expires:
                return self._live  # another request refreshed while we waited
            window = retrieval_window(self._settings)
            try:
                raw_f, raw_a = await fetch_live(self._client, window)
            except UpstreamError as exc:
                log.warning("live_fetch_failed_using_snapshot", extra={"kind": exc.kind})
                snap = self.snapshot()
                snap.provenance.warnings = [
                    f"Live Elexon query failed ({exc}). Showing the packaged historical snapshot instead."
                ]
                # Retry upstream sooner than a full TTL.
                self._live, self._live_expires = None, 0.0
                return snap
            self._live = build_dataset(
                raw_f,
                raw_a,
                source="live",
                label="Elexon Insights API (live query)",
                retrieved_at=datetime.now(UTC),
                endpoints=[
                    f"{self._settings.elexon_base_url}/datasets/WINDFOR/stream",
                    f"{self._settings.elexon_base_url}/datasets/FUELHH/stream?fuelType=WIND",
                ],
            )
            self._live_expires = _time.monotonic() + self._settings.live_cache_ttl_s
            return self._live


__all__ = ["DataQualityReport", "DataRepository", "Dataset", "build_dataset", "load_snapshot", "retrieval_window"]
