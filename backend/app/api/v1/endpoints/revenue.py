from fastapi import APIRouter, Depends, Query

from app.api.v1.analytics_route import AnalyticsRoute
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository
from app.schemas.analytics import RevenueResponse
from app.services.analytics import build_revenue, filters_model, metadata, validate_period

router = APIRouter(route_class=AnalyticsRoute)


@router.get("", response_model=RevenueResponse, summary="Série de receita e decomposição demonstrativa preço-volume")
def get_revenue_analysis(
    competencia_inicio: str | None = Query(None, max_length=7),
    competencia_fim: str | None = Query(None, max_length=7),
    municipio: str | None = Query(None, max_length=100),
    bairro: str | None = Query(None, max_length=100),
    classe: str | None = Query(None, max_length=100),
    alimentador: str | None = Query(None, max_length=100),
    repository: AnalyticsRepository = Depends(get_analytics_repository),
):
    start, end = validate_period(competencia_inicio, competencia_fim)
    filters = filters_model(municipio, bairro, classe, alimentador)
    data = build_revenue(repository, start, end, filters)
    state = "empty" if not data["series"] else ("partial" if data["price_volume"]["status"] == "unavailable" else data["price_volume"]["status"])
    result_metadata = metadata(repository, state, start, end, filters)
    for limitation in data["price_volume"]["limitations"]:
        if limitation not in result_metadata.limitations:
            result_metadata.limitations.append(limitation)
    return {"data": data, "metadata": result_metadata}
