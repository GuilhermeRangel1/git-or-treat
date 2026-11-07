"""O prompt semântico do provedor precisa incluir regras e janela temporal aprovadas."""

import asyncio
import json

import pytest

from app.agent.access import ReadAccessPolicy
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.providers.intent_proposer import GeminiIntentProposer
from app.providers.protocols import ModelProviderInvalidResponse, ModelProviderUnavailable
from app.schemas.interpretation import (
    ClarificationReason,
    IntentInterpretation,
    InterpretationStatus,
)
from app.schemas.questions import ConversationTurn
from app.schemas.read_plan import LogicalReadPlan
from app.schemas.version import INTERNAL_CONTRACT_VERSION

from .test_gold_question_filters import _setup


class _Models:
    def __init__(self, text: str):
        self.text = text
        self.request = None

    async def generate_content(self, **request):
        self.request = request
        return type("Response", (), {"text": self.text, "usage_metadata": None})()


class _Client:
    def __init__(self, text: str):
        self.aio = type("AsyncClient", (), {"models": _Models(text)})()


def _clarification_response() -> str:
    return json.dumps({
        "status": "needs_clarification",
        "clarification_question": "Você quer consumo medido ou energia faturada?",
        "clarification_reason": "ambiguous_metric",
    })


def _ready_response(metric_id: str, domain: str, *, groups: list[str] | None = None) -> str:
    intent = {
        "domain": domain,
        "metric_id": metric_id,
        "period_phrase": "último ano",
    }
    if groups:
        intent["group_by_dimension_ids"] = groups
    return json.dumps({"status": "ready", "intent": intent})


def _plan_followup(prior_question: str, question: str, intent: dict):
    core, request = _setup(prior_question)
    coverage = {
        item.metric_id: (item.kind, item.competencies)
        for item in request.temporal_coverage
    }
    dimensions = {
        item.dimension_id: item.values
        for item in request.dimension_value_coverage
    }
    access_context = request.access_scope.to_context("00000000000040008000000000000001")
    prior = core.question._analysis_planner.plan(
        prior_question, [], access_context, temporal_coverage=coverage,
        dimension_value_coverage=dimensions,
    )
    assert prior.read_plan is not None
    request = request.model_copy(update={
        "question": question,
        "context": [ConversationTurn(role="user", content=prior_question)],
        "previous_approved_plan": prior.read_plan,
    })
    client = _Client(json.dumps({"status": "ready", "intent": intent}))
    interpretation = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    ).propose())
    payload = json.loads(client.aio.models.request["contents"])
    assert payload["previous_approved_plan"] == prior.read_plan.model_dump(mode="json")
    result = core.question._analysis_planner.plan(
        request.question,
        request.context,
        access_context,
        temporal_coverage=coverage,
        dimension_value_coverage=dimensions,
        interpretation_override=interpretation,
    )
    return result


@pytest.mark.parametrize(("question", "filters"), [
    (
        "E em Olinda?",
        {"customer.consumption_class": "COMERCIAL", "geography.municipality": "Olinda"},
    ),
    (
        "Agora só residencial.",
        {"customer.consumption_class": "RESIDENCIAL", "geography.municipality": "Recife"},
    ),
    (
        "Tira o filtro de município.",
        {"customer.consumption_class": "COMERCIAL"},
    ),
])
def test_approved_plan_is_carried_into_followup_without_losing_other_filters(question, filters):
    result = _plan_followup(
        "Receita comercial em Recife em março de 2025?",
        question,
        {
            "domain": "revenue",
            "metric_id": "billing.revenue",
            "period_phrase": "março de 2025",
            "filters": filters,
        },
    )
    assert result.read_plan is not None
    assert {
        item.dimension_id: item.values[0] for item in result.read_plan.filters
    } == filters
    assert result.read_plan.window.start.isoformat() == "2025-03-01"
    assert result.read_plan.window.end.isoformat() == "2025-03-31"


def test_followup_without_approved_antecedent_does_not_guess_metric_or_period():
    core, request = _setup("E em Olinda?")
    interpretation = IntentInterpretation(
        status=InterpretationStatus.NEEDS_CLARIFICATION,
        clarification_question="Qual indicador e período você quer consultar?",
        clarification_reason=ClarificationReason.MISSING_METRIC,
    )
    coverage = {
        item.metric_id: (item.kind, item.competencies)
        for item in request.temporal_coverage
    }
    result = core.question._analysis_planner.plan(
        request.question,
        [],
        request.access_scope.to_context("00000000000040008000000000000001"),
        temporal_coverage=coverage,
        interpretation_override=interpretation,
    )
    assert result.read_plan is None
    assert result.interpretation.clarification_reason is ClarificationReason.MISSING_METRIC


def test_previous_year_followup_with_missing_coverage_does_not_shorten_the_window():
    result = _plan_followup(
        "Receita comercial em Recife em março de 2025?",
        "E no ano anterior?",
        {
            "domain": "revenue",
            "metric_id": "billing.revenue",
            "period_phrase": "março de 2024",
            "filters": {
                "customer.consumption_class": "COMERCIAL",
                "geography.municipality": "Recife",
            },
        },
    )
    assert result.read_plan is None
    assert result.clarification is not None


def test_complete_topic_change_does_not_inherit_revenue_filters():
    result = _plan_followup(
        "Receita comercial em Recife em março de 2025?",
        "Qual o FEC no alimentador AL-01 em março de 2025?",
        {
            "domain": "network",
            "metric_id": "network.equivalent_interruption_frequency",
            "period_phrase": "março de 2025",
            "filters": {"network.feeder": "AL-01"},
        },
    )
    assert result.read_plan is not None
    assert result.read_plan.metric_id == "network.equivalent_interruption_frequency"
    assert {item.dimension_id for item in result.read_plan.filters} == {"network.feeder"}


def test_model_context_includes_specific_ambiguity_rules_and_relative_time_contract():
    client = _Client(_clarification_response())
    _, request = _setup("Qual foi o valor da conta de luz em Olinda no último ano?")
    approved = LogicalReadPlan(
        catalog_version="v1", operation="read",
        profile_id="v-energy-grid-360-gold", source_id="gold.local",
        domain_id="revenue", metric_id="billing.revenue",
        dimension_ids=("geography.municipality",), unit="R$",
        window={"kind": "bounded", "start": "2025-03-01", "end": "2025-03-31",
                "granularity": "month"},
        filters=[{"dimension_id": "geography.municipality", "operator": "eq",
                  "values": ["Olinda"]}], limit=100,
    )
    request = request.model_copy(update={"previous_approved_plan": approved})

    result = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
        max_output_tokens=512,
    ).propose())

    assert result.status.value == "needs_clarification"
    payload = json.loads(client.aio.models.request["contents"])
    rules = payload["ambiguity_rules"]
    assert payload["previous_approved_plan"] == approved.model_dump(mode="json")
    assert rules
    assert "conta de luz" in rules[0]["matched_phrases"]
    assert "consumo" in rules[0]["clarification"]
    assert any("mês completo mais recente" in rule for rule in payload["temporal_rules"])
    assert "a frase mais específica prevalece" in client.aio.models.request[
        "config"
    ]["system_instruction"]
    assert "nunca omita um filtro explícito" in client.aio.models.request[
        "config"
    ]["system_instruction"]
    assert "ranking_direction e ranking_limit" in client.aio.models.request[
        "config"
    ]["system_instruction"]
    assert "required_filter_dimension_ids" in client.aio.models.request[
        "config"
    ]["system_instruction"]
    assert client.aio.models.request["config"]["max_output_tokens"] == 512


def test_provider_overrides_ready_model_guess_for_unresolved_residential_volume():
    client = _Client(_ready_response("billing.revenue", "revenue"))
    _, request = _setup("Quanto entrou no caixa em Olinda no último ano?")

    result = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    ).propose())

    assert result.status.value == "needs_clarification"
    assert result.intent is None
    assert result.clarification_reason.value == "ambiguous_metric"
    assert "não comprova pagamento" in result.clarification_question


def test_provider_clarifies_energy_spending_without_choosing_currency_or_consumption():
    client = _Client(_ready_response("energy.consumption", "consumption"))
    _, request = _setup("Quanto foi o gasto de energia em Olinda no último ano?")

    result = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    ).propose())

    assert result.status.value == "needs_clarification"
    assert "kWh" in result.clarification_question
    assert "R$" in result.clarification_question


def test_required_filter_uses_only_unique_exact_value_from_authorized_coverage():
    client = _Client(json.dumps({
        "status": "ready",
        "intent": {
            "domain": "network",
            "metric_id": "network.equivalent_interruption_duration",
            "dimension_ids": ["network.feeder"],
            "period_phrase": "março de 2025",
        },
    }))
    _, request = _setup("Pode mostrar o DEC do alimentador AL-01 em março de 2025?")

    result = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    ).propose())

    assert result.intent is not None
    assert result.intent.filters["network.feeder"] == "AL-01"


def test_invalid_provider_response_has_sanitized_diagnostic_without_raw_text():
    client = _Client("not-json-PRIVATE-MARKER")
    _, request = _setup("Qual foi a receita em Recife em março de 2025?")
    proposer = GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    )

    with pytest.raises(ModelProviderInvalidResponse):
        asyncio.run(proposer.propose())

    assert proposer.last_response_diagnostic["kind"] == "invalid_json"
    assert "PRIVATE-MARKER" not in json.dumps(proposer.last_response_diagnostic)


def test_provider_internal_version_is_canonical_and_optional_nulls_are_omitted():
    client = _Client(json.dumps({
        "status": "ready",
        "intent": {
            "contract_version": "untrusted-version",
            "domain": "revenue",
            "metric_id": "billing.revenue",
            "metric_phrase": None,
            "period_phrase": "março de 2025",
            "geography_phrase": "Recife",
            "class_phrase": None,
        },
    }))
    _, request = _setup("Qual foi a receita em Recife em março de 2025?")

    result = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    ).propose())

    assert result.intent is not None
    assert result.intent.contract_version == INTERNAL_CONTRACT_VERSION
    assert result.intent.metric_phrase is None
    assert result.intent.class_phrase is None


def test_explicit_energy_consumption_resolves_energy_spending_ambiguity():
    client = _Client(_ready_response("energy.consumption", "consumption"))
    _, request = _setup(
        "Quero consumo medido, não o valor faturado, para entender o gasto de energia em Olinda."
    )

    result = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    ).propose())

    assert result.status.value == "ready"
    assert result.intent.metric_id == "energy.consumption"


def test_provider_allows_residential_volume_after_user_explicitly_established_consumption():
    client = _Client(_ready_response(
        "energy.consumption",
        "consumption",
        groups=["geography.neighborhood"],
    ))
    _, request = _setup("E o volume residencial por bairro?")
    payload = request.model_dump(mode="json")
    payload["context"] = [{
        "role": "user",
        "content": "Mostre o consumo residencial medido em Recife em março de 2025.",
    }]
    request = type(request).model_validate(payload)

    result = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    ).propose())

    assert result.status.value == "ready"
    assert result.intent.metric_id == "energy.consumption"


def test_model_context_omits_unmatched_ambiguities_for_a_plain_revenue_question():
    client = _Client(json.dumps({
        "status": "ready",
        "intent": {
            "domain": "revenue",
            "metric_id": "billing.revenue",
            "period_phrase": "janeiro de 2024",
        },
    }))
    _, request = _setup("Qual foi o faturamento total em janeiro de 2024?")

    result = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    ).propose())

    assert result.intent is not None
    payload = json.loads(client.aio.models.request["contents"])
    assert payload["ambiguity_rules"] == []
    assert payload["question"] == "Qual foi o faturamento total em janeiro de 2024?"


def test_proposer_preserves_multiple_authorized_filter_values():
    client = _Client(json.dumps({
        "status": "ready",
        "intent": {
            "domain": "revenue",
            "metric_id": "billing.revenue",
            "period_phrase": "março de 2025",
            "filters": {
                "geography.municipality": ["Recife", "Olinda", "Jaboatão"],
            },
        },
    }))
    core, request = _setup("Receita em Recife, Olinda e Jaboatão em março de 2025?")
    payload = request.model_dump(mode="python")
    payload["dimension_value_coverage"] = [
        {
            "dimension_id": "geography.municipality",
            "values": ["Recife", "Olinda", "Jaboatão"],
        },
    ]
    request = type(request).model_validate(payload)

    result = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    ).propose())

    assert result.intent.filters["geography.municipality"] == (
        "Recife", "Olinda", "Jaboatão",
    )
    planned = core.question._analysis_planner.plan(
        request.question,
        request.context,
        request.access_scope.to_context("00000000000040008000000000000001"),
        temporal_coverage={
            item.metric_id: (item.kind, item.competencies)
            for item in request.temporal_coverage
        },
        dimension_value_coverage={
            item.dimension_id: item.values
            for item in request.dimension_value_coverage
        },
        interpretation_override=result,
    )
    assert planned.read_plan is not None
    assert planned.read_plan.filters[0].operator.value == "in"
    assert planned.read_plan.filters[0].values == ("Recife", "Olinda", "Jaboatão")


def test_filter_values_are_canonicalized_from_authorized_publication_coverage():
    response = json.dumps({
        "status": "ready",
        "intent": {
            "domain": "revenue",
            "metric_id": "billing.revenue",
            "period_phrase": "último trimestre",
            "filters": {"geography.municipality": "RECIFE"},
        },
    })
    client = _Client(response)
    _, request = _setup("Quanto faturou a distribuidora em Recife no último trimestre?")

    result = asyncio.run(GeminiIntentProposer(
        client=client,
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    ).propose())

    assert result.intent is not None
    assert result.intent.filters == {"geography.municipality": "Recife"}
    payload = json.loads(client.aio.models.request["contents"])
    municipality = next(
        item for item in payload["dimensions"] if item["id"] == "geography.municipality"
    )
    assert {"value": "Recife", "aliases": ["Recife"]} in municipality["values"]


def test_filter_value_outside_authorized_publication_coverage_is_rejected():
    response = json.dumps({
        "status": "ready",
        "intent": {
            "domain": "revenue",
            "metric_id": "billing.revenue",
            "period_phrase": "último trimestre",
            "filters": {"geography.municipality": "Jaboatão"},
        },
    })
    _, request = _setup("Quanto faturou a distribuidora em Recife no último trimestre?")

    try:
        asyncio.run(GeminiIntentProposer(
            client=_Client(response),
            model="test-model",
            profile=GRID360_GOLD_PROFILE,
            request=request,
            access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
        ).propose())
    except ValueError as error:
        assert "catálogo autorizado" in str(error)
    else:
        raise AssertionError("valor de filtro ausente na publicação deveria ser rejeitado")


def test_provider_timeout_is_sanitized_as_unavailable():
    class TimeoutModels:
        async def generate_content(self, **_request):
            raise TimeoutError("private transport detail")

    _, request = _setup("Qual foi o faturamento total em janeiro de 2024?")
    proposer = GeminiIntentProposer(
        client=type("Client", (), {
            "aio": type("Async", (), {"models": TimeoutModels()})(),
        })(),
        model="test-model",
        profile=GRID360_GOLD_PROFILE,
        request=request,
        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
    )

    with pytest.raises(ModelProviderUnavailable, match="temporariamente indisponível"):
        asyncio.run(proposer.propose())
