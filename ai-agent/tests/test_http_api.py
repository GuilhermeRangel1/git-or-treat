from app.providers.protocols import GeneratedAnswer, ModelProviderUnavailable
from app.schemas.questions import ConversationTurn
from app.tools.evidence import EvidenceToolUnavailable


def test_health_reports_only_process_liveness(client_factory) -> None:
    with client_factory() as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_capabilities_describe_the_contract_without_internal_configuration(client_factory) -> None:
    with client_factory() as client:
        response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v1"
    assert body["question_endpoint"] == "/api/v1/questions"
    assert body["requires_gold"] is False
    assert "secret" not in str(body).lower()
    assert "key" not in str(body).lower()


def test_question_without_evidence_admits_insufficient_data(client_factory) -> None:
    with client_factory() as client:
        response = client.post("/api/v1/questions", json={"question": "Qual foi o consumo?"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "no_evidence",
        "answer": None,
        "message": (
            "Ainda não há uma fonte analítica configurada para responder com evidências."
        ),
        "evidence": [],
    }


def test_question_returns_a_structured_answer_with_demo_evidence(
    client_factory,
    demo_evidence,
) -> None:
    from conftest import FakeEvidenceTool, FakeModelAdapter

    with client_factory(
        evidence_tool=FakeEvidenceTool(demo_evidence),
        model_adapter=FakeModelAdapter(),
    ) as client:
        response = client.post(
            "/api/v1/questions",
            json={
                "question": "Qual foi o consumo?",
                "context": [{"role": "user", "content": "Pergunta anterior"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["answer"] == "Resposta de demonstração."
    assert body["evidence"] == [
        {
            "source": "fixture_sintetica",
            "description": "Dados fictícios para teste de contrato; não representam a V-Energy.",
            "is_demo": True,
        }
    ]


def test_question_input_rejects_blank_text_and_context_over_limit(client_factory) -> None:
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


def test_question_converts_provider_outage_to_recoverable_status(
    client_factory,
    demo_evidence,
) -> None:
    from conftest import FakeEvidenceTool, FakeModelAdapter

    with client_factory(
        evidence_tool=FakeEvidenceTool(demo_evidence),
        model_adapter=FakeModelAdapter(error=ModelProviderUnavailable("private provider detail")),
    ) as client:
        response = client.post("/api/v1/questions", json={"question": "Consumo?"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "recoverable_error",
        "answer": None,
        "message": "O serviço de resposta está temporariamente indisponível. Tente novamente.",
        "evidence": [],
    }
    assert "private provider detail" not in response.text


def test_evidence_failure_does_not_leak_internal_error(client_factory) -> None:
    from conftest import FakeEvidenceTool

    with client_factory(
        evidence_tool=FakeEvidenceTool(error=EvidenceToolUnavailable("private storage detail")),
    ) as client:
        response = client.post("/api/v1/questions", json={"question": "Consumo?"})

    assert response.json()["status"] == "recoverable_error"
    assert "private storage detail" not in response.text


def test_model_controlled_states_are_preserved(client_factory, demo_evidence) -> None:
    from conftest import FakeEvidenceTool, FakeModelAdapter

    cases = [
        ("needs_clarification", "Qual período você quer comparar?"),
        ("refused", "Não posso executar essa solicitação."),
    ]
    for status, message in cases:
        with client_factory(
            evidence_tool=FakeEvidenceTool(demo_evidence),
            model_adapter=FakeModelAdapter(result=GeneratedAnswer(status=status, answer=message)),
        ) as client:
            response = client.post("/api/v1/questions", json={"question": "Me diga sobre a conta."})
        assert response.json()["status"] == status
        assert response.json()["answer"] == message


def test_request_contract_accepts_only_bounded_context(client_factory) -> None:
    with client_factory() as client:
        response = client.post(
            "/api/v1/questions",
            json={
                "question": "Consumo?",
                "context": [
                    ConversationTurn(role="user", content="Pergunta anterior").model_dump()
                ],
            },
        )

    assert response.status_code == 200
