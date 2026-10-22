import inspect

import pytest
from pydantic import ValidationError

from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.scenarios import SYNTHETIC_SCENARIOS
from app.schemas.analysis import AnalysisIntent
from app.schemas.scenarios import SyntheticScenario
from app.tools.synthetic_analytics import SyntheticScenarioTool


def test_synthetic_catalog_covers_prd_domains_and_marks_every_result_as_demo() -> None:
    scenarios = {scenario.scenario_id: scenario for scenario in SYNTHETIC_SCENARIOS}

    assert set(scenarios) == {
        "revenue_comparison_demo",
        "consumption_demo",
        "network_interruptions_demo",
        "service_attendance_demo",
    }
    assert {scenario.intent.domain for scenario in scenarios.values()} == {
        domain.id for domain in GRID360_DEMO_PROFILE.domains
    }
    assert all(scenario.evidence.reference.is_demo for scenario in scenarios.values())
    assert all(scenario.limitations for scenario in scenarios.values())


def test_synthetic_catalog_values_match_explicit_demo_expectations() -> None:
    scenarios = {scenario.scenario_id: scenario for scenario in SYNTHETIC_SCENARIOS}

    assert scenarios["revenue_comparison_demo"].evidence.records == [
        {"period_label": "período A", "value": 100, "unit": "unidades fictícias"},
        {"period_label": "período B", "value": 95, "unit": "unidades fictícias"},
    ]
    assert scenarios["consumption_demo"].evidence.records == [
        {"value": 420, "unit": "unidades fictícias"}
    ]
    assert scenarios["network_interruptions_demo"].evidence.records == [
        {"value": 2, "unit": "ocorrências fictícias"}
    ]
    assert scenarios["service_attendance_demo"].evidence.records == [
        {"value": 1, "unit": "atendimento fictício"}
    ]


def test_synthetic_scenario_rejects_evidence_not_marked_as_demo() -> None:
    scenario_data = SYNTHETIC_SCENARIOS[0].model_dump()
    scenario_data["evidence"]["reference"]["is_demo"] = False

    with pytest.raises(ValidationError):
        SyntheticScenario.model_validate(scenario_data)


def test_analysis_intent_keeps_unapproved_business_terms_as_phrases() -> None:
    intent = AnalysisIntent(
        domain="revenue",
        metric_phrase="receita",
        period_phrase="último ano",
        geography_phrase="bairro mencionado pela pessoa",
        class_phrase="residencial",
    )

    assert intent.metric_phrase == "receita"
    assert intent.period_phrase == "último ano"
    assert intent.model_dump()["filters"] == {}


def test_synthetic_source_retrieve_matches_evidence_port_keyword() -> None:
    inspect.signature(SyntheticScenarioTool.retrieve).bind(
        SyntheticScenarioTool(), plan=object(), access_context=object()
    )
