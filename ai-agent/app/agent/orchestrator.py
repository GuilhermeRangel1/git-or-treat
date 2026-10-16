"""Coordena evidência e geração sem acoplar o serviço a um fornecedor."""

from app.providers.protocols import ModelAdapter, ModelProviderUnavailable
from app.schemas.questions import QuestionRequest, QuestionResponse, QuestionStatus
from app.tools.evidence import EvidenceTool, EvidenceToolUnavailable


NO_EVIDENCE_MESSAGE = (
    "Ainda não há uma fonte analítica configurada para responder com evidências."
)
RECOVERABLE_ERROR_MESSAGE = (
    "O serviço de resposta está temporariamente indisponível. Tente novamente."
)


class QuestionOrchestrator:
    def __init__(self, evidence_tool: EvidenceTool, model_adapter: ModelAdapter) -> None:
        self._evidence_tool = evidence_tool
        self._model_adapter = model_adapter

    async def answer(self, request: QuestionRequest) -> QuestionResponse:
        try:
            evidence = await self._evidence_tool.retrieve(request.question, request.context)
        except EvidenceToolUnavailable:
            return self._recoverable_error()

        if evidence is None or not evidence.records:
            return QuestionResponse(status=QuestionStatus.NO_EVIDENCE, message=NO_EVIDENCE_MESSAGE)

        try:
            generated = await self._model_adapter.generate(
                request.question,
                request.context,
                evidence,
            )
        except ModelProviderUnavailable:
            return self._recoverable_error()

        return QuestionResponse(
            status=QuestionStatus(generated.status),
            answer=generated.answer,
            evidence=[evidence.reference],
        )

    @staticmethod
    def _recoverable_error() -> QuestionResponse:
        return QuestionResponse(
            status=QuestionStatus.RECOVERABLE_ERROR,
            message=RECOVERABLE_ERROR_MESSAGE,
        )
