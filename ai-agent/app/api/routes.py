"""Rotas públicas do serviço, agrupadas sob o contrato da API v1."""

from fastapi import APIRouter, Request

from app.schemas.capabilities import CapabilitiesResponse
from app.schemas.questions import QuestionRequest, QuestionResponse

router = APIRouter()


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
        requires_gold=False,
        requires_model=False,
    )


@router.post("/api/v1/questions", response_model=QuestionResponse)
async def ask_question(payload: QuestionRequest, request: Request) -> QuestionResponse:
    """Recebe pergunta com contexto limitado e delega ao orquestrador injetado."""

    return await request.app.state.question_orchestrator.answer(payload)
