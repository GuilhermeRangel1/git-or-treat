from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.operational import OrderStatus
from app.schemas.common import PaginatedResponse
from app.schemas.inspections import OrderCreateRequest, OrderResponse, OrderUpdateRequest
from app.services import inspections as inspection_service

router = APIRouter()


@router.get("/queue", summary="Fila de UCs com suspeita de anomalia (Gold)")
def get_inspection_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retorna a fila priorizada gerada pelas regras analíticas da Gold (WEB-04)."""
    return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)


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
