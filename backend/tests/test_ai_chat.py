import asyncio
import json
from typing import Any

import httpx
import pytest

from app.main import app
from app.schemas.ai import AIQuestionResponse
from app.services.genai_client import (
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from tests.support.platform_auth import login_as_profile


@pytest.fixture(autouse=True)
def authenticated_commercial_session(client, monkeypatch):
    """Public AI route tests use the real session contract and a permitted profile."""
    return login_as_profile(client, monkeypatch, "commercial", username="ai-commercial")


def _answered_response(correlation_id: str) -> dict[str, Any]:
    return {
        "contract_version": "v1",
        "correlation_id": correlation_id,
        "audit_reference": None,
        "error": None,
        "status": "answered",
        "model_tier": "light",
        "answer": "Resposta demonstrativa.",
        "message": None,
        "evidence": [
            {
                "source": "synthetic.fixture",
                "description": "Cenário sintético de consumo.",
                "is_demo": True,
            }
        ],
        "limitations": ["Valor fictício; não representa a Gold."],
        "analysis_context": {
            "metric": "consumption",
            "unit": "kWh",
            "period": "período de demonstração",
            "filters": {"municipality": "Olinda"},
        },
    }


class FakeQuestionGateway:
    def __init__(self, response: dict[str, Any] | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[tuple[object, str]] = []

    async def ask(self, payload, correlation_id: str) -> AIQuestionResponse:
        self.calls.append((payload, correlation_id))
        if self.error is not None:
            raise self.error
        return AIQuestionResponse.model_validate(
            self.response or _answered_response(correlation_id)
        )


def test_ai_question_endpoint_forwards_versioned_contract_and_correlation(client, monkeypatch):
    gateway = FakeQuestionGateway()
    monkeypatch.setattr(app.state, "genai_question_client", gateway, raising=False)

    response = client.post(
        "/api/v1/ai/questions",
        json={
            "question": "Qual foi o consumo em Olinda?",
            "context": [{"role": "user", "content": "No período demonstrativo."}],
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert response.json()["contract_version"] == "v1"
    assert response.json()["evidence"][0]["is_demo"] is True
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]
    assert len(gateway.calls) == 1
    payload, correlation_id = gateway.calls[0]
    assert payload.contract_version == "v1"
    assert payload.question == "Qual foi o consumo em Olinda?"
    assert payload.context[0].content == "No período demonstrativo."
    assert correlation_id == response.headers["x-correlation-id"]


def test_ai_question_contract_rejects_oversized_or_extra_fields_without_echoing_input(
    client, monkeypatch
):
    gateway = FakeQuestionGateway()
    monkeypatch.setattr(app.state, "genai_question_client", gateway, raising=False)
    oversized = "x" * 1001

    response = client.post(
        "/api/v1/ai/questions",
        json={"question": oversized, "unexpected": "private marker"},
    )

    assert response.status_code == 422
    assert response.json()["status"] == "error"
    assert response.json()["error"]["code"] == "invalid_request"
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]
    assert oversized not in response.text
    assert "private marker" not in response.text
    assert gateway.calls == []


@pytest.mark.parametrize(
    ("error", "status_code", "error_code", "retryable"),
    [
        (GenAIServiceUnavailable(), 503, "service_unavailable", True),
        (GenAITimeout(), 504, "service_unavailable", True),
        (GenAIResponseInvalid(), 502, "invalid_upstream_response", False),
    ],
)
def test_ai_question_endpoint_maps_upstream_failures_to_safe_public_errors(
    client, monkeypatch, error, status_code, error_code, retryable
):
    gateway = FakeQuestionGateway(error=error)
    monkeypatch.setattr(app.state, "genai_question_client", gateway, raising=False)

    response = client.post(
        "/api/v1/ai/questions", json={"question": "Qual foi o consumo?"}
    )

    assert response.status_code == status_code
    assert response.json()["status"] == "error"
    assert response.json()["error"] == {"code": error_code, "retryable": retryable}
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]
    assert "upstream secret" not in response.text


def test_unconfigured_genai_gateway_returns_a_controlled_unavailable_error(client, monkeypatch):
    gateway = FakeQuestionGateway(error=GenAIServiceUnavailable())
    monkeypatch.setattr(app.state, "genai_question_client", gateway, raising=False)

    response = client.post(
        "/api/v1/ai/questions", json={"question": "Qual foi o consumo?"}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_genai_client_sends_contract_service_auth_and_correlation():
    request_log: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        request_log.append(request)
        correlation_id = request.headers["x-correlation-id"]
        return httpx.Response(
            200,
            json=_answered_response(correlation_id),
            headers={"X-Correlation-ID": correlation_id},
        )

    async def run() -> AIQuestionResponse:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), timeout=httpx.Timeout(2.5)
        ) as http_client:
            gateway = GenAIQuestionClient(
                http_client=http_client,
                base_url="http://genai.test",
                service_token="s" * 40,
            )
            return await gateway.ask(
                {"contract_version": "v1", "question": "Pergunta de teste", "context": []},
                correlation_id="a" * 32,
            )

    result = asyncio.run(run())

    assert result.status == "answered"
    assert len(request_log) == 1
    sent = request_log[0]
    assert sent.method == "POST"
    assert sent.url.path == "/api/v1/questions"
    assert sent.headers["authorization"] == f"Bearer {'s' * 40}"
    assert sent.headers["x-correlation-id"] == "a" * 32
    assert json.loads(sent.read()) == {
        "contract_version": "v1",
        "question": "Pergunta de teste",
        "context": [],
    }


def test_public_question_route_reaches_internal_http_contract(client, monkeypatch):
    sent_requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent_requests.append(request)
        correlation_id = request.headers["x-correlation-id"]
        return httpx.Response(
            200,
            json=_answered_response(correlation_id),
            headers={"X-Correlation-ID": correlation_id},
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(
        app.state,
        "genai_question_client",
        GenAIQuestionClient(
            http_client=http_client,
            base_url="http://genai.test",
            service_token="s" * 40,
        ),
    )

    response = client.post(
        "/api/v1/ai/questions",
        json={"question": "Qual foi o consumo no período de demonstração?"},
    )
    asyncio.run(http_client.aclose())

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]
    assert len(sent_requests) == 1
    assert sent_requests[0].headers["authorization"] == f"Bearer {'s' * 40}"
    assert sent_requests[0].headers["x-correlation-id"] == response.headers[
        "x-correlation-id"
    ]
    assert json.loads(sent_requests[0].read())["question"] == (
        "Qual foi o consumo no período de demonstração?"
    )


@pytest.mark.parametrize(
    ("handler", "expected_error"),
    [
        (
            lambda request: httpx.Response(200, json={"status": "answered"}),
            GenAIResponseInvalid,
        ),
        (
            lambda request: httpx.Response(503, json={"detail": "private upstream detail"}),
            GenAIServiceUnavailable,
        ),
        (
            lambda request: (_ for _ in ()).throw(
                httpx.ReadTimeout("private timeout detail", request=request)
            ),
            GenAITimeout,
        ),
        (
            lambda request: (_ for _ in ()).throw(
                httpx.ConnectError("private connection detail", request=request)
            ),
            GenAIServiceUnavailable,
        ),
    ],
)
def test_genai_client_classifies_timeout_network_and_invalid_responses(
    handler, expected_error
):
    async def run() -> AIQuestionResponse:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            gateway = GenAIQuestionClient(
                http_client=http_client,
                base_url="http://genai.test",
                service_token="s" * 40,
            )
            return await gateway.ask(
                {"contract_version": "v1", "question": "Pergunta de teste", "context": []},
                correlation_id="a" * 32,
            )

    with pytest.raises(expected_error):
        asyncio.run(run())

@pytest.mark.parametrize('status', [401, 403])
def test_gold_authorization_dependency_uses_safe_chat_contract(client, status):
    from fastapi import HTTPException

    from app.core.genai_gold_database import get_question_gold_resources

    def denied():
        raise HTTPException(status, 'private identity and scope detail')

    previous = app.dependency_overrides.get(get_question_gold_resources)
    app.dependency_overrides[get_question_gold_resources] = denied
    try:
        response = client.post('/api/v1/ai/questions', json={'question': 'Qual a receita?'})
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_question_gold_resources, None)
        else:
            app.dependency_overrides[get_question_gold_resources] = previous
    assert response.status_code == status
    body = response.json()
    assert body['error'] == {'code': 'access_denied', 'retryable': False}
    assert body['correlation_id'] == response.headers['x-correlation-id']
    assert 'private' not in response.text
    assert 'answer' not in body

def test_gold_audit_failure_blocks_public_question_before_planning(client, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.genai_gold_database import get_question_gold_resources
    from app.services.genai_audit import AuditStore
    from tests.support.database import test_engine

    gateway = FakeQuestionGateway()
    monkeypatch.setattr(app.state, 'genai_question_client', gateway, raising=False)

    def unavailable(self, *args, **kwargs):
        raise SQLAlchemyError('private audit storage detail')

    monkeypatch.setattr(AuditStore, 'record', unavailable)
    previous = app.dependency_overrides.get(get_question_gold_resources)
    app.dependency_overrides[get_question_gold_resources] = lambda: (test_engine, lambda: None)
    try:
        response = client.post('/api/v1/ai/questions', json={'question': 'Qual a receita?'})
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_question_gold_resources, None)
        else:
            app.dependency_overrides[get_question_gold_resources] = previous
    assert response.status_code == 503
    body = response.json()
    assert body['error'] == {'code': 'service_unavailable', 'retryable': False}
    assert body['correlation_id'] == response.headers['x-correlation-id']
    assert 'private' not in response.text
    assert 'answer' not in body

@pytest.mark.parametrize('failure_name', ['GoldPublicationUnavailable', 'GoldPublicationInvalid'])
def test_gold_unavailable_publication_returns_safe_chat_error(client, monkeypatch, failure_name):
    from app.api.v1.endpoints import ai
    from app.core.genai_gold_database import get_question_gold_resources
    from app.repositories import gold_publication
    from tests.support.database import test_engine

    async def unavailable(*args, **kwargs):
        raise getattr(gold_publication, failure_name)('private publication detail')

    monkeypatch.setattr(ai, 'answer_gold_question', unavailable)
    previous = app.dependency_overrides.get(get_question_gold_resources)
    app.dependency_overrides[get_question_gold_resources] = lambda: (test_engine, lambda: None)
    try:
        response = client.post('/api/v1/ai/questions', json={'question': 'Qual a receita?'})
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_question_gold_resources, None)
        else:
            app.dependency_overrides[get_question_gold_resources] = previous
    assert response.status_code == 503
    body = response.json()
    assert body['error'] == {'code': 'service_unavailable', 'retryable': False}
    assert body['correlation_id'] == response.headers['x-correlation-id']
    assert 'answer' not in body
    assert 'private' not in response.text
