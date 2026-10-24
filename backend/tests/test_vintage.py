from __future__ import annotations

from datetime import date, time, timedelta

import pytest

from app.domain.analysis import analyse_day
from app.domain.models import ActualRecord, ForecastRecord
from app.domain.timeutil import decision_cutoff_utc
from app.domain.vintage import VintageIndex, select_eligible_forecast
from tests.conftest import utc

T = utc(2026, 1, 2, 12)
CUT = utc(2026, 1, 1, 15, 30)


def recs(*items: tuple[int, int, float]) -> list[ForecastRecord]:
    """(publish day, publish hour:minute as HHMM, value) for target T."""
    out = []
    for day, hhmm, v in items:
        out.append(ForecastRecord(T, utc(2026, 1, day, hhmm // 100, hhmm % 100), v))
    return out


@pytest.mark.parametrize("impl", ["index", "pure"])
class TestSelection:
    def select(self, impl: str, records: list[ForecastRecord], cutoff=CUT):
        if impl == "index":
            return VintageIndex(records).select(T, cutoff)
        return select_eligible_forecast(records, T, cutoff)

    def test_latest_eligible_selected(self, impl: str) -> None:
        v = self.select(impl, recs((1, 930, 1.0), (1, 1130, 2.0), (1, 1430, 3.0)))
        assert v is not None and v.generation_mw == 3.0 and v.publish_time == utc(2026, 1, 1, 14, 30)

    def test_post_cutoff_publications_excluded(self, impl: str) -> None:
        v = self.select(impl, recs((1, 1130, 2.0), (1, 1531, 99.0), (2, 200, 98.0)))
        assert v is not None and v.generation_mw == 2.0

    def test_publication_exactly_at_cutoff_is_eligible(self, impl: str) -> None:
        v = self.select(impl, recs((1, 1130, 2.0), (1, 1530, 7.0)))
        assert v is not None and v.generation_mw == 7.0

    def test_no_eligible_returns_none_not_latest(self, impl: str) -> None:
        assert self.select(impl, recs((1, 1600, 5.0), (2, 100, 6.0))) is None

    def test_out_of_order_input(self, impl: str) -> None:
        v = self.select(impl, recs((1, 1430, 3.0), (1, 930, 1.0), (1, 1800, 9.0), (1, 1130, 2.0)))
        assert v is not None and v.generation_mw == 3.0

    def test_other_targets_ignored(self, impl: str) -> None:
        records = [*recs((1, 1000, 1.0)), ForecastRecord(T + timedelta(hours=1), utc(2026, 1, 1, 15), 50.0)]
        v = self.select(impl, records)
        assert v is not None and v.generation_mw == 1.0


def test_look_ahead_bias_regression() -> None:
    """A later vintage matches the actual perfectly; scoring MUST still use the eligible one."""
    delivery = date(2026, 1, 2)
    cutoff_t = time(15, 30)
    forecasts = []
    actuals = {}
    for h in range(24):
        t = utc(2026, 1, 2, h)
        forecasts.append(ForecastRecord(t, utc(2026, 1, 1, 15, 30), 1000.0))  # decision-time vintage
        forecasts.append(ForecastRecord(t, utc(2026, 1, 1, 18, 30), 600.0))  # later, perfect vintage
        actuals[t] = ActualRecord(t, None, None, None, 600.0)
    r = analyse_day(VintageIndex(forecasts), actuals, delivery, cutoff_t, 1)
    assert all(i.publish_time == utc(2026, 1, 1, 15, 30) for i in r.intervals)
    assert all(i.forecast_mw == 1000.0 for i in r.intervals)
    assert r.metrics.mae.value == pytest.approx(400.0)
    assert r.metrics.bias.value == pytest.approx(400.0)
    assert r.metrics.mae.value != 0.0


def test_cutoff_is_configurable() -> None:
    delivery = date(2026, 1, 2)
    forecasts = [
        ForecastRecord(utc(2026, 1, 2, 0), utc(2026, 1, 1, 9, 30), 10.0),
        ForecastRecord(utc(2026, 1, 2, 0), utc(2026, 1, 1, 11, 30), 20.0),
    ]
    idx = VintageIndex(forecasts)
    assert idx.select(utc(2026, 1, 2, 0), decision_cutoff_utc(delivery, time(10, 0), 1)).generation_mw == 10.0  # type: ignore[union-attr]
    assert idx.select(utc(2026, 1, 2, 0), decision_cutoff_utc(delivery, time(12, 0), 1)).generation_mw == 20.0  # type: ignore[union-attr]


def test_missing_intervals_and_coverage() -> None:
    delivery = date(2026, 1, 2)
    forecasts = [ForecastRecord(utc(2026, 1, 2, h), utc(2026, 1, 1, 12), 100.0) for h in range(12)]
    actuals = {utc(2026, 1, 2, h): ActualRecord(utc(2026, 1, 2, h), None, None, None, 50.0) for h in range(6, 24)}
    r = analyse_day(VintageIndex(forecasts), actuals, delivery, time(15, 30), 1)
    assert r.expected == 24
    assert r.forecast_available == 12
    assert r.actual_available == 18
    assert r.metrics.matched == 6
    statuses = {i.status for i in r.intervals}
    assert statuses == {"matched", "missing_forecast", "missing_actual"}
    assert r.metrics.mae.value == pytest.approx(50.0)


def test_deterministic_across_runs() -> None:
    forecasts = [
        ForecastRecord(utc(2026, 1, 2, h), utc(2026, 1, 1, p), float(h * p)) for h in range(24) for p in (3, 9, 15)
    ]
    actuals = {utc(2026, 1, 2, h): ActualRecord(utc(2026, 1, 2, h), None, None, None, float(h * 7)) for h in range(24)}
    results = {
        repr(
            analyse_day(
                VintageIndex(list(reversed(forecasts)) if i % 2 else forecasts),
                actuals,
                date(2026, 1, 2),
                time(15, 30),
                1,
            ).metrics
        )
        for i in range(5)
    }
    assert len(results) == 1
