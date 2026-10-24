from fastapi import APIRouter, Depends, Query

from app.api.v1.analytics_route import AnalyticsRoute
from app.repositories.panorama import PanoramaRepository, get_panorama_repository
from app.schemas.common import AnalyticalMetadata
from app.schemas.panorama import PanoramaResponse
from app.services.panorama import DEFAULT_PERIOD, build_panorama

router = APIRouter(route_class=AnalyticsRoute)


@router.get("", response_model=PanoramaResponse, summary="Indicadores do Panorama")
def get_panorama(
    competencia: str = Query(DEFAULT_PERIOD, description="Competência no formato YYYY-MM"),
    comparacao: str = Query("anterior", description="Comparação com o período anterior (anterior, ano_anterior, nenhuma)"),
    municipio: str = Query("todos", description="Município do recorte ou 'todos'"),
    classe: str = Query("todas", description="Classe de consumo do recorte ou 'todas'"),
    repository: PanoramaRepository = Depends(get_panorama_repository),
):
    """Indicadores do Panorama (WEB-01) com comparação de período e série mensal.

    Grandezas faturada, paga, consumida e faturada em energia são distintas; o período
    em aberto é sinalizado e a base zero da comparação não vira percentual.
    """
    data = build_panorama(repository, competencia, comparacao, municipio, classe)
    return PanoramaResponse(
        data=data,
        metadata=AnalyticalMetadata(
            periodo=data.filtros["periodo"],
            filtros_aplicados=data.filtros,
            unidade="BRL / kWh / UCs / Horas",
            lote_gold_versao=data.loteVersao,
            qualidade_cobertura="Demonstração sintética; não reconciliada com Gold",
        ),
    )
