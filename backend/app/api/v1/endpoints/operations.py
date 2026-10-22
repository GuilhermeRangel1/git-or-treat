from fastapi import APIRouter, Depends, Query

from app.api.v1.analytics_route import AnalyticsRoute
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository
from app.schemas.analytics import ContinuityResponse
from app.services.analytics import AnalyticsAPIError, build_continuity, filters_model, metadata, validate_period

router = APIRouter(route_class=AnalyticsRoute)


@router.get("/continuity", response_model=ContinuityResponse, summary="DEC/FEC demonstrativos por alimentador e competência")
def get_continuity_metrics(
    periodo: str | None = Query(None, max_length=7),
    competencia_inicio: str | None = Query(None, max_length=7),
    competencia_fim: str | None = Query(None, max_length=7),
    alimentador: str | None = Query(None, max_length=100),
    repository: AnalyticsRepository = Depends(get_analytics_repository),
):
    if periodo is not None:
        if competencia_inicio is not None or competencia_fim is not None:
            raise AnalyticsAPIError(422, "invalid_query", "Use periodo ou o intervalo, sem combiná-los.", [{"field": "periodo", "message": "Parâmetro incompatível com competencia_inicio/competencia_fim."}])
        competencia_inicio = competencia_fim = periodo
    start, end = validate_period(competencia_inicio, competencia_fim)
    filters = filters_model(alimentador=alimentador)
    items, state = build_continuity(repository, start, end, filters)
    result_metadata = metadata(repository, state, start, end, filters)
    for item in items:
        for limitation in item.limitations:
            if limitation not in result_metadata.limitations:
                result_metadata.limitations.append(limitation)
    return {"data": {"items": items}, "metadata": result_metadata}
