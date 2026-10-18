import httpx
import pytest

from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.config import Settings
from app.main import create_app
from app.providers.protocols import GeneratedAnswer
from app.schemas.questions import EvidenceReference
from app.schemas.analysis import AnalysisIntent
from app.tools.evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceResult,
)


class AlternateEvidenceSource:
    def retrieve(self, intent: AnalysisIntent) -> EvidenceLookupResult:
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.AVAILABLE,
            evidence=EvidenceResult(
                reference=EvidenceReference(
                    source="controlled_adapter:test",
                    description="Evidence returned by an alternate adapter.",
                ),
                records=[{"value": 5, "unit": "kWh"}],
            ),
        )


class FixedModelAdapter:
    async def generate(self, question, context, evidence) -> GeneratedAnswer:
        return GeneratedAnswer(status="answered", answer="O consumo foi 5 kWh.")


@pytest.mark.anyio
async def test_questions_api_uses_an_alternate_evidence_source() -> None:
    orchestrator = QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(
            QuestionInterpreter(), AlternateEvidenceSource()
        ),
        model_adapter=FixedModelAdapter(),
    )
    app = create_app(
        settings=Settings(_env_file=None),
        question_orchestrator=orchestrator,
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/questions",
            json={"question": "Qual foi o consumo no período de demonstração?"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert response.json()["answer"] == "O consumo foi 5 kWh."
    assert response.json()["evidence"] == [
        {
            "source": "controlled_adapter:test",
            "description": "Evidence returned by an alternate adapter.",
            "is_demo": False,
        }
    ]
