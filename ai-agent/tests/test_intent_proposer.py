"""O prompt semântico do provedor precisa incluir regras e janela temporal aprovadas."""

import asyncio
import json

from app.agent.access import ReadAccessPolicy
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.providers.intent_proposer import GeminiIntentProposer

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


def test_model_context_includes_specific_ambiguity_rules_and_relative_time_contract():
    client = _Client(_clarification_response())
    _, request = _setup("Qual bairro mais perdeu volume residencial no último ano?")

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
    assert rules
    assert "volume residencial" in rules[0]["matched_phrases"]
    assert "energia faturada" in rules[0]["clarification"]
    assert "consumo medido é outro indicador" in rules[0]["clarification"]
    assert any("mês completo mais recente" in rule for rule in payload["temporal_rules"])
    assert "a frase mais específica prevalece" in client.aio.models.request[
        "config"
    ]["system_instruction"]
    assert client.aio.models.request["config"]["max_output_tokens"] == 512


def test_provider_overrides_ready_model_guess_for_unresolved_residential_volume():
    client = _Client(_ready_response("energy.consumption", "consumption"))
    _, request = _setup("Qual bairro mais perdeu volume residencial no último ano?")

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
    assert "energia faturada" in result.clarification_question
    assert "consumo medido é outro indicador" in result.clarification_question


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
