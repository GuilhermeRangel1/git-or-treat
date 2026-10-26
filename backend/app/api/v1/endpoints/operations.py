from typing import Literal

from fastapi import APIRouter, Depends, Path, Query

from app.api.v1.analytics_route import StrictAnalyticsRoute
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository
from app.schemas.analytics import (
    AnalyticsErrorResponse,
    ContinuityData,
    ContinuityResponse,
)
from app.schemas.operations import (
    OperationDetailResponse,
    OperationRankingData,
    OperationRankingResponse,
    OperationSeriesData,
    OperationSeriesResponse,
)
from app.services.analytics import (
    AnalyticsAPIError,
    build_continuity,
    filters_model,
    metadata,
    validate_period,
)
from app.services.operations import (
    build_feeder_detail,
    operation_metadata,
    operation_points,
    operation_ranking,
    operation_series,
    validate_operation_window,
)

router = APIRouter(route_class=StrictAnalyticsRoute)


def operation_period(
    periodo: str | None = Query(None, max_length=7),
    competencia_inicio: str | None = Query(None, max_length=7),
    competencia_fim: str | None = Query(None, max_length=7),
) -> tuple[str, str]:
    if periodo is not None:
        if competencia_inicio is not None or competencia_fim is not None:
            raise AnalyticsAPIError(
                422,
                "invalid_query",
                "Use periodo ou o intervalo, sem combiná-los.",
                [{
                    "field": "periodo",
                    "message": "Parâmetro incompatível com competencia_inicio/competencia_fim.",
                }],
            )
        competencia_inicio = competencia_fim = periodo
    return validate_period(competencia_inicio, competencia_fim)


def exploration_period(
    period: tuple[str, str] = Depends(operation_period),
) -> tuple[str, str]:
    validate_operation_window(*period)
    return period


@router.get(
    "/continuity",
    response_model=ContinuityResponse,
    summary="DEC/FEC demonstrativos por alimentador e competência",
)
def get_continuity_metrics(
    period: tuple[str, str] = Depends(operation_period),
    alimentador: str | None = Query(None, max_length=100),
    repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> ContinuityResponse:
    start, end = period
    filters = filters_model(alimentador=alimentador)
    items, state = build_continuity(repository, start, end, filters)
    result_metadata = metadata(repository, state, start, end, filters)
    for item in items:
        for limitation in item.limitations:
            if limitation not in result_metadata.limitations:
                result_metadata.limitations.append(limitation)
    return ContinuityResponse(
        data=ContinuityData(items=items), metadata=result_metadata,
    )


@router.get(
    "/series",
    response_model=OperationSeriesResponse,
    summary="Evolução mensal e alternativa textual de DEC/FEC",
)
def get_operation_series(
    period: tuple[str, str] = Depends(exploration_period),
    alimentador: str | None = Query(None, max_length=100),
    repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> OperationSeriesResponse:
    start, end = period
    filters = filters_model(alimentador=alimentador)
    points, state = operation_points(repository, start, end, filters)
    series = operation_series(repository, start, end, filters)
    return OperationSeriesResponse(
        data=OperationSeriesData(items=series),
        metadata=operation_metadata(
            repository, state, start, end, filters, points + series,
        ),
    )


@router.get(
    "/ranking",
    response_model=OperationRankingResponse,
    summary="Piores alimentadores por DEC ou FEC demonstrativo",
)
def get_operation_ranking(
    period: tuple[str, str] = Depends(exploration_period),
    alimentador: str | None = Query(None, max_length=100),
    metric: Literal["dec", "fec"] = "dec",
    repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> OperationRankingResponse:
    start, end = period
    filters = filters_model(alimentador=alimentador)
    points, state = operation_points(repository, start, end, filters)
    ranked, excluded = operation_ranking(points, metric)
    return OperationRankingResponse(
        data=OperationRankingData(items=ranked, excluded=excluded, metric=metric),
        metadata=operation_metadata(repository, state, start, end, filters, points),
    )


@router.get(
    "/feeders/{feeder_id}",
    response_model=OperationDetailResponse,
    responses={404: {"model": AnalyticsErrorResponse}},
    summary="Detalhe do alimentador e ocorrências relacionadas",
)
def get_feeder_detail(
    feeder_id: str = Path(..., min_length=1, max_length=100),
    period: tuple[str, str] = Depends(exploration_period),
    page: int = Query(1, ge=1, le=1000000),
    page_size: int = Query(20, ge=1, le=100),
    repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> OperationDetailResponse:
    return build_feeder_detail(repository, feeder_id, *period, page, page_size)
