"""Forecast accuracy metrics on matched pairs.

Convention: ``error_mw = forecast_mw - actual_mw`` (positive = over-forecast).
Metrics are computed only from matched, valid pairs; missing data is never
treated as zero. Unavailable metrics carry a reason instead of a number.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Pair:
    forecast_mw: float
    actual_mw: float

    @property
    def error_mw(self) -> float:
        return self.forecast_mw - self.actual_mw


@dataclass(frozen=True, slots=True)
class MetricValue:
    value: float | None
    unit: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Metrics:
    mae: MetricValue
    rmse: MetricValue
    bias: MetricValue
    wape: MetricValue
    max_abs_error: MetricValue
    matched: int


NO_PAIRS = "No matched forecast/actual pairs in the selection."


def _na(unit: str) -> MetricValue:
    return MetricValue(None, unit, NO_PAIRS)


def compute_metrics(pairs: Sequence[Pair]) -> Metrics:
    n = len(pairs)
    if n == 0:
        return Metrics(_na("MW"), _na("MW"), _na("MW"), _na("%"), _na("MW"), 0)

    errors = [p.error_mw for p in pairs]
    abs_errors = [abs(e) for e in errors]
    sum_abs = math.fsum(abs_errors)
    mae = sum_abs / n
    rmse = math.sqrt(math.fsum(e * e for e in errors) / n)
    bias = math.fsum(errors) / n
    sum_actual = math.fsum(p.actual_mw for p in pairs)
    if sum_actual > 0:
        wape = MetricValue(100.0 * sum_abs / sum_actual, "%")
    else:
        wape = MetricValue(None, "%", "Sum of actual generation is zero; WAPE is undefined.")
    return Metrics(
        mae=MetricValue(mae, "MW"),
        rmse=MetricValue(rmse, "MW"),
        bias=MetricValue(bias, "MW"),
        wape=wape,
        max_abs_error=MetricValue(max(abs_errors), "MW"),
        matched=n,
    )


def histogram(values: Sequence[float], bin_width: float) -> list[tuple[float, float, int]]:
    """Fixed-width histogram aligned to multiples of ``bin_width``.

    Returns ``(lower, upper, count)`` triples covering the data range.
    """
    if not values:
        return []
    if bin_width <= 0:
        raise ValueError("bin_width must be positive")
    lo = math.floor(min(values) / bin_width) * bin_width
    hi = math.floor(max(values) / bin_width) * bin_width
    nbins = round((hi - lo) / bin_width) + 1
    counts = [0] * nbins
    for v in values:
        idx = math.floor((v - lo) / bin_width)
        counts[min(max(idx, 0), nbins - 1)] += 1
    return [(lo + i * bin_width, lo + (i + 1) * bin_width, c) for i, c in enumerate(counts)]


def percentile(values: Sequence[float], q: float) -> float | None:
    """Linear-interpolated percentile (q in [0, 100]); ``None`` when empty."""
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)
