import logging
import hashlib
import json
from typing import Callable, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.models.operational import InspectionOrder, OrderStatus
from app.schemas.inspections import OrderCreateRequest, OrderUpdateRequest, QueueOrderCreateRequest, OrderPage
from app.schemas.order_snapshot import OrderSnapshotV1
from app.schemas.inspections import OrderSummary
from app.repositories.analytics import AnalyticsRepository
from app.services.inspection_analytics import build_suspicion_response

class OrderConflictError(Exception):
    def __init__(self, message: str, code: str = "order_conflict", order_id: int | None = None):
        super().__init__(message)
        self.code = code
        self.order_id = order_id


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


def get_order(db: Session, order_id: int) -> InspectionOrder | None:
    return db.get(InspectionOrder, order_id)


def _active_order(db: Session, uc_id: str) -> InspectionOrder | None:
    return db.query(InspectionOrder).filter(
        InspectionOrder.uc_id == uc_id,
        InspectionOrder.status.in_([OrderStatus.PENDING, OrderStatus.IN_PROGRESS]),
    ).first()


def _active_conflict(order: InspectionOrder) -> OrderConflictError:
    return OrderConflictError(
        f"Já existe ordem ativa para esta UC: {order.id}.", "active_order_exists", order.id,
    )


def create_order(db: Session, payload: OrderCreateRequest) -> InspectionOrder:
    active = _active_order(db, payload.uc_id)
    if active:
        raise _active_conflict(active)
    order = InspectionOrder(
        uc_id=payload.uc_id, reason=payload.reason, priority=payload.priority,
        notes=payload.notes, status=OrderStatus.PENDING,
    )
    db.add(order)
    try:
        db.commit()
        db.refresh(order)
        return order
    except IntegrityError:
        db.rollback()
        active = _active_order(db, payload.uc_id)
        if active:
            raise _active_conflict(active) from None
        raise
    except Exception:
        db.rollback()
        raise


def _fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _replay(db: Session, key: str, fingerprint: str) -> InspectionOrder | None:
    existing = db.query(InspectionOrder).filter_by(idempotency_key=key).first()
    if existing and existing.request_fingerprint != fingerprint:
        raise OrderConflictError("Chave de idempotência já usada com outra solicitação.", "idempotency_key_reused", existing.id)
    return existing


def create_from_queue(
    db: Session, repository_provider: Callable[[], AnalyticsRepository], uc_id: str,
    payload: QueueOrderCreateRequest, key: str,
) -> tuple[InspectionOrder, bool]:
    fingerprint = _fingerprint({"uc_id": uc_id, **payload.model_dump()})
    existing = _replay(db, key, fingerprint)
    if existing:
        return existing, False
    snapshot = build_suspicion_response(repository_provider(), uc_id)
    if (snapshot.metadata.source.version != payload.source_version
            or snapshot.data.rule_version != payload.rule_version):
        raise OrderConflictError("A suspeita mudou. Atualize a fila antes de criar a ordem.", "stale_suspicion")
    reference = _fingerprint({
        "uc_id": uc_id, "source": snapshot.metadata.source.model_dump(exclude={"updated_at"}),
        "rule_version": snapshot.data.rule_version,
    })
    active = _active_order(db, uc_id)
    if active:
        # A competing request may commit after the first key lookup but before
        # this active-order query. Reconcile the key before reporting conflict.
        existing = _replay(db, key, fingerprint)
        if existing:
            return existing, False
        raise _active_conflict(active)
    order = InspectionOrder(
        uc_id=snapshot.data.uc_id, reason=snapshot.data.reason,
        priority=payload.priority, notes=payload.notes, status=OrderStatus.PENDING,
        suspicion_reference=reference,
        suspicion_snapshot=OrderSnapshotV1.model_validate(snapshot.model_dump(mode="json")).model_dump(mode="json"),
        idempotency_key=key, request_fingerprint=fingerprint,
    )
    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # The unique indexes arbitrate competing workers, not a process-local lock.
        existing = _replay(db, key, fingerprint)
        if existing:
            return existing, False
        active = _active_order(db, uc_id)
        if active:
            raise _active_conflict(active) from None
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(order)
    return order, True


def search_orders(db: Session, status_filter: OrderStatus | None, uc_id: str | None,
                  priority: str | None, page: int, page_size: int) -> OrderPage:
    query = db.query(InspectionOrder)
    if status_filter:
        query = query.filter(InspectionOrder.status == status_filter)
    if uc_id:
        query = query.filter(InspectionOrder.uc_id == uc_id)
    if priority:
        query = query.filter(InspectionOrder.priority == priority)
    total = query.with_entities(func.count(InspectionOrder.id)).scalar()
    offset = (page - 1) * page_size
    items = []
    if offset < total:
        # Project only summary columns; do not fetch or deserialize historical JSON.
        columns = [getattr(InspectionOrder, name) for name in OrderSummary.model_fields]
        rows = query.with_entities(*columns).order_by(
            InspectionOrder.created_at.desc(), InspectionOrder.id.desc(),
        ).offset(offset).limit(page_size).all()
        items = [OrderSummary.model_validate(row) for row in rows]
    return OrderPage(items=items, pagination={
        "page": page, "page_size": page_size, "total": total,
        "total_pages": (total + page_size - 1) // page_size,
    })


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
