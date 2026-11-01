"""Public contracts for the DEV-08 demonstration, independent of Gold columns."""
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.analytics import AnalyticsMetadata, AnalyticsPeriod, ContinuityItem, Pagination
from app.schemas.gold import GoldMetadata


class GoldFeederOption(BaseModel):
    id: str
    municipio: str | None


class GoldOperationOptions(BaseModel):
    competencias: list[str]
    municipios: list[str]
    alimentadores: list[GoldFeederOption]


class GoldOperationOptionsResponse(BaseModel):
    data: GoldOperationOptions
    metadata: GoldMetadata


class GoldOperationPoint(BaseModel):
    feeder_id: str
    municipality: str | None
    period: AnalyticsPeriod
    observed_period: AnalyticsPeriod | None
    observed_competencies: list[str] = Field(default_factory=list)
    missing_competencies: list[str] = Field(default_factory=list)
    duration_hours_sum: float | None
    interruption_count: int | None
    denominator_uc_count: int | None
    dec_hours_per_uc: float | None
    fec_interruptions_per_uc: float | None
    status: Literal["available", "empty", "partial", "unavailable"]
    dec_status: Literal["available", "empty", "partial", "unavailable"]
    fec_status: Literal["available", "empty", "partial", "unavailable"]
    limitations: list[str] = Field(default_factory=list)


class GoldContinuityDefinition(BaseModel):
    reference: str = "docs/dicionario_gold.md#2-indicadores_dec_fec"
    dec_formula: str = "Soma das durações observadas em horas / denominador cadastral atual, uma vez por alimentador quando constante na janela."
    fec_formula: str = "Soma das frequências originais de pares UC–ocorrência / denominador cadastral atual, uma vez por alimentador quando constante na janela."
    dec_unit: str = "h/UC"
    fec_unit: str = "interrupções/UC"
    event_grain: str = "A Gold contém agregado por alimentador e competência; ocorrências individuais não estão disponíveis."
    population: str = "Cadastro atual de UCs por alimentador; não é uma população histórica mensal."
    completeness: str = "Competências e linhas observadas não declaram fechamento nem completude da origem."


class GoldContinuityResponse(BaseModel):
    data: list[GoldOperationPoint]
    definition: GoldContinuityDefinition = Field(default_factory=GoldContinuityDefinition)
    metadata: GoldMetadata


class GoldOperationSeriesData(BaseModel):
    items: list[GoldOperationPoint]
    definition: GoldContinuityDefinition = Field(default_factory=GoldContinuityDefinition)


class GoldOperationSeriesResponse(BaseModel):
    data: GoldOperationSeriesData
    metadata: GoldMetadata


class GoldRankedFeeder(GoldOperationPoint):
    rank: int


class GoldOperationRankingData(BaseModel):
    items: list[GoldRankedFeeder]
    excluded: list[GoldOperationPoint]
    metric: Literal["dec", "fec"]
    order: str = "Decrescente pelo indicador observado; empate desfeito pelo ID do alimentador."
    definition: GoldContinuityDefinition = Field(default_factory=GoldContinuityDefinition)


class GoldOperationRankingResponse(BaseModel):
    data: GoldOperationRankingData
    metadata: GoldMetadata


class GoldOperationSummary(BaseModel):
    period: AnalyticsPeriod
    observed_period: AnalyticsPeriod | None
    duration_hours_sum: float | None
    interruption_count: int | None
    denominator_uc_count: int | None
    dec_hours_per_uc: float | None
    fec_interruptions_per_uc: float | None
    dec_denominator_uc_count: int | None
    fec_denominator_uc_count: int | None
    dec_included_feeder_ids: list[str]
    fec_included_feeder_ids: list[str]
    dec_excluded_feeder_ids: list[str]
    fec_excluded_feeder_ids: list[str]
    included_feeder_ids: list[str] | None
    excluded_feeder_ids: list[str] | None
    dec_status: Literal["available", "empty", "partial", "unavailable"]
    fec_status: Literal["available", "empty", "partial", "unavailable"]
    status: Literal["available", "empty", "partial", "unavailable"]
    limitations: list[str] = Field(default_factory=list)


class GoldOperationSummaryResponse(BaseModel):
    data: GoldOperationSummary
    definition: GoldContinuityDefinition = Field(default_factory=GoldContinuityDefinition)
    metadata: GoldMetadata


class GoldOperationDetailData(BaseModel):
    summary: GoldOperationPoint
    series: list[GoldOperationPoint]
    occurrences: None = None
    occurrences_status: Literal["unavailable"] = "unavailable"
    definition: GoldContinuityDefinition = Field(default_factory=GoldContinuityDefinition)


class GoldOperationDetailResponse(BaseModel):
    data: GoldOperationDetailData
    metadata: GoldMetadata


class GoldObservedOccurrence(BaseModel):
    event_id: str
    uc_id: str
    opened_at: str
    cause: str | None
    duration_hours: float | None


class GoldOccurrencePage(BaseModel):
    data: list[GoldObservedOccurrence]
    pagination: Pagination
    metadata: GoldMetadata


class ContinuityDefinition(BaseModel):
    reference: str = "docs/contracts/operations-dev08.md#definicao-demonstrativa"
    label: str = "Indicadores simplificados de demonstração; sem apuração regulatória oficial."
    dec_formula: str = "Soma das durações em horas dos registros UC-interrupção / denominador de UCs do alimentador."
    fec_formula: str = "Quantidade de registros UC-interrupção / denominador de UCs do alimentador."
    dec_unit: str = "h/UC"
    fec_unit: str = "interrupções/UC"
    event_grain: str = "Uma ocorrência registrada corresponde a uma UC afetada; não contar apenas UCs distintas."
    population: str = "UCs ativas do snapshot demonstrativo por alimentador; denominador configurado e constante na janela."
    rounding: str = "Três casas decimais, conforme o contrato DEV-01; não somar valores já arredondados."


class OperationSummaryDefinition(ContinuityDefinition):
    inclusion_rule: str = (
        "Incluir somente alimentadores com estado available em toda a janela solicitada "
        "e denominador inteiro positivo; excluir os demais e identificá-los na resposta."
    )


class OperationSummary(BaseModel):
    period: AnalyticsPeriod
    observed_period: AnalyticsPeriod | None
    dec_hours_per_uc: float | None
    fec_interruptions_per_uc: float | None
    duration_hours_sum: float | None
    interruption_count: int | None
    denominator_uc_count: int | None
    served_uc_count: int
    included_uc_count: int
    included_feeder_ids: list[str]
    excluded_feeder_ids: list[str]
    status: Literal["available", "partial", "unavailable", "empty"]
    limitations: list[str] = Field(default_factory=list)
    text_alternative: str


class OperationSummaryData(BaseModel):
    summary: OperationSummary
    definition: OperationSummaryDefinition


class OperationSummaryResponse(BaseModel):
    data: OperationSummaryData
    metadata: AnalyticsMetadata


class OperationPoint(ContinuityItem):
    period: AnalyticsPeriod
    observed_period: AnalyticsPeriod | None
    duration_hours_sum: float
    text_alternative: str


class OperationSeriesData(BaseModel):
    items: list[OperationPoint]
    definition: ContinuityDefinition = Field(default_factory=ContinuityDefinition)


class OperationSeriesResponse(BaseModel):
    data: OperationSeriesData
    metadata: AnalyticsMetadata


class RankedFeeder(OperationPoint):
    rank: int


class OperationRankingData(BaseModel):
    items: list[RankedFeeder]
    excluded: list[OperationPoint]
    metric: Literal["dec", "fec"]
    order: str = "Decrescente pelo indicador; empate desfeito pelo ID do alimentador."
    definition: ContinuityDefinition = Field(default_factory=ContinuityDefinition)


class OperationRankingResponse(BaseModel):
    data: OperationRankingData
    metadata: AnalyticsMetadata


class OperationOccurrence(BaseModel):
    event_id: str
    uc_id: str
    feeder_id: str
    competencia: str
    duration_hours: float


class OperationDetailData(BaseModel):
    summary: OperationPoint
    series: list[OperationPoint]
    occurrences: list[OperationOccurrence]
    definition: ContinuityDefinition = Field(default_factory=ContinuityDefinition)


class OperationDetailResponse(BaseModel):
    data: OperationDetailData
    pagination: Pagination
    metadata: AnalyticsMetadata
