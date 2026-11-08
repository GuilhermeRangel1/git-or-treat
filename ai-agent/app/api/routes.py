"""Rotas públicas do serviço, agrupadas sob o contrato da API v1."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.agent.execution import ExecutionLimitExceeded
from app.api.access import require_service_auth, resolve_access_context
from app.api.errors import ServiceAuthenticationError
from app.ports.events import AuditUnavailable
from app.providers.protocols import (
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.readiness.models import PublicationFacts, ReadinessReport
from app.schemas.access import AccessContext
from app.schemas.capabilities import CapabilitiesResponse
from app.schemas.insights import (
    GoldScreenInsightRequest,
    ScreenInsightRequest,
    ScreenInsightResponse,
)
from app.schemas.internal import (
    QuestionPlanRequest,
    QuestionPlanResponse,
    QuestionPlanStatus,
    QuestionSynthesisRequest,
)
from app.schemas.questions import QuestionRequest, QuestionResponse
from app.schemas.responses import PublicError, PublicErrorCode, PublicErrorResponse
from app.schemas.sql_generation import SqlGenerationRequest, SqlGenerationResponse

router = APIRouter()
ResolvedAccess = Annotated[AccessContext | None, Depends(resolve_access_context)]


def require_gold_auth(request: Request) -> None:
    """A borda de planejamento Gold exige composição externa e token configurado."""
    if (
        request.app.state.service_api_token is None
        or request.app.state.source_mode != "external"
        or request.app.state.source_id != "gold.local"
        or request.app.state.domain_profile.profile_id != "v-energy-grid-360-gold"
    ):
        raise ServiceAuthenticationError(configured=False)
    require_service_auth(request, request.headers.get("authorization"))


@router.post(
    "/api/v1/internal/sql-candidates", response_model=SqlGenerationResponse,
    dependencies=[Depends(require_gold_auth)],
)
async def generate_sql_candidate(payload: SqlGenerationRequest, request: Request):
    service = request.app.state.sql_candidate_service
    retryable = False
    status = 503
    code = PublicErrorCode.SERVICE_UNAVAILABLE
    try:
        if service is not None:
            return await service.generate(payload, request.state.correlation_id)
    except (ExecutionLimitExceeded, ModelProviderUnavailable):
        retryable = True
    except ModelProviderInvalidResponse:
        status = 502
        code = PublicErrorCode.INVALID_UPSTREAM_RESPONSE
    except (AuditUnavailable, ModelProviderRejected):
        pass
    body = PublicErrorResponse(
        correlation_id=request.state.correlation_id,
        error=PublicError(code=code, retryable=retryable),
        message="Não foi possível concluir a geração de candidato SQL.",
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


@router.post(
    "/api/v1/internal/question-plans",
    response_model=QuestionPlanResponse,
    dependencies=[Depends(require_gold_auth)],
)
async def plan_question(payload: QuestionPlanRequest, request: Request) -> QuestionPlanResponse:
    """Recebe escopo e cobertura do Backend autenticado, sem consultar fonte ou modelo."""
    response = await request.app.state.question_orchestrator.plan(
        payload, request.state.correlation_id
    )
    catalog = request.app.state.domain_profile.physical_catalog
    if response.status is not QuestionPlanStatus.PLANNED or catalog is None:
        return response
    # O Backend recusa executar plano produzido sob outro catálogo físico.
    return QuestionPlanResponse.model_validate(
        {**response.model_dump(mode="json"), "physical_catalog": catalog.model_dump(mode="json")}
    )


@router.post(
    "/api/v1/internal/question-syntheses",
    response_model=QuestionResponse,
    dependencies=[Depends(require_gold_auth)],
)
async def synthesize_question(
    payload: QuestionSynthesisRequest, request: Request
) -> QuestionResponse:
    """Revalida plano, escopo e lookup do Backend antes da resposta fundamentada."""
    response = await request.app.state.question_orchestrator.synthesize(
        payload, request.state.correlation_id
    )
    return response.model_copy(update={"correlation_id": request.state.correlation_id})


def require_readiness_auth(request: Request) -> None:
    """Prontidão real nunca herda a dispensa de token da demonstração local."""
    if request.app.state.service_api_token is None:
        raise ServiceAuthenticationError(configured=False)
    require_service_auth(request, request.headers.get("authorization"))


@router.post(
    "/api/v1/internal/gold-readiness",
    response_model=ReadinessReport,
    dependencies=[Depends(require_readiness_auth)],
)
async def gold_readiness(payload: PublicationFacts, request: Request) -> ReadinessReport:
    handler = request.app.state.readiness_handler
    if handler is None:
        raise ServiceAuthenticationError(configured=False)
    return handler(payload)


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Indica liveness do processo, sem expor configuração ou dependências internas."""

    return {"status": "ok"}


@router.get("/api/v1/internal/runtime-status", dependencies=[Depends(require_gold_auth)])
async def runtime_status(request: Request) -> dict:
    """Diagnóstico autenticado de configuração; não comprova conectividade do provedor."""
    active = request.app.state.runtime_settings
    configured = (
        active.model_provider == "gemini" and active.gemini_api_key is not None
        or active.model_provider == "groq" and active.groq_api_key is not None
    )
    return {
        "source": request.app.state.source_id,
        "schema_version": "gold-csv-v2",
        "catalog": request.app.state.domain_profile.physical_catalog.model_dump(mode="json"),
        "audit_configured": active.audit_url is not None and active.audit_write_token is not None,
        "generation_configured": configured,
        "sql_generation_enabled": active.sql_generation_enabled,
        "sql_generation_configured": request.app.state.sql_candidate_service is not None,
        "routing_enabled": active.model_routing_enabled,
        "cache_enabled": active.model_cache_ttl_seconds > 0,
        "limits": {
            name: getattr(active, name) for name in (
                "request_timeout_ms", "source_timeout_ms", "model_timeout_ms",
                "model_total_timeout_ms", "model_max_calls", "concurrent_requests",
                "concurrent_models", "evidence_max_rows", "evidence_max_bytes",
            )
        },
    }


@router.get("/api/v1/capabilities", response_model=CapabilitiesResponse)
async def capabilities() -> CapabilitiesResponse:
    """Descreve o contrato disponível sem divulgar segredos ou estado interno."""

    return CapabilitiesResponse(
        api_version="v1",
        question_endpoint="/api/v1/questions",
        insight_endpoint="/api/v1/insights",
        requires_gold=False,
        requires_model=False,
    )


@router.post(
    "/api/v1/questions",
    response_model=QuestionResponse,
    dependencies=[Depends(require_service_auth)],
    responses={
        422: {"model": PublicErrorResponse, "description": "Solicitação fora do contrato v1."},
        500: {"model": PublicErrorResponse, "description": "Falha interna controlada."},
    },
)
async def ask_question(
    payload: QuestionRequest,
    request: Request,
    access_context: ResolvedAccess,
) -> QuestionResponse:
    """Recebe pergunta com contexto limitado e delega ao orquestrador injetado."""

    response = await request.app.state.question_orchestrator.answer(
        payload, access_context, request.state.correlation_id
    )
    return response.model_copy(update={"correlation_id": request.state.correlation_id})


@router.post(
    "/api/v1/insights",
    response_model=ScreenInsightResponse,
    dependencies=[Depends(require_service_auth)],
    responses={
        422: {"model": PublicErrorResponse, "description": "Solicitação fora do contrato v1."},
        503: {"model": PublicErrorResponse, "description": "Insight indisponível para a fonte."},
        500: {"model": PublicErrorResponse, "description": "Falha interna controlada."},
    },
)
async def generate_screen_insight(
    payload: ScreenInsightRequest,
    request: Request,
    access_context: ResolvedAccess,
) -> ScreenInsightResponse | JSONResponse:
    """Gera hipótese exploratória a partir do recorte estruturado enviado pelo portal."""

    if request.app.state.source_mode == "external":
        body = PublicErrorResponse(
            correlation_id=request.state.correlation_id,
            error=PublicError(code=PublicErrorCode.SERVICE_UNAVAILABLE, retryable=False),
            message="O insight para esta fonte ainda não está disponível.",
        )
        return JSONResponse(
            status_code=503,
            content=body.model_dump(mode="json"),
            headers={"X-Correlation-ID": request.state.correlation_id},
        )
    response = await request.app.state.insight_orchestrator.generate(
        payload.screen, access_context, request.state.correlation_id
    )
    return response.model_copy(update={"correlation_id": request.state.correlation_id})


@router.post(
    "/api/v1/internal/insight-syntheses",
    response_model=ScreenInsightResponse,
    dependencies=[Depends(require_gold_auth)],
)
async def synthesize_gold_insight(
    payload: GoldScreenInsightRequest,
    request: Request,
) -> ScreenInsightResponse | JSONResponse:
    """Interpreta somente contexto recalculado e autorizado pelo Backend."""
    try:
        async with asyncio.timeout(payload.remaining_timeout_ms / 1000):
            response = await request.app.state.insight_orchestrator.generate(
                payload.screen,
                payload.access_scope.to_context(request.state.correlation_id),
                request.state.correlation_id,
            )
    except TimeoutError:
        return JSONResponse(
            status_code=503,
            content=PublicErrorResponse(
                correlation_id=request.state.correlation_id,
                error=PublicError(code=PublicErrorCode.SERVICE_UNAVAILABLE, retryable=True),
                message="O prazo da interpretação foi excedido. Tente novamente.",
            ).model_dump(mode="json"),
        )
    return response.model_copy(update={"correlation_id": request.state.correlation_id})
