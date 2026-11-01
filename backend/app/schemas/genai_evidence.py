"""Contrato interno de lookup v1; estados vazios não representam falha de execução."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    model_serializer,
    model_validator,
)

from app.schemas.ai import AIEvidenceReference
from app.schemas.genai_physical_catalog import PhysicalCatalogRef
from app.schemas.genai_plan import (
    ContractVersion,
    LogicalIdentifier,
    ReadFilter,
    ReadWindow,
)
from app.schemas.gold_publication import PublicationReference


def _validate_batch_ref(value: str) -> str:
    PublicationReference.parse(value)
    return value


GoldBatchRef = Annotated[StrictStr, AfterValidator(_validate_batch_ref)]


class GoldEvidenceQuality(BaseModel):
    """Resumo da prontidão aprovada para a capacidade usada nesta evidência."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    readiness_version: Literal["gold-readiness-v2"]
    batch_ref: GoldBatchRef
    lot_state: Literal["ready", "partial"]
    available_capability_ids: tuple[LogicalIdentifier, ...] = Field(
        min_length=1, max_length=64
    )

    @model_validator(mode="after")
    def require_unique_capabilities(self) -> Self:
        if len(self.available_capability_ids) != len(set(self.available_capability_ids)):
            raise ValueError("capacidade repetida na qualidade da evidência")
        return self


class EvidenceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: LogicalIdentifier
    reference_source: LogicalIdentifier
    plan_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    catalog_version: ContractVersion
    metric_id: LogicalIdentifier
    unit: str = Field(min_length=1, max_length=200)
    window: ReadWindow
    filters: tuple[ReadFilter, ...] = Field(default=(), max_length=20)
    dimension_ids: tuple[LogicalIdentifier, ...] = Field(default=(), max_length=10)
    batch_ref: GoldBatchRef | None = None
    quality: GoldEvidenceQuality | None = None
    # Catálogo físico usado pelo executor; opcional para compatibilidade.
    physical_catalog: PhysicalCatalogRef | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_physical_catalog(self, handler):
        # Ausência não é serializada: consumidores anteriores recusam campos extras.
        data = handler(self)
        if self.physical_catalog is None and isinstance(data, dict):
            data.pop("physical_catalog", None)
        return data


class EvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: ContractVersion = "v1"
    reference: AIEvidenceReference
    records: list[dict[str, object]] = Field(default_factory=list, max_length=100)
    provenance: EvidenceProvenance | None = None
    cache_scope: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$", exclude=True, repr=False
    )


class EvidenceLookupStatus(StrEnum):
    AVAILABLE = "available"
    NO_EVIDENCE = "no_evidence"
    NEEDS_CLARIFICATION = "needs_clarification"


class EvidenceLookupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: ContractVersion = "v1"
    status: EvidenceLookupStatus
    evidence: EvidenceResult | None = None
    message: str | None = Field(default=None, min_length=1, max_length=1000)
    limitations: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_status_fields(self) -> Self:
        if self.status is EvidenceLookupStatus.AVAILABLE:
            if self.evidence is None or not self.evidence.records or self.message is not None:
                raise ValueError("resultado disponível exige registros e não admite mensagem")
        elif self.evidence is not None or self.message is None:
            raise ValueError("ausência ou esclarecimento exige mensagem e não admite dados")
        return self
