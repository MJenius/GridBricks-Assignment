"""Synthetic fixtures for automated tests only. NOT real Elexon observations."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.config import Settings
from app.services.repository import DataRepository, Dataset, build_dataset


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def windfor_row(start: datetime, publish: datetime, gen: Any) -> dict[str, Any]:
    return {"dataset": "WINDFOR", "startTime": iso(start), "publishTime": iso(publish), "generation": gen}


def fuelhh_row(start: datetime, gen: Any, publish: datetime | None = None, fuel: str = "WIND") -> dict[str, Any]:
    return {
        "dataset": "FUELHH",
        "startTime": iso(start),
        "publishTime": iso(publish or start + timedelta(minutes=30)),
        "settlementDate": start.date().isoformat(),
        "settlementPeriod": start.hour * 2 + start.minute // 30 + 1,
        "fuelType": fuel,
        "generation": gen,
    }


def make_fixture_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Delivery day 2026-01-02 (decision 2026-01-01, cutoff 15:30 UTC in winter).

    Two vintages per hour: 2026-01-01T15:30Z (eligible, exactly at cutoff)
    forecasting 1000 MW, and 2026-01-01T18:30Z (post-cutoff) forecasting 900 MW.
    Actuals are 900 MW every half-hour, except 2026-01-02T05:00Z which is missing.
    """
    eligible = utc(2026, 1, 1, 15, 30)
    later = utc(2026, 1, 1, 18, 30)
    forecasts: list[dict[str, Any]] = []
    actuals: list[dict[str, Any]] = []
    day = utc(2026, 1, 2)
    for h in range(24):
        t = day + timedelta(hours=h)
        forecasts.append(windfor_row(t, eligible, 1000))
        forecasts.append(windfor_row(t, later, 900))
    for hh in range(48):
        t = day + timedelta(minutes=30 * hh)
        if t != utc(2026, 1, 2, 5):
            actuals.append(fuelhh_row(t, 900))
    return forecasts, actuals


def fixture_dataset() -> Dataset:
    f, a = make_fixture_rows()
    return build_dataset(f, a, source="fixture", label="TEST FIXTURE (synthetic)", retrieved_at=None, endpoints=[])


class FixtureRepo(DataRepository):
    def __init__(self, settings: Settings, ds: Dataset) -> None:
        super().__init__(settings)
        self._ds = ds

    def snapshot(self) -> Dataset:
        return self._ds

    async def get(self) -> Dataset:
        return self._ds


@pytest.fixture
def settings() -> Settings:
    return Settings(decision_start=date(2026, 1, 1), decision_end=date(2026, 1, 31))
