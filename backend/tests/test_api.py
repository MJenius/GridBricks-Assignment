from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas.api import AnalysisOut, DeliveryDayOut, RevisionsOut
from tests.conftest import FixtureRepo, fixture_dataset


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings, FixtureRepo(settings, fixture_dataset())))


def test_health(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert "X-Request-ID" in r.headers


def test_delivery_day_uses_eligible_vintage(client: TestClient) -> None:
    r = client.get("/api/v1/delivery-days/2026-01-02")
    assert r.status_code == 200
    body = DeliveryDayOut.model_validate(r.json())
    assert body.decision_date.isoformat() == "2026-01-01"
    assert body.cutoff_utc.isoformat() == "2026-01-01T15:30:00+00:00"
    assert [v.isoformat() for v in body.vintages_used] == ["2026-01-01T15:30:00+00:00"]
    assert body.coverage.expected == 24 and body.coverage.matched == 23
    assert body.metrics.mae.value == pytest.approx(100.0)  # 1000 vs 900, not later 900 vs 900
    assert body.metrics.bias.value == pytest.approx(100.0)
    missing = [i for i in body.intervals if i.status == "missing_actual"]
    assert len(missing) == 1 and missing[0].error_mw is None
    assert body.provenance.source == "fixture"
    assert len(body.actual_series) == 47


def test_earlier_cutoff_yields_no_forecast_and_null_metrics(client: TestClient) -> None:
    body = client.get("/api/v1/delivery-days/2026-01-02", params={"cutoff": "15:29"}).json()
    assert body["coverage"]["forecast_available"] == 0
    assert body["metrics"]["mae"]["value"] is None and body["metrics"]["mae"]["reason"]
    assert body["context"]["is_illustrative_default"] is False


def test_revisions_flags_eligibility(client: TestClient) -> None:
    body = RevisionsOut.model_validate(client.get("/api/v1/forecast-revisions/2026-01-02").json())
    flags = [(v.publish_time.hour, v.eligible, v.is_decision_vintage) for v in body.vintages]
    assert flags == [(15, True, True), (18, False, False)]
    assert body.vintages[1].mae_mw == pytest.approx(0.0)  # later revision better, but not used


def test_analysis_range(client: TestClient) -> None:
    r = client.get("/api/v1/analysis", params={"decision_from": "2026-01-01", "decision_to": "2026-01-02"})
    body = AnalysisOut.model_validate(r.json())
    assert body.coverage.expected == 48 and body.coverage.matched == 23
    assert body.daily[1].mae_mw is None  # no data for delivery 2026-01-03
    assert body.daily[1].coverage.matched_pct == 0
    assert len(body.heatmap) == 48 and len(body.by_hour) == 24
    assert body.top_misses[0].abs_error_mw == pytest.approx(100.0)


@pytest.mark.parametrize(
    "params,code",
    [
        ({"cutoff": "25:00"}, "invalid_cutoff"),
        ({"cutoff": "abc"}, "invalid_cutoff"),
        ({"decision_from": "2025-12-31"}, "out_of_scope"),
        ({"decision_from": "2026-01-10", "decision_to": "2026-01-05"}, "invalid_range"),
        ({"decision_from": "not-a-date"}, "validation_error"),
        ({"lead_days": 9}, "validation_error"),
    ],
)
def test_invalid_inputs(client: TestClient, params: dict[str, str], code: str) -> None:
    r = client.get("/api/v1/analysis", params=params)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == code
    assert "Traceback" not in r.text


def test_delivery_out_of_scope(client: TestClient) -> None:
    r = client.get("/api/v1/delivery-days/2026-03-01")
    assert r.status_code == 422 and r.json()["error"]["code"] == "out_of_scope"


def test_csv_export(client: TestClient) -> None:
    r = client.get("/api/v1/analysis/export.csv", params={"decision_from": "2026-01-01", "decision_to": "2026-01-01"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 24
    first = rows[0]
    assert first["forecast_publish_time_utc"] == "2026-01-01T15:30:00+00:00"
    assert first["error_mw"] == "100" and first["data_source"] == "fixture"
    assert any(row["status"] == "missing_actual" and row["error_mw"] == "" for row in rows)


def test_unknown_api_route_is_structured(client: TestClient) -> None:
    r = client.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "http_error"


def test_real_snapshot_loads_if_present() -> None:
    """Uses the packaged real snapshot (not a fixture) to confirm it parses."""
    from app.services.repository import load_snapshot

    s = Settings()
    if not (s.snapshot_dir / "manifest.json").exists():
        pytest.skip("snapshot not present")
    ds = load_snapshot(s.snapshot_dir)
    assert ds.provenance.source == "snapshot"
    assert len(ds.forecasts) > 10000 and len(ds.actuals) > 1000
