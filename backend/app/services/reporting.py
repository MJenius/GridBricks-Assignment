"""Assemble API responses from the pure domain layer."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, timedelta

from app.config import Settings
from app.domain.analysis import (
    ACTUAL_STEP_MINUTES,
    DayResult,
    IntervalResult,
    analyse_day,
    pairs_of,
)
from app.domain.metrics import Metrics, MetricValue, Pair, compute_metrics, histogram, percentile
from app.domain.timeutil import interval_starts, london_day_bounds_utc, to_london
from app.schemas.api import (
    ActualPointOut,
    AnalysisOut,
    CoverageOut,
    DailyStatOut,
    DecisionContextOut,
    DeliveryDayOut,
    HeatmapCellOut,
    HistogramBinOut,
    HourStatOut,
    IntervalOut,
    MetricOut,
    MetricsOut,
    PercentilesOut,
    ProvenanceOut,
    RevisionsOut,
    VintageOut,
    VintagePointOut,
)
from app.services.repository import Dataset

HISTOGRAM_BIN_MW = 500.0
TOP_MISSES = 15


def context_out(settings: Settings, cutoff: time, lead_days: int) -> DecisionContextOut:
    return DecisionContextOut(
        cutoff_local=cutoff.strftime("%H:%M"),
        lead_days=lead_days,
        is_illustrative_default=(cutoff == settings.default_cutoff and lead_days == settings.lead_days),
        rule=(
            "For each delivery interval, use the latest WINDFOR vintage with "
            "publishTime <= cutoff; later vintages are never used for scoring."
        ),
    )


def provenance_out(ds: Dataset) -> ProvenanceOut:
    p = ds.provenance
    return ProvenanceOut(
        source=p.source,
        label=p.label,
        retrieved_at=p.retrieved_at,
        loaded_at=p.loaded_at,
        endpoints=p.endpoints,
        quality=p.quality,
        warnings=p.warnings,
        forecast_records=len(ds.forecasts),
        actual_records=len(ds.actuals),
        publish_times=len({f.publish_time for f in ds.forecasts}),
    )


def metrics_out(m: Metrics) -> MetricsOut:
    def mv(x: MetricValue) -> MetricOut:
        return MetricOut(value=x.value, unit=x.unit, reason=x.reason)

    return MetricsOut(
        mae=mv(m.mae),
        rmse=mv(m.rmse),
        bias=mv(m.bias),
        wape=mv(m.wape),
        max_abs_error=mv(m.max_abs_error),
        matched=m.matched,
    )


def _pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 2) if d > 0 else None


def coverage_of(intervals: Sequence[IntervalResult]) -> CoverageOut:
    expected = len(intervals)
    f = sum(1 for i in intervals if i.forecast_mw is not None)
    a = sum(1 for i in intervals if i.actual_mw is not None)
    m = sum(1 for i in intervals if i.status == "matched")
    return CoverageOut(
        expected=expected,
        forecast_available=f,
        actual_available=a,
        matched=m,
        forecast_pct=_pct(f, expected),
        actual_pct=_pct(a, expected),
        matched_pct=_pct(m, expected),
    )


def interval_out(i: IntervalResult, delivery: date) -> IntervalOut:
    err = i.error_mw
    return IntervalOut(
        delivery_date=delivery,
        start_time=i.start_time,
        start_local=to_london(i.start_time),
        forecast_mw=i.forecast_mw,
        publish_time=i.publish_time,
        horizon_hours=i.horizon_hours,
        actual_mw=i.actual_mw,
        error_mw=err,
        abs_error_mw=abs(err) if err is not None else None,
        status=i.status,  # type: ignore[arg-type]
    )


def actual_series(ds: Dataset, delivery: date) -> list[ActualPointOut]:
    out: list[ActualPointOut] = []
    for t in interval_starts(delivery, ACTUAL_STEP_MINUTES):
        a = ds.actuals_by_start.get(t)
        if a is not None:
            out.append(
                ActualPointOut(start_time=t, generation_mw=a.generation_mw, settlement_period=a.settlement_period)
            )
    return out


def delivery_day(ds: Dataset, settings: Settings, delivery: date, cutoff: time, lead_days: int) -> DeliveryDayOut:
    r = analyse_day(ds.index, ds.actuals_by_start, delivery, cutoff, lead_days)
    return DeliveryDayOut(
        delivery_date=r.delivery_date,
        decision_date=r.decision_date,
        cutoff_utc=r.cutoff_utc,
        cutoff_local=to_london(r.cutoff_utc),
        context=context_out(settings, cutoff, lead_days),
        metrics=metrics_out(r.metrics),
        coverage=coverage_of(r.intervals),
        vintages_used=r.vintages_used,
        intervals=[interval_out(i, delivery) for i in r.intervals],
        actual_series=actual_series(ds, delivery),
        provenance=provenance_out(ds),
    )


def _mean(values: Iterable[float]) -> float | None:
    vals = list(values)
    return sum(vals) / len(vals) if vals else None


def analyse_range(ds: Dataset, decision_from: date, decision_to: date, cutoff: time, lead_days: int) -> list[DayResult]:
    days: list[DayResult] = []
    d = decision_from
    while d <= decision_to:
        days.append(analyse_day(ds.index, ds.actuals_by_start, d + timedelta(days=lead_days), cutoff, lead_days))
        d += timedelta(days=1)
    return days


def analysis(
    ds: Dataset, settings: Settings, decision_from: date, decision_to: date, cutoff: time, lead_days: int
) -> AnalysisOut:
    days = analyse_range(ds, decision_from, decision_to, cutoff, lead_days)
    all_intervals = [(d.delivery_date, i) for d in days for i in d.intervals]
    flat = [i for _, i in all_intervals]
    pairs = pairs_of(flat)
    errors = [p.error_mw for p in pairs]

    daily: list[DailyStatOut] = []
    for d in days:
        m = d.metrics
        daily.append(
            DailyStatOut(
                delivery_date=d.delivery_date,
                decision_date=d.decision_date,
                cutoff_utc=d.cutoff_utc,
                mae_mw=m.mae.value,
                rmse_mw=m.rmse.value,
                bias_mw=m.bias.value,
                wape_pct=m.wape.value,
                mean_actual_mw=_mean(
                    i.actual_mw for i in d.intervals if i.actual_mw is not None and i.forecast_mw is not None
                ),
                mean_forecast_mw=_mean(
                    i.forecast_mw for i in d.intervals if i.actual_mw is not None and i.forecast_mw is not None
                ),
                coverage=coverage_of(d.intervals),
            )
        )

    by_hour_pairs: dict[int, list[Pair]] = defaultdict(list)
    heatmap: list[HeatmapCellOut] = []
    for delivery, i in all_intervals:
        hour = to_london(i.start_time).hour
        heatmap.append(HeatmapCellOut(delivery_date=delivery, hour_local=hour, error_mw=i.error_mw))
        if i.status == "matched":
            assert i.forecast_mw is not None and i.actual_mw is not None
            by_hour_pairs[hour].append(Pair(i.forecast_mw, i.actual_mw))
    by_hour = []
    for h in range(24):
        hm = compute_metrics(by_hour_pairs.get(h, []))
        by_hour.append(HourStatOut(hour_local=h, mae_mw=hm.mae.value, bias_mw=hm.bias.value, matched=hm.matched))

    matched_sorted = sorted(
        ((dd, i) for dd, i in all_intervals if i.error_mw is not None),
        key=lambda x: (-abs(x[1].error_mw or 0.0), x[1].start_time),
    )
    return AnalysisOut(
        decision_from=decision_from,
        decision_to=decision_to,
        delivery_from=days[0].delivery_date,
        delivery_to=days[-1].delivery_date,
        context=context_out(settings, cutoff, lead_days),
        metrics=metrics_out(compute_metrics(pairs)),
        coverage=coverage_of(flat),
        daily=daily,
        by_hour=by_hour,
        histogram=[
            HistogramBinOut(lower_mw=lo, upper_mw=hi, count=c) for lo, hi, c in histogram(errors, HISTOGRAM_BIN_MW)
        ],
        histogram_bin_mw=HISTOGRAM_BIN_MW,
        error_percentiles=PercentilesOut(
            p05_mw=percentile(errors, 5), p50_mw=percentile(errors, 50), p95_mw=percentile(errors, 95)
        ),
        top_misses=[interval_out(i, dd) for dd, i in matched_sorted[:TOP_MISSES]],
        heatmap=heatmap,
        provenance=provenance_out(ds),
    )


CSV_COLUMNS = [
    "decision_date",
    "delivery_date",
    "decision_cutoff_utc",
    "interval_start_utc",
    "interval_start_london",
    "forecast_publish_time_utc",
    "forecast_horizon_hours",
    "forecast_mw",
    "actual_mw",
    "error_mw",
    "abs_error_mw",
    "status",
    "data_source",
]


def export_csv(ds: Dataset, decision_from: date, decision_to: date, cutoff: time, lead_days: int) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)

    def fmt(x: float | None) -> str:
        return "" if x is None else f"{x:.3f}".rstrip("0").rstrip(".")

    def ts(x: datetime | None) -> str:
        return "" if x is None else x.isoformat()

    for d in analyse_range(ds, decision_from, decision_to, cutoff, lead_days):
        for i in d.intervals:
            err = i.error_mw
            w.writerow(
                [
                    d.decision_date.isoformat(),
                    d.delivery_date.isoformat(),
                    ts(d.cutoff_utc),
                    ts(i.start_time),
                    to_london(i.start_time).isoformat(),
                    ts(i.publish_time),
                    fmt(i.horizon_hours),
                    fmt(i.forecast_mw),
                    fmt(i.actual_mw),
                    fmt(err),
                    fmt(abs(err) if err is not None else None),
                    i.status,
                    ds.provenance.source,
                ]
            )
    return buf.getvalue()


def revisions(ds: Dataset, settings: Settings, delivery: date, cutoff: time, lead_days: int) -> RevisionsOut:
    r = analyse_day(ds.index, ds.actuals_by_start, delivery, cutoff, lead_days)
    day_start, _ = london_day_bounds_utc(delivery)
    targets = [i.start_time for i in r.intervals]
    used = set(r.vintages_used)
    by_publish: dict[datetime, list[VintagePointOut]] = defaultdict(list)
    for t in targets:
        for v in ds.index.vintages(t):
            by_publish[v.publish_time].append(VintagePointOut(start_time=t, generation_mw=v.generation_mw))
    vintages: list[VintageOut] = []
    for publish in sorted(by_publish):
        pts = by_publish[publish]
        vp = [
            Pair(p.generation_mw, ds.actuals_by_start[p.start_time].generation_mw)
            for p in pts
            if p.start_time in ds.actuals_by_start
        ]
        vm = compute_metrics(vp)
        vintages.append(
            VintageOut(
                publish_time=publish,
                eligible=publish <= r.cutoff_utc,
                is_decision_vintage=publish in used,
                hours_before_delivery_start=(day_start - publish).total_seconds() / 3600.0,
                points=pts,
                mae_mw=vm.mae.value,
                matched=vm.matched,
            )
        )
    return RevisionsOut(
        delivery_date=delivery,
        decision_date=r.decision_date,
        cutoff_utc=r.cutoff_utc,
        cutoff_local=to_london(r.cutoff_utc),
        context=context_out(settings, cutoff, lead_days),
        vintages=vintages,
        decision_intervals=[interval_out(i, delivery) for i in r.intervals],
        actual_series=actual_series(ds, delivery),
        provenance=provenance_out(ds),
    )
