"""Validated API response models (Pydantic). Units: MW, %, hours; times ISO-8601."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

IntervalStatus = Literal["matched", "missing_forecast", "missing_actual", "missing_both"]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, object]] | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class MetricOut(BaseModel):
    value: float | None = Field(description="Metric value, or null when unavailable")
    unit: str
    reason: str | None = Field(None, description="Why the value is unavailable")


class MetricsOut(BaseModel):
    mae: MetricOut
    rmse: MetricOut
    bias: MetricOut
    wape: MetricOut
    max_abs_error: MetricOut
    matched: int


class CoverageOut(BaseModel):
    expected: int
    forecast_available: int
    actual_available: int
    matched: int
    forecast_pct: float | None
    actual_pct: float | None
    matched_pct: float | None


class DecisionContextOut(BaseModel):
    timezone: Literal["Europe/London"] = "Europe/London"
    cutoff_local: str = Field(description="HH:MM Europe/London on the decision date")
    lead_days: int
    is_illustrative_default: bool
    rule: str


class ProvenanceOut(BaseModel):
    source: str
    label: str
    retrieved_at: datetime | None
    loaded_at: datetime
    endpoints: list[str]
    quality: dict[str, dict[str, int]]
    warnings: list[str]
    forecast_records: int
    actual_records: int
    publish_times: int


class IntervalOut(BaseModel):
    delivery_date: date
    start_time: datetime
    start_local: datetime
    forecast_mw: float | None
    publish_time: datetime | None = Field(description="Publish time of the eligible vintage (<= cutoff)")
    horizon_hours: float | None
    actual_mw: float | None
    error_mw: float | None = Field(description="forecast - actual; positive = over-forecast")
    abs_error_mw: float | None
    status: IntervalStatus


class ActualPointOut(BaseModel):
    start_time: datetime
    generation_mw: float
    settlement_period: int | None


class DeliveryDayOut(BaseModel):
    delivery_date: date
    decision_date: date
    cutoff_utc: datetime
    cutoff_local: datetime
    context: DecisionContextOut
    metrics: MetricsOut
    coverage: CoverageOut
    vintages_used: list[datetime]
    intervals: list[IntervalOut]
    actual_series: list[ActualPointOut]
    provenance: ProvenanceOut


class DailyStatOut(BaseModel):
    delivery_date: date
    decision_date: date
    cutoff_utc: datetime
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    wape_pct: float | None
    mean_actual_mw: float | None
    mean_forecast_mw: float | None
    coverage: CoverageOut


class HourStatOut(BaseModel):
    hour_local: int
    mae_mw: float | None
    bias_mw: float | None
    matched: int


class HistogramBinOut(BaseModel):
    lower_mw: float
    upper_mw: float
    count: int


class HeatmapCellOut(BaseModel):
    delivery_date: date
    hour_local: int
    error_mw: float | None


class PercentilesOut(BaseModel):
    p05_mw: float | None
    p50_mw: float | None
    p95_mw: float | None


class AnalysisOut(BaseModel):
    decision_from: date
    decision_to: date
    delivery_from: date
    delivery_to: date
    context: DecisionContextOut
    metrics: MetricsOut
    coverage: CoverageOut
    daily: list[DailyStatOut]
    by_hour: list[HourStatOut]
    histogram: list[HistogramBinOut]
    histogram_bin_mw: float
    error_percentiles: PercentilesOut
    top_misses: list[IntervalOut]
    heatmap: list[HeatmapCellOut]
    provenance: ProvenanceOut


class VintagePointOut(BaseModel):
    start_time: datetime
    generation_mw: float


class VintageOut(BaseModel):
    publish_time: datetime
    eligible: bool = Field(description="publish_time <= decision cutoff")
    is_decision_vintage: bool = Field(description="Used by the historical decision replay")
    hours_before_delivery_start: float
    points: list[VintagePointOut]
    mae_mw: float | None = Field(description="Retrospective MAE vs actuals over covered intervals")
    matched: int


class RevisionsOut(BaseModel):
    delivery_date: date
    decision_date: date
    cutoff_utc: datetime
    cutoff_local: datetime
    context: DecisionContextOut
    vintages: list[VintageOut]
    decision_intervals: list[IntervalOut]
    actual_series: list[ActualPointOut]
    provenance: ProvenanceOut


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    data_source: str
    data_loaded: bool
    retrieved_at: datetime | None
    detail: str | None = None
