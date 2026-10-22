from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.operational import OrderStatus
from app.schemas.analytics import AnalyticsListResponse, InspectionQueueItem
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository
from app.api.v1.analytics_route import AnalyticsRoute
from app.services.analytics import DEFAULT_END, DEFAULT_START, filters_model, metadata, page_items
from app.services.inspection_analytics import build_inspection_queue
from app.schemas.inspections import OrderCreateRequest, OrderResponse, OrderUpdateRequest
from app.services import inspections as inspection_service

router = APIRouter()
analytics_router = APIRouter(route_class=AnalyticsRoute)


@analytics_router.get("/queue", response_model=AnalyticsListResponse[InspectionQueueItem], summary="Fila sintética de UCs com suspeita")
def get_inspection_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_by: str = Query("priority", max_length=40),
    municipio: str | None = Query(None, max_length=100),
    bairro: str | None = Query(None, max_length=100),
    classe: str | None = Query(None, max_length=100),
    alimentador: str | None = Query(None, max_length=100),
    repository: AnalyticsRepository = Depends(get_analytics_repository),
):
    """Read-only demonstration queue; estimates are provisional and not Gold metrics."""
    filters = filters_model(municipio, bairro, classe, alimentador)
    items, state = build_inspection_queue(repository, filters)
    selected, pagination = page_items(items, page, page_size, order_by, {"priority", "uc_id", "potential_recoverable_energy_kwh"}, descending=order_by == "priority")
    result_metadata = metadata(repository, state, DEFAULT_START, DEFAULT_END, filters)
    if state == "partial":
        result_metadata.limitations.append("Há suspeitas sem estimativa demonstrativa de energia recuperável.")
    return {"data": {"items": selected}, "pagination": pagination, "metadata": result_metadata}


router.include_router(analytics_router)


@router.get(
    "/orders",
    response_model=list[OrderResponse],
    summary="Listar ordens de inspeção operacionais",
)
def list_orders(
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """Lista as ordens registradas no portal (WEB-05)."""
    return inspection_service.list_orders(db, status_filter)


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar nova ordem de inspeção",
)
def create_order(payload: OrderCreateRequest, db: Session = Depends(get_db)):
    """Cria uma ordem de inspeção mantida separadamente dos dados analíticos."""
    return inspection_service.create_order(db, payload)


@router.patch(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Atualizar status ou resultado da ordem",
)
def update_order(order_id: int, payload: OrderUpdateRequest, db: Session = Depends(get_db)):
    """Atualiza o ciclo de vida ou desfecho da fiscalização."""
    order = inspection_service.update_order(db, order_id, payload)
    if not order:
        raise HTTPException(status_code=404, detail="Ordem de inspeção não encontrada.")
    return order
