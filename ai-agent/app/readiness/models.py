"""Contratos da prontidão Gold: fatos da publicação na entrada, códigos e estados na saída."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.analysis import LogicalIdentifier

READINESS_VERSION = "gold-readiness-v1"
ReadinessVersion = Literal["gold-readiness-v1"]

# Mesmo formato do GoldBatchRef proposto para a proveniência da evidência; quando ele estiver
# em app.schemas.evidence, este alias passa a importá-lo.
GoldBatchRef = Annotated[
    str,
    StringConstraints(
        strict=True,
        max_length=100,
        pattern=(
            r"^gold-csv-v1:GOLD_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}:"
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
    ),
]
ControlId = Annotated[str, StringConstraints(strict=True, pattern=r"^C[0-9]{2}$")]
Competencia = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
]


class GoldTable(StrEnum):
    """As sete tabelas analíticas de docs/dicionario_gold.md."""

    DIAGNOSTICO_RECEITA = "diagnostico_receita"
    INDICADORES_DEC_FEC = "indicadores_dec_fec"
    FILA_INSPECAO = "fila_inspecao"
    VISAO_360_UC = "visao_360_uc"
    CONSUMO_RECEITA_BAIRRO = "consumo_receita_bairro"
    VARIACAO_CONSUMO_UC = "variacao_consumo_uc"
    CONSUMO_MENSAL_UC = "consumo_mensal_uc"


class LotState(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    MIXED = "mixed"
    STALE = "stale"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class CapabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ReasonCode(StrEnum):
    TABLE_MISSING = "table_missing"
    TABLE_EMPTY = "table_empty"
    PERIOD_MISSING = "period_missing"
    PERIOD_INSUFFICIENT = "period_insufficient"
    DEFINITION_PENDING = "definition_pending"
    CONTROL_PENDING = "control_pending"
    SOURCE_NOT_IN_GOLD = "source_not_in_gold"
    PUBLICATION_STALE = "publication_stale"
    PUBLICATION_MIXED = "publication_mixed"
    PUBLICATION_UNIDENTIFIED = "publication_unidentified"
    BACKEND_UNAVAILABLE = "backend_unavailable"


class TableFacts(BaseModel):
    """O que o Backend observou de uma tabela no banco local; sem contagens nem valores."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    present: bool
    has_rows: bool
    batch_ref: GoldBatchRef | None = None
    periods: tuple[Competencia, ...] = Field(default=(), max_length=1200)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if len(set(self.periods)) != len(self.periods):
            raise ValueError("competência duplicada")
        if not self.present and (self.has_rows or self.batch_ref is not None):
            raise ValueError("tabela ausente não pode ter linhas nem lote")
        if not self.has_rows and self.periods:
            raise ValueError("tabela sem linhas não pode ter competências")
        return self


class PublicationFacts(BaseModel):
    """Fatos da publicação Gold carregada, fornecidos pelo Backend em tempo de execução."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    readiness_version: ReadinessVersion = READINESS_VERSION
    batch_ref: GoldBatchRef | None = None
    expected_batch_ref: GoldBatchRef | None = None
    tables: dict[GoldTable, TableFacts] = Field(default_factory=dict)
    approved_controls: frozenset[ControlId] = frozenset()
    backend_reachable: bool


class CapabilityReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: CapabilityStatus
    reasons: tuple[ReasonCode, ...] = ()

    @model_validator(mode="after")
    def validate_reasons(self) -> Self:
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("motivo duplicado")
        if (self.status is CapabilityStatus.AVAILABLE) != (not self.reasons):
            raise ValueError("capacidade disponível não tem motivo; indisponível exige motivo")
        return self


class ReadinessReport(BaseModel):
    """Estado do lote e de cada capacidade; só códigos, nunca contagens, valores ou períodos."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    readiness_version: ReadinessVersion = READINESS_VERSION
    lot_state: LotState
    batch_ref: GoldBatchRef | None
    capabilities: dict[LogicalIdentifier, CapabilityReadiness]
