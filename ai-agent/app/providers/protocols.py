"""Interfaces independentes de fornecedor para a geração de respostas."""

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.evidence import EvidenceResult
from app.schemas.questions import ConversationTurn

GeneratedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "needs_clarification", "refused"]
    answer: GeneratedText


class ModelProviderUnavailable(Exception):
    """Sinaliza indisponibilidade temporária do provedor de linguagem."""


class ModelAdapter(Protocol):
    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer: ...
