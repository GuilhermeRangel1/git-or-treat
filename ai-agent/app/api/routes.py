"""Rotas públicas do serviço, agrupadas sob o contrato da API v1."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.access import require_service_auth, resolve_access_context
from app.schemas.access import AccessContext
from app.schemas.capabilities import CapabilitiesResponse
from app.schemas.insights import ScreenInsightRequest, ScreenInsightResponse
from app.schemas.questions import QuestionRequest, QuestionResponse
from app.schemas.responses import PublicError, PublicErrorCode, PublicErrorResponse

router = APIRouter()
ResolvedAccess = Annotated[AccessContext | None, Depends(resolve_access_context)]


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Indica liveness do processo, sem expor configuração ou dependências internas."""

    return {"status": "ok"}


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
