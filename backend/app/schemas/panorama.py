from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import AnalyticalMetadata
from app.schemas.analytics import AnalyticsStatus
from app.schemas.gold import GoldMetadata
from app.schemas.visual_reading import VisualReading


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


class PanoramaDistributionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segmento: str
    valor: float | None
    percentual: float | None = None


class PanoramaDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reading: VisualReading | None = None
    dimension: Literal["municipio", "classe"]
    periodo: str
    metricId: str
    unidade: str
    total: float
    completo: bool
    pontos: list[PanoramaDistributionPoint] = Field(max_length=1000)
    visual: list[PanoramaDistributionPoint] = Field(max_length=10)
    agrupados: int = Field(default=0, ge=0, le=1000)


class PanoramaData(BaseModel):
    filtros: dict[str, Any]
    periodoIncompleto: bool
    fechamentoMensalDeclarado: bool = False
    totalRegistros: int
    dataAtualizacao: str
    loteVersao: str
    metricas: dict[str, PanoramaMetric]
    distribuicao: PanoramaDistribution | None = None
    serieMensal: list[PanoramaSeriesPoint] = Field(default_factory=list)
    opcoesFiltros: PanoramaFilterOptions | None = None


class PanoramaResponse(BaseModel):
    data: PanoramaData
    metadata: AnalyticalMetadata | GoldMetadata = Field(default_factory=AnalyticalMetadata)
