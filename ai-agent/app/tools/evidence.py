"""Interface de consulta a evidências, ainda sem conexão com banco Gold."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.questions import ConversationTurn, EvidenceReference

if TYPE_CHECKING:
    from app.schemas.scenarios import AnalysisIntent


class EvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: EvidenceReference
    records: list[dict[str, object]] = Field(default_factory=list, max_length=100)


class EvidenceLookupStatus(StrEnum):
    AVAILABLE = "available"
    NO_EVIDENCE = "no_evidence"
    NEEDS_CLARIFICATION = "needs_clarification"


class EvidenceLookupResult(BaseModel):
    """Resultado genérico da consulta; não define tabelas ou métricas Gold."""

    model_config = ConfigDict(extra="forbid")

    status: EvidenceLookupStatus
    evidence: EvidenceResult | None = None
    message: str | None = None
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status_fields(self) -> Self:
        if self.status is EvidenceLookupStatus.AVAILABLE:
            if self.evidence is None or not self.evidence.records:
                raise ValueError("resultado disponível exige evidência com registros")
            if self.message is not None:
                raise ValueError("resultado disponível não deve conter mensagem de erro")
        elif self.evidence is not None or not self.message:
            raise ValueError("resultado sem evidência exige mensagem e não pode conter dados")
        return self


class EvidenceToolUnavailable(Exception):
    """Sinaliza fonte indisponível ou resposta que viola o contrato de evidências."""


class EvidenceSource(Protocol):
    """Porta interna; implementações devem autorizar, limitar e sanitizar a consulta."""

    def retrieve(self, intent: AnalysisIntent) -> EvidenceLookupResult: ...


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
