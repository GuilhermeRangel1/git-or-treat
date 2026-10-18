import asyncio

import httpx

from app.config import Settings
from app.main import create_app
from app.providers.protocols import GeneratedAnswer
from app.schemas.evidence import EvidenceResult
from app.schemas.questions import ConversationTurn


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


class FakeModelAdapter:
    def __init__(
        self,
        result: GeneratedAnswer | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or GeneratedAnswer(
            status="answered",
            answer="Resposta de demonstração.",
            observation_ids=("row_1",),
        )
        self.error = error

    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        if self.error:
            raise self.error
        return self.result


def client_factory() -> InProcessClient:
    return InProcessClient(create_app(settings=Settings(_env_file=None)))
