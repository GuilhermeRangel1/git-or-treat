"""Afirmações quantitativas conferidas pelo caso de uso, sem provedor externo."""

import asyncio
import json

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.execution import ExecutionController, ExecutionLimits
from app.agent.insights import ScreenInsightOrchestrator
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.routing import ModelRouter, ModelTier, RoutingPolicy
from app.schemas.insights import ScreenContext
from app.schemas.questions import QuestionRequest
from app.tools.synthetic_analytics import SyntheticScenarioTool


class ClaimModel:
    def __init__(self, claim, *, text="Observação selecionada.", ids=("row_1",)):
        self.claim = claim
        self.text = text
        self.ids = ids

    async def generate(self, question, context, evidence):
        return {
            "status": "answered",
            "answer": self.text,
            "observation_ids": self.ids,
            "claims": [self.claim] if self.claim is not None else [],
        }


def ask(claim, *, strong_claim=None):
    model = ClaimModel(claim)
    router = ModelRouter({ModelTier.LIGHT: model, ModelTier.STRONG: ClaimModel(strong_claim)},
                         RoutingPolicy(light_intents={"consumption"})) if strong_claim else None
    orchestrator = QuestionOrchestrator(
        QuestionAnalysisPlanner(
            QuestionInterpreter(GRID360_DEMO_PROFILE),
            SyntheticScenarioTool(),
            ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID),
        ),
        model if router is None else None,
        model_router=router,
        execution_controller=ExecutionController(ExecutionLimits(max_model_calls=2)),
    )
    return asyncio.run(orchestrator.answer(
        QuestionRequest(question="Qual foi o consumo no período de demonstração?"),
        demo_access_context(GRID360_DEMO_PROFILE, "0" * 32),
    ))


def test_wrong_unit_is_not_grounded_even_when_value_matches():
    response = ask({
        "observation_id": "row_1", "value": 420, "metric": "energy.consumption",
        "unit": "R$", "period": "período de demonstração", "filters": {},
    })
    assert response.status == "refused"
    assert response.error.code == "ungrounded_response"
    assert response.answer is None


@pytest.mark.parametrize("change", [
    {"metric": "billing.revenue"}, {"period": "2025-03"},
    {"filters": {"geography.municipality": "Olinda"}}, {"value": 419},
    {"unit": "%", "value": 10}, {"observation_id": "row_2"},
    {"dimensions": {"geography.municipality": "Recife"}},
])
def test_claim_must_match_the_selected_observation_context(change):
    claim = {
        "observation_id": "row_1", "value": 420, "metric": "energy.consumption",
        "unit": "unidades fictícias", "period": "período de demonstração", "filters": {},
    }
    response = ask(claim | change)
    assert response.status == "refused"
    assert response.error.code == "ungrounded_response"


def test_matching_claim_keeps_server_rendered_value_and_context():
    response = ask({
        "observation_id": "row_1", "value": 420, "metric": "energy.consumption",
        "unit": "unidades fictícias", "period": "período de demonstração", "filters": {},
    })
    assert response.status == "answered"
    assert "420 unidades fictícias" in response.answer
    assert response.analysis_context.metric == "energy.consumption"


def test_context_mismatch_escalates_through_existing_router_then_validates_strong_claim():
    claim = {
        "observation_id": "row_1", "value": 420, "metric": "energy.consumption",
        "unit": "unidades fictícias", "period": "período de demonstração", "filters": {},
    }
    response = ask(claim | {"unit": "R$"}, strong_claim=claim)
    assert response.status == "answered"
    assert response.model_tier == "strong"
    assert "420 unidades fictícias" in response.answer


def test_wrong_context_from_strong_model_is_also_rejected():
    claim = {
        "observation_id": "row_1", "value": 420, "metric": "energy.consumption",
        "unit": "R$", "period": "período de demonstração", "filters": {},
    }
    response = ask(claim, strong_claim=claim)
    assert response.status == "refused"
    assert response.model_tier == "strong"
    assert response.answer is None


def screen_context(value=90):
    return ScreenContext.model_validate({
        "metric": "Energia faturada", "unit": "kWh",
        "period": {"start": "2025-01-01", "end": "2025-01-31", "granularity": "month"},
        "filters": {"municipio": "Recife"},
        "observations": [{"label": "Atual", "value": value}],
        "reference": {"source": "synthetic.screen", "description": "Inventado", "is_demo": True},
        "limitations": ["Dados inventados."],
    })

def insight_claim(**changes):
    return {
        "observation_id": "row_1", "metric": "Energia faturada", "value": 90, "unit": "kWh",
        "period": "2025-01-01 a 2025-01-31", "filters": {"municipio": "Recife"},
    } | changes


def insight(model, screen=None):
    return asyncio.run(ScreenInsightOrchestrator(
        model, ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID),
    ).generate(screen or screen_context(), demo_access_context(GRID360_DEMO_PROFILE, "0" * 32)))


@pytest.mark.parametrize("change", [
    {"metric": "Receita"}, {"unit": "MWh"}, {"value": 2025},
    {"period": "2025-02-01 a 2025-02-28"},
    {"filters": {"municipio": "Olinda"}},
    {"filters": {}}, {"filters": {"municipio": "Recife", "classe": "residencial"}},
    {"unit": "%", "value": 10},
    {"filter_operators": {"municipio": "ne"}},
    {"filter_operators": {"classe": "eq"}},
])
def test_insight_rejects_context_mismatch_but_preserves_observed_data(change):
    response = insight(ClaimModel(insight_claim(**change)))
    assert response.status == "refused"
    assert response.hypothesis is None
    assert response.observation.values[0].value == 90


def test_matching_insight_keeps_hypothesis_separate_from_observations():
    response = insight(ClaimModel(insight_claim()))
    assert response.status == "answered"
    assert "não comprova uma causa" in response.hypothesis
    assert response.observation.values[0].value == 90


@pytest.mark.parametrize("value,rounded,places", [
    (90.125, 90.13, 2), (-90.125, -90.13, 2), (0, 0, 0), (90.5, 91, 0),
])
def test_declared_decimal_rounding_preserves_original_observed_value(value, rounded, places):
    response = insight(ClaimModel(
        insight_claim(value=rounded, decimal_places=places), text=f"Valor: {rounded} kWh.",
    ), screen_context(value))
    assert response.status == "answered"
    assert response.observation.values[0].value == value


def test_rounding_is_not_an_arbitrary_numeric_tolerance():
    response = insight(ClaimModel(insight_claim(value=90.12, decimal_places=2)),
                       screen_context(90.125))
    assert response.status == "refused"


def test_values_from_two_selected_rows_cannot_be_swapped():
    payload = screen_context().model_dump() | {"observations": [
        {"label": "Atual", "value": 90}, {"label": "Anterior", "value": 100},
    ]}
    screen = ScreenContext.model_validate(payload)
    response = insight(ClaimModel(insight_claim(value=100), ids=("row_1", "row_2")), screen)
    assert response.status == "refused"


def test_legacy_model_without_claims_cannot_invent_an_insight_percentage():
    response = insight(ClaimModel(None, text="Houve queda de 10%."))
    assert response.status == "refused"


def test_grounding_uses_injected_domain_instead_of_grid360_metric_names():
    from .weather_fixture import WEATHER_PROFILE, WEATHER_SOURCE_ID, WeatherEvidenceSource

    claim = {
        "observation_id": "row_1", "metric": "weather.rainfall", "value": 12,
        "unit": "mm fictícios", "period": "período de demonstração", "filters": {},
    }
    core = QuestionOrchestrator(QuestionAnalysisPlanner(
        QuestionInterpreter(WEATHER_PROFILE), WeatherEvidenceSource(),
        ReadAccessPolicy(WEATHER_PROFILE, WEATHER_SOURCE_ID),
    ), ClaimModel(claim))
    response = asyncio.run(core.answer(
        QuestionRequest(question="Qual foi a chuva no período de demonstração?"),
        demo_access_context(WEATHER_PROFILE, "0" * 32, WEATHER_SOURCE_ID),
    ))
    assert response.status == "answered"
    assert "12 mm fictícios" in response.answer
    assert response.analysis_context.metric == "weather.rainfall"


class BoundClaimModel:
    def __init__(self, replay=False):
        self.context_id = None
        self.replay = replay
        self.payloads = []

    async def generate(self, question, context, evidence):
        self.payloads.append(evidence.model_dump(mode="json"))
        row = evidence.records[0]["observations"][0]
        if self.context_id is None or not self.replay:
            self.context_id = row["context_id"]
        return {
            "status": "answered", "answer": "Investigue o recorte selecionado.",
            "observation_ids": ["row_1"],
            "claims": [{"observation_id": "row_1", "value": row["value"],
                        "context_id": self.context_id}],
        }


def test_insight_binds_claim_without_sending_metric_or_filter_values_to_provider():
    payload = screen_context().model_dump()
    payload["metric"] = "Métrica artificial restrita"
    payload["filters"] = {"municipio": "Local artificial restrito"}
    model = BoundClaimModel()
    response = insight(model, ScreenContext.model_validate(payload))
    assert response.status == "answered"
    serialized = json.dumps(model.payloads, ensure_ascii=False)
    assert "Métrica artificial restrita" not in serialized
    assert "Local artificial restrito" not in serialized
    assert response.context.filters == {"municipio": "Local artificial restrito"}


@pytest.mark.parametrize("change", [
    {"metric": "Outra métrica"}, {"filters": {"municipio": "Olinda"}},
    {"unit": "MWh"}, {},
])
def test_insight_rejects_replayed_context_even_when_value_is_unchanged(change):
    model = BoundClaimModel(replay=True)
    first = insight(model)
    payload = screen_context().model_dump() | change
    second = insight(model, ScreenContext.model_validate(payload))
    assert first.status == "answered"
    assert second.status == "refused"
    assert second.hypothesis is None
    assert second.observation.values[0].value == 90
