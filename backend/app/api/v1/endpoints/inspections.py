from typing import Callable, Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, Header, Response, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from app.core.database import get_db
from app.core.order_access import OrderIdentity, get_order_identity, require_orders_read, require_orders_write
from app.models.operational import OrderStatus
from app.schemas.inspection_queue import QueueResponse, SuspicionResponse
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository, get_analytics_repository_provider
from app.api.v1.analytics_route import AnalyticsRoute
from app.services.analytics import filters_model
from app.services.inspection_analytics import build_queue_response, build_suspicion_response
from app.schemas.inspections import OrderCreateRequest, OrderResponse, OrderUpdateRequest, QueueOrderCreateRequest, OrderPage, OrderConflictResponse, OrderAccessResponse
from app.services import inspections as inspection_service

router = APIRouter()
analytics_router = APIRouter(route_class=AnalyticsRoute)


def order_conflict_response(exc: inspection_service.OrderConflictError) -> JSONResponse:
    body = OrderConflictResponse(
        detail=str(exc), error={"code": exc.code, "message": str(exc), "order_id": exc.order_id},
    )
    return JSONResponse(status_code=409, content=body.model_dump())


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


@router.get("/access", response_model=OrderAccessResponse, summary="Identidade e permissões das ordens")
def get_order_access(response: Response, identity: OrderIdentity = Depends(get_order_identity)):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    return OrderAccessResponse(actor=identity.actor, auth_mode=identity.auth_mode, permissions=sorted(identity.permissions))


@router.post("/queue/{uc_id}/orders", response_model=OrderResponse, status_code=201,
             responses={409: {"model": OrderConflictResponse}},
             dependencies=[Depends(require_orders_write)], summary="Criar ordem pela suspeita selecionada")
def create_order_from_queue(
    payload: QueueOrderCreateRequest, response: Response,
    uc_id: str = Path(min_length=1, max_length=50),
    idempotency_key: str = Header(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
    db: Session = Depends(get_db),
    repository_provider: Callable[[], AnalyticsRepository] = Depends(get_analytics_repository_provider),
    actor: str = Depends(require_orders_write),
):
    try:
        order, created = inspection_service.create_from_queue(db, repository_provider, uc_id, payload, idempotency_key, actor=actor)
    except inspection_service.OrderConflictError as exc:
        return order_conflict_response(exc)
    response.status_code = 201 if created else 200
    return order


@router.get("/orders/search", response_model=OrderPage, dependencies=[Depends(require_orders_read)],
            summary="Consultar ordens com filtros e paginação")
def search_orders(
    status_filter: OrderStatus | None = Query(None, alias="status"),
    uc_id: str | None = Query(None, min_length=1, max_length=50),
    priority: Literal["BAIXA", "MEDIA", "ALTA"] | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return inspection_service.search_orders(db, status_filter, uc_id, priority, page, page_size)


@router.get("/orders/{order_id}", response_model=OrderResponse, dependencies=[Depends(require_orders_read)])
def get_order(order_id: int = Path(ge=1, le=9223372036854775807), db: Session = Depends(get_db)):
    order = inspection_service.get_order(db, order_id)
    if order is None:
        raise HTTPException(404, "Ordem de inspeção não encontrada.")
    return order


@router.get(
    "/orders",
    response_model=list[OrderResponse],
    summary="Listar ordens de inspeção operacionais",
    dependencies=[Depends(require_orders_read)],
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
    responses={409: {"model": OrderConflictResponse}},
    dependencies=[Depends(require_orders_write)],
)
def create_order(payload: OrderCreateRequest, db: Session = Depends(get_db), actor: str = Depends(require_orders_write)):
    """Cria uma ordem de inspeção mantida separadamente dos dados analíticos."""
    try:
        return inspection_service.create_order(db, payload, actor=actor)
    except inspection_service.OrderConflictError as exc:
        return order_conflict_response(exc)


@router.patch(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Atualizar status ou resultado da ordem",
    responses={409: {"model": OrderConflictResponse}},
    dependencies=[Depends(require_orders_write)],
)
def update_order(payload: OrderUpdateRequest, order_id: int = Path(ge=1, le=9223372036854775807), db: Session = Depends(get_db), actor: str = Depends(require_orders_write)):
    """Atualiza o ciclo de vida ou desfecho da fiscalização."""
    try:
        order = inspection_service.update_order(db, order_id, payload, actor=actor)
    except inspection_service.OrderConflictError as exc:
        return order_conflict_response(exc)
    except inspection_service.OrderResultRequiredError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not order:
        raise HTTPException(status_code=404, detail="Ordem de inspeção não encontrada.")
    return order
