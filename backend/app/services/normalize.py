"""Normalise raw Elexon rows into domain records with a deterministic policy.

Duplicate policy (documented in docs/METHODOLOGY.md):

* WINDFOR key = (startTime, publishTime). Identical duplicates collapse to one.
  Rows with the same key but different ``generation`` are *conflicting*: the
  source offers no field to arbitrate, so the key is excluded and counted.
  Values are never averaged.
* FUELHH key = startTime (WIND only). The row with the latest ``publishTime``
  wins (a later settlement-data revision supersedes an earlier one). If the
  latest publishTime is shared by rows with different values, the key is
  excluded as conflicting.

Invalid rows (missing/unparseable timestamps, non-numeric, non-finite or
negative generation, wrong fuel type) are dropped and counted.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

from app.domain.models import ActualRecord, DataQualityReport, ForecastRecord
from app.domain.timeutil import parse_utc


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out < 0:
        return None
    return out


def normalize_forecasts(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[list[ForecastRecord], DataQualityReport]:
    received = invalid = exact = 0
    buckets: dict[tuple[datetime, datetime], set[float]] = defaultdict(set)
    for row in rows:
        received += 1
        start = parse_utc(row.get("startTime"))
        publish = parse_utc(row.get("publishTime"))
        gen = _number(row.get("generation"))
        if start is None or publish is None or gen is None:
            invalid += 1
            continue
        key = (start, publish)
        if key in buckets and gen in buckets[key]:
            exact += 1
        buckets[key].add(gen)

    records: list[ForecastRecord] = []
    conflicting = 0
    for (start, publish), values in buckets.items():
        if len(values) > 1:
            conflicting += 1
            continue
        records.append(ForecastRecord(start, publish, next(iter(values))))
    records.sort(key=lambda r: (r.start_time, r.publish_time))
    return records, DataQualityReport(received, len(records), invalid, exact, conflicting)


def normalize_actuals(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[list[ActualRecord], DataQualityReport]:
    received = invalid = exact = 0
    by_start: dict[datetime, list[ActualRecord]] = defaultdict(list)
    for row in rows:
        received += 1
        if str(row.get("fuelType", "")).upper() != "WIND":
            invalid += 1
            continue
        start = parse_utc(row.get("startTime"))
        gen = _number(row.get("generation"))
        if start is None or gen is None:
            invalid += 1
            continue
        publish = parse_utc(row.get("publishTime"))
        sd_raw = row.get("settlementDate")
        try:
            sd = date.fromisoformat(sd_raw) if isinstance(sd_raw, str) else None
        except ValueError:
            sd = None
        sp_raw = row.get("settlementPeriod")
        sp = sp_raw if isinstance(sp_raw, int) and not isinstance(sp_raw, bool) else None
        rec = ActualRecord(start, publish, sd, sp, gen)
        if rec in by_start[start]:
            exact += 1
            continue
        by_start[start].append(rec)

    records: list[ActualRecord] = []
    conflicting = superseded = 0
    epoch = datetime.min.replace(tzinfo=None)
    for recs in by_start.values():

        def pkey(r: ActualRecord) -> datetime:
            return r.publish_time.replace(tzinfo=None) if r.publish_time else epoch

        latest = max(pkey(r) for r in recs)
        top = [r for r in recs if pkey(r) == latest]
        superseded += len(recs) - len(top)
        if len({r.generation_mw for r in top}) > 1:
            conflicting += 1
            continue
        records.append(top[0])
    records.sort(key=lambda r: r.start_time)
    return records, DataQualityReport(received, len(records), invalid, exact, conflicting, superseded)
