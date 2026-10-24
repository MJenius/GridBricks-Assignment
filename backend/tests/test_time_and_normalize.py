from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.domain.timeutil import (
    decision_cutoff_utc,
    ensure_utc,
    interval_starts,
    london_day_bounds_utc,
    parse_utc,
    to_london,
)
from app.services.normalize import normalize_actuals, normalize_forecasts
from tests.conftest import fuelhh_row, utc, windfor_row


class TestTime:
    def test_winter_cutoff_equals_utc(self) -> None:
        assert decision_cutoff_utc(date(2026, 1, 2), time(15, 30), 1) == utc(2026, 1, 1, 15, 30)

    def test_summer_cutoff_bst_offset(self) -> None:
        assert decision_cutoff_utc(date(2026, 7, 2), time(15, 30), 1) == utc(2026, 7, 1, 14, 30)

    def test_dst_day_lengths(self) -> None:
        assert len(interval_starts(date(2026, 3, 29), 60)) == 23
        assert len(interval_starts(date(2026, 10, 25), 60)) == 25
        assert len(interval_starts(date(2026, 1, 15), 30)) == 48
        start, end = london_day_bounds_utc(date(2026, 3, 29))
        assert start == utc(2026, 3, 29, 0) and end == utc(2026, 3, 29, 23)

    def test_parse_and_convert(self) -> None:
        assert parse_utc("2026-01-01T15:30:00Z") == utc(2026, 1, 1, 15, 30)
        assert parse_utc("2026-07-01T15:30:00+01:00") == utc(2026, 7, 1, 14, 30)
        assert parse_utc("2026-01-01T15:30:00") is None  # naive rejected
        assert parse_utc("garbage") is None
        assert parse_utc(None) is None
        assert to_london(utc(2026, 7, 1, 14, 30)).hour == 15
        with pytest.raises(ValueError):
            ensure_utc(datetime(2026, 1, 1))
        assert ensure_utc(datetime(2026, 1, 1, tzinfo=UTC)).tzinfo == UTC


class TestNormalizeForecasts:
    def test_exact_duplicates_collapse(self) -> None:
        t, p = utc(2026, 1, 2), utc(2026, 1, 1, 9)
        recs, q = normalize_forecasts([windfor_row(t, p, 100), windfor_row(t, p, 100)])
        assert len(recs) == 1 and q.exact_duplicates == 1 and q.conflicting_duplicates == 0

    def test_conflicting_duplicates_excluded_never_averaged(self) -> None:
        t, p = utc(2026, 1, 2), utc(2026, 1, 1, 9)
        recs, q = normalize_forecasts(
            [windfor_row(t, p, 100), windfor_row(t, p, 200), windfor_row(t, utc(2026, 1, 1, 7), 50)]
        )
        assert [r.generation_mw for r in recs] == [50]
        assert q.conflicting_duplicates == 1

    @pytest.mark.parametrize(
        "bad",
        [
            {"startTime": None, "publishTime": "2026-01-01T00:00:00Z", "generation": 1},
            {"startTime": "2026-01-01T00:00:00Z", "publishTime": "", "generation": 1},
            {"startTime": "2026-01-01T00:00:00Z", "publishTime": "nope", "generation": 1},
            {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:00:00Z", "generation": "x"},
            {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:00:00Z", "generation": float("nan")},
            {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:00:00Z", "generation": -5},
            {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:00:00Z", "generation": None},
            {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:00:00Z", "generation": True},
        ],
    )
    def test_invalid_rows_dropped(self, bad: dict[str, object]) -> None:
        recs, q = normalize_forecasts([bad])
        assert recs == [] and q.invalid == 1 and q.received == 1

    def test_output_sorted(self) -> None:
        rows = [windfor_row(utc(2026, 1, 2, h), utc(2026, 1, 1, 9), h) for h in (5, 1, 3)]
        recs, _ = normalize_forecasts(rows)
        assert [r.start_time.hour for r in recs] == [1, 3, 5]


class TestNormalizeActuals:
    def test_non_wind_rejected(self) -> None:
        recs, q = normalize_actuals([fuelhh_row(utc(2026, 1, 2), 10, fuel="CCGT")])
        assert recs == [] and q.invalid == 1

    def test_late_revision_supersedes(self) -> None:
        t = utc(2026, 1, 2)
        rows = [fuelhh_row(t, 10, publish=t + timedelta(minutes=30)), fuelhh_row(t, 12, publish=t + timedelta(hours=5))]
        recs, q = normalize_actuals(rows)
        assert [r.generation_mw for r in recs] == [12] and q.superseded == 1

    def test_same_publish_conflict_excluded(self) -> None:
        t = utc(2026, 1, 2)
        recs, q = normalize_actuals([fuelhh_row(t, 10), fuelhh_row(t, 11)])
        assert recs == [] and q.conflicting_duplicates == 1

    def test_exact_duplicate(self) -> None:
        t = utc(2026, 1, 2)
        recs, q = normalize_actuals([fuelhh_row(t, 10), fuelhh_row(t, 10)])
        assert len(recs) == 1 and q.exact_duplicates == 1
        assert recs[0].settlement_period == 1
