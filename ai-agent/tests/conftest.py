import asyncio
from collections.abc import Callable

import httpx
import pytest

from app.agent.orchestrator import QuestionOrchestrator
from app.config import Settings
from app.main import create_app
from app.providers.protocols import GeneratedAnswer
from app.tools.evidence import EvidenceResult, EvidenceReference


class InProcessClient:
    """Cliente ASGI local que não abre sockets nem depende de servidor externo."""

    def __init__(self, application) -> None:
        self._application = application

    async def _send(self, method: str, path: str, json: dict | None = None) -> httpx.Response:
        transport = httpx.ASGITransport(app=self._application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)

    def request(self, method: str, path: str, json: dict | None = None) -> httpx.Response:
        return asyncio.run(self._send(method, path, json))

    def get(self, path: str) -> httpx.Response:
        return self.request("GET", path)

    def post(self, path: str, json: dict | None = None) -> httpx.Response:
        return self.request("POST", path, json)

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None


class FakeEvidenceTool:
    def __init__(
        self,
        result: EvidenceResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error

    async def retrieve(self, question: str, context: list[dict[str, str]]) -> EvidenceResult | None:
        if self.error:
            raise self.error
        return self.result


class FakeModelAdapter:
    def __init__(
        self,
        result: GeneratedAnswer | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or GeneratedAnswer(
            status="answered",
            answer="Resposta de demonstração.",
        )
        self.error = error

    async def generate(
        self,
        question: str,
        context: list[dict[str, str]],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def demo_evidence() -> EvidenceResult:
    return EvidenceResult(
        reference=EvidenceReference(
            source="fixture_sintetica",
            description="Dados fictícios para teste de contrato; não representam a V-Energy.",
            is_demo=True,
        ),
        records=[{"metric": "consumo_demo", "value": 123.0}],
    )


@pytest.fixture
def client_factory() -> Callable[..., InProcessClient]:
    def create_client(
        *, evidence_tool: object | None = None, model_adapter: object | None = None
    ) -> InProcessClient:
        orchestrator = None
        if evidence_tool is not None or model_adapter is not None:
            from app.providers.unavailable import UnavailableModelAdapter
            from app.tools.evidence import NoEvidenceTool

            orchestrator = QuestionOrchestrator(
                evidence_tool=evidence_tool or NoEvidenceTool(),
                model_adapter=model_adapter or UnavailableModelAdapter(),
            )
        return InProcessClient(
            create_app(
                settings=Settings(_env_file=None),
                question_orchestrator=orchestrator,
            )
        )

    return create_client
