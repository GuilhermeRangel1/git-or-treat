from typing import Callable, Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, Header, Response, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from app.core.database import get_db
from app.core.order_access import OrderIdentity, get_order_identity, require_orders_read, require_orders_write
from app.models.operational import OrderStatus
from app.schemas.inspection_queue import QueueResponse, SuspicionResponse
from app.schemas.inspection_queue import GoldInspectionQueueResponse, GoldSuspicionResponse
from app.repositories.gold_context import GoldContext, get_optional_gold_context
from app.repositories.gold_inspections import GoldInspectionRepository
from app.repositories.analytics import AnalyticsRepository, get_analytics_repository_provider
from app.api.v1.analytics_route import StrictAnalyticsRoute
from app.services.analytics import AnalyticsAPIError, filters_model
from app.services.inspection_analytics import build_gold_queue_response, build_gold_suspicion_response, build_queue_response, build_suspicion_response
from app.schemas.inspections import OrderCreateRequest, OrderResponse, OrderUpdateRequest, QueueOrderCreateRequest, OrderPage, OrderConflictResponse, OrderAccessResponse
from app.services import inspections as inspection_service
from app.schemas.inspections import OrderCancelRequest, OrderResultRequest, OrderHistoryResponse

router = APIRouter()
analytics_router = APIRouter(route_class=StrictAnalyticsRoute)


def order_conflict_response(exc: inspection_service.OrderConflictError) -> JSONResponse:
    body = OrderConflictResponse(
        detail=str(exc), error={"code": exc.code, "message": str(exc), "order_id": exc.order_id},
    )
    return JSONResponse(status_code=409, content=body.model_dump())


@analytics_router.get(
    "/queue", response_model=QueueResponse | GoldInspectionQueueResponse,
    summary="Fila de inspeção",
    description="Gold: snapshot cadastral sem competência. A ordenação padrão é por UC; `category` ordena pelo texto original e desempata por UC. `priority` e recuperação não são métricas Gold.",
)
def get_inspection_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_by: Literal["priority", "uc_id", "potential_recoverable_energy_kwh", "category"] | None = None,
    direction: Literal["asc", "desc"] = "desc",
    municipio: str | None = Query(None, max_length=100),
    bairro: str | None = Query(None, max_length=100),
    classe: str | None = Query(None, max_length=100),
    alimentador: str | None = Query(None, max_length=100),
    expected_lote: str | None = Query(None, max_length=100),
    expected_fingerprint: str | None = Query(None, max_length=64, pattern=r"^[a-f0-9]{64}$"),
    gold_context: GoldContext | None = Depends(get_optional_gold_context),
    repository_provider: Callable[[], AnalyticsRepository] = Depends(get_analytics_repository_provider),
):
    """Read-only demonstration queue; estimates are provisional and not Gold metrics."""
    filters = filters_model(municipio, bairro, classe, alimentador)
    if gold_context is not None:
        if order_by not in {None, "uc_id", "category"}:
            raise AnalyticsAPIError(422, "invalid_query", "Ordenação indisponível para a fila Gold.", [{"field": "order_by", "message": "Use uc_id ou category; a categoria não é um score."}])
        return build_gold_queue_response(
            GoldInspectionRepository(gold_context), filters, page, page_size,
            "uc_id" if order_by is None else order_by,
            direction,
        )
    repository = repository_provider()
    return build_queue_response(repository, filters, page, page_size, order_by or "priority", direction)


@analytics_router.get("/queue/{uc_id}", response_model=SuspicionResponse | GoldSuspicionResponse, summary="Evidências da suspeita")
def get_suspicion_detail(
    uc_id: str,
    expected_lote: str | None = Query(None, max_length=100),
    expected_fingerprint: str | None = Query(None, max_length=64, pattern=r"^[a-f0-9]{64}$"),
    gold_context: GoldContext | None = Depends(get_optional_gold_context),
    repository_provider: Callable[[], AnalyticsRepository] = Depends(get_analytics_repository_provider),
):
    if gold_context is not None:
        return build_gold_suspicion_response(GoldInspectionRepository(gold_context), uc_id)
    repository = repository_provider()
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


@router.get("/orders/{order_id}/history", response_model=list[OrderHistoryResponse],
            dependencies=[Depends(require_orders_read)])
def get_order_history(order_id: int = Path(ge=1, le=9223372036854775807), db: Session = Depends(get_db)):
    if inspection_service.get_order(db, order_id) is None:
        raise HTTPException(404, "Ordem de inspeção não encontrada.")
    return inspection_service.get_history(db, order_id)


@router.post("/orders/{order_id}/result", response_model=OrderResponse,
             responses={409: {"model": OrderConflictResponse}},
             summary="Registrar resultado e concluir a ordem",
             description="Exige EM_ANDAMENTO e a versão atual da ordem. Versão obsoleta retorna 409; consulte novamente antes de reenviar.")
def register_order_result(payload: OrderResultRequest, order_id: int = Path(ge=1, le=9223372036854775807),
                          db: Session = Depends(get_db), actor: str = Depends(require_orders_write)):
    try:
        order = inspection_service.register_result(db, order_id, payload, actor=actor)
    except inspection_service.OrderConflictError as exc:
        return order_conflict_response(exc)
    if order is None:
        raise HTTPException(404, "Ordem de inspeção não encontrada.")
    return order


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse,
             responses={409: {"model": OrderConflictResponse}},
             summary="Confirmar cancelamento da ordem",
             description="Exige versão atual e confirmed_order_id igual ao ID da rota. Esta é a única rota de cancelamento; use no exemplo o ID real da ordem selecionada.")
def cancel_inspection_order(payload: OrderCancelRequest, order_id: int = Path(ge=1, le=9223372036854775807),
                            db: Session = Depends(get_db), actor: str = Depends(require_orders_write)):
    try:
        order = inspection_service.cancel_order(db, order_id, payload, actor=actor)
    except inspection_service.OrderConflictError as exc:
        return order_conflict_response(exc)
    if order is None:
        raise HTTPException(404, "Ordem de inspeção não encontrada.")
    return order


@router.get("/orders/search", response_model=OrderPage, dependencies=[Depends(require_orders_read)],
            summary="Consultar ordens com filtros e paginação")
def search_orders(
    status_filter: OrderStatus | None = Query(None, alias="status"),
    uc_id: str | None = Query(None, min_length=1, max_length=50),
    priority: Literal["BAIXA", "MEDIA", "ALTA"] | None = None,
    has_result: bool | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return inspection_service.search_orders(
        db, status_filter, uc_id, priority, page, page_size, has_result=has_result,
    )


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
    summary="Atualizar status, observações ou resultado da ordem",
    description="Exige a versão atual retornada pelo GET. CANCELADA não é aceita: use POST /orders/{order_id}/cancel com confirmação do ID. Sem versão: 422; versão obsoleta: 409.",
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
