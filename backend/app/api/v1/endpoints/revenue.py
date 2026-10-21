from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.analytics_route import AnalyticsRoute
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository
from app.schemas.analytics import RevenueResponse
from app.services.analytics import AnalyticsAPIError, filters_model, metadata, validate_period
from app.services.revenue_analytics import build_revenue

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
    repeated = sorted(name for name in request.query_params.keys() if len(request.query_params.getlist(name)) > 1)
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
    metric_coverage = [data["coverage"][name]["status"] for name in (
        "billed_amount", "billed_energy_kwh", "paid_amount", "measured_energy_kwh"
    )]
    if data["comparison"]["initial"]["status"] == "empty":
        state = "empty"
    elif any(status in {"partial", "unavailable"} for status in metric_coverage):
        state = "partial"
    elif start != end and data["price_volume"]["status"] == "unavailable":
        state = "partial"
    else:
        state = "available"
    result_metadata = metadata(repository, state, start, end, filters)
    result_metadata = result_metadata.model_copy(update={"contract_version": "1.1.0"})
    return {"data": data, "metadata": result_metadata}
