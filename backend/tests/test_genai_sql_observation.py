import asyncio
import json

import httpx
import pytest
from app.services.genai_client import (
    GenAIQuestionClient,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_sql_observation import observe_sql_generation
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
