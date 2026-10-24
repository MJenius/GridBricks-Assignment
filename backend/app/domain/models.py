"""Internal, source-agnostic domain records. All datetimes are tz-aware UTC."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class ForecastRecord:
    """One WINDFOR value: forecast for ``start_time`` published at ``publish_time``."""

    start_time: datetime
    publish_time: datetime
    generation_mw: float


@dataclass(frozen=True, slots=True)
class ActualRecord:
    """One FUELHH WIND value for the half-hour starting at ``start_time``."""

    start_time: datetime
    publish_time: datetime | None
    settlement_date: date | None
    settlement_period: int | None
    generation_mw: float


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    """Counts produced by normalisation so that data handling is auditable."""

    received: int
    accepted: int
    invalid: int
    exact_duplicates: int
    conflicting_duplicates: int
    superseded: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "received": self.received,
            "accepted": self.accepted,
            "invalid": self.invalid,
            "exact_duplicates": self.exact_duplicates,
            "conflicting_duplicates": self.conflicting_duplicates,
            "superseded": self.superseded,
        }
