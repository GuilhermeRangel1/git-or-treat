from fastapi import APIRouter, Depends, Query

from app.api.v1.analytics_route import StrictAnalyticsRoute
from app.repositories.gold_context import GoldContext, get_optional_gold_context
from app.repositories.panorama import GoldPanoramaRepository, get_panorama_repository
from app.schemas.common import AnalyticalMetadata
from app.schemas.analytics import AnalyticsFilters, AnalyticsSource
from app.schemas.gold import GoldMetadata
from app.schemas.panorama import PanoramaResponse
from app.services.panorama import DEFAULT_PERIOD, build_gold_panorama, build_panorama

router = APIRouter(route_class=StrictAnalyticsRoute)


@router.get("", response_model=PanoramaResponse, summary="Indicadores do Panorama")
def get_panorama(
    competencia: str | None = Query(None, description="Competência no formato YYYY-MM; omissa, usa a mais recente da fonte"),
    comparacao: str = Query("anterior", description="Comparação com o período anterior (anterior, ano_anterior, nenhuma)"),
    municipio: str = Query("todos", description="Município do recorte ou 'todos'"),
    classe: str = Query("todas", description="Classe de consumo do recorte ou 'todas'"),
    gold_context: GoldContext | None = Depends(get_optional_gold_context),
):
    """Indicadores do Panorama (WEB-01) com comparação de período e série mensal.

    Grandezas faturada, paga, consumida e faturada em energia são distintas; o período
    em aberto é sinalizado e a base zero da comparação não vira percentual.
    """
    if gold_context is not None:
        repository = GoldPanoramaRepository(gold_context)
        data = build_gold_panorama(repository, competencia, comparacao, municipio, classe)
        result_metadata = GoldMetadata(
            status="partial" if data.totalRegistros else "empty",
            period={"start": data.filtros["periodo"], "end": data.filtros["periodo"]},
            filters=AnalyticsFilters(
                municipio=None if data.filtros["municipio"] == "todos" else data.filtros["municipio"],
                classe=None if data.filtros["classe"] == "todas" else data.filtros["classe"],
            ),
            source=AnalyticsSource(kind="gold", version=gold_context.lote, is_demo=False, updated_at=gold_context.imported_at.isoformat()),
            limitations=repository.source_limitations + ["Competências observadas não declaram fechamento mensal."],
            temporal_scope="monthly",
            schema_version=gold_context.schema_version,
            fingerprint=gold_context.fingerprint,
        )
    else:
        repository = get_panorama_repository()
        data = build_panorama(repository, competencia or DEFAULT_PERIOD, comparacao, municipio, classe)
        result_metadata = AnalyticalMetadata(
            periodo=data.filtros["periodo"],
            filtros_aplicados=data.filtros,
            unidade="BRL / kWh / UCs / Horas",
            lote_gold_versao=data.loteVersao,
            qualidade_cobertura="Demonstração sintética; não reconciliada com Gold",
        )
    return PanoramaResponse(
        data=data,
        metadata=result_metadata,
    )
