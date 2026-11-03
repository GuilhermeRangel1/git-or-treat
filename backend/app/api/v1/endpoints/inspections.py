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
    description="Gold: snapshot cadastral sem competência. A ordenação padrão usa posicao_fila_inspecao ascendente, com desempate por UC; aceita queue_position, uc_id ou category e direção explícita. `priority` e recuperação não são métricas Gold.",
)
def get_inspection_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_by: Literal["priority", "uc_id", "potential_recoverable_energy_kwh", "category", "queue_position"] | None = None,
    direction: Literal["asc", "desc"] | None = None,
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
        if order_by not in {None, "uc_id", "category", "queue_position"}:
            raise AnalyticsAPIError(422, "invalid_query", "Ordenação indisponível para a fila Gold.", [{"field": "order_by", "message": "Use queue_position, uc_id ou category; a categoria não é um score."}])
        return build_gold_queue_response(
            GoldInspectionRepository(gold_context), filters, page, page_size,
            "queue_position" if order_by is None else order_by,
            direction or ("asc" if order_by in {None, "queue_position"} else "desc"),
        )
    if order_by == "queue_position":
        raise AnalyticsAPIError(422, "invalid_query", "Ordenação queue_position só está disponível no modo Gold.", [{"field": "order_by", "message": "Use uma ordenação disponível para a fonte sintética."}])
    repository = repository_provider()
    return build_queue_response(repository, filters, page, page_size, order_by or "priority", direction or "desc")


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


from app.services.field_files import FieldUpload, import_results, read_xlsx, field_template


@router.post("/field-results/import", summary="Importar CSV de resultados de campo")
def import_field_results(payload: FieldUpload, db: Session = Depends(get_db),
                         actor: str = Depends(require_orders_write)):
    if payload.xlsx is not None:
        try:
            content = read_xlsx(payload.xlsx)
        except Exception:
            return {"imported": 0, "errors": [{"line": 1, "message": "XLSX inválido. Use a aba Resultados do modelo, até 500 ordens, sem fórmulas."}]}
    else:
        content = payload.csv
    return import_results(db, content, actor)


@router.get("/field-results/template", summary="Modelo Excel das ordens em andamento")
def download_field_template(response: Response, format: Literal["xlsx", "csv"] = "xlsx", actor: str = Depends(require_orders_write), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return field_template(db, format)
    except ModuleNotFoundError:
        raise HTTPException(503, "O serviço de planilhas Excel está indisponível. Baixe o modelo CSV ou solicite a atualização do backend.") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/field-queue/export", summary="Exportar a página filtrada da fila")
def export_field_queue(actor: str = Depends(require_orders_read),
                       municipio: str | None = Query(None, max_length=100),
                       bairro: str | None = Query(None, max_length=100),
                       classe: str | None = Query(None, max_length=100),
                       categoria: str | None = Query(None, max_length=100),
                       options_only: bool = False,
                       count_only: bool = False,
                       order_by: Literal["priority", "uc_id", "potential_recoverable_energy_kwh", "category", "queue_position"] | None = None,
                       direction: Literal["asc", "desc"] | None = None,
                       gold_context: GoldContext | None = Depends(get_optional_gold_context),
                       repository_provider: Callable[[], AnalyticsRepository] = Depends(get_analytics_repository_provider)):
    import csv
    import io
    import json
    if count_only and gold_context is not None:
        count = GoldInspectionRepository(gold_context).count(filters_model(municipio, bairro, classe, None), categoria)
        return {"count": count}
    queue = get_inspection_queue(
        page=1, page_size=1 if options_only or count_only else 50001,
        order_by=order_by, direction=direction, municipio=municipio,
        bairro=bairro, classe=classe, alimentador=None,
        expected_lote=None, expected_fingerprint=None,
        gold_context=gold_context, repository_provider=repository_provider,
    )
    if options_only:
        categories = getattr(queue.data.summary, "categories", {})
        if gold_context is not None:
            neighborhoods = queue.data.neighborhoods
        else:
            neighborhoods = [dict(municipio=municipality, bairro=neighborhood) for municipality, neighborhood in sorted({
                (unit["municipio"], unit["bairro"]) for unit in repository_provider().units
                if unit.get("municipio") and unit.get("bairro")
            })]
        return {"options": {**queue.data.filter_options, "categoria": sorted(categories)}, "neighborhoods": neighborhoods}
    if gold_context is not None and categoria is not None:
        queue = build_gold_queue_response(
            GoldInspectionRepository(gold_context), filters_model(municipio, bairro, classe, None),
            1, 50001, order_by or "queue_position", direction or "asc", categoria,
        )
    if count_only:
        if categoria is not None:
            raise HTTPException(422, "Esta fonte não publica categorias para filtrar a fila.")
        return {"count": queue.pagination.total}
    if queue.pagination.total > 50000:
        raise HTTPException(422, "O recorte excede 50.000 UCs. Aplique filtros para exportar.")
    rows = [item.model_dump(mode="json") for item in queue.data.items]
    if categoria is not None:
        categories = getattr(queue.data.summary, "categories", {})
        if categoria not in categories:
            raise HTTPException(422, "Categoria indisponível neste recorte.")
        rows = [row for row in rows if row.get("category") == categoria]
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    columns = list(rows[0]) if rows else ["uc_id"]
    writer.writerow([*columns, "fonte", "filtros"])
    filters = json.dumps({"municipio": municipio, "bairro": bairro, "classe": classe, "categoria": categoria, "order_by": order_by, "direction": direction}, ensure_ascii=False)
    def safe(value):
        value = "" if value is None else json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    for row in rows:
        writer.writerow([*[safe(row.get(key)) for key in columns], safe(queue.metadata.source.version), safe(filters)])
    return {"csv": output.getvalue(), "count": len(rows)}


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


@router.delete("/orders/{order_id}", status_code=204, summary="Excluir ordem do portal preservando auditoria")
def delete_inspection_order(payload: OrderCancelRequest, order_id: int = Path(ge=1, le=9223372036854775807),
                            db: Session = Depends(get_db), actor: str = Depends(require_orders_write)):
    try:
        if not inspection_service.delete_order(db, order_id, payload.version, payload.confirmed_order_id, actor):
            raise HTTPException(404, "Ordem não encontrada ou já excluída.")
    except inspection_service.OrderConflictError as exc:
        return order_conflict_response(exc)
    return Response(status_code=204)


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
