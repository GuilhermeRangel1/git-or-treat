"""Envelopes internos Backend ↔ GenAI de planejar e sintetizar (GENAI-01, proposta).

Seguem docs/contracts/genai-query-execution.md. Só a borda interna os recebe; ainda não há rota.
O escopo vem do Backend sem correlação: ela chega pelo cabeçalho X-Correlation-ID.
"""

import unicodedata
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.access import AccessContext
from app.schemas.analysis import LogicalIdentifier
from app.schemas.domain_profile import CatalogOperation
from app.schemas.evidence import EvidenceLookupResult, GoldBatchRef
from app.schemas.questions import QuestionRequest, QuestionResponse, QuestionStatus
from app.schemas.read_plan import LogicalReadPlan
from app.schemas.responses import CorrelationId
from app.schemas.version import INTERNAL_CONTRACT_VERSION, InternalContractVersion

_FINGERPRINT_PATTERN = r"^[a-f0-9]{64}$"


def _normalize_dimension_value(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


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


class TemporalCoverage(BaseModel):
    """Cobertura publicada de uma métrica lógica; ausência de período é explícita."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: LogicalIdentifier
    kind: Literal["monthly", "none"]
    competencies: tuple[
        Annotated[str, Field(strict=True, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")], ...
    ] = Field(default=(), max_length=1200)

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        if self.kind == "none" and self.competencies:
            raise ValueError("métrica sem período não admite competências")
        for competency in self.competencies:
            date.fromisoformat(competency + "-01")
        if tuple(sorted(set(self.competencies))) != self.competencies:
            raise ValueError("competências devem ser únicas e ordenadas")
        return self


class DimensionValueCoverage(BaseModel):
    """Valores de dimensão da mesma publicação, resolvidos e autorizados pelo Backend."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension_id: LogicalIdentifier
    values: tuple[
        Annotated[
            str,
            StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=120),
        ],
        ...,
    ] = Field(max_length=2000)

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        if len({_normalize_dimension_value(value) for value in self.values}) != len(self.values):
            raise ValueError("valores de dimensão devem ser únicos")
        return self


class QuestionPlanRequest(QuestionRequest):
    """Pergunta e até três turnos de contexto, com o escopo enviado pelo Backend."""

    access_scope: AccessScope
    remaining_timeout_ms: int = Field(strict=True, gt=0, le=35000)
    batch_ref: GoldBatchRef | None = None
    temporal_coverage: tuple[TemporalCoverage, ...] = Field(default=(), max_length=100)
    dimension_value_coverage: tuple[DimensionValueCoverage, ...] = Field(
        default=(), max_length=20
    )

    @model_validator(mode="after")
    def validate_publication(self) -> Self:
        if self.access_scope.source_id.startswith("gold."):
            if self.batch_ref is None or (
                self.access_scope.allowed_metric_ids and not self.temporal_coverage
            ):
                raise ValueError("planejamento Gold exige publicação e cobertura explícitas")
        elif self.batch_ref is not None or self.temporal_coverage or self.dimension_value_coverage:
            raise ValueError("metadados Gold exigem fonte Gold")
        metrics = [item.metric_id for item in self.temporal_coverage]
        if len(set(metrics)) != len(metrics):
            raise ValueError("cobertura repetida para a mesma métrica")
        if not set(metrics) <= self.access_scope.allowed_metric_ids:
            raise ValueError("cobertura fora do escopo permitido")
        dimensions = [item.dimension_id for item in self.dimension_value_coverage]
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("cobertura repetida para a mesma dimensão")
        if not set(dimensions) <= self.access_scope.allowed_dimension_ids:
            raise ValueError("valores de dimensão fora do escopo permitido")
        if any(
            item.dimension_id == "customer.consumer_unit"
            for item in self.dimension_value_coverage
        ):
            raise ValueError("valores identificadores de UC não entram no vocabulário")
        return self


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
    remaining_timeout_ms: int = Field(strict=True, gt=0, le=35000)
    plan: LogicalReadPlan
    plan_fingerprint: str = Field(pattern=_FINGERPRINT_PATTERN)
    lookup: EvidenceLookupResult
    expected_batch_ref: GoldBatchRef | None = None

    @model_validator(mode="after")
    def validate_fingerprint(self) -> Self:
        if self.plan.source_id.startswith("gold."):
            if self.expected_batch_ref is None:
                raise ValueError("síntese Gold exige publicação esperada")
        elif self.expected_batch_ref is not None:
            raise ValueError("publicação Gold exige plano Gold")
        if self.plan_fingerprint != self.plan.fingerprint():
            raise ValueError("fingerprint divergente do plano")
        return self
