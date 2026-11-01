from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.genai_gold_database import (
    get_question_gold_readiness_gate,
    get_question_gold_resources,
)
from app.repositories.gold_publication import GoldPublicationChanged
from app.repositories.panorama import PanoramaRepository, get_panorama_repository
from app.schemas.ai import (
    AIQueryRequest,
    AIQuestionError,
    AIQuestionErrorResponse,
    AIQuestionRequest,
    AIQuestionResponse,
)
from app.schemas.ai_insight import (
    AIInsightResponse,
    PanoramaInsightEnvelope,
    PanoramaInsightRequest,
)
from app.schemas.genai_internal import AccessScope
from app.services.analytics import AnalyticsAPIError
from app.services.genai_audit import AuditStore
from app.services.genai_client import (
    GenAIInsightClient,
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.genai_coordination import answer_gold_question
from app.services.genai_executor import GoldExecutionDenied
from app.services.panorama_insights import (
    StalePanoramaInsight,
    UnsupportedPanoramaInsight,
    build_panorama_insight,
)

router = APIRouter()

class AIQuestionRoute(APIRoute):
    """Retorna erro de validação estável sem ecoar valores da pergunta."""

    def __init__(self, *args, **kwargs):
        kwargs["responses"] = {
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

            except HTTPException as exc:
                if exc.status_code != 503:
                    raise
                return _question_error(
                    request, status_code=503, code="service_unavailable",
                    retryable=False,
                    message="O serviço de resposta está temporariamente indisponível.",
                )

        return ai_question_handler


questions_router = APIRouter(route_class=AIQuestionRoute)
insights_router = APIRouter(route_class=AIQuestionRoute)


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
    payload: AIQuestionRequest,
    request: Request,
    genai: Annotated[GenAIQuestionClient, Depends(get_genai_question_client)],
    gold_resources: Annotated[
        tuple[Engine, Callable[[], AccessScope]] | None, Depends(get_question_gold_resources)
    ],
    readiness_gate: Annotated[Callable | None, Depends(get_question_gold_readiness_gate)],
    db: Annotated[Session, Depends(get_db)],
) -> AIQuestionResponse | JSONResponse:
    """Encaminha pergunta e contexto transitório sem acessar banco ou persistir sessão."""

    try:
        if gold_resources is not None:
            engine, resolve_scope = gold_resources
            result = await answer_gold_question(
                engine, genai, payload, resolve_scope=resolve_scope,
                correlation_id=request.state.correlation_id,
                readiness_gate=readiness_gate,
                audit_store=AuditStore(db.get_bind()),
            )
        else:
            result = await genai.ask(
                payload, correlation_id=request.state.correlation_id,
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
    except SQLAlchemyError:
        return _question_error(
            request, status_code=503, code="service_unavailable", retryable=True,
            message="A consulta Gold está temporariamente indisponível.",
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


@insights_router.post(
    "/insights",
    response_model=PanoramaInsightEnvelope,
    summary="Gera insight contextual do Panorama",
)
async def generate_panorama_insight(
    payload: PanoramaInsightRequest,
    request: Request,
    repository: Annotated[PanoramaRepository, Depends(get_panorama_repository)],
    genai: Annotated[GenAIInsightClient, Depends(get_genai_insight_client)],
) -> PanoramaInsightEnvelope | JSONResponse:
    """Monta os números no servidor e os envia pelo contrato de insight v1."""

    try:
        insight_request, metric, source, analysis = build_panorama_insight(
            repository, payload
        )
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
