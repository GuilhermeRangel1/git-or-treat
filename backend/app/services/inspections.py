import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.operational import InspectionOrder, OrderStatus
from app.schemas.inspections import OrderCreateRequest, OrderUpdateRequest

class OrderConflictError(Exception):
    pass


class OrderResultRequiredError(ValueError):
    pass


logger = logging.getLogger(__name__)
TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED},
    OrderStatus.IN_PROGRESS: {OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
}


def list_orders(db: Session, status_filter: Optional[OrderStatus] = None) -> list[InspectionOrder]:
    query = db.query(InspectionOrder)
    if status_filter:
        query = query.filter(InspectionOrder.status == status_filter)
    return query.all()


def create_order(db: Session, payload: OrderCreateRequest) -> InspectionOrder:
    order = InspectionOrder(
        uc_id=payload.uc_id, reason=payload.reason, priority=payload.priority,
        notes=payload.notes, status=OrderStatus.PENDING,
    )
    db.add(order)
    try:
        db.commit()
        db.refresh(order)
        return order
    except Exception:
        db.rollback()
        raise


def update_order(db: Session, order_id: int, payload: OrderUpdateRequest) -> Optional[InspectionOrder]:
    order = db.query(InspectionOrder).filter(InspectionOrder.id == order_id).first()
    if not order:
        return None
    previous = order.status
    target = payload.status or previous
    if target != previous and target not in TRANSITIONS[previous]:
        raise OrderConflictError("Transição de status não permitida.")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("status") is None:
        changes.pop("status", None)
    if previous in {OrderStatus.COMPLETED, OrderStatus.CANCELLED}:
        if any(getattr(order, key) != value for key, value in changes.items()):
            raise OrderConflictError("Ordem encerrada não pode ser alterada.")
        return order
    if target == OrderStatus.COMPLETED and not (changes.get("result", order.result) or "").strip():
        raise OrderResultRequiredError("Informe o resultado para concluir a ordem.")
    try:
        changed = (
            db.query(InspectionOrder)
            .filter(InspectionOrder.id == order_id, InspectionOrder.status == previous)
            .update(changes, synchronize_session=False)
        )
        if changed != 1:
            raise OrderConflictError("Ordem alterada por outra solicitação. Consulte novamente.")
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise
    if target != previous:
        logger.info("inspection_order_status_changed", extra={
            "order_id": order_id, "previous_status": previous.value,
            "new_status": target.value, "actor": "orders-writer",
        })
    return order
