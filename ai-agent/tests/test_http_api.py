"""Contratos HTTP públicos do serviço GenAI."""

import asyncio

import httpx

from app.config import Settings
from app.main import create_app

from .conftest import client_factory


def test_health_reports_only_process_liveness() -> None:
    with client_factory() as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_capabilities_describe_the_contract_without_internal_configuration() -> None:
    with client_factory() as client:
        response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v1"
    assert body["question_endpoint"] == "/api/v1/questions"
    assert body["insight_endpoint"] == "/api/v1/insights"
    assert body["requires_gold"] is False
    assert "secret" not in str(body).lower()
    assert "key" not in str(body).lower()


def test_question_input_rejects_blank_text_and_context_over_limit() -> None:
    with client_factory() as client:
        blank = client.post("/api/v1/questions", json={"question": "   "})
        oversized_question = client.post(
            "/api/v1/questions",
            json={"question": "x" * 1001},
        )
        oversized_context = client.post(
            "/api/v1/questions",
            json={
                "question": "Consumo?",
                "context": [
                    {"role": "user", "content": "Pergunta"},
                    {"role": "assistant", "content": "Resposta"},
                    {"role": "user", "content": "Continuação"},
                    {"role": "assistant", "content": "Excesso"},
                ],
            },
        )
        unexpected_field = client.post(
            "/api/v1/questions",
            json={"question": "Consumo?", "instruction": "valor que não deve ser ecoado"},
        )

    assert blank.status_code == 422
    assert oversized_question.status_code == 422
    assert oversized_context.status_code == 422
    assert unexpected_field.status_code == 422
    error = unexpected_field.json()
    assert error["contract_version"] == "v1"
    assert error["status"] == "error"
    assert error["error"] == {"code": "invalid_request", "retryable": False}
    assert error["message"] == "A solicitação não segue o contrato esperado."
    assert error["correlation_id"] == unexpected_field.headers["x-correlation-id"]
    assert error["audit_reference"] is None
    assert "valor que não deve ser ecoado" not in unexpected_field.text


def test_default_api_does_not_answer_without_configured_provider() -> None:
    with client_factory() as client:
        response = client.post(
            "/api/v1/questions",
            json={"question": "Qual foi o consumo no período de demonstração?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "recoverable_error"
    assert body["evidence"] == []
    assert body["contract_version"] == "v1"
    assert body["correlation_id"] == response.headers["x-correlation-id"]
    assert body["audit_reference"] is None
    assert body["error"] == {"code": "service_unavailable", "retryable": True}


def test_openapi_describes_the_stable_invalid_request_envelope() -> None:
    with client_factory() as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    question_errors = schema["paths"]["/api/v1/questions"]["post"]["responses"]["422"]
    insight_errors = schema["paths"]["/api/v1/insights"]["post"]["responses"]["422"]
    question_internal_errors = schema["paths"]["/api/v1/questions"]["post"]["responses"]["500"]
    assert question_errors["content"]["application/json"]["schema"]["$ref"].endswith(
        "/PublicErrorResponse"
    )
    assert insight_errors["content"]["application/json"]["schema"]["$ref"].endswith(
        "/PublicErrorResponse"
    )
    assert question_internal_errors["content"]["application/json"]["schema"]["$ref"].endswith(
        "/PublicErrorResponse"
    )
    response_schema = schema["components"]["schemas"]["QuestionResponse"]["properties"]
    assert {
        "contract_version",
        "correlation_id",
        "audit_reference",
        "error",
        "analysis_context",
    }.issubset(response_schema)


def test_unexpected_failure_returns_safe_envelope_and_correlation() -> None:
    class ExplodingQuestionOrchestrator:
        async def answer(self, _payload, _access_context, _correlation_id):
            raise RuntimeError("segredo interno que não deve ser exposto")

    application = create_app(
        settings=Settings(
            _env_file=None,
            environment="local",
            enable_demo_access=True,
        ),
        question_orchestrator=ExplodingQuestionOrchestrator(),
    )

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/v1/questions", json={"question": "Consumo?"})

    response = asyncio.run(send_request())

    assert response.status_code == 500
    body = response.json()
    assert body["contract_version"] == "v1"
    assert body["status"] == "error"
    assert body["error"] == {"code": "internal_error", "retryable": False}
    assert body["correlation_id"] == response.headers["x-correlation-id"]
    assert "segredo interno" not in response.text
