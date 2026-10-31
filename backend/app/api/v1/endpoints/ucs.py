from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.v1.analytics_route import AnalyticsRoute
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository
from app.schemas.analytics import (
    AnalyticsErrorResponse,
    AnalyticsFilters,
    AnalyticsListResponse,
    UCDetailResponse,
    UCListItem,
)
from app.schemas.uc360 import UCHistoryResponse, UCOverviewResponse
from app.services.analytics import DEFAULT_END, DEFAULT_START, metadata
from app.services.uc_analytics import (
    build_uc_detail,
    build_uc_history,
    build_uc_overview,
    build_uc_search,
)

router = APIRouter(route_class=AnalyticsRoute)
AnalyticsRepositoryDep = Annotated[
    AnalyticsRepository, Depends(get_analytics_repository)
]


def _uc_metadata(
    repository, status, start: str, end: str, limitations: list[str] | None = None
):
    result = metadata(repository, status, start, end, AnalyticsFilters())
    result.contract_version = "1.1.0"
    if limitations:
        result.limitations.extend(limitations)
    return result


def _source_period(repository):
    from app.repositories.gold import GoldAnalyticsRepository
    if isinstance(repository, GoldAnalyticsRepository):
        months = repository.options()["competencias"]
        if not months:
            from app.services.analytics import AnalyticsAPIError
            raise AnalyticsAPIError(503, "source_unavailable", "Gold sem competências observadas.")
        return months[0], months[-1]
    return DEFAULT_START, DEFAULT_END


@router.get(
    "",
    response_model=AnalyticsListResponse[UCListItem],
    summary="Buscar Unidades Consumidoras por identificador",
)
def search_ucs(
    repository: AnalyticsRepositoryDep,
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_by: str = Query("uc_id", max_length=32),
):
    selected, pagination, state = build_uc_search(
        repository, q, page, page_size, order_by
    )
    return {
        "data": {"items": selected},
        "pagination": pagination,
        "metadata": metadata(
            repository, state, *_source_period(repository), AnalyticsFilters()
        ),
    }


@router.get(
    "/{uc_id}/overview",
    response_model=UCOverviewResponse,
    summary="Resumo e comparação da UC",
)
def get_uc_overview(
    uc_id: str,
    repository: AnalyticsRepositoryDep,
    start: str | None = Query(None, min_length=7, max_length=7),
    end: str | None = Query(None, min_length=7, max_length=7),
):
    result = build_uc_overview(repository, uc_id, start, end)
    period = result["data"]["period"]
    return {
        **result,
        "metadata": _uc_metadata(
            repository,
            result["status"],
            period["start"],
            period["end"],
            result["limitations"],
        ),
    }


@router.get(
    "/{uc_id}/history/{section}",
    response_model=UCHistoryResponse,
    summary="Histórico paginado da UC",
)
def get_uc_history(
    uc_id: str,
    section: Literal[
        "consumption",
        "invoices",
        "meters",
        "distributed_generation",
        "interruptions",
        "calls",
    ],
    repository: AnalyticsRepositoryDep,
    start: str | None = Query(None, min_length=7, max_length=7),
    end: str | None = Query(None, min_length=7, max_length=7),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_by: str | None = Query(None, max_length=32),
):
    result = build_uc_history(
        repository, uc_id, section, start, end, page, page_size, order_by
    )
    period = result["period"]
    return {
        **result,
        "metadata": _uc_metadata(
            repository,
            result["status"],
            period["start"],
            period["end"],
            result["limitations"],
        ),
    }


@router.get(
    "/{uc_id}",
    response_model=UCDetailResponse,
    responses={404: {"model": AnalyticsErrorResponse}},
    summary="Visão 360 da Unidade Consumidora sintética",
)
def get_uc_360(uc_id: str, repository: AnalyticsRepositoryDep):
    data, state, limitations = build_uc_detail(repository, uc_id)
    filters = AnalyticsFilters()
    result_metadata = metadata(repository, state, *_source_period(repository), filters)
    result_metadata.limitations.extend(limitations)
    return {"data": data, "metadata": result_metadata}
