from typing import Annotated, Callable, Literal

from fastapi import APIRouter, Depends, Path, Query, Request

from app.api.v1.analytics_route import StrictAnalyticsRoute
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository, get_analytics_repository_provider
from app.repositories.gold_context import GoldContext, get_optional_gold_context
from app.repositories.gold_operations import GoldOperationsRepository
from app.schemas.gold import GoldMetadata
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
    GoldContinuityResponse,
    GoldOperationSeriesResponse,
    GoldOperationSummaryResponse,
    GoldOperationRankingResponse,
    GoldOperationDetailResponse,
    GoldOperationRankingData,
    GoldRankedFeeder,
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
    gold_operation_points,
    gold_operation_series,
    build_gold_operation_summary,
    build_gold_feeder_detail,
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
    response_model=ContinuityResponse | GoldContinuityResponse,
    summary="DEC/FEC demonstrativos por alimentador e competência",
)
def get_continuity_metrics(
    period: Annotated[tuple[str, str], Depends(operation_period)],
    alimentador: Annotated[str | None, Query(max_length=100)] = None,
    municipio: Annotated[str | None, Query(max_length=100)] = None,
    gold_context: GoldContext | None = Depends(get_optional_gold_context),
    repository_provider: Callable[[], AnalyticsRepository] = Depends(get_analytics_repository_provider),
) -> ContinuityResponse | GoldContinuityResponse:
    start, end = period
    if gold_context is not None:
        validate_operation_window(start, end)
        gold_repository = GoldOperationsRepository(gold_context)
        points, meta = gold_operation_points(gold_repository, start, end, municipio, alimentador)
        return GoldContinuityResponse(data=points, metadata=meta)
    if municipio is not None:
        raise AnalyticsAPIError(422, "invalid_query", "Filtro não suportado.", [{"field": "municipio", "message": "Este filtro está disponível somente quando a fonte Gold está ativa."}])
    repository = repository_provider()
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
    response_model=OperationSeriesResponse | GoldOperationSeriesResponse,
    summary="Evolução mensal e alternativa textual de DEC/FEC",
)
def get_operation_series(
    period: Annotated[tuple[str, str], Depends(exploration_period)],
    alimentador: Annotated[str | None, Query(max_length=100)] = None,
    municipio: Annotated[str | None, Query(max_length=100)] = None,
    gold_context: GoldContext | None = Depends(get_optional_gold_context),
    repository_provider: Callable[[], AnalyticsRepository] = Depends(get_analytics_repository_provider),
) -> OperationSeriesResponse | GoldOperationSeriesResponse:
    start, end = period
    if gold_context is not None:
        return gold_operation_series(GoldOperationsRepository(gold_context), start, end, municipio, alimentador)
    if municipio is not None:
        raise AnalyticsAPIError(422, "invalid_query", "Filtro não suportado.", [{"field": "municipio", "message": "Este filtro está disponível somente quando a fonte Gold está ativa."}])
    repository = repository_provider()
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
    response_model=OperationSummaryResponse | GoldOperationSummaryResponse,
    summary="Consolidado demonstrativo de DEC/FEC por alimentadores elegíveis",
)
def get_operation_summary(
    period: Annotated[tuple[str, str], Depends(exploration_period)],
    alimentador: Annotated[str | None, Query(max_length=100)] = None,
    municipio: Annotated[str | None, Query(max_length=100)] = None,
    gold_context: GoldContext | None = Depends(get_optional_gold_context),
    repository_provider: Callable[[], AnalyticsRepository] = Depends(get_analytics_repository_provider),
) -> OperationSummaryResponse | GoldOperationSummaryResponse:
    start, end = period
    if gold_context is not None:
        return build_gold_operation_summary(GoldOperationsRepository(gold_context), start, end, municipio, alimentador)
    if municipio is not None:
        raise AnalyticsAPIError(422, "invalid_query", "Filtro não suportado.", [{"field": "municipio", "message": "Este filtro está disponível somente quando a fonte Gold está ativa."}])
    repository = repository_provider()
    filters = filters_model(alimentador=alimentador)
    return build_operation_summary(repository, start, end, filters)


@router.get(
    "/ranking",
    response_model=OperationRankingResponse | GoldOperationRankingResponse,
    summary="Piores alimentadores por DEC ou FEC demonstrativo",
)
def get_operation_ranking(
    period: Annotated[tuple[str, str], Depends(exploration_period)],
    alimentador: Annotated[str | None, Query(max_length=100)] = None,
    metric: Literal["dec", "fec"] = "dec",
    municipio: Annotated[str | None, Query(max_length=100)] = None,
    gold_context: GoldContext | None = Depends(get_optional_gold_context),
    repository_provider: Callable[[], AnalyticsRepository] = Depends(get_analytics_repository_provider),
) -> OperationRankingResponse | GoldOperationRankingResponse:
    start, end = period
    if gold_context is not None:
        gold_repository = GoldOperationsRepository(gold_context)
        points, meta = gold_operation_points(gold_repository, start, end, municipio, alimentador)
        value_field = "dec_hours_per_uc" if metric == "dec" else "fec_interruptions_per_uc"
        ranked_points = sorted(
            (point for point in points if getattr(point, value_field) is not None),
            key=lambda point: (-getattr(point, value_field), point.feeder_id),
        )
        items = [GoldRankedFeeder(**point.model_dump(), rank=index) for index, point in enumerate(ranked_points, 1)]
        excluded = [point for point in points if getattr(point, value_field) is None]
        meta.status = "partial" if ranked_points else ("empty" if not points else "unavailable")
        return GoldOperationRankingResponse(
            data=GoldOperationRankingData(items=items, excluded=excluded, metric=metric), metadata=meta,
        )
    if municipio is not None:
        raise AnalyticsAPIError(422, "invalid_query", "Filtro não suportado.", [{"field": "municipio", "message": "Este filtro está disponível somente quando a fonte Gold está ativa."}])
    repository = repository_provider()
    filters = filters_model(alimentador=alimentador)
    points, state = operation_points(repository, start, end, filters)
    ranked, excluded = operation_ranking(points, metric)
    return OperationRankingResponse(
        data=OperationRankingData(items=ranked, excluded=excluded, metric=metric),
        metadata=operation_metadata(repository, state, start, end, filters, points),
    )


@router.get(
    "/feeders/{feeder_id}",
    response_model=OperationDetailResponse | GoldOperationDetailResponse,
    responses={404: {"model": AnalyticsErrorResponse}},
    summary="Detalhe do alimentador e ocorrências relacionadas",
)
def get_feeder_detail(
    request: Request,
    feeder_id: Annotated[str, Path(min_length=1, max_length=100)],
    period: Annotated[tuple[str, str], Depends(exploration_period)],
    page: Annotated[int, Query(ge=1, le=1000000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    municipio: Annotated[str | None, Query(max_length=100)] = None,
    gold_context: GoldContext | None = Depends(get_optional_gold_context),
    repository_provider: Callable[[], AnalyticsRepository] = Depends(get_analytics_repository_provider),
) -> OperationDetailResponse | GoldOperationDetailResponse:
    if gold_context is not None:
        if "page" in request.query_params or "page_size" in request.query_params:
            raise AnalyticsAPIError(422, "unsupported_pagination", "Paginação de ocorrências indisponível na fonte Gold.", [{"field": "page", "message": "A Gold não exporta ocorrências individuais."}])
        return build_gold_feeder_detail(GoldOperationsRepository(gold_context), feeder_id, *period, municipio)
    if municipio is not None:
        raise AnalyticsAPIError(422, "invalid_query", "Filtro não suportado.", [{"field": "municipio", "message": "Este filtro está disponível somente quando a fonte Gold está ativa."}])
    repository = repository_provider()
    return build_feeder_detail(repository, feeder_id, *period, page, page_size)
