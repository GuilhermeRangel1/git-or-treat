from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.common import AnalyticalMetadata


class PanoramaMetric(BaseModel):
    """Indicador do Panorama com grandezas, unidade, definição e comparação."""

    id: str
    nome: str
    subtitulo: Optional[str] = None
    categoria: Literal["financeiro", "fisico", "operacional"]
    tipoGrandeza: Literal["faturado", "pago", "consumido", "operacao"]
    valorAtual: float
    valorAnterior: Optional[float] = None
    variacaoAbsoluta: Optional[float] = None
    variacaoPercentual: Optional[float] = None
    unidade: str
    definicao: str
    formula: str
    baseZero: bool = False
    bomSentido: Literal["positivo", "negativo"] = "positivo"


class PanoramaSeriesPoint(BaseModel):
    competencia: str
    label: str
    receitaFaturada: float
    receitaPaga: float
    energiaConsumidaKwh: float
    energiaFaturadaKwh: float
    ucsAtivas: int
    decHoras: float
    fecVezes: float


class PanoramaData(BaseModel):
    filtros: dict[str, Any]
    periodoIncompleto: bool
    totalRegistros: int
    dataAtualizacao: str
    loteVersao: str
    metricas: dict[str, PanoramaMetric]
    serieMensal: list[PanoramaSeriesPoint] = Field(default_factory=list)


class PanoramaResponse(BaseModel):
    data: PanoramaData
    metadata: AnalyticalMetadata = Field(default_factory=AnalyticalMetadata)
