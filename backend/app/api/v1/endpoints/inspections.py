from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.operational import InspectionOrder, OrderStatus
from app.schemas.common import PaginatedResponse

router = APIRouter()


class OrderCreateRequest(BaseModel):
    uc_id: str
    reason: str
    priority: str = "MEDIA"
    notes: Optional[str] = None


class OrderUpdateRequest(BaseModel):
    status: Optional[OrderStatus] = None
    notes: Optional[str] = None
    result: Optional[str] = None


@router.get("/queue", summary="Fila de UCs com suspeita de anomalia (Gold)")
def get_inspection_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retorna a fila priorizada gerada pelas regras analíticas da Gold (WEB-04)."""
    return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)


@router.get("/orders", summary="Listar ordens de inspeção operacionais")
def list_orders(
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """Lista as ordens registradas no portal (WEB-05)."""
    query = db.query(InspectionOrder)
    if status_filter:
        query = query.filter(InspectionOrder.status == status_filter)
    orders = query.all()
    return orders


@router.post("/orders", status_code=status.HTTP_201_CREATED, summary="Criar nova ordem de inspeção")
def create_order(payload: OrderCreateRequest, db: Session = Depends(get_db)):
    """Cria uma ordem de inspeção mantida separadamente dos dados analíticos."""
    order = InspectionOrder(
        uc_id=payload.uc_id,
        reason=payload.reason,
        priority=payload.priority,
        notes=payload.notes,
        status=OrderStatus.PENDING,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.patch("/orders/{order_id}", summary="Atualizar status ou resultado da ordem")
def update_order(order_id: int, payload: OrderUpdateRequest, db: Session = Depends(get_db)):
    """Atualiza o ciclo de vida ou desfecho da fiscalização."""
    order = db.query(InspectionOrder).filter(InspectionOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordem de inspeção não encontrada.")

    if payload.status:
        order.status = payload.status
    if payload.notes is not None:
        order.notes = payload.notes
    if payload.result is not None:
        order.result = payload.result

    db.commit()
    db.refresh(order)
    return order
