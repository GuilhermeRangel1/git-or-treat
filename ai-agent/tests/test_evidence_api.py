import httpx
import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.api.access import SYNTHETIC_SOURCE_ID
from app.config import Settings
from app.main import create_app
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.protocols import GeneratedAnswer
from app.schemas.evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceProvenance,
    EvidenceReference,
    EvidenceResult,
)
from app.schemas.read_plan import LogicalReadPlan


class AlternateEvidenceSource:
    async def retrieve(self, plan: LogicalReadPlan, _access_context) -> EvidenceLookupResult:
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.AVAILABLE,
            evidence=EvidenceResult(
                reference=EvidenceReference(
                    source="synthetic_fixture:alternate_test",
                    description="Evidence returned by an alternate adapter.",
                    is_demo=True,
                ),
                records=[{"value": 5, "unit": "unidades fictícias"}],
                provenance=EvidenceProvenance(
                    source_id=plan.source_id,
                    reference_source="synthetic_fixture:alternate_test",
                    plan_fingerprint=plan.fingerprint(),
                    catalog_version=plan.catalog_version,
                    metric_id=plan.metric_id,
                    unit=plan.unit,
                    window=plan.window,
                    filters=plan.filters,
                    dimension_ids=plan.dimension_ids,
                ),
            ),
            limitations=[
                "Valor inventado; não representa leitura, consumo ou unidade consumidora "
                "da V-Energy."
            ],
        )


class FixedModelAdapter:
    async def generate(self, question, context, evidence) -> GeneratedAnswer:
        return GeneratedAnswer(
            status="answered", answer="O consumo foi 5 unidades fictícias.",
            observation_ids=("row_1",),
        )


@pytest.mark.anyio
async def test_questions_api_uses_an_alternate_evidence_source() -> None:
    orchestrator = QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(
            QuestionInterpreter(GRID360_DEMO_PROFILE),
            AlternateEvidenceSource(),
            ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID),
        ),
        model_adapter=FixedModelAdapter(),
    )
    app = create_app(
        settings=Settings(_env_file=None, environment="local", enable_demo_access=True),
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
    assert "5 unidades fictícias" in response.json()["answer"]
    assert response.json()["evidence"] == [
        {
            "source": response.json()["evidence"][0]["source"],
            "description": "Evidência agregada validada pelo serviço.",
            "is_demo": True,
        }
    ]
    assert response.json()["evidence"][0]["source"].startswith(f"{SYNTHETIC_SOURCE_ID}:")
