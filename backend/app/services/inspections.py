from typing import Optional

from sqlalchemy.orm import Session

from app.models.operational import InspectionOrder, OrderStatus
from app.schemas.inspections import OrderCreateRequest, OrderUpdateRequest


def list_orders(
    db: Session, status_filter: Optional[OrderStatus] = None
) -> list[InspectionOrder]:
    query = db.query(InspectionOrder)
    if status_filter:
        query = query.filter(InspectionOrder.status == status_filter)
    return query.all()


def create_order(db: Session, payload: OrderCreateRequest) -> InspectionOrder:
    order = InspectionOrder(
        uc_id=payload.uc_id,
        reason=payload.reason,
        priority=payload.priority,
        notes=payload.notes,
        status=OrderStatus.PENDING,
    )
    db.add(order)
    try:
        db.commit()
        db.refresh(order)
        return order
    except Exception:
        db.rollback()
        raise


def update_order(
    db: Session, order_id: int, payload: OrderUpdateRequest
) -> Optional[InspectionOrder]:
    order = (
        db.query(InspectionOrder)
        .filter(InspectionOrder.id == order_id)
        .first()
    )
    if not order:
        return None

    if payload.status:
        order.status = payload.status
    if payload.notes is not None:
        order.notes = payload.notes
    if payload.result is not None:
        order.result = payload.result

    try:
        db.commit()
        db.refresh(order)
        return order
    except Exception:
        db.rollback()
        raise
