from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.analytics_route import AnalyticsRoute, repeated_query_parameters
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository
from app.schemas.analytics import RevenueResponse
from app.services.analytics import AnalyticsAPIError, filters_model, metadata, validate_period
from app.services.revenue_analytics import build_revenue, revenue_metadata_status

router = APIRouter(route_class=AnalyticsRoute)


@router.get("", response_model=RevenueResponse, summary="Série de receita e decomposição demonstrativa preço-volume")
def get_revenue_analysis(
    request: Request,
    competencia_inicio: str | None = Query(None, max_length=7),
    competencia_fim: str | None = Query(None, max_length=7),
    municipio: str | None = Query(None, max_length=100),
    bairro: str | None = Query(None, max_length=100),
    classe: str | None = Query(None, max_length=100),
    alimentador: str | None = Query(None, max_length=100),
    group_by: Literal["municipio", "bairro", "classe"] = Query("municipio"),
    repository: AnalyticsRepository = Depends(get_analytics_repository),
):
    repeated = repeated_query_parameters(request.query_params)
    if repeated:
        raise AnalyticsAPIError(
            422,
            "invalid_query",
            "Parâmetros escalares repetidos.",
            [{"field": name, "message": "Informe cada parâmetro escalar uma única vez."} for name in repeated],
        )
    start, end = validate_period(competencia_inicio, competencia_fim)
    filters = filters_model(municipio, bairro, classe, alimentador)
    data = build_revenue(repository, start, end, filters, group_by=group_by)
    state = revenue_metadata_status(data, start, end)
    result_metadata = metadata(repository, state, start, end, filters)
    result_metadata = result_metadata.model_copy(update={"contract_version": "1.1.0"})
    return {"data": data, "metadata": result_metadata}
