"""Envelopes internos Backend ↔ GenAI de planejar e sintetizar (GENAI-01, proposta).

Seguem docs/contracts/genai-query-execution.md. Só a borda interna os recebe; ainda não há rota.
O escopo vem do Backend sem correlação: ela chega pelo cabeçalho X-Correlation-ID.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.access import AccessContext
from app.schemas.analysis import LogicalIdentifier
from app.schemas.domain_profile import CatalogOperation
from app.schemas.evidence import EvidenceLookupResult
from app.schemas.questions import QuestionRequest, QuestionResponse, QuestionStatus
from app.schemas.read_plan import LogicalReadPlan
from app.schemas.responses import CorrelationId
from app.schemas.version import INTERNAL_CONTRACT_VERSION, InternalContractVersion

_FINGERPRINT_PATTERN = r"^[a-f0-9]{64}$"


class AccessScope(BaseModel):
    """Escopo da pessoa usuária resolvido pelo Backend; mesmos campos de AccessContext."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    caller_ref: LogicalIdentifier
    profile_id: LogicalIdentifier
    source_id: LogicalIdentifier
    allowed_operations: frozenset[CatalogOperation] = Field(default_factory=frozenset)
    allowed_metric_ids: frozenset[LogicalIdentifier] = Field(default_factory=frozenset)
    allowed_dimension_ids: frozenset[LogicalIdentifier] = Field(default_factory=frozenset)

    def to_context(self, correlation_id: str) -> AccessContext:
        """Combina o escopo com a correlação do cabeçalho no contexto usado pelo núcleo."""

        return AccessContext(**self.model_dump(), correlation_id=correlation_id)


class QuestionPlanRequest(QuestionRequest):
    """Pergunta e até três turnos de contexto, com o escopo enviado pelo Backend."""

    access_scope: AccessScope


class QuestionPlanStatus(StrEnum):
    PLANNED = "planned"
    NEEDS_CLARIFICATION = "needs_clarification"
    REFUSED = "refused"
    RECOVERABLE_ERROR = "recoverable_error"


class QuestionPlanResponse(BaseModel):
    """Plano aprovado em ``planned``; nos demais estados, o envelope público a devolver."""

    model_config = ConfigDict(extra="forbid")

    contract_version: InternalContractVersion = INTERNAL_CONTRACT_VERSION
    correlation_id: CorrelationId
    status: QuestionPlanStatus
    plan: LogicalReadPlan | None = None
    plan_fingerprint: str | None = Field(default=None, pattern=_FINGERPRINT_PATTERN)
    response: QuestionResponse | None = None

    @model_validator(mode="after")
    def validate_content_for_status(self) -> Self:
        if self.status is QuestionPlanStatus.PLANNED:
            if self.plan is None or self.plan_fingerprint is None or self.response is not None:
                raise ValueError("plano pronto exige plano e fingerprint, sem resposta")
            if self.plan_fingerprint != self.plan.fingerprint():
                raise ValueError("fingerprint divergente do plano")
            return self
        if self.plan is not None or self.plan_fingerprint is not None or self.response is None:
            raise ValueError("estado sem plano exige resposta, sem plano nem fingerprint")
        # O Backend devolve a resposta ao portal sem alterar; estado e correlação precisam bater.
        if self.response.status is not QuestionStatus(self.status.value):
            raise ValueError("estado da resposta diverge do estado do planejamento")
        if self.response.correlation_id != self.correlation_id:
            raise ValueError("correlação da resposta diverge do envelope")
        return self


class QuestionSynthesisRequest(QuestionRequest):
    """Plano devolvido em ``planned`` e o resultado da execução no Backend."""

    access_scope: AccessScope
    plan: LogicalReadPlan
    plan_fingerprint: str = Field(pattern=_FINGERPRINT_PATTERN)
    lookup: EvidenceLookupResult
    # A publicação esperada (batch_ref) exigida pelo EvidenceGuard ainda não tem campo:
    # o transporte depende de acordo com o Backend.

    @model_validator(mode="after")
    def validate_fingerprint(self) -> Self:
        if self.plan_fingerprint != self.plan.fingerprint():
            raise ValueError("fingerprint divergente do plano")
        return self
