import pytest
from pydantic import ValidationError

from app.schemas.questions import EvidenceReference
from app.schemas.analysis import AnalysisDomain, AnalysisIntent
from app.schemas.scenarios import SyntheticScenario
from app.tools.evidence import EvidenceResult
from app.tools.synthetic_analytics import (
    SyntheticComparisonRequest,
    SyntheticObservation,
    SyntheticPeriodComparisonTool,
    SyntheticScenarioRequest,
    SyntheticScenarioTool,
    ToolStatus,
)


def test_scenario_tool_returns_the_demo_evidence_for_a_supported_intent() -> None:
    result = SyntheticScenarioTool().execute(
        SyntheticScenarioRequest(
            intent=AnalysisIntent(
                domain=AnalysisDomain.CONSUMPTION,
                metric_phrase="consumo",
            )
        )
    )

    assert result.status is ToolStatus.SUCCESS
    assert result.evidence is not None
    assert result.evidence.reference.source == "synthetic_fixture:consumption_demo"
    assert result.evidence.reference.is_demo is True
    assert result.evidence.records == [{"value": 420, "unit": "unidades fictícias"}]


def test_scenario_tool_does_not_apply_filters_absent_from_the_fixture() -> None:
    result = SyntheticScenarioTool().execute(
        SyntheticScenarioRequest(
            intent=AnalysisIntent(
                domain=AnalysisDomain.CONSUMPTION,
                metric_phrase="consumo",
                period_phrase="último ano",
                geography_phrase="Olinda",
            )
        )
    )

    assert result.status is ToolStatus.NO_EVIDENCE
    assert result.evidence is None
    assert "filtros" in result.message


def test_unknown_scenario_returns_no_evidence_instead_of_zero() -> None:
    result = SyntheticScenarioTool().execute(
        SyntheticScenarioRequest(scenario_id="unknown_demo")
    )

    assert result.status is ToolStatus.NO_EVIDENCE
    assert result.evidence is None
    assert "correspondente" in result.message


def test_empty_demo_scenario_returns_no_evidence_instead_of_zero() -> None:
    empty_scenario = SyntheticScenario(
        scenario_id="empty_results_demo",
        question="Pergunta sem registros no cenário artificial.",
        intent=AnalysisIntent(domain=AnalysisDomain.CONSUMPTION),
        evidence=EvidenceResult(
            reference=EvidenceReference(
                source="synthetic_fixture:empty_results_demo",
                description="Cenário vazio para teste; não representa dado real.",
                is_demo=True,
            ),
            records=[],
        ),
        limitations=["Cenário artificial sem registros."],
    )

    result = SyntheticScenarioTool(catalog=(empty_scenario,)).execute(
        SyntheticScenarioRequest(scenario_id="empty_results_demo")
    )

    assert result.status is ToolStatus.NO_EVIDENCE
    assert result.evidence is None


def test_synthetic_period_comparison_uses_explicit_values_and_units() -> None:
    result = SyntheticPeriodComparisonTool().compare(
        SyntheticComparisonRequest(
            observations=[
                SyntheticObservation(
                    period_label="período-base-demo",
                    granularity="month",
                    value=100,
                    unit="unidades fictícias",
                ),
                SyntheticObservation(
                    period_label="período-atual-demo",
                    granularity="month",
                    value=95,
                    unit="unidades fictícias",
                ),
            ],
            reference=EvidenceReference(
                source="synthetic_fixture:period_comparison",
                description="Valores explicitamente artificiais para validar a comparação.",
                is_demo=True,
            ),
        )
    )

    assert result.status is ToolStatus.SUCCESS
    assert result.evidence is not None
    assert result.evidence.records == [
        {
            "baseline_period": "período-base-demo",
            "current_period": "período-atual-demo",
            "baseline_value": 100,
            "current_value": 95,
            "absolute_change": -5,
            "percentage_change": -5,
            "unit": "unidades fictícias",
        }
    ]
    assert result.evidence.reference.is_demo is True
    assert "não uma fórmula oficial" in result.limitations[0]


def test_zero_denominator_returns_no_evidence_and_never_zero_percent() -> None:
    result = SyntheticPeriodComparisonTool().compare(
        SyntheticComparisonRequest(
            observations=[
                SyntheticObservation(
                    period_label="base-demo",
                    granularity="month",
                    value=0,
                    unit="unidades fictícias",
                ),
                SyntheticObservation(
                    period_label="atual-demo",
                    granularity="month",
                    value=10,
                    unit="unidades fictícias",
                ),
            ],
            reference=EvidenceReference(
                source="synthetic_fixture:zero_denominator",
                description="Caso artificial com denominador zero.",
                is_demo=True,
            ),
        )
    )

    assert result.status is ToolStatus.NO_EVIDENCE
    assert result.evidence is None
    assert "denominador zero" in result.message


def test_empty_comparison_has_no_evidence_instead_of_a_zero_value() -> None:
    result = SyntheticPeriodComparisonTool().compare(
        SyntheticComparisonRequest(
            observations=[],
            reference=EvidenceReference(
                source="synthetic_fixture:no_period_values",
                description="Nenhum valor disponível no cenário artificial.",
                is_demo=True,
            ),
        )
    )

    assert result.status is ToolStatus.NO_EVIDENCE
    assert result.evidence is None
    assert "dois períodos" in result.message


def test_incomparable_periods_request_clarification() -> None:
    result = SyntheticPeriodComparisonTool().compare(
        SyntheticComparisonRequest(
            observations=[
                SyntheticObservation(
                    period_label="mês-demo",
                    granularity="month",
                    value=100,
                    unit="unidades fictícias",
                ),
                SyntheticObservation(
                    period_label="ano-demo",
                    granularity="year",
                    value=1200,
                    unit="unidades fictícias",
                ),
            ],
            reference=EvidenceReference(
                source="synthetic_fixture:incomparable_periods",
                description="Caso artificial com granularidades diferentes.",
                is_demo=True,
            ),
        )
    )

    assert result.status is ToolStatus.NEEDS_CLARIFICATION
    assert result.evidence is None
    assert "comparáveis" in result.message


def test_comparison_with_different_units_requests_clarification() -> None:
    result = SyntheticPeriodComparisonTool().compare(
        SyntheticComparisonRequest(
            observations=[
                SyntheticObservation(
                    period_label="período-base-demo",
                    granularity="month",
                    value=100,
                    unit="kWh demonstrativos",
                ),
                SyntheticObservation(
                    period_label="período-atual-demo",
                    granularity="month",
                    value=95,
                    unit="unidades demonstrativas",
                ),
            ],
            reference=EvidenceReference(
                source="synthetic_fixture:different_units",
                description="Caso artificial com unidades incompatíveis.",
                is_demo=True,
            ),
        )
    )

    assert result.status is ToolStatus.NEEDS_CLARIFICATION
    assert result.evidence is None


def test_comparison_requires_demo_reference_and_exactly_two_observations() -> None:
    with pytest.raises(ValidationError):
        SyntheticComparisonRequest(
            observations=[],
            reference=EvidenceReference(
                source="gold:real",
                description="Fonte real não permitida na ferramenta sintética.",
                is_demo=False,
            ),
        )
