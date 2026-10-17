"""Interface de consulta a evidências, ainda sem conexão com banco Gold."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.questions import ConversationTurn, EvidenceReference


class EvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: EvidenceReference
    records: list[dict[str, object]] = Field(default_factory=list)


class EvidenceToolUnavailable(Exception):
    """Sinaliza que a fonte analítica não pode ser consultada no momento."""


class EvidenceTool(Protocol):
    async def retrieve(
        self,
        question: str,
        context: list[ConversationTurn],
    ) -> EvidenceResult | None: ...


class NoEvidenceTool:
    """Fonte padrão vazia; impede que a aplicação fabrique respostas de negócio."""

    async def retrieve(
        self,
        question: str,
        context: list[ConversationTurn],
    ) -> EvidenceResult | None:
        return None
