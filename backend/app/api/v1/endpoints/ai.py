import asyncio
from collections.abc import Callable
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.progressive import progressive_handler
from app.core.config import settings
from app.core.database import get_db
from app.core.genai_gold_database import (
    get_question_gold_readiness_gate,
    get_question_gold_resources,
)
from app.core.genai_limits import GOLD_REQUEST_TIMEOUT_SECONDS
from app.core.platform_identity import require_permission
from app.repositories.gold_publication import (
    GoldPublicationChanged,
    GoldPublicationUnavailable,
)
from app.repositories.panorama import PanoramaRepository, get_panorama_repository
from app.schemas.ai import (
    AIQueryRequest,
    AIQuestionError,
    AIQuestionErrorResponse,
    AIQuestionResponse,
)
from app.schemas.ai_insight import (
    AIInsightResponse,
    PanoramaInsightEnvelope,
    PanoramaInsightRequest,
)
from app.schemas.ai_question_publication import AIQuestionPublicRequest
from app.schemas.genai_audit import BackendAuditEvent
from app.schemas.genai_internal import AccessScope, QuestionPlanRequest
from app.schemas.sql_analysis import SqlAnalysisRequest, SqlAnalysisResponse
from app.services.analytics import AnalyticsAPIError
from app.services.genai_audit import AuditStore
from app.services.genai_client import (
    GenAIInsightClient,
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.genai_continuation import (
    InvalidContinuation,
    issue_context_continuation,
    issue_continuation,
    restore_continuation,
)
from app.services.genai_coordination import (
    GoldCoverageUnavailable,
    answer_gold_question,
)
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_executor import GoldExecutionDenied
from app.services.genai_expected_publication import (
    ExpectedPublicationMismatch,
    resolve_expected_batch_ref,
)
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_pipeline import run_sql_question
from app.services.gold_catalog import GoldCatalogIncompatible
from app.services.gold_panorama_coordination import generate_gold_panorama_insight
from app.services.panorama_insights import (
    StalePanoramaInsight,
    UnsupportedPanoramaInsight,
    build_panorama_insight,
)

router = APIRouter(dependencies=[Depends(require_permission("ai:ask"))])


def get_sql_genai_question_client(request: Request) -> GenAIQuestionClient:
    return request.app.state.genai_question_client


@router.post("/sql-analyses", response_model=SqlAnalysisResponse)
async def run_f1_sql_analysis(
    payload: SqlAnalysisRequest,
    request: Request,
    genai: Annotated[GenAIQuestionClient, Depends(get_sql_genai_question_client)],
    gold_resources: Annotated[tuple[Engine, Callable[[], AccessScope]] | None,
                              Depends(get_question_gold_resources)],
    db: Annotated[Session, Depends(get_db)],
):
    """Rota autenticada opt-in; entrega evidência sem expor SQL interno."""
    if not settings.GENAI_SQL_EXECUTION_ENABLED or settings.ANALYTICS_SOURCE != "gold":
        raise HTTPException(503, "Análise SQL indisponível.")
    if gold_resources is None or gold_resources[0] is None:
        raise HTTPException(503, "Leitura Gold indisponível.")
    engine, resolve_scope = gold_resources

    def resolve_f1_scope():
        current = resolve_scope()
        return current.model_copy(update={
            "allowed_metric_ids": frozenset({"billing.revenue"}),
            "allowed_dimension_ids": current.allowed_dimension_ids & {
                "geography.municipality", "customer.consumption_class",
            },
        })

    scope = resolve_f1_scope()
    if "billing.revenue" not in scope.allowed_metric_ids:
        raise HTTPException(403, "Métrica fora do acesso atual.")
    publication = GoldPublicationContext.capture(engine)
    fields = publication.planning_fields(engine, scope)
    remaining_ms = min(int(GOLD_REQUEST_TIMEOUT_SECONDS * 1000),
                       int(settings.AI_AGENT_TIMEOUT_SECONDS * 1000))
    plan_request = QuestionPlanRequest.model_validate({
        **payload.model_dump(mode="json"), "access_scope": scope.model_dump(mode="json"),
        "remaining_timeout_ms": remaining_ms, **fields,
    })
    deadline = GenAIRequestDeadline.start(remaining_ms / 1000)
    audit_store = AuditStore(db.get_bind())
    started = monotonic()

    async def record_audit(stage, code, outcome, *, row_count=0, evidence_ref=None,
                           model_calls=0, source_calls=0):
        event = BackendAuditEvent(
            correlation_id=request.state.correlation_id,
            stage=stage,
            code=code,
            outcome=outcome,
            duration_ms=max(0, int((monotonic() - started) * 1000)),
            row_count=row_count,
            model_calls=model_calls,
            source_calls=source_calls,
            batch_ref=publication.batch_ref,
            caller_ref=scope.caller_ref,
            metric_id="billing.revenue",
            source_id=scope.source_id,
            evidence_ref=evidence_ref,
        )
        try:
            return await deadline.run(
                GOLD_REQUEST_TIMEOUT_SECONDS,
                lambda: asyncio.to_thread(audit_store.record, event, service="backend"),
            )
        except (SQLAlchemyError, ValueError, GenAITimeout):
            raise GenAIServiceUnavailable(retryable=False) from None

    try:
        await record_audit("request", "started", "started")
    except GenAIServiceUnavailable:
        raise HTTPException(503, "A trilha de auditoria está indisponível.") from None

    async def record_failure(stage, code, outcome, *, model_calls=0):
        try:
            await record_audit(stage, code, outcome, model_calls=model_calls)
        except (GenAIServiceUnavailable, GenAITimeout):
            # O erro primário continua sem resposta quantitativa se a própria
            # trilha de auditoria também estiver indisponível.
            return

    try:
        run = await run_sql_question(
            plan_request, engine=engine, readiness_engine=db.get_bind(),
            publication=publication, client=genai, resolve_scope=resolve_f1_scope,
            approved_controls=frozenset(settings.GENAI_GOLD_APPROVED_CONTROLS),
            deadline=deadline, correlation_id=request.state.correlation_id,
        )
        publication.assert_current(engine)
        current_scope = resolve_f1_scope()
        if current_scope != scope:
            raise GoldExecutionDenied
        if run.evidence is not None:
            await record_audit(
                "source", "completed", "success", row_count=len(run.evidence.rows),
                evidence_ref=run.evidence.evidence_digest, source_calls=1,
            )
            outcome, code = "success", "available"
        elif run.candidate.status == "needs_clarification":
            outcome, code = "success", "clarification"
        else:
            outcome, code = "refused", "refused"
        audit_reference = await record_audit(
            "response", code, outcome,
            row_count=len(run.evidence.rows) if run.evidence is not None else 0,
            evidence_ref=run.evidence.evidence_digest if run.evidence is not None else None,
            model_calls=1,
        )
        publication.assert_current(engine)
        if resolve_f1_scope() != scope:
            raise GoldExecutionDenied
        return SqlAnalysisResponse.from_run(
            request.state.correlation_id, run, audit_reference=audit_reference,
        )
    except GoldExecutionDenied:
        await record_failure("policy", "denied", "refused")
        raise HTTPException(403, "A consulta não está autorizada com o acesso atual.") from None
    except GoldPublicationChanged:
        await record_failure("source", "invalid", "error")
        raise HTTPException(409, "A publicação Gold mudou. Refaça a pergunta.") from None
    except (GoldPublicationUnavailable, GoldCoverageUnavailable, SQLAlchemyError):
        await record_failure("source", "unavailable", "error")
        raise HTTPException(503, "A análise Gold está temporariamente indisponível.") from None
    except GenAIServiceUnavailable:
        await record_failure("response", "unavailable", "error")
        raise HTTPException(503, "O serviço de resposta está temporariamente indisponível.") from None
    except GenAITimeout:
        await record_failure("response", "limit", "error")
        raise HTTPException(504, "O serviço de resposta excedeu o tempo limite.") from None
    except GenAIResponseInvalid:
        await record_failure("response", "invalid", "error")
        raise HTTPException(502, "O serviço de resposta não retornou um resultado válido.") from None

class AIQuestionRoute(APIRoute):
    """Retorna erro de validação estável sem ecoar valores da pergunta."""

    def __init__(self, *args, **kwargs):
        kwargs["responses"] = {
            401: {
                "model": AIQuestionErrorResponse,
                "description": "Sessão individual ausente ou inválida.",
            },
            403: {
                "model": AIQuestionErrorResponse,
                "description": "Consulta não autorizada pelo acesso atual.",
            },
            422: {
                "model": AIQuestionErrorResponse,
                "description": "Solicitação fora do contrato v1.",
            },
            409: {
                "model": AIQuestionErrorResponse,
                "description": "O lote dos indicadores mudou.",
            },
            502: {
                "model": AIQuestionErrorResponse,
                "description": "Resposta inválida do serviço GenAI.",
            },
            503: {
                "model": AIQuestionErrorResponse,
                "description": "Serviço GenAI indisponível.",
            },
            504: {
                "model": AIQuestionErrorResponse,
                "description": "Tempo limite do serviço GenAI.",
            },
            **(kwargs.get("responses") or {}),
        }
        super().__init__(*args, **kwargs)

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def ai_question_handler(request: Request):
            try:
                return await original_handler(request)
            except RequestValidationError:
                return _question_error(
                    request,
                    status_code=422,
                    code="invalid_request",
                    retryable=False,
                    message="A solicitação não segue o contrato v1.",
                )

            except SQLAlchemyError:
                return _question_error(request, status_code=503, code="service_unavailable",
                    retryable=True, message="O serviço está temporariamente indisponível.")

            except HTTPException as exc:
                if exc.status_code in {401, 403}:
                    return _question_error(
                        request, status_code=exc.status_code,
                        code="access_denied", retryable=False,
                        message="A consulta não está autorizada com o acesso atual.",
                    )
                if exc.status_code != 503:
                    raise
                return _question_error(
                    request, status_code=503, code="service_unavailable",
                    retryable=False,
                    message="O serviço de resposta está temporariamente indisponível.",
                )

        return progressive_handler(ai_question_handler)


questions_router = APIRouter(
    route_class=AIQuestionRoute,
    dependencies=[Depends(require_permission("ai:ask"))],
)
insights_router = APIRouter(
    route_class=AIQuestionRoute,
    dependencies=[
        Depends(require_permission("ai:ask")),
        Depends(require_permission("panorama:read")),
    ],
)


def _question_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    retryable: bool,
    message: str,
) -> JSONResponse:
    body = AIQuestionErrorResponse(
        correlation_id=request.state.correlation_id,
        message=message,
        error=AIQuestionError(code=code, retryable=retryable),
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={"X-Correlation-ID": request.state.correlation_id},
    )


def get_genai_question_client(request: Request) -> GenAIQuestionClient:
    return request.app.state.genai_question_client


def get_genai_insight_client(request: Request) -> GenAIInsightClient:
    return request.app.state.genai_insight_client


@router.post(
    "/query",
    response_model=AIQuestionErrorResponse,
    status_code=503,
    summary="Consulta analítica legada ainda indisponível",
)
def query_analytical_data(
    payload: AIQueryRequest, request: Request
) -> AIQuestionErrorResponse:
    """O contrato legado não executa Gold e nunca deve simular sucesso."""

    return AIQuestionErrorResponse(
        correlation_id=request.state.correlation_id,
        message="A consulta analítica ainda não está disponível.",
        error=AIQuestionError(code="service_unavailable", retryable=False),
    )


@questions_router.post(
    "/questions",
    response_model=AIQuestionResponse,
    summary="Envia uma pergunta conversacional ao serviço GenAI",
)
async def ask_genai_question(
    payload: AIQuestionPublicRequest,
    request: Request,
    genai: Annotated[GenAIQuestionClient, Depends(get_genai_question_client)],
    gold_resources: Annotated[
        tuple[Engine | None, Callable[[], AccessScope]] | None, Depends(get_question_gold_resources)
    ],
    readiness_gate: Annotated[Callable | None, Depends(get_question_gold_readiness_gate)],
    db: Annotated[Session, Depends(get_db)],
) -> AIQuestionResponse | JSONResponse:
    """Coordena consulta e contexto curto autenticado, sem persistir histórico."""

    question = payload.without_publication()
    deadline = GenAIRequestDeadline.start(GOLD_REQUEST_TIMEOUT_SECONDS)
    try:
        if gold_resources is not None:
            engine, resolve_scope = gold_resources
            expected_batch_ref = None
            secret = (settings.AI_AGENT_SERVICE_API_TOKEN.get_secret_value()
                      if settings.AI_AGENT_SERVICE_API_TOKEN is not None else None)
            session = request.cookies.get("grid360_session", "")
            if payload.continuation_token is not None:
                if not secret or not session or not payload.conversation_id:
                    raise InvalidContinuation
                scope = await deadline.run(GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(resolve_scope))
                expected_batch_ref, restored = restore_continuation(
                    payload.continuation_token, scope, session=session,
                    conversation=payload.conversation_id, secret=secret,
                    context=question.context,
                )
                question = question.model_copy(update={"context": restored})
            if payload.expected_publication is not None:
                displayed_batch = await deadline.run(
                    GOLD_REQUEST_TIMEOUT_SECONDS, lambda: asyncio.to_thread(
                        resolve_expected_batch_ref, db.get_bind(), payload.expected_publication,
                    ),
                )
                if expected_batch_ref is not None and expected_batch_ref != displayed_batch:
                    raise InvalidContinuation
                expected_batch_ref = displayed_batch

            def continuation(planned, response):
                if not secret or not session or not payload.conversation_id:
                    return None
                if planned.response.pending_question is not None:
                    return issue_context_continuation(
                        planned.response.pending_question, planned.access_scope,
                        planned.publication.batch_ref, session=session,
                        conversation=payload.conversation_id, secret=secret, kind="pending",
                        response_text=response.message or "",
                    )
                return issue_continuation(
                    planned.response.plan, planned.access_scope, planned.publication.batch_ref,
                    session=session, conversation=payload.conversation_id, secret=secret,
                    response_text=response.answer or response.message or "",
                )

            result = await answer_gold_question(
                engine, genai, question, resolve_scope=resolve_scope,
                correlation_id=request.state.correlation_id,
                readiness_gate=readiness_gate,
                audit_store=AuditStore(db.get_bind()),
                expected_batch_ref=expected_batch_ref,
                continuation=continuation,
                request_deadline=deadline,
                on_visual=getattr(request.state, "publish_visual", None),
            )
        else:
            if payload.continuation_token is not None:
                raise InvalidContinuation
            if payload.expected_publication is not None:
                return _question_error(
                    request, status_code=422, code="invalid_request", retryable=False,
                    message="A publicação esperada só se aplica à fonte Gold.",
                )
            result = await genai.ask(
                question, correlation_id=request.state.correlation_id,
            )
    except InvalidContinuation:
        return _question_error(
            request, status_code=409, code="invalid_continuation", retryable=False,
            message="O contexto anterior não é mais válido. Inicie uma nova conversa.",
        )
    except ExpectedPublicationMismatch:
        return _question_error(
            request, status_code=409, code="invalid_context", retryable=False,
            message="Os dados da tela foram atualizados. Recarregue a tela antes de perguntar.",
        )
    except GoldCatalogIncompatible:
        return _question_error(
            request, status_code=503, code="service_unavailable", retryable=False,
            message="O catálogo Gold dos serviços não é compatível; a consulta não foi executada.",
        )
    except GoldExecutionDenied:
        return _question_error(
            request, status_code=403, code="access_denied", retryable=False,
            message="A consulta não está autorizada com o acesso atual.",
        )
    except GoldPublicationChanged:
        return _question_error(
            request, status_code=409, code="invalid_context", retryable=True,
            message="A publicação Gold mudou. Refaça a pergunta.",
        )
    except GoldPublicationUnavailable:
        return _question_error(
            request, status_code=503, code="service_unavailable", retryable=False,
            message="A publicação Gold não está disponível para esta consulta.",
        )
    except SQLAlchemyError:
        return _question_error(
            request, status_code=503, code="service_unavailable", retryable=True,
            message="A consulta Gold está temporariamente indisponível.",
        )
    except GoldCoverageUnavailable:
        return _question_error(
            request, status_code=503, code="service_unavailable", retryable=False,
            message="Os dados disponíveis não têm cobertura suficiente para responder "
                    "a esse indicador no recorte solicitado. Tente outro período ou indicador.",
        )
    except GenAIServiceUnavailable as exc:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=exc.retryable,
            message="O serviço de resposta está temporariamente indisponível.",
        )
    except GenAITimeout:
        return _question_error(
            request,
            status_code=504,
            code="service_unavailable",
            retryable=True,
            message="O serviço de resposta excedeu o tempo limite.",
        )
    except GenAIResponseInvalid:
        return _question_error(
            request,
            status_code=502,
            code="invalid_upstream_response",
            retryable=False,
            message="O serviço de resposta não retornou um resultado válido.",
        )

    return result


def get_panorama_insight_repository() -> PanoramaRepository | None:
    if settings.ANALYTICS_SOURCE == "gold":
        return None
    return get_panorama_repository()


@insights_router.post(
    "/insights",
    response_model=PanoramaInsightEnvelope,
    summary="Gera insight contextual do Panorama",
)
async def generate_panorama_insight(
    payload: PanoramaInsightRequest,
    request: Request,
    repository: Annotated[PanoramaRepository | None, Depends(get_panorama_insight_repository)],
    genai: Annotated[GenAIInsightClient, Depends(get_genai_insight_client)],
    gold_resources: Annotated[
        tuple[Engine, Callable[[], AccessScope]] | None, Depends(get_question_gold_resources)
    ],
    readiness_client: Annotated[GenAIQuestionClient, Depends(get_genai_question_client)],
    db: Annotated[Session, Depends(get_db)],
) -> PanoramaInsightEnvelope | JSONResponse:
    """Monta os números no servidor e os envia pelo contrato de insight v1."""

    try:
        if gold_resources is not None:
            engine, resolve_scope = gold_resources
            return await generate_gold_panorama_insight(
                engine, db.get_bind(), genai, readiness_client, payload,
                resolve_scope=resolve_scope, correlation_id=request.state.correlation_id,
                audit_store=AuditStore(db.get_bind()),
                approved_controls=settings.GENAI_GOLD_APPROVED_CONTROLS,
            )
        insight_request, metric, source, analysis = build_panorama_insight(
            repository, payload
        )
    except GoldExecutionDenied:
        return _question_error(request, status_code=403, code="access_denied", retryable=False,
            message="A interpretação não está autorizada com o acesso atual.")
    except GoldPublicationChanged:
        return _question_error(request, status_code=409, code="invalid_context", retryable=False,
            message="O lote mudou. Atualize o Panorama antes de gerar o insight.")
    except (GoldPublicationUnavailable, SQLAlchemyError, GenAIServiceUnavailable):
        return _question_error(request, status_code=503, code="service_unavailable", retryable=False,
            message="A interpretação Gold está temporariamente indisponível.")
    except GenAITimeout:
        return _question_error(request, status_code=504, code="service_unavailable", retryable=True,
            message="A interpretação excedeu o tempo limite.")
    except GenAIResponseInvalid:
        return _question_error(request, status_code=502, code="invalid_upstream_response", retryable=False,
            message="A interpretação não corresponde ao recorte solicitado.")
    except StalePanoramaInsight:
        return _question_error(
            request,
            status_code=409,
            code="invalid_context",
            retryable=False,
            message="O lote dos indicadores mudou. Atualize o Panorama antes de gerar o insight.",
        )
    except UnsupportedPanoramaInsight:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=False,
            message="A fonte atual ainda não permite gerar este insight.",
        )
    except AnalyticsAPIError:
        return _question_error(
            request,
            status_code=422,
            code="invalid_request",
            retryable=False,
            message="Os filtros do insight não são válidos para o Panorama.",
        )

    if isinstance(insight_request, AIInsightResponse):
        return PanoramaInsightEnvelope(
            insight=insight_request.model_copy(
                update={"correlation_id": request.state.correlation_id}
            ),
            metric=metric, source=source, analysis=analysis,
        )

    try:
        result = await genai.generate(
            insight_request,
            correlation_id=request.state.correlation_id,
        )
    except GenAIServiceUnavailable as exc:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=exc.retryable,
            message="O serviço de insight está temporariamente indisponível.",
        )
    except GenAITimeout:
        return _question_error(
            request,
            status_code=504,
            code="service_unavailable",
            retryable=True,
            message="O serviço de insight excedeu o tempo limite.",
        )
    except GenAIResponseInvalid:
        return _question_error(
            request,
            status_code=502,
            code="invalid_upstream_response",
            retryable=False,
            message="O serviço de insight não retornou um resultado válido.",
        )

    if result.status == "answered":
        expected_screen = insight_request.screen
        if (
            result.context.model_dump(mode="json")
            != expected_screen.model_dump(
                mode="json", exclude={"observations", "reference", "limitations"}
            )
            or [item.model_dump(mode="json") for item in result.observation.values]
            != [item.model_dump(mode="json") for item in expected_screen.observations]
            or any(not item.is_demo for item in result.evidence)
        ):
            return _question_error(
                request,
                status_code=502,
                code="invalid_upstream_response",
                retryable=False,
                message="O serviço de insight retornou outro recorte de indicadores.",
            )

    return PanoramaInsightEnvelope(
        insight=result, metric=metric, source=source, analysis=analysis
    )
