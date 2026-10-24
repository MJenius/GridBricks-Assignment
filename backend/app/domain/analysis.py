"""Decision replay: match eligible forecasts to actuals per delivery interval."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time

from app.domain.metrics import Metrics, Pair, compute_metrics
from app.domain.models import ActualRecord
from app.domain.timeutil import decision_cutoff_utc, decision_date_for, interval_starts
from app.domain.vintage import VintageIndex

#: WINDFOR targets are hourly; scoring is done on the hourly grid where both
#: a forecast target and a FUELHH half-hour start coincide.
FORECAST_STEP_MINUTES = 60
ACTUAL_STEP_MINUTES = 30


@dataclass(frozen=True, slots=True)
class IntervalResult:
    start_time: datetime
    forecast_mw: float | None
    publish_time: datetime | None
    actual_mw: float | None

    @property
    def error_mw(self) -> float | None:
        if self.forecast_mw is None or self.actual_mw is None:
            return None
        return self.forecast_mw - self.actual_mw

    @property
    def status(self) -> str:
        if self.forecast_mw is None and self.actual_mw is None:
            return "missing_both"
        if self.forecast_mw is None:
            return "missing_forecast"
        if self.actual_mw is None:
            return "missing_actual"
        return "matched"

    @property
    def horizon_hours(self) -> float | None:
        if self.publish_time is None:
            return None
        return (self.start_time - self.publish_time).total_seconds() / 3600.0


@dataclass(frozen=True, slots=True)
class DayResult:
    delivery_date: date
    decision_date: date
    cutoff_utc: datetime
    intervals: list[IntervalResult]
    metrics: Metrics

    @property
    def expected(self) -> int:
        return len(self.intervals)

    @property
    def forecast_available(self) -> int:
        return sum(1 for i in self.intervals if i.forecast_mw is not None)

    @property
    def actual_available(self) -> int:
        return sum(1 for i in self.intervals if i.actual_mw is not None)

    @property
    def vintages_used(self) -> list[datetime]:
        return sorted({i.publish_time for i in self.intervals if i.publish_time is not None})


def pairs_of(intervals: Sequence[IntervalResult]) -> list[Pair]:
    return [
        Pair(i.forecast_mw, i.actual_mw) for i in intervals if i.forecast_mw is not None and i.actual_mw is not None
    ]


def analyse_day(
    index: VintageIndex,
    actuals: Mapping[datetime, ActualRecord],
    delivery_date: date,
    cutoff_local: time,
    lead_days: int,
) -> DayResult:
    """Replay the decision for one delivery day using only eligible forecasts."""
    cutoff = decision_cutoff_utc(delivery_date, cutoff_local, lead_days)
    intervals: list[IntervalResult] = []
    for t in interval_starts(delivery_date, FORECAST_STEP_MINUTES):
        vintage = index.select(t, cutoff)
        actual = actuals.get(t)
        intervals.append(
            IntervalResult(
                start_time=t,
                forecast_mw=vintage.generation_mw if vintage else None,
                publish_time=vintage.publish_time if vintage else None,
                actual_mw=actual.generation_mw if actual else None,
            )
        )
    return DayResult(
        delivery_date=delivery_date,
        decision_date=decision_date_for(delivery_date, lead_days),
        cutoff_utc=cutoff,
        intervals=intervals,
        metrics=compute_metrics(pairs_of(intervals)),
    )
