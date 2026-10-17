"""Coordena evidência e geração sem acoplar o serviço a um fornecedor."""

from app.agent.grounding import contains_only_evidence_numbers
from app.agent.planner import AnalysisPlanStatus, QuestionAnalysisPlanner, ScenarioToolUnavailable
from app.agent.safety import QuestionSafetyGate
from app.providers.protocols import ModelAdapter, ModelProviderUnavailable
from app.schemas.questions import QuestionRequest, QuestionResponse, QuestionStatus

RECOVERABLE_ERROR_MESSAGE = (
    "O serviço de resposta está temporariamente indisponível. Tente novamente."
)
UNGROUNDED_ANSWER_MESSAGE = (
    "Não consigo confirmar essa resposta com os dados sintéticos disponíveis."
)


class QuestionOrchestrator:
    def __init__(
        self,
        analysis_planner: QuestionAnalysisPlanner,
        model_adapter: ModelAdapter,
    ) -> None:
        self._analysis_planner = analysis_planner
        self._model_adapter = model_adapter
        self._safety_gate = QuestionSafetyGate()

    async def answer(self, request: QuestionRequest) -> QuestionResponse:
        refusal = self._safety_gate.refusal_reason(request.question)
        for turn in request.context:
            if refusal is not None:
                break
            refusal = self._safety_gate.refusal_reason(turn.content)
        if refusal is not None:
            return QuestionResponse(status=QuestionStatus.REFUSED, answer=refusal)

        try:
            plan = self._analysis_planner.prepare(request.question, request.context)
        except ScenarioToolUnavailable:
            return self._recoverable_error()
        if plan.status is AnalysisPlanStatus.NEEDS_CLARIFICATION:
            question = plan.interpretation.clarification_question
            if plan.tool_result is not None:
                question = plan.tool_result.message
            return QuestionResponse(
                status=QuestionStatus.NEEDS_CLARIFICATION,
                message=question,
            )
        if plan.status is AnalysisPlanStatus.NO_EVIDENCE:
            assert plan.tool_result is not None
            return QuestionResponse(
                status=QuestionStatus.NO_EVIDENCE,
                message=plan.tool_result.message,
                limitations=plan.tool_result.limitations,
            )
        if plan.tool_result is None or plan.tool_result.evidence is None:
            return self._recoverable_error()
        evidence = plan.tool_result.evidence
        try:
            generated = await self._model_adapter.generate(
                request.question,
                request.context,
                evidence,
            )
        except ModelProviderUnavailable:
            return self._recoverable_error()

        if generated.status == "answered" and not contains_only_evidence_numbers(
            generated.answer,
            evidence.records,
        ):
            return QuestionResponse(
                status=QuestionStatus.REFUSED,
                answer=UNGROUNDED_ANSWER_MESSAGE,
                evidence=[evidence.reference],
                limitations=plan.tool_result.limitations,
            )

        answer = generated.answer
        if generated.status == "answered" and evidence.reference.is_demo:
            answer = f"Demonstração sintética: {answer}"

        return QuestionResponse(
            status=QuestionStatus(generated.status),
            answer=answer,
            evidence=[evidence.reference],
            limitations=plan.tool_result.limitations,
        )

    @staticmethod
    def _recoverable_error() -> QuestionResponse:
        return QuestionResponse(
            status=QuestionStatus.RECOVERABLE_ERROR,
            message=RECOVERABLE_ERROR_MESSAGE,
        )
