from fastapi import APIRouter, Depends, Query

from app.api.v1.analytics_route import AnalyticsRoute
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository
from app.schemas.analytics import (
    AnalyticsFilters,
    AnalyticsErrorResponse,
    AnalyticsListResponse,
    UCDetailResponse,
    UCListItem,
)
from app.services.analytics import DEFAULT_END, DEFAULT_START, metadata
from app.services.uc_analytics import build_uc_detail, build_uc_search

router = APIRouter(route_class=AnalyticsRoute)


@router.get("", response_model=AnalyticsListResponse[UCListItem], summary="Buscar Unidades Consumidoras por identificador")
def search_ucs(
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_by: str = Query("uc_id", max_length=32),
    repository: AnalyticsRepository = Depends(get_analytics_repository),
):
    selected, pagination, state = build_uc_search(repository, q, page, page_size, order_by)
    return {
        "data": {"items": selected},
        "pagination": pagination,
        "metadata": metadata(repository, state, DEFAULT_START, DEFAULT_END, AnalyticsFilters()),
    }


@router.get("/{uc_id}", response_model=UCDetailResponse, responses={404: {"model": AnalyticsErrorResponse}}, summary="Visão 360 da Unidade Consumidora sintética")
def get_uc_360(uc_id: str, repository: AnalyticsRepository = Depends(get_analytics_repository)):
    data, state, limitations = build_uc_detail(repository, uc_id)
    filters = AnalyticsFilters()
    result_metadata = metadata(repository, state, DEFAULT_START, DEFAULT_END, filters)
    result_metadata.limitations.extend(limitations)
    return {"data": data, "metadata": result_metadata}
