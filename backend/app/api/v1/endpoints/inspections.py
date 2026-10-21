from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.operational import OrderStatus
from app.schemas.common import PaginatedResponse
from app.schemas.inspections import (
    OrderCancelRequest,
    OrderCreateRequest,
    OrderHistoryResponse,
    OrderResponse,
    OrderResultRequest,
    OrderUpdateRequest,
)
from app.services import inspections as inspection_service
from app.services.inspections import (
    ActiveOrderConflictError,
    ConcurrencyConflictError,
    FieldResultRequiredError,
    InvalidStateTransitionError,
    OrderNotFoundError,
    OrderTerminalStateError,
)

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
    uc_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Lista as ordens registradas no portal (WEB-05)."""
    return inspection_service.list_orders(db, status_filter=status_filter, uc_id=uc_id)


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Buscar ordem de inspeção por ID",
)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Retorna os dados detalhados de uma ordem de inspeção."""
    order = inspection_service.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem de inspeção não encontrada.",
        )
    return order


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar nova ordem de inspeção",
)
def create_order(
    payload: OrderCreateRequest,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """Cria uma ordem de inspeção com validação de idempotência e de ordens ativas simultâneas."""
    try:
        return inspection_service.create_order(
            db, payload, idempotency_key=x_idempotency_key
        )
    except ActiveOrderConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))


@router.patch(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Atualizar status ou dados da ordem",
)
def update_order(
    order_id: int,
    payload: OrderUpdateRequest,
    db: Session = Depends(get_db),
):
    """Atualiza o ciclo de vida ou dados da ordem com controle de transições e concorrência."""
    try:
        order = inspection_service.update_order(db, order_id, payload)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ordem de inspeção não encontrada.",
            )
        return order
    except OrderTerminalStateError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
    except ConcurrencyConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
    except (InvalidStateTransitionError, FieldResultRequiredError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/orders/{order_id}/result",
    response_model=OrderResponse,
    summary="Registrar resultado de campo e concluir ordem",
)
def register_result(
    order_id: int,
    payload: OrderResultRequest,
    db: Session = Depends(get_db),
):
    """Registra o desfecho da fiscalização de campo, concluindo a ordem com auditoria."""
    try:
        return inspection_service.register_result(db, order_id, payload)
    except OrderNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except (OrderTerminalStateError, ConcurrencyConflictError) as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
    except FieldResultRequiredError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Confirmar cancelamento da ordem de inspeção",
)
def cancel_order(
    order_id: int,
    payload: Optional[OrderCancelRequest] = None,
    db: Session = Depends(get_db),
):
    """Confirma o cancelamento da ordem identificada, registrando justificativa e auditoria."""
    try:
        return inspection_service.cancel_order(db, order_id, payload)
    except OrderNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except (OrderTerminalStateError, ConcurrencyConflictError) as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))


@router.get(
    "/orders/{order_id}/history",
    response_model=list[OrderHistoryResponse],
    summary="Consultar histórico e trilha de auditoria da ordem",
)
def get_order_history(order_id: int, db: Session = Depends(get_db)):
    """Retorna o histórico cronológico de transições e eventos da ordem."""
    try:
        return inspection_service.get_order_history(db, order_id)
    except OrderNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
