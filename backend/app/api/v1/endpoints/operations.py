from typing import Annotated, Literal

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
    OperationSummaryResponse,
)
from app.services.analytics import (
    AnalyticsAPIError,
    build_continuity,
    filters_model,
    metadata,
    validate_period,
)
from app.services.operations import (
    build_operation_summary,
    build_feeder_detail,
    operation_metadata,
    operation_points,
    operation_ranking,
    operation_series,
    validate_operation_window,
)

router = APIRouter(route_class=StrictAnalyticsRoute)


def operation_period(
    periodo: Annotated[str | None, Query(max_length=7)] = None,
    competencia_inicio: Annotated[str | None, Query(max_length=7)] = None,
    competencia_fim: Annotated[str | None, Query(max_length=7)] = None,
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
    period: Annotated[tuple[str, str], Depends(operation_period)],
) -> tuple[str, str]:
    validate_operation_window(*period)
    return period


@router.get(
    "/continuity",
    response_model=ContinuityResponse,
    summary="DEC/FEC demonstrativos por alimentador e competência",
)
def get_continuity_metrics(
    period: Annotated[tuple[str, str], Depends(operation_period)],
    repository: Annotated[AnalyticsRepository, Depends(get_analytics_repository)],
    alimentador: Annotated[str | None, Query(max_length=100)] = None,
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
    period: Annotated[tuple[str, str], Depends(exploration_period)],
    repository: Annotated[AnalyticsRepository, Depends(get_analytics_repository)],
    alimentador: Annotated[str | None, Query(max_length=100)] = None,
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
    "/summary",
    response_model=OperationSummaryResponse,
    summary="Consolidado demonstrativo de DEC/FEC por alimentadores elegíveis",
)
def get_operation_summary(
    period: Annotated[tuple[str, str], Depends(exploration_period)],
    repository: Annotated[AnalyticsRepository, Depends(get_analytics_repository)],
    alimentador: Annotated[str | None, Query(max_length=100)] = None,
) -> OperationSummaryResponse:
    start, end = period
    filters = filters_model(alimentador=alimentador)
    return build_operation_summary(repository, start, end, filters)


@router.get(
    "/ranking",
    response_model=OperationRankingResponse,
    summary="Piores alimentadores por DEC ou FEC demonstrativo",
)
def get_operation_ranking(
    period: Annotated[tuple[str, str], Depends(exploration_period)],
    repository: Annotated[AnalyticsRepository, Depends(get_analytics_repository)],
    alimentador: Annotated[str | None, Query(max_length=100)] = None,
    metric: Literal["dec", "fec"] = "dec",
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
    feeder_id: Annotated[str, Path(min_length=1, max_length=100)],
    period: Annotated[tuple[str, str], Depends(exploration_period)],
    repository: Annotated[AnalyticsRepository, Depends(get_analytics_repository)],
    page: Annotated[int, Query(ge=1, le=1000000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OperationDetailResponse:
    return build_feeder_detail(repository, feeder_id, *period, page, page_size)
