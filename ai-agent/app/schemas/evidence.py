"""Contratos de evidência compartilhados pelo núcleo e pelos adaptadores."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.version import INTERNAL_CONTRACT_VERSION, InternalContractVersion

EvidenceSourceId = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$",
        max_length=120,
    ),
]


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: EvidenceSourceId
    description: str = Field(min_length=1, max_length=500)
    is_demo: bool = False


class EvidenceResult(BaseModel):
    """Registros agregados com proveniência controlada para fundamentar uma resposta."""

    model_config = ConfigDict(extra="forbid")

    contract_version: InternalContractVersion = INTERNAL_CONTRACT_VERSION
    reference: EvidenceReference
    records: list[dict[str, object]] = Field(default_factory=list, max_length=100)


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
