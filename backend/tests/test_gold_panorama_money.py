"""Exact arithmetic for artificial Gold Panorama metrics."""

from decimal import Decimal, getcontext

import pytest

from app.services.panorama import _gold_metric


def build_metric(current, previous, **kwargs):
    return _gold_metric(
        "test", "Teste", "", "financeiro", "faturado", current, previous,
        "R$", "Métrica artificial", "current / previous", "available", [],
        **kwargs,
    )


def test_price_change_uses_unrounded_values_before_rounding_absolute_change():
    current_price = Decimal("101") / Decimal("300")
    previous_price = Decimal("100") / Decimal("300")

    metric = build_metric(current_price, previous_price, value_precision=2)

    assert metric.valorAtual == 0.34
    assert metric.valorAnterior == 0.33
    assert metric.variacaoAbsoluta == 0.0
    assert metric.variacaoPercentual == 1.0


def test_large_numeric_revenue_quantizes_without_changing_decimal_context():
    current = Decimal("1000000000000000000000000000000000.01")
    previous = Decimal("1000000000000000000000000000000000.00")
    global_precision = getcontext().prec

    metric = build_metric(current, previous, value_precision=2)

    assert getcontext().prec == global_precision
    assert metric.valorAtual == float(current)
    assert metric.valorAnterior == float(previous)
    assert metric.variacaoAbsoluta == 0.01
    assert metric.variacaoPercentual == 0.0


@pytest.mark.parametrize(
    ("current", "previous", "expected_change", "expected_percent", "base_zero"),
    [
        (Decimal("5"), Decimal("0"), 5.0, None, True),
        (None, Decimal("5"), None, None, False),
        (Decimal("5"), None, None, None, False),
    ],
)
def test_zero_base_and_missing_values_remain_explicit(
    current, previous, expected_change, expected_percent, base_zero
):
    metric = build_metric(current, previous)

    assert metric.variacaoAbsoluta == expected_change
    assert metric.variacaoPercentual == expected_percent
    assert metric.baseZero is base_zero
