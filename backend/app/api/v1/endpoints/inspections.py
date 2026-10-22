from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.operational import OrderStatus
from app.schemas.inspection_queue import QueueResponse, SuspicionResponse
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository
from app.api.v1.analytics_route import AnalyticsRoute
from app.services.analytics import filters_model
from app.services.inspection_analytics import build_queue_response, build_suspicion_response
from app.schemas.inspections import OrderCreateRequest, OrderResponse, OrderUpdateRequest
from app.services import inspections as inspection_service

router = APIRouter()
analytics_router = APIRouter(route_class=AnalyticsRoute)


@analytics_router.get("/queue", response_model=QueueResponse, summary="Fila sintética de UCs com suspeita")
def get_inspection_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_by: Literal["priority", "uc_id", "potential_recoverable_energy_kwh"] = "priority",
    direction: Literal["asc", "desc"] = "desc",
    municipio: str | None = Query(None, max_length=100),
    bairro: str | None = Query(None, max_length=100),
    classe: str | None = Query(None, max_length=100),
    alimentador: str | None = Query(None, max_length=100),
    repository: AnalyticsRepository = Depends(get_analytics_repository),
):
    """Read-only demonstration queue; estimates are provisional and not Gold metrics."""
    filters = filters_model(municipio, bairro, classe, alimentador)
    return build_queue_response(repository, filters, page, page_size, order_by, direction)


@analytics_router.get("/queue/{uc_id}", response_model=SuspicionResponse, summary="Evidências sintéticas da suspeita")
def get_suspicion_detail(uc_id: str, repository: AnalyticsRepository = Depends(get_analytics_repository)):
    return build_suspicion_response(repository, uc_id)


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
