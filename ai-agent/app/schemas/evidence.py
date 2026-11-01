"""Contratos de evidência compartilhados pelo núcleo e pelos adaptadores."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    model_serializer,
    model_validator,
)

from app.schemas.analysis import LogicalIdentifier
from app.schemas.physical_catalog import PhysicalCatalogRef
from app.schemas.read_plan import ReadFilter, ReadWindow
from app.schemas.version import INTERNAL_CONTRACT_VERSION, InternalContractVersion

EvidenceSourceId = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$",
        max_length=120,
    ),
]

GoldBatchRef = Annotated[
    str,
    StringConstraints(
        strict=True,
        max_length=100,
        pattern=(
            r"^gold-csv-v[12]:GOLD_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}:"
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
    ),
]


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


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: EvidenceSourceId
    description: str = Field(min_length=1, max_length=500)
    is_demo: bool = False


class PublishedWindows(BaseModel):
    """Janelas da decomposição materializada na mesma publicação Gold v2."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    p0_start: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    p0_end: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    p1_start: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    p1_end: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    method: Literal["PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3"]

    @model_validator(mode="after")
    def validate_windows(self):
        values = [date.fromisoformat(value + "-01") for value in (
            self.p0_start, self.p0_end, self.p1_start, self.p1_end,
        )]
        first, end_first, last, end_last = values
        if (end_first >= last or any(
            (end.year - start.year) * 12 + end.month - start.month != 11
            for start, end in ((first, end_first), (last, end_last))
        ) or first.month != last.month):
            raise ValueError("decomposição exige duas janelas anuais equivalentes sem sobreposição")
        return self

    def describe(self) -> str:
        return f"P0 {self.p0_start} a {self.p0_end}; P1 {self.p1_start} a {self.p1_end}"


class EvidenceProvenance(BaseModel):
    """Recorte aplicado pela fonte, conferido contra o plano antes da geração."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: LogicalIdentifier
    reference_source: EvidenceSourceId
    plan_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    catalog_version: InternalContractVersion
    metric_id: LogicalIdentifier
    unit: str = Field(min_length=1, max_length=200)
    window: ReadWindow
    filters: tuple[ReadFilter, ...] = Field(default=(), max_length=20)
    dimension_ids: tuple[LogicalIdentifier, ...] = Field(default=(), max_length=10)
    batch_ref: GoldBatchRef | None = None
    quality: GoldEvidenceQuality | None = None
    published_windows: PublishedWindows | None = None
    physical_catalog: PhysicalCatalogRef | None = None

    @model_serializer(mode="wrap")
    def omit_absent_metadata(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        payload = handler(self)
        if self.published_windows is None:
            payload.pop("published_windows", None)
        if self.physical_catalog is None:
            payload.pop("physical_catalog", None)
        return payload


class EvidenceResult(BaseModel):
    """Registros agregados com proveniência controlada para fundamentar uma resposta."""

    model_config = ConfigDict(extra="forbid")

    contract_version: InternalContractVersion = INTERNAL_CONTRACT_VERSION
    reference: EvidenceReference
    records: list[dict[str, object]] = Field(default_factory=list, max_length=100)
    provenance: EvidenceProvenance | None = None
    # Preenchido somente pelo orquestrador após autorização; nunca enviado ao provedor.
    cache_scope: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$", exclude=True, repr=False
    )


class EvidenceLookupStatus(StrEnum):
    AVAILABLE = "available"
    NO_EVIDENCE = "no_evidence"
    NEEDS_CLARIFICATION = "needs_clarification"


class EvidenceLookupResult(BaseModel):
    """Estados de consulta sem confundir resultado vazio com falha da fonte."""

    model_config = ConfigDict(extra="forbid")

    contract_version: InternalContractVersion = INTERNAL_CONTRACT_VERSION
    status: EvidenceLookupStatus
    evidence: EvidenceResult | None = None
    message: str | None = Field(default=None, min_length=1, max_length=1000)
    limitations: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_status_fields(self) -> Self:
        if self.status is EvidenceLookupStatus.AVAILABLE:
            if self.evidence is None or not self.evidence.records:
                raise ValueError("resultado disponível exige evidência com registros")
            if self.message is not None:
                raise ValueError("resultado disponível não deve conter mensagem de falha")
        elif self.evidence is not None or self.message is None:
            raise ValueError("ausência ou esclarecimento exige mensagem e não pode conter dados")
        return self
