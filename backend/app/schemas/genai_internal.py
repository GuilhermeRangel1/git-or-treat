"""Envelopes internos v1 do Backend; independentes da implantação GenAI."""

import unicodedata
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_serializer,
    model_validator,
)

from app.schemas.ai import AICorrelationId, AIQuestionRequest, AIQuestionResponse
from app.schemas.genai_evidence import EvidenceLookupResult, GoldBatchRef
from app.schemas.genai_physical_catalog import PhysicalCatalogRef
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
    allowed_dimension_ids: frozenset[LogicalIdentifier] = Field(
        default_factory=frozenset
    )


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


def _normalize_dimension_value(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


class DimensionValueCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension_id: LogicalIdentifier
    values: tuple[
        Annotated[
            str,
            StringConstraints(
                strict=True, strip_whitespace=True, min_length=1, max_length=120
            ),
        ],
        ...,
    ] = Field(max_length=2000)

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        if len({_normalize_dimension_value(value) for value in self.values}) != len(
            self.values
        ):
            raise ValueError("valores de dimensão devem ser únicos")
        return self


class QuestionPlanRequest(AIQuestionRequest):
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
                raise ValueError(
                    "planejamento Gold exige publicação e cobertura explícitas"
                )
        elif (
            self.batch_ref is not None
            or self.temporal_coverage
            or self.dimension_value_coverage
        ):
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


class QuestionPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: ContractVersion = "v1"
    correlation_id: AICorrelationId
    status: QuestionPlanStatus
    plan: LogicalReadPlan | None = None
    plan_fingerprint: PlanFingerprint | None = None
    response: AIQuestionResponse | None = None
    # Catálogo físico sob o qual o plano foi produzido; opcional para compatibilidade.
    physical_catalog: PhysicalCatalogRef | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_physical_catalog(self, handler):
        # Ausência não é serializada: consumidores anteriores recusam campos extras.
        data = handler(self)
        if self.physical_catalog is None and isinstance(data, dict):
            data.pop("physical_catalog", None)
        return data

    @model_validator(mode="after")
    def validate_content_for_status(self) -> Self:
        if self.physical_catalog is not None and self.status is not QuestionPlanStatus.PLANNED:
            raise ValueError("catálogo físico só acompanha plano pronto")
        if self.status is QuestionPlanStatus.PLANNED:
            if (
                self.plan is None
                or self.plan_fingerprint is None
                or self.response is not None
            ):
                raise ValueError("plano pronto exige plano e fingerprint, sem resposta")
            if self.plan_fingerprint != self.plan.fingerprint():
                raise ValueError("fingerprint divergente do plano")
            return self
        if (
            self.plan is not None
            or self.plan_fingerprint is not None
            or self.response is None
        ):
            raise ValueError(
                "estado sem plano exige resposta, sem plano nem fingerprint"
            )
        if self.response.status != self.status.value:
            raise ValueError("estado público diverge do planejamento")
        if self.response.correlation_id != self.correlation_id:
            raise ValueError("correlação pública diverge do planejamento")
        return self


class QuestionSynthesisRequest(AIQuestionRequest):
    dimension_value_coverage: tuple[DimensionValueCoverage, ...] = Field(default=(), max_length=20)
    access_scope: AccessScope
    remaining_timeout_ms: int = Field(strict=True, gt=0, le=35000)
    plan: LogicalReadPlan
    plan_fingerprint: PlanFingerprint
    lookup: EvidenceLookupResult
    expected_batch_ref: GoldBatchRef | None = None

    @model_validator(mode="after")
    def validate_fingerprint(self) -> Self:
        ids = [item.dimension_id for item in self.dimension_value_coverage]
        if (len(ids) != len(set(ids))
            or not set(ids) <= self.access_scope.allowed_dimension_ids
            or "customer.consumer_unit" in ids):
            raise ValueError("vocabulário de síntese fora do escopo")
        if self.plan.source_id.startswith("gold."):
            if self.expected_batch_ref is None:
                raise ValueError("síntese Gold exige publicação esperada")
        elif self.expected_batch_ref is not None:
            raise ValueError("publicação Gold exige plano Gold")
        if self.plan_fingerprint != self.plan.fingerprint():
            raise ValueError("fingerprint divergente do plano")
        return self
