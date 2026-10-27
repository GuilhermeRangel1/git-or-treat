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
