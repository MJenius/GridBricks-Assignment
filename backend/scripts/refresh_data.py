"""Reproducible snapshot refresh from the Elexon Insights API.

Usage (from backend/):  python -m scripts.refresh_data [--out ../data/snapshot]

Writes:
  raw/windfor.json.gz        all WINDFOR vintages published in the window (as returned)
  raw/fuelhh_wind.json.gz    FUELHH rows filtered to fuelType=WIND (as returned)
  normalized/forecasts.csv   start_time_utc,publish_time_utc,generation_mw
  normalized/actuals.csv     start_time_utc,settlement_date,settlement_period,publish_time_utc,generation_mw
  manifest.json              source, queries, retrieval time, record counts, schema
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from app.config import get_settings
from app.services.elexon import FUELHH_PATH, WINDFOR_PATH, ElexonClient
from app.services.normalize import normalize_actuals, normalize_forecasts
from app.services.repository import fetch_live, retrieval_window


def _write_gz(path: Path, rows: list[dict[str, object]]) -> str:
    data = json.dumps(rows, separators=(",", ":"), sort_keys=True).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(path, "wb", mtime=0) as fh:
        fh.write(data)
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


async def main(out: Path) -> None:
    settings = get_settings()
    window = retrieval_window(settings)
    client = ElexonClient(settings.elexon_base_url, settings.http_timeout_s, settings.http_max_retries)
    retrieved_at = datetime.now(UTC)
    raw_f, raw_a = await fetch_live(client, window)
    # Stable ordering for reproducible files.
    raw_f.sort(key=lambda r: (str(r.get("publishTime")), str(r.get("startTime"))))
    raw_a.sort(key=lambda r: (str(r.get("startTime")), str(r.get("publishTime"))))

    sha_f = _write_gz(out / "raw" / "windfor.json.gz", raw_f)
    sha_a = _write_gz(out / "raw" / "fuelhh_wind.json.gz", raw_a)

    forecasts, fq = normalize_forecasts(raw_f)
    actuals, aq = normalize_actuals(raw_a)
    (out / "normalized").mkdir(parents=True, exist_ok=True)
    with open(out / "normalized" / "forecasts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["start_time_utc", "publish_time_utc", "generation_mw"])
        for f in forecasts:
            w.writerow([_iso(f.start_time), _iso(f.publish_time), f.generation_mw])
    with open(out / "normalized" / "actuals.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["start_time_utc", "settlement_date", "settlement_period", "publish_time_utc", "generation_mw"])
        for a in actuals:
            w.writerow(
                [
                    _iso(a.start_time),
                    a.settlement_date.isoformat() if a.settlement_date else "",
                    a.settlement_period or "",
                    _iso(a.publish_time) if a.publish_time else "",
                    a.generation_mw,
                ]
            )

    base = settings.elexon_base_url
    manifest = {
        "source_kind": "snapshot",
        "label": "Elexon Insights API historical snapshot",
        "provider": "Elexon BMRS Insights Solution",
        "retrieved_at": retrieved_at.isoformat(),
        "decision_period": {"from": settings.decision_start.isoformat(), "to": settings.decision_end.isoformat()},
        "queries": [
            {
                "dataset": "WINDFOR",
                "url": f"{base}{WINDFOR_PATH}?"
                + urlencode(
                    {"publishDateTimeFrom": _iso(window.publish_from), "publishDateTimeTo": _iso(window.publish_to)}
                ),
                "note": "Queried by publish time in 7-day chunks to preserve every historical vintage.",
            },
            {
                "dataset": "FUELHH",
                "url": f"{base}{FUELHH_PATH}?"
                + urlencode(
                    {
                        "settlementDateFrom": window.settlement_from.isoformat(),
                        "settlementDateTo": window.settlement_to.isoformat(),
                        "fuelType": "WIND",
                    }
                ),
            },
        ],
        "record_counts": {
            "windfor_raw": len(raw_f),
            "windfor_normalized": fq.accepted,
            "windfor_publish_times": len({f.publish_time for f in forecasts}),
            "fuelhh_raw": len(raw_a),
            "fuelhh_normalized": aq.accepted,
        },
        "quality": {"forecasts": fq.as_dict(), "actuals": aq.as_dict()},
        "sha256": {"raw/windfor.json.gz": sha_f, "raw/fuelhh_wind.json.gz": sha_a},
        "schema": {
            "WINDFOR": {
                "dataset": "str",
                "publishTime": "ISO-8601 UTC",
                "startTime": "ISO-8601 UTC (hourly)",
                "generation": "MW",
            },
            "FUELHH": {
                "dataset": "str",
                "publishTime": "ISO-8601 UTC",
                "startTime": "ISO-8601 UTC (half-hourly)",
                "settlementDate": "YYYY-MM-DD",
                "settlementPeriod": "int 1-50",
                "fuelType": "str",
                "generation": "MW",
            },
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest["record_counts"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=get_settings().snapshot_dir)
    args = parser.parse_args()
    asyncio.run(main(args.out))
