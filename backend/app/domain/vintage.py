"""Point-in-time (as-of) forecast vintage selection.

Core rule, for delivery interval ``t`` and decision cutoff ``c``::

    selected_forecast(t, c) = forecast(t, max(publish_time where publish_time <= c))

A forecast published after the cutoff is NEVER selected, and there is no
fallback to the latest forecast. If nothing eligible exists the result is
``None`` and the interval is reported as missing.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.domain.models import ForecastRecord
from app.domain.timeutil import ensure_utc


@dataclass(frozen=True, slots=True)
class Vintage:
    publish_time: datetime
    generation_mw: float


class VintageIndex:
    """All forecast vintages per target interval, sorted by publish time."""

    def __init__(self, records: Iterable[ForecastRecord]) -> None:
        grouped: dict[datetime, list[Vintage]] = defaultdict(list)
        for r in records:
            grouped[ensure_utc(r.start_time)].append(Vintage(ensure_utc(r.publish_time), r.generation_mw))
        self._by_target: dict[datetime, list[Vintage]] = {}
        self._publish_keys: dict[datetime, list[datetime]] = {}
        for target, vintages in grouped.items():
            vintages.sort(key=lambda v: v.publish_time)
            self._by_target[target] = vintages
            self._publish_keys[target] = [v.publish_time for v in vintages]

    def vintages(self, target: datetime) -> list[Vintage]:
        return list(self._by_target.get(ensure_utc(target), []))

    def select(self, target: datetime, cutoff: datetime) -> Vintage | None:
        """Latest vintage for ``target`` with ``publish_time <= cutoff`` (inclusive)."""
        target = ensure_utc(target)
        cutoff = ensure_utc(cutoff)
        keys = self._publish_keys.get(target)
        if not keys:
            return None
        idx = bisect_right(keys, cutoff)  # first index with publish > cutoff
        if idx == 0:
            return None
        chosen = self._by_target[target][idx - 1]
        # Defensive invariant: look-ahead must be impossible.
        assert chosen.publish_time <= cutoff
        return chosen

    def targets(self) -> list[datetime]:
        return sorted(self._by_target)


def select_eligible_forecast(records: Iterable[ForecastRecord], target: datetime, cutoff: datetime) -> Vintage | None:
    """Pure functional form of :meth:`VintageIndex.select` for a record list."""
    target = ensure_utc(target)
    cutoff = ensure_utc(cutoff)
    best: Vintage | None = None
    for r in records:
        if ensure_utc(r.start_time) != target:
            continue
        p = ensure_utc(r.publish_time)
        if p > cutoff:
            continue
        if best is None or p > best.publish_time:
            best = Vintage(p, r.generation_mw)
    return best
