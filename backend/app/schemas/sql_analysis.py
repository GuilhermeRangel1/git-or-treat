"""Envelope público da análise Text-to-SQL; nunca expõe SQL nem parâmetros."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.ai import AICorrelationId, AIQuestionRequest
from app.schemas.sql_evidence import SqlEvidence
from app.schemas.sql_generation import SqlClarification, SqlUnsupported


class SqlAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: AICorrelationId
    status: Literal["answered", "needs_clarification", "unsupported"]
    evidence: SqlEvidence | None = None
    clarification: SqlClarification | None = None
    unsupported_reason: SqlUnsupported | None = None

    @classmethod
    def from_run(cls, correlation_id, run):
        candidate = run.candidate
        if run.evidence is not None:
            return cls(correlation_id=correlation_id, status="answered", evidence=run.evidence)
        return cls(correlation_id=correlation_id, status=candidate.status,
                   clarification=candidate.clarification,
                   unsupported_reason=candidate.unsupported_reason)


class SqlAnalysisRequest(AIQuestionRequest):
    """Pergunta F1 autenticada pelo Backend; contexto segue conversa existente."""
