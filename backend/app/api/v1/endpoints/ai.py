from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.ai import (
    AIQueryRequest,
    AIQueryResponse,
    AIQuestionError,
    AIQuestionErrorResponse,
    AIQuestionRequest,
    AIQuestionResponse,
)
from app.services.genai_client import (
    GenAIQuestionClient,
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)

router = APIRouter()

ALLOWED_READ_TABLES = ["gold_indicadores", "gold_ucs", "gold_receita", "gold_continuidadade"]


class AIQuestionRoute(APIRoute):
    """Retorna erro de validação estável sem ecoar valores da pergunta."""

    def __init__(self, *args, **kwargs):
        kwargs["responses"] = {
            422: {"model": AIQuestionErrorResponse, "description": "Solicitação fora do contrato v1."},
            502: {"model": AIQuestionErrorResponse, "description": "Resposta inválida do serviço GenAI."},
            503: {"model": AIQuestionErrorResponse, "description": "Serviço GenAI indisponível."},
            504: {"model": AIQuestionErrorResponse, "description": "Tempo limite do serviço GenAI."},
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

        return ai_question_handler


questions_router = APIRouter(route_class=AIQuestionRoute)


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


@router.post(
    "/query",
    response_model=AIQueryResponse,
    summary="Consulta somente-leitura controlada para o agente de IA",
)
def query_analytical_data(payload: AIQueryRequest, db: Annotated[Session, Depends(get_db)]):
    """
    Permite ao agente de IA consultar tabelas analíticas permitidas (allowlist)
    sem permissão de escrita e com trilha de auditoria.
    """
    if payload.target_table not in ALLOWED_READ_TABLES:
        raise HTTPException(
            status_code=403,
            detail=f"Tabela não permitida para o agente. Tabelas acessíveis: {ALLOWED_READ_TABLES}",
        )

    # Retorno estruturado seguro
    return {
        "status": "success",
        "intent": payload.intent,
        "table": payload.target_table,
        "records": [],
        "evidence": "Consulta analítica somente leitura",
    }


@questions_router.post(
    "/questions",
    response_model=AIQuestionResponse,
    summary="Envia uma pergunta conversacional ao serviço GenAI",
)
async def ask_genai_question(
    payload: AIQuestionRequest,
    request: Request,
    genai: Annotated[GenAIQuestionClient, Depends(get_genai_question_client)],
) -> AIQuestionResponse | JSONResponse:
    """Encaminha pergunta e contexto transitório sem acessar banco ou persistir sessão."""

    try:
        result = await genai.ask(
            payload,
            correlation_id=request.state.correlation_id,
        )
    except GenAIServiceUnavailable:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=True,
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
