"""Contratos da prontidão Gold: fatos da publicação na entrada, códigos e estados na saída."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.analysis import LogicalIdentifier
from app.schemas.evidence import GoldBatchRef

READINESS_VERSION = "gold-readiness-v1"
ReadinessVersion = Literal["gold-readiness-v1", "gold-readiness-v2"]

ControlId = Annotated[str, StringConstraints(strict=True, pattern=r"^C[0-9]{2}$")]
Competencia = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
]


class GoldTable(StrEnum):
    """Inventário analítico; não inclui cadastro pessoal ou controle operacional."""

    DIAGNOSTICO_RECEITA = "diagnostico_receita"
    INDICADORES_DEC_FEC = "indicadores_dec_fec"
    FILA_INSPECAO = "fila_inspecao"
    VISAO_360_UC = "visao_360_uc"
    CONSUMO_RECEITA_BAIRRO = "consumo_receita_bairro"
    VARIACAO_CONSUMO_UC = "variacao_consumo_uc"
    CONSUMO_MENSAL_UC = "consumo_mensal_uc"
    FATURAS_UC = "faturas_uc"
    MEDIDOR_UC = "medidor_uc"
    ATENDIMENTOS_UC = "atendimentos_uc"
    OCORRENCIAS_UC = "ocorrencias_uc"
    GD_UC = "gd_uc"
    TRATATIVAS_UC = "tratativas_uc"
    COBERTURA_DOMINIOS = "cobertura_dominios"
    DECOMPOSICAO_RECEITA = "decomposicao_receita"


class LotState(StrEnum):
    """Estado interno da publicação; não é um status do chat público."""

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
    CONTROL_FAILED = "control_failed"
    CONTROL_PUBLICATION_MISMATCH = "control_publication_mismatch"
    COVERAGE_MISSING = "coverage_missing"
    COVERAGE_INCOMPLETE = "coverage_incomplete"
    COVERAGE_PUBLICATION_MISMATCH = "coverage_publication_mismatch"


class TableFacts(BaseModel):
    """O que o Backend observou de uma tabela no banco local; sem contagens nem valores."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    present: bool = Field(strict=True)
    has_rows: bool = Field(strict=True)
    batch_ref: GoldBatchRef | None = None
    periods: tuple[Competencia, ...] = Field(default=(), max_length=1200)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        for period in self.periods:
            date.fromisoformat(period + "-01")
        if len(set(self.periods)) != len(self.periods):
            raise ValueError("competência duplicada")
        if not self.present and (self.has_rows or self.batch_ref is not None):
            raise ValueError("tabela ausente não pode ter linhas nem lote")
        if not self.has_rows and self.periods:
            raise ValueError("tabela sem linhas não pode ter competências")
        return self


class ControlFacts(BaseModel):
    """Resultado aprovado para uma publicação; não é concedido por texto do navegador."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    batch_ref: GoldBatchRef
    status: Literal["passed", "failed", "pending", "unavailable"]
    approved: bool = Field(default=False, strict=True)


class CoverageFacts(BaseModel):
    """Recorte temporal validado no Backend; fechamento não é deduzido de linhas."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    batch_ref: GoldBatchRef
    requested_periods: tuple[Competencia, ...] = Field(min_length=1, max_length=1200)
    observed_periods: tuple[Competencia, ...] = Field(default=(), max_length=1200)
    closed_periods: tuple[Competencia, ...] = Field(default=(), max_length=1200)
    zero_confirmed_periods: tuple[Competencia, ...] = Field(default=(), max_length=1200)
    has_undated_records: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_periods(self) -> Self:
        for periods in (self.requested_periods, self.observed_periods,
                        self.closed_periods, self.zero_confirmed_periods):
            if len(set(periods)) != len(periods):
                raise ValueError("competência duplicada")
            for period in periods:
                date.fromisoformat(period + "-01")
        if not set(self.zero_confirmed_periods) <= set(self.closed_periods):
            raise ValueError("zero confirmado exige fechamento")
        if set(self.zero_confirmed_periods) & set(self.observed_periods):
            raise ValueError("zero confirmado contradiz registros observados")
        return self


class PublicationFacts(BaseModel):
    """Fatos da publicação Gold carregada, fornecidos pelo Backend em tempo de execução."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    readiness_version: ReadinessVersion = READINESS_VERSION
    batch_ref: GoldBatchRef | None = None
    expected_batch_ref: GoldBatchRef | None = None
    tables: dict[GoldTable, TableFacts] = Field(default_factory=dict, max_length=15)
    approved_controls: frozenset[ControlId] = frozenset()
    control_results: dict[ControlId, ControlFacts] = Field(default_factory=dict, max_length=100)
    coverage: dict[LogicalIdentifier, CoverageFacts] = Field(default_factory=dict, max_length=64)
    backend_reachable: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_version(self) -> Self:
        if self.readiness_version == "gold-readiness-v1":
            if self.control_results or self.coverage:
                raise ValueError("fatos v2 exigem versão de prontidão v2")
            refs = [self.batch_ref, self.expected_batch_ref,
                    *(table.batch_ref for table in self.tables.values())]
            if any(ref and ref.startswith("gold-csv-v2:") for ref in refs):
                raise ValueError("publicação v2 exige prontidão v2")
        elif self.approved_controls:
            raise ValueError("v2 exige resultados de controle vinculados ao lote")
        return self


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
