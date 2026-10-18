"""Interfaces independentes de fornecedor para a geração de respostas."""

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from app.schemas.evidence import EvidenceResult
from app.schemas.questions import ConversationTurn


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "needs_clarification", "refused"]
    answer: str


class ModelProviderUnavailable(Exception):
    """Sinaliza indisponibilidade temporária do provedor de linguagem."""


class ModelAdapter(Protocol):
    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer: ...
