"""Contratos HTTP públicos do serviço GenAI."""

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

    assert blank.status_code == 422
    assert oversized_question.status_code == 422
    assert oversized_context.status_code == 422


def test_default_api_does_not_answer_without_configured_provider() -> None:
    with client_factory() as client:
        response = client.post(
            "/api/v1/questions",
            json={"question": "Qual foi o consumo no período de demonstração?"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "recoverable_error"
    assert response.json()["evidence"] == []
