from dataclasses import replace
from decimal import Decimal

import pytest
from app.schemas.genai_evidence import PublishedWindows
from app.schemas.sql_analysis import ObservedComparisonWindows, SqlCompoundAnalysis
from app.services.genai_sql_compound import (
    CompoundEvidenceUnavailable,
    CompoundResult,
    ConsumptionTotals,
    EvidenceScope,
    MunicipalityDecline,
    RevenueEffect,
    compose_consumption_revenue,
)
from app.services.genai_sql_compound_route import (
    financial_comparison_scope,
    is_price_volume_question,
    is_ranked_consumption_revenue_impact_question,
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


@pytest.mark.parametrize(
    "question",
    [
        "Quais municípios apresentaram a maior queda no consumo de energia nos últimos 12 meses e como essa redução impactou a Receita faturada, considerando as diferentes classes de consumo?",
        "Para os três municípios com maior queda de consumo entre jul/2024–jun/2025 e jul/2025–jun/2026, compare também a receita por classe.",
    ],
)
def test_recognizes_supported_ranked_consumption_revenue_composition(question):
    assert is_ranked_consumption_revenue_impact_question(question)
    assert is_price_volume_question(question)


@pytest.mark.parametrize(
    "question",
    [
        "Compare consumo e receita por município em junho de 2026.",
        "Qual foi o impacto da queda no consumo sobre a receita por classe em agosto de 2026?",
        "Quais municípios caíram no consumo e como isso impactou a receita nos últimos 12 meses?",
    ],
)
def test_does_not_assume_published_windows_for_unbounded_compound_questions(question):
    assert not is_ranked_consumption_revenue_impact_question(question)


def test_recognizes_the_two_typed_consumption_price_compound_questions():
    comparison = financial_comparison_scope(
        "Como variaram consumo e preço observado por kWh em Recife entre janeiro e junho de 2026?"
    )
    assert comparison is not None
    assert comparison.municipality == "recife"
    assert comparison.periods == tuple(f"2026-{month:02d}" for month in range(1, 7))
    assert comparison.metric_ids == ("energy.consumption", "billing.effective_tariff")

    snapshot = financial_comparison_scope(
        "Para Recife em junho de 2026, mostre faturamento, consumo e preço observado na base comparável."
    )
    assert snapshot is not None
    assert snapshot.periods == ("2026-06",)
    assert snapshot.metric_ids == (
        "billing.revenue", "energy.consumption", "billing.effective_tariff",
    )


def test_does_not_accept_reversed_financial_comparison_periods():
    assert financial_comparison_scope(
        "Como variaram consumo e preço observado por kWh em Recife entre junho e janeiro de 2026?"
    ) is None


def test_compound_response_limits_to_top_three_after_validating_full_population():
    consumption = tuple(
        ConsumptionTotals(name, Decimal(100), Decimal(current))
        for name, current in (("A", 0), ("B", 20), ("C", 30), ("D", 40))
    )
    revenue = tuple(
        RevenueEffect(name, "RESIDENCIAL", Decimal(-10), Decimal(-4), neighborhood="CENTRO")
        for name, _ in (("A", 0), ("B", 20), ("C", 30), ("D", 40))
    )
    complete = compose_consumption_revenue(
        SCOPE,
        SCOPE,
        consumption,
        revenue,
        expected_municipalities=frozenset({"A", "B", "C", "D"}),
        expected_revenue_groups=frozenset(
            (name, "CENTRO", "RESIDENCIAL") for name in ("A", "B", "C", "D")
        ),
    )
    analysis = SqlCompoundAnalysis.from_sources(
        complete,
        {"method": SCOPE.windows.method, "csv_sha256": "a" * 64},
        "b" * 64,
        municipality_limit=3,
    )

    assert [row.municipality for row in analysis.municipalities] == ["A", "B", "C"]
    assert "três municípios" in analysis.answer


def test_monthly_snapshot_reports_values_without_fabricating_a_change():
    snapshot_scope = EvidenceScope(
        "gold-csv-v2:test",
        "snapshot-scope",
        ObservedComparisonWindows(
            p0_start="2026-06", p0_end="2026-06",
            p1_start="2026-06", p1_end="2026-06",
            method="VARIACAO_OBSERVADA",
        ),
    )
    result = compose_consumption_revenue(
        snapshot_scope,
        snapshot_scope,
        (ConsumptionTotals("RECIFE", Decimal("5353512.0"), Decimal("5353512.0")),),
        (RevenueEffect(
            "RECIFE", "Todas", Decimal("4313585.27"), None, None, None,
            state="DECOMPOSICAO_INDISPONIVEL", consumption_change_kwh=Decimal("0.0"),
        ),),
        expected_municipalities=frozenset({"RECIFE"}),
        expected_revenue_groups=frozenset({("RECIFE", "Todas")}),
        only_declines=False,
        snapshot=True,
    )

    analysis = SqlCompoundAnalysis.from_sources(result, None, None)

    assert analysis.municipalities[0].previous_consumption_kwh == "5353512"
    assert analysis.municipalities[0].current_consumption_kwh == "5353512"
    assert analysis.municipalities[0].change_kwh == "0"
    assert analysis.municipalities[0].change_percent == "0.000000"
    assert analysis.municipalities[0].revenue_by_class[0].consumption_change_kwh == "0"
    assert analysis.answer == (
        "Em junho de 2026, RECIFE teve o maior consumo medido "
        "(5.353.512 kWh) e o maior faturamento (R$ 4.313.585,27) entre os municípios consultados."
    )


def test_month_to_month_class_comparison_explains_observed_directions():
    comparison_scope = EvidenceScope(
        "gold-csv-v2:test",
        "comparison-scope",
        ObservedComparisonWindows(
            p0_start="2026-05", p0_end="2026-05",
            p1_start="2026-06", p1_end="2026-06",
            method="VARIACAO_OBSERVADA",
        ),
    )
    result = compose_consumption_revenue(
        comparison_scope,
        comparison_scope,
        (ConsumptionTotals("RECIFE", Decimal("1000000"), Decimal("900784")),),
        (RevenueEffect(
            "RECIFE", "INDUSTRIAL", Decimal("72.52"), None, None, None,
            state="DECOMPOSICAO_INDISPONIVEL", consumption_change_kwh=Decimal("-99216"),
        ),),
        expected_municipalities=frozenset({"RECIFE"}),
        expected_revenue_groups=frozenset({("RECIFE", "INDUSTRIAL")}),
    )

    analysis = SqlCompoundAnalysis.from_sources(result, None, None)

    assert analysis.municipalities[0].change_kwh == "-99216"
    assert analysis.municipalities[0].revenue_by_class[0].consumption_change_kwh == "-99216"
    assert analysis.answer == (
        "Entre maio de 2026 e junho de 2026, em RECIFE, na classe INDUSTRIAL, "
        "o consumo caiu 99.216 kWh e o faturamento subiu R$ 72,52. "
        "São variações observadas; elas não demonstram que a queda de consumo causou a alta do faturamento."
    )


def test_annual_class_comparison_summarizes_both_metrics_without_claiming_causality():
    comparison_scope = EvidenceScope(
        "gold-csv-v2:test",
        "annual-class-scope",
        ObservedComparisonWindows(
            p0_start="2024-07", p0_end="2025-06",
            p1_start="2025-07", p1_end="2026-06",
            method="VARIACAO_OBSERVADA",
        ),
    )
    result = CompoundResult(
        scope=comparison_scope,
        municipalities=(MunicipalityDecline(
            consumption=ConsumptionTotals("RECIFE", Decimal("79821812"), Decimal("78260448")),
            change_kwh=Decimal("-1561364"),
            change_percent=Decimal("-1.956062"),
            revenue_by_class=(
                RevenueEffect("RECIFE", "COMERCIAL", Decimal("510261.75"), None,
                              state="DECOMPOSICAO_INDISPONIVEL", consumption_change_kwh=Decimal("-1034244")),
                RevenueEffect("RECIFE", "INDUSTRIAL", Decimal("-2148035.93"), None,
                              state="DECOMPOSICAO_INDISPONIVEL", consumption_change_kwh=Decimal("207113")),
                RevenueEffect("RECIFE", "PODER PUBLICO", Decimal("159163.17"), None,
                              state="DECOMPOSICAO_INDISPONIVEL", consumption_change_kwh=Decimal("-876")),
                RevenueEffect("RECIFE", "RESIDENCIAL", Decimal("507445.43"), None,
                              state="DECOMPOSICAO_INDISPONIVEL", consumption_change_kwh=Decimal("-736062")),
                RevenueEffect("RECIFE", "RURAL", Decimal("65958.14"), None,
                              state="DECOMPOSICAO_INDISPONIVEL", consumption_change_kwh=Decimal("2705")),
            ),
        ),),
    )

    analysis = SqlCompoundAnalysis.from_sources(result, None, None)

    assert "COMERCIAL: consumo caiu 1.034.244 kWh; receita faturada subiu R$ 510.261,75" in analysis.answer
    assert "INDUSTRIAL: consumo subiu 207.113 kWh; receita faturada caiu R$ 2.148.035,93" in analysis.answer
    assert "RURAL: consumo subiu 2.705 kWh; receita faturada subiu R$ 65.958,14" in analysis.answer
    assert "não demonstram que a variação do consumo causou" in analysis.answer
