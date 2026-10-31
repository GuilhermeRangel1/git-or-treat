"""Envelopes internos v1 do Backend; independentes da implantação GenAI."""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.ai import AICorrelationId, AIQuestionRequest, AIQuestionResponse
from app.schemas.genai_evidence import EvidenceLookupResult, GoldBatchRef
from app.schemas.genai_plan import (
    ContractVersion,
    LogicalIdentifier,
    LogicalReadPlan,
    PlanFingerprint,
    QuestionPlanStatus,
)


class AccessScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    caller_ref: LogicalIdentifier
    profile_id: LogicalIdentifier
    source_id: LogicalIdentifier
    allowed_operations: frozenset[Literal["read"]] = Field(default_factory=frozenset)
    allowed_metric_ids: frozenset[LogicalIdentifier] = Field(default_factory=frozenset)
    allowed_dimension_ids: frozenset[LogicalIdentifier] = Field(default_factory=frozenset)


class TemporalCoverage(BaseModel):
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


class QuestionPlanRequest(AIQuestionRequest):
    access_scope: AccessScope
    remaining_timeout_ms: int = Field(strict=True, gt=0, le=35000)
    batch_ref: GoldBatchRef | None = None
    temporal_coverage: tuple[TemporalCoverage, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def validate_publication(self) -> Self:
        if self.access_scope.source_id.startswith("gold."):
            if self.batch_ref is None or (
                self.access_scope.allowed_metric_ids and not self.temporal_coverage
            ):
                raise ValueError("planejamento Gold exige publicação e cobertura explícitas")
        elif self.batch_ref is not None or self.temporal_coverage:
            raise ValueError("metadados Gold exigem fonte Gold")
        metrics = [item.metric_id for item in self.temporal_coverage]
        if len(set(metrics)) != len(metrics):
            raise ValueError("cobertura repetida para a mesma métrica")
        if not set(metrics) <= self.access_scope.allowed_metric_ids:
            raise ValueError("cobertura fora do escopo permitido")
        return self


class QuestionPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: ContractVersion = "v1"
    correlation_id: AICorrelationId
    status: QuestionPlanStatus
    plan: LogicalReadPlan | None = None
    plan_fingerprint: PlanFingerprint | None = None
    response: AIQuestionResponse | None = None

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
        if self.response.status != self.status.value:
            raise ValueError("estado público diverge do planejamento")
        if self.response.correlation_id != self.correlation_id:
            raise ValueError("correlação pública diverge do planejamento")
        return self


class QuestionSynthesisRequest(AIQuestionRequest):
    access_scope: AccessScope
    remaining_timeout_ms: int = Field(strict=True, gt=0, le=35000)
    plan: LogicalReadPlan
    plan_fingerprint: PlanFingerprint
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
