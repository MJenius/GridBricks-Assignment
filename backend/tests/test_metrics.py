from __future__ import annotations

import math

import pytest

from app.domain.metrics import Pair, compute_metrics, histogram, percentile


def test_known_values() -> None:
    # errors: +100, -50, +0, +250 ; actuals: 1000, 500, 200, 300
    pairs = [Pair(1100, 1000), Pair(450, 500), Pair(200, 200), Pair(550, 300)]
    m = compute_metrics(pairs)
    assert m.matched == 4
    assert m.mae.value == pytest.approx(100.0)  # (100+50+0+250)/4
    assert m.rmse.value == pytest.approx(math.sqrt((100**2 + 50**2 + 0 + 250**2) / 4))
    assert m.bias.value == pytest.approx(75.0)  # (100-50+0+250)/4
    assert m.wape.value == pytest.approx(400 / 2000 * 100)
    assert m.max_abs_error.value == 250
    assert m.mae.unit == "MW" and m.wape.unit == "%"


def test_sign_convention_over_forecast_positive() -> None:
    assert compute_metrics([Pair(10, 4)]).bias.value == 6
    assert compute_metrics([Pair(4, 10)]).bias.value == -6


def test_empty_returns_structured_unavailable() -> None:
    m = compute_metrics([])
    assert m.matched == 0
    for metric in (m.mae, m.rmse, m.bias, m.wape, m.max_abs_error):
        assert metric.value is None
        assert metric.reason


def test_all_zero_actuals_wape_undefined_but_others_valid() -> None:
    m = compute_metrics([Pair(5, 0), Pair(0, 0)])
    assert m.wape.value is None and "zero" in (m.wape.reason or "")
    assert m.mae.value == pytest.approx(2.5)


def test_histogram_and_percentile() -> None:
    h = histogram([-600, -10, 0, 499, 500, 1200], 500)
    assert h[0] == (-1000, -500, 1)
    assert sum(c for _, _, c in h) == 6
    assert h[-1] == (1000, 1500, 1)
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([], 50) is None
    assert histogram([], 500) == []
    with pytest.raises(ValueError):
        histogram([1], 0)
