import asyncio
import json
import logging

import httpx
import pytest

from app.services.genai_client import (
    GenAIQuestionClient,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_sql_context import (
    SqlContextUnavailable,
    build_sql_generation_context,
)
from app.services.genai_sql_observation import (
    log_sql_context_ready,
    log_sql_context_unavailable,
    observe_sql_generation,
)
from app.services.genai_sql_structure import SqlStructureRejected
from tests.test_genai_sql_semantics import query
from tests.test_genai_sql_structure import sql_request as fixture_sql_request

sql_request = fixture_sql_request


def run(request, *, status="sql_candidate", mutation=None, http_status=200, expired=False,
        stage_expired=False):
    captured = []
    clock = [0.0]

    def handler(incoming):
        body = json.loads(incoming.content)
        captured.append(body)
        assert incoming.url.path == "/api/v1/internal/sql-candidates"
        candidate = query(request).model_dump(mode="json")
        if mutation:
            candidate = mutation(candidate)
        if stage_expired:
            clock[0] = 33
        if status == "needs_clarification":
            candidate = {"status": status, "generation_contract_version": "text-to-sql-f1-v1",
                         "context_version": body["context_version"],
                         "clarification": {"question": "Qual período?", "missing_fields": ["period"]}}
        return httpx.Response(http_status, json={"correlation_id": "b" * 32,
            "candidate": candidate}, headers={"x-correlation-id": "b" * 32})

    async def action():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = GenAIQuestionClient(http_client=http, base_url="http://genai",
                                        service_token="synthetic-service-token-0000000000")
            deadline = GenAIRequestDeadline.start(60 if stage_expired else 10,
                                                   clock=lambda: clock[0])
            clock[0] = 11 if expired else 2
            result = await observe_sql_generation(request, client=client, deadline=deadline,
                                                   correlation_id="b" * 32)
            assert captured[0]["remaining_timeout_ms"] == 8000
            return result

    return asyncio.run(action())


def test_generation_and_semantic_review_share_backend_context_and_budget(sql_request):
    result = run(sql_request)
    assert result.review.measure_semantics == (("revenue", "revenue_total"),)


def test_context_telemetry_contains_versions_and_shape_but_not_prompt_or_values(
    sql_request, caplog,
):
    payload = sql_request.model_dump(mode="json")
    payload["dimension_value_coverage"] = [{
        "dimension_id": "geography.municipality",
        "values": ["Recife"],
    }]
    request = type(sql_request).model_validate(payload)
    with caplog.at_level(logging.INFO, logger="app.services.genai_sql_observation"):
        log_sql_context_ready(build_sql_generation_context(request), "b" * 32)

    message = caplog.text
    assert "genai_sql_context outcome=ready" in message
    assert "correlation_id=" + "b" * 32 in message
    assert "mapping_version=" in message
    assert "dictionary_version=" in message
    assert "billing.revenue" in message
    assert "receita_total_reais" in message
    assert "dimension_value_count=1" in message
    assert "truncation=none" in message
    assert request.question not in message
    assert "Recife" not in message
    assert request.access_scope.caller_ref not in message


def test_context_rejection_logs_only_reason_and_size_not_context_values(sql_request, caplog):
    payload = sql_request.model_dump(mode="json")
    payload["dimension_value_coverage"] = [{
        "dimension_id": "geography.municipality",
        "values": [f"Municipio{i:04}" + "x" * 100 for i in range(700)],
    }]
    oversized = type(sql_request).model_validate(payload)
    with caplog.at_level(logging.WARNING, logger="app.services.genai_sql_observation"):
        with pytest.raises(SqlContextUnavailable) as error:
            build_sql_generation_context(oversized)
        log_sql_context_unavailable(error.value, "b" * 32)

    message = caplog.text
    assert "outcome=unavailable" in message
    assert "reason=context_too_large" in message
    assert "context_bytes=" in message
    assert "Municipio" not in message
    assert sql_request.access_scope.caller_ref not in message


def test_clarification_does_not_generate_review_or_trigger_execution(sql_request):
    assert run(sql_request, status="needs_clarification").review is None


def test_wrong_recuts_are_not_promoted_to_review(sql_request):
    def mutate(candidate):
        candidate["parameters"]["city"]["value"] = "Olinda"
        return candidate
    with pytest.raises(SqlStructureRejected):
        run(sql_request, mutation=mutate)


def test_provider_failure_is_not_a_clarification(sql_request):
    with pytest.raises(GenAIServiceUnavailable):
        run(sql_request, http_status=503)


def test_expired_global_deadline_prevents_provider_call(sql_request):
    with pytest.raises(GenAITimeout):
        run(sql_request, expired=True)


def test_envelope_budget_caps_wider_global_deadline(sql_request):
    with pytest.raises(GenAITimeout):
        run(sql_request, stage_expired=True)


@pytest.mark.parametrize("question", [
    "Qual a receita de miojo em janeiro de 2026?",
    "Qual foi o FATURAMENTO DE HAMBÚRGUER em janeiro de 2026?",
    "Qual a previsão do tempo em janeiro de 2026?",
])
def test_explicit_external_subject_stops_before_the_generator(sql_request, question):
    request = sql_request.model_copy(update={"question": question})

    class UnexpectedGenerator:
        async def generate_sql_candidate(self, *args, **kwargs):
            pytest.fail("Pedido externo chegou ao gerador")

    result = asyncio.run(observe_sql_generation(
        request, client=UnexpectedGenerator(), deadline=GenAIRequestDeadline.start(60),
        correlation_id="b" * 32,
    ))
    assert result.review is None
    assert result.candidate.status == "unsupported"
    assert result.candidate.sql is None


@pytest.mark.parametrize("question", [
    "Qual foi a receita em janeiro de 2026?",
    "Qual foi a receita de Recife em 2026?",
    "Qual foi a receita residencial?",
])
def test_energy_revenue_still_reaches_the_generator(sql_request, question):
    request = sql_request.model_copy(update={"question": question})
    assert run(request).review is not None
