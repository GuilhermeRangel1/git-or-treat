from typing import Optional
from sqlalchemy.orm import Session

from app.models.operational import (
    InspectionOrder,
    OperationalOrderHistory,
    OrderAction,
    OrderStatus,
)
from app.schemas.inspections import (
    OrderCancelRequest,
    OrderCreateRequest,
    OrderResultRequest,
    OrderUpdateRequest,
)


class InspectionDomainError(Exception):
    """Erro base para operações operacionais de inspeções."""
    pass


class OrderNotFoundError(InspectionDomainError):
    """Ordem de inspeção não encontrada."""
    pass


class InvalidStateTransitionError(InspectionDomainError):
    """Transição de status não permitida pelas regras de ciclo operacional."""
    pass


class OrderTerminalStateError(InspectionDomainError):
    """Operação rejeitada porque a ordem já se encontra em estado terminal (cancelada ou concluída)."""
    pass


class ConcurrencyConflictError(InspectionDomainError):
    """Conflito de versão detectado em alteração concorrente (controle otimista)."""
    pass


class ActiveOrderConflictError(InspectionDomainError):
    """Já existe uma ordem ativa (PENDENTE ou EM_ANDAMENTO) para a UC informada."""
    pass


class FieldResultRequiredError(InspectionDomainError):
    """Registro de resultado de campo é obrigatório para concluir a ordem de inspeção."""
    pass


ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED, OrderStatus.COMPLETED},
    OrderStatus.IN_PROGRESS: {OrderStatus.COMPLETED, OrderStatus.CANCELLED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
}


def list_orders(
    db: Session,
    status_filter: Optional[OrderStatus] = None,
    uc_id: Optional[str] = None,
) -> list[InspectionOrder]:
    query = db.query(InspectionOrder)
    if status_filter:
        query = query.filter(InspectionOrder.status == status_filter)
    if uc_id:
        query = query.filter(InspectionOrder.uc_id == uc_id)
    return query.order_by(InspectionOrder.id.asc()).all()


def get_order(db: Session, order_id: int) -> Optional[InspectionOrder]:
    return db.query(InspectionOrder).filter(InspectionOrder.id == order_id).first()


def create_order(
    db: Session,
    payload: OrderCreateRequest,
    idempotency_key: Optional[str] = None,
) -> InspectionOrder:
    key = payload.idempotency_key or idempotency_key
    if key:
        existing_by_key = (
            db.query(InspectionOrder)
            .filter(InspectionOrder.idempotency_key == key)
            .first()
        )
        if existing_by_key:
            return existing_by_key

    # Prevenção de duplicidade: impede múltiplas ordens abertas para a mesma UC
    active_order = (
        db.query(InspectionOrder)
        .filter(
            InspectionOrder.uc_id == payload.uc_id,
            InspectionOrder.status.in_([OrderStatus.PENDING, OrderStatus.IN_PROGRESS]),
        )
        .first()
    )
    if active_order:
        raise ActiveOrderConflictError(
            f"Já existe uma ordem ativa ({active_order.status.value}) para a UC '{payload.uc_id}' (Ordem #{active_order.id}). Conclua ou cancele a ordem ativa antes de abrir uma nova."
        )

    try:
        order = InspectionOrder(
            uc_id=payload.uc_id,
            reason=payload.reason,
            priority=payload.priority,
            notes=payload.notes,
            status=OrderStatus.PENDING,
            version=1,
            idempotency_key=key,
        )
        db.add(order)
        db.flush()

        history = OperationalOrderHistory(
            order_id=order.id,
            previous_status=None,
            new_status=OrderStatus.PENDING,
            action=OrderAction.CREATED,
            notes=payload.notes,
            details=f"Ordem de inspeção criada com prioridade {order.priority}. Motivo: {order.reason}",
        )
        db.add(history)
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

    # Validação de concorrência otimista
    if payload.version is not None and payload.version != order.version:
        raise ConcurrencyConflictError(
            f"Conflito de concorrência: a ordem foi modificada por outro processo. "
            f"Versão informada: {payload.version}, versão atual: {order.version}."
        )

    # Prevenção da regressão do protótipo: ordem cancelada não pode ser reativada ou alterada
    if order.status == OrderStatus.CANCELLED:
        raise OrderTerminalStateError(
            f"Transição inválida: a ordem #{order_id} já está cancelada e não pode ser reativada ou alterada."
        )

    # Ordem concluída não pode ter seu ciclo de vida revertido
    if order.status == OrderStatus.COMPLETED and payload.status and payload.status != OrderStatus.COMPLETED:
        raise OrderTerminalStateError(
            f"Transição inválida: a ordem #{order_id} já foi concluída e não pode ter seu status alterado."
        )

    old_status = order.status
    status_changed = payload.status is not None and payload.status != old_status

    if status_changed:
        # Se estiver concluindo, o resultado de campo é estritamente obrigatório
        if payload.status == OrderStatus.COMPLETED:
            eff_result = payload.result if payload.result is not None else order.result
            if not eff_result or not eff_result.strip():
                raise FieldResultRequiredError(
                    "O registro de resultado de campo é obrigatório para concluir a ordem de inspeção."
                )

        allowed = ALLOWED_TRANSITIONS.get(old_status, set())
        if payload.status not in allowed:
            raise InvalidStateTransitionError(
                f"Transição de status inválida: não é permitido transitar de '{old_status.value}' para '{payload.status.value}'."
            )

        order.status = payload.status

    if payload.notes is not None:
        order.notes = payload.notes
    if payload.result is not None:
        order.result = payload.result

    order.version += 1

    # Registra evento na trilha de auditoria
    if status_changed:
        if order.status == OrderStatus.CANCELLED:
            action = OrderAction.CANCELLED
            details = "Ordem cancelada via atualização"
        elif order.status == OrderStatus.COMPLETED:
            action = OrderAction.RESULT_REGISTERED
            details = f"Ordem concluída. Resultado: {order.result}"
        else:
            action = OrderAction.STATUS_UPDATED
            details = f"Status alterado de {old_status.value} para {order.status.value}"

        history = OperationalOrderHistory(
            order_id=order.id,
            previous_status=old_status,
            new_status=order.status,
            action=action,
            notes=payload.notes,
            details=details,
        )
        db.add(history)
    elif payload.notes is not None or payload.result is not None:
        history = OperationalOrderHistory(
            order_id=order.id,
            previous_status=old_status,
            new_status=order.status,
            action=OrderAction.STATUS_UPDATED,
            notes=payload.notes,
            details="Dados complementares (observações/resultado) atualizados",
        )
        db.add(history)

    try:
        db.commit()
        db.refresh(order)
        return order
    except Exception:
        db.rollback()
        raise


def register_result(
    db: Session, order_id: int, payload: OrderResultRequest
) -> InspectionOrder:
    order = (
        db.query(InspectionOrder)
        .filter(InspectionOrder.id == order_id)
        .first()
    )
    if not order:
        raise OrderNotFoundError("Ordem de inspeção não encontrada.")

    if payload.version is not None and payload.version != order.version:
        raise ConcurrencyConflictError(
            f"Conflito de concorrência: a ordem foi modificada por outro processo. "
            f"Versão informada: {payload.version}, versão atual: {order.version}."
        )

    if order.status == OrderStatus.CANCELLED:
        raise OrderTerminalStateError(
            f"Não é possível registrar resultado na ordem #{order_id} pois ela já se encontra cancelada."
        )

    if order.status == OrderStatus.COMPLETED:
        raise OrderTerminalStateError(
            f"A ordem #{order_id} já se encontra concluída com resultado registrado."
        )

    if not payload.result or not payload.result.strip():
        raise FieldResultRequiredError(
            "O registro de resultado de campo é obrigatório para concluir a ordem de inspeção."
        )

    old_status = order.status
    order.result = payload.result.strip()
    if payload.notes is not None:
        order.notes = payload.notes
    order.status = OrderStatus.COMPLETED
    order.version += 1

    history = OperationalOrderHistory(
        order_id=order.id,
        previous_status=old_status,
        new_status=OrderStatus.COMPLETED,
        action=OrderAction.RESULT_REGISTERED,
        notes=payload.notes,
        details=f"Resultado de campo registrado: {order.result}",
    )
    db.add(history)

    try:
        db.commit()
        db.refresh(order)
        return order
    except Exception:
        db.rollback()
        raise


def cancel_order(
    db: Session, order_id: int, payload: Optional[OrderCancelRequest] = None
) -> InspectionOrder:
    order = (
        db.query(InspectionOrder)
        .filter(InspectionOrder.id == order_id)
        .first()
    )
    if not order:
        raise OrderNotFoundError("Ordem de inspeção não encontrada.")

    if payload and payload.version is not None and payload.version != order.version:
        raise ConcurrencyConflictError(
            f"Conflito de concorrência: a ordem foi modificada por outro processo. "
            f"Versão informada: {payload.version}, versão atual: {order.version}."
        )

    if order.status == OrderStatus.CANCELLED:
        raise OrderTerminalStateError(
            f"A ordem #{order_id} já se encontra cancelada."
        )

    if order.status == OrderStatus.COMPLETED:
        raise OrderTerminalStateError(
            f"Não é possível cancelar a ordem #{order_id} pois ela já foi concluída em campo."
        )

    old_status = order.status
    order.status = OrderStatus.CANCELLED
    reason = (
        payload.reason.strip()
        if (payload and payload.reason and payload.reason.strip())
        else None
    )
    if reason:
        order.cancellation_reason = reason

    order.version += 1

    history = OperationalOrderHistory(
        order_id=order.id,
        previous_status=old_status,
        new_status=OrderStatus.CANCELLED,
        action=OrderAction.CANCELLED,
        notes=order.notes,
        details=f"Ordem cancelada. Motivo: {reason or 'Cancelamento confirmado pelo operador'}",
    )
    db.add(history)

    try:
        db.commit()
        db.refresh(order)
        return order
    except Exception:
        db.rollback()
        raise


def get_order_history(
    db: Session, order_id: int
) -> list[OperationalOrderHistory]:
    order = (
        db.query(InspectionOrder)
        .filter(InspectionOrder.id == order_id)
        .first()
    )
    if not order:
        raise OrderNotFoundError("Ordem de inspeção não encontrada.")

    return (
        db.query(OperationalOrderHistory)
        .filter(OperationalOrderHistory.order_id == order_id)
        .order_by(OperationalOrderHistory.created_at.asc(), OperationalOrderHistory.id.asc())
        .all()
    )
