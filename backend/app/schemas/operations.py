"""Public contracts for the DEV-08 demonstration, independent of Gold columns."""
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.analytics import AnalyticsMetadata, AnalyticsPeriod, ContinuityItem, Pagination


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
