from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.common import AnalyticalMetadata
from app.schemas.analytics import AnalyticsStatus
from app.schemas.gold import GoldMetadata


class PanoramaMetric(BaseModel):
    """Indicador do Panorama com grandezas, unidade, definição e comparação."""

    id: str
    nome: str
    subtitulo: Optional[str] = None
    categoria: Literal["financeiro", "fisico", "operacional"]
    tipoGrandeza: Literal["faturado", "pago", "consumido", "operacao"]
    valorAtual: float | None
    valorAnterior: Optional[float] = None
    variacaoAbsoluta: Optional[float] = None
    variacaoPercentual: Optional[float] = None
    unidade: str
    definicao: str
    formula: str
    baseZero: bool = False
    bomSentido: Literal["positivo", "negativo"] = "positivo"
    status: AnalyticsStatus = "available"
    limitacoes: list[str] = Field(default_factory=list)
    statusComparacao: AnalyticsStatus = "available"
    limitacoesComparacao: list[str] = Field(default_factory=list)


class PanoramaSeriesPoint(BaseModel):
    competencia: str
    label: str
    receitaFaturada: float | None
    receitaPaga: float | None
    energiaConsumidaKwh: float | None
    energiaFaturadaKwh: float | None
    ucsAtivas: int | None
    decHoras: float | None
    fecVezes: float | None
    status: AnalyticsStatus = "available"


class PanoramaFilterOptions(BaseModel):
    competencias: list[str] = Field(default_factory=list)
    municipios: list[str] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)


class PanoramaData(BaseModel):
    filtros: dict[str, Any]
    periodoIncompleto: bool
    fechamentoMensalDeclarado: bool = False
    totalRegistros: int
    dataAtualizacao: str
    loteVersao: str
    metricas: dict[str, PanoramaMetric]
    serieMensal: list[PanoramaSeriesPoint] = Field(default_factory=list)
    opcoesFiltros: PanoramaFilterOptions | None = None


class PanoramaResponse(BaseModel):
    data: PanoramaData
    metadata: AnalyticalMetadata | GoldMetadata = Field(default_factory=AnalyticalMetadata)
