from dataclasses import replace
from decimal import Decimal

import pytest
from app.schemas.genai_evidence import PublishedWindows
from app.services.genai_sql_compound import (
    CompoundEvidenceUnavailable,
    ConsumptionTotals,
    EvidenceScope,
    RevenueEffect,
    compose_consumption_revenue,
)

SCOPE = EvidenceScope(
    "batch",
    "scope",
    PublishedWindows(
        p0_start="2024-07",
        p0_end="2025-06",
        p1_start="2025-07",
        p1_end="2026-06",
        method="PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3",
    ),
)
CONSUMPTION = (
    ConsumptionTotals("B", Decimal(50), Decimal(30)),
    ConsumptionTotals("A", Decimal(100), Decimal(80)),
    ConsumptionTotals("C", Decimal(0), Decimal(10)),
)
REVENUE = (
    RevenueEffect("A", "Residencial", Decimal(12), Decimal(-3)),
    RevenueEffect("A", "Comercial", Decimal(-5), Decimal(-2)),
    RevenueEffect("B", "Comercial", Decimal(-4), Decimal(-1)),
)


def compose(consumption=CONSUMPTION, revenue=REVENUE, revenue_scope=SCOPE):
    return compose_consumption_revenue(
        SCOPE,
        revenue_scope,
        consumption,
        revenue,
        expected_municipalities=frozenset({"A", "B", "C"}),
        expected_revenue_groups=frozenset(
            {("A", "Residencial"), ("A", "Comercial"), ("B", "Comercial")}
        ),
    )


def test_ranks_absolute_declines_with_stable_ties_and_keeps_class_effects():
    a, b = compose().municipalities
    assert (a.consumption.municipality, a.change_kwh, a.change_percent) == ("A", -20, -20)
    assert (b.consumption.municipality, b.change_kwh, b.change_percent) == ("B", -20, -40)
    assert [
        (effect.consumption_class, effect.variation_brl, effect.volume_effect_brl)
        for effect in a.revenue_by_class
    ] == [("Comercial", -5, -2), ("Residencial", 12, -3)]


@pytest.mark.parametrize(
    "changes",
    [
        {"consumption": CONSUMPTION[:-1]},
        {"consumption": (*CONSUMPTION, CONSUMPTION[0])},
        {"revenue": REVENUE[:-1]},
        {"revenue": (*REVENUE, REVENUE[0])},
        {"revenue_scope": replace(SCOPE, batch_ref="other")},
        {"revenue_scope": replace(SCOPE, scope_digest="other")},
        {"revenue_scope": replace(SCOPE, windows=PublishedWindows(
            p0_start="2022-07", p0_end="2023-06",
            p1_start="2025-07", p1_end="2026-06",
            method="PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3",
        ))},
        {"revenue": (replace(REVENUE[0], volume_effect_brl=Decimal("NaN")), *REVENUE[1:])},
    ],
)
def test_refuses_inconsistent_evidence_instead_of_returning_partial_results(changes):
    with pytest.raises(CompoundEvidenceUnavailable):
        compose(**changes)
