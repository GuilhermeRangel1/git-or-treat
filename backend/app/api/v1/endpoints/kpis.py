from fastapi import APIRouter, Depends, Query

from app.api.v1.analytics_route import AnalyticsRoute
from app.core.platform_identity import require_permission
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository
from app.schemas.analytics import KPIResponse
from app.services.analytics import AnalyticsAPIError, build_kpis, filters_model, metadata, validate_period

router = APIRouter(route_class=AnalyticsRoute, dependencies=[Depends(require_permission("panorama:read"))])


@router.get("", response_model=KPIResponse, summary="Listar indicadores agregados")
def get_kpis(
    competencia: str | None = Query(None, max_length=7),
    competencia_inicio: str | None = Query(None, max_length=7),
    competencia_fim: str | None = Query(None, max_length=7),
    municipio: str | None = Query(None, max_length=100),
    bairro: str | None = Query(None, max_length=100),
    classe: str | None = Query(None, max_length=100),
    alimentador: str | None = Query(None, max_length=100),
    repository: AnalyticsRepository = Depends(get_analytics_repository),
):
    if competencia is not None:
        if competencia_inicio is not None or competencia_fim is not None:
            raise AnalyticsAPIError(422, "invalid_query", "Use a competência única ou o intervalo, sem combiná-los.", [{"field": "competencia", "message": "Parâmetro incompatível com competencia_inicio/competencia_fim."}])
        competencia_inicio = competencia_fim = competencia
    start, end = validate_period(competencia_inicio, competencia_fim)
    filters = filters_model(municipio, bairro, classe, alimentador)
    metrics, state = build_kpis(repository, start, end, filters)
    result_metadata = metadata(repository, state, start, end, filters)
    for item in metrics:
        for limitation in item.limitations:
            if limitation not in result_metadata.limitations:
                result_metadata.limitations.append(limitation)
    return {"data": {"metrics": metrics}, "metadata": result_metadata}
