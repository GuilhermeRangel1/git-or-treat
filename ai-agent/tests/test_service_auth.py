from app.config import Settings
from app.main import create_app
from app.schemas.questions import QuestionResponse, QuestionStatus

from .conftest import InProcessClient

TOKEN = "internal-service-token-that-is-at-least-32-chars"
QUESTION = {"contract_version": "v1", "question": "Qual foi o consumo?", "context": []}


class SpyQuestionOrchestrator:
    def __init__(self):
        self.calls = []

    async def answer(self, payload, access_context, correlation_id):
        self.calls.append((payload, access_context, correlation_id))
        return QuestionResponse(
            status=QuestionStatus.NEEDS_CLARIFICATION,
            message="Qual período você quer consultar?",
        )


def _test_client(orchestrator):
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="local",
            enable_demo_access=True,
            service_api_token=TOKEN,
        ),
        question_orchestrator=orchestrator,
    )
    return InProcessClient(app)


def test_question_endpoint_rejects_missing_or_invalid_service_token_before_orchestration():
    for headers in ({}, {"Authorization": "Bearer wrong-token"}):
        orchestrator = SpyQuestionOrchestrator()
        with _test_client(orchestrator) as client:
            response = client.post("/api/v1/questions", json=QUESTION, headers=headers)

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "access_denied"
        assert response.json()["correlation_id"] == response.headers["x-correlation-id"]
        assert orchestrator.calls == []


def test_question_endpoint_accepts_service_token_and_propagates_correlation_id():
    correlation_id = "a" * 32
    orchestrator = SpyQuestionOrchestrator()

    with _test_client(orchestrator) as client:
        response = client.post(
            "/api/v1/questions",
            json=QUESTION,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "X-Correlation-ID": correlation_id,
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_clarification"
    assert response.json()["correlation_id"] == correlation_id
    assert response.headers["x-correlation-id"] == correlation_id
    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0][1].caller_ref == "local.demo"
    assert orchestrator.calls[0][2] == correlation_id


def test_local_direct_demo_access_remains_explicit_when_service_token_is_not_configured():
    orchestrator = SpyQuestionOrchestrator()
    app = create_app(
        settings=Settings(_env_file=None, environment="local", enable_demo_access=True),
        question_orchestrator=orchestrator,
    )

    with InProcessClient(app) as client:
        response = client.post("/api/v1/questions", json=QUESTION)

    assert response.status_code == 200
    assert len(orchestrator.calls) == 1


def test_real_mode_without_service_token_fails_closed_before_orchestration():
    orchestrator = SpyQuestionOrchestrator()
    app = create_app(
        settings=Settings(_env_file=None, environment="production"),
        question_orchestrator=orchestrator,
    )

    with InProcessClient(app) as client:
        response = client.post("/api/v1/questions", json=QUESTION)

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "service_unavailable",
        "retryable": False,
    }
    assert orchestrator.calls == []
