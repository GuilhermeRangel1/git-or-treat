from decimal import Decimal

import pytest

from app.services.panorama import (
    gold_panorama_revenue_metric,
    read_gold_panorama_financials,
)
from app.services.panorama_distribution import (
    distribution_from_groups,
    gold_distribution,
)
from tests import test_panorama_current_composition as existing_fixtures

snapshot_repository = existing_fixtures.snapshot_repository


@pytest.mark.parametrize(
    "municipality, consumption_class, expected, complete",
    [
        ("todos", "todas", {"A": 50, "B": 50}, False),
        ("A", "todas", {"RESIDENCIAL": 30, "COMERCIAL": 20}, True),
        ("todos", "RESIDENCIAL", {"A": 30, "B": 50}, True),
    ],
)
def test_partition_uses_same_snapshot_and_keeps_applied_filters(
    snapshot_repository, municipality, consumption_class, expected, complete
):
    financials = read_gold_panorama_financials(
        snapshot_repository, "2026-06", "nenhuma", municipality, consumption_class
    )
    metric = gold_panorama_revenue_metric(
        financials.actual, financials.prior, financials.reference
    )
    result = gold_distribution(snapshot_repository, financials, metric)
    assert {point.segmento: point.valor for point in result.pontos} == expected
    assert result.total == sum(expected.values()) == metric.valorAtual
    assert result.completo is complete
    if complete:
        assert all(
            point.percentual == round(point.valor / result.total * 100, 2)
            for point in result.pontos
        )
    else:
        assert all(point.percentual is None for point in result.pontos)


def test_two_specific_filters_do_not_expand_scope(snapshot_repository):
    f = read_gold_panorama_financials(
        snapshot_repository, "2026-06", "nenhuma", "A", "RESIDENCIAL"
    )
    metric = gold_panorama_revenue_metric(f.actual, f.prior, f.reference)
    assert gold_distribution(snapshot_repository, f, metric) is None


@pytest.mark.parametrize(
    "values,total,complete",
    [([25, 75], 101, True), ([1], 1, True), ([1] * 1001, 1001, True)],
)
def test_unreconciled_or_outside_limits_is_not_published(values, total, complete):
    rows = [{"segment": str(i), "revenue": Decimal(v)} for i, v in enumerate(values)]
    assert (
        distribution_from_groups(
            rows,
            dimension="municipio",
            period="2026-06",
            metric_id="rec_fat",
            unit="R$",
            total=total,
            complete=complete,
        )
        is None
    )


@pytest.mark.parametrize("values,total", [([None, 0], 0), ([-5, 5], 0)])
def test_missing_zero_and_negative_are_not_pie_shares(values, total):
    rows = [{"segment": str(i), "revenue": v} for i, v in enumerate(values)]
    result = distribution_from_groups(
        rows,
        dimension="municipio",
        period="2026-06",
        metric_id="rec_fat",
        unit="R$",
        total=total,
        complete=True,
    )
    assert [p.valor for p in result.pontos].count(None) == values.count(None)
    assert result.completo is False
    assert all(p.percentual is None for p in result.pontos)


def test_many_municipalities_preserve_full_list_and_reconcile_other_slice():
    rows = [
        {"segment": f"Município de teste {i:03d}", "revenue": Decimal(i)}
        for i in range(1, 201)
    ]
    result = distribution_from_groups(
        rows,
        dimension="municipio",
        period="2026-06",
        metric_id="rec_fat",
        unit="R$",
        total=Decimal(20100),
        complete=True,
    )
    assert len(result.pontos) == 200
    assert len(result.visual) == 6
    assert result.agrupados == 195
    assert [p.valor for p in result.visual[:5]] == [200, 199, 198, 197, 196]
    assert result.visual[-1].valor == 19110
    assert (
        sum(p.valor for p in result.visual)
        == sum(p.valor for p in result.pontos)
        == 20100
    )
    assert result.visual[-1].percentual == 95.07


def test_partial_many_groups_keep_full_list_and_only_ten_visual_points():
    rows = [{"segment": str(i), "revenue": 1} for i in range(30)]
    result = distribution_from_groups(
        rows,
        dimension="municipio",
        period="2026-06",
        metric_id="rec_fat",
        unit="R$",
        total=30,
        complete=False,
    )
    assert len(result.pontos) == 30
    assert len(result.visual) == 10
    assert result.agrupados == 0
    assert all(p.percentual is None for p in result.visual)
