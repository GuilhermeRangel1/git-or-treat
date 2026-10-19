"""Interfaces independentes de fornecedor para a geração de respostas."""

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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
    observation_ids: tuple[
        Annotated[str, StringConstraints(pattern=r"^row_[1-9][0-9]{0,2}$")], ...
    ] = Field(default=(), max_length=10)


class ModelProviderUnavailable(Exception):
    """Sinaliza indisponibilidade temporária do provedor de linguagem."""


class ModelProviderRejected(Exception):
    """Erro definitivo do provedor; não aciona fallback ou nova tentativa."""


class ModelProviderInvalidResponse(Exception):
    """Saída incompatível com o contrato; não aciona fallback."""


class ModelAdapter(Protocol):
    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer: ...
