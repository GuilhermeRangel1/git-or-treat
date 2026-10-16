"""Coordena evidência e geração sem acoplar o serviço a um fornecedor."""

import re
from decimal import Decimal, InvalidOperation

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
_NUMBER = re.compile(r"(?<!\w)[+-]?\d[\d.,]*(?:\s*%)?(?!\w)")


def _decimal_token(value: str) -> Decimal | None:
    normalized = value.strip().replace("%", "").replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        left, right = normalized.rsplit(",", maxsplit=1)
        normalized = f"{left.replace(',', '')}.{right}"
    elif normalized.count(".") > 1 or (
        normalized.count(".") == 1 and len(normalized.rsplit(".", maxsplit=1)[1]) == 3
    ):
        normalized = normalized.replace(".", "")
        normalized = normalized.replace(".", "")
    try:
        return Decimal(normalized).normalize()
    except InvalidOperation:
        return None


def _evidence_numbers(value: object) -> set[Decimal]:
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, (int, float, Decimal)):
        try:
            return {Decimal(str(value)).normalize()}
        except InvalidOperation:
            return set()
    if isinstance(value, str):
        return {
            number
            for match in _NUMBER.finditer(value)
            if (number := _decimal_token(match.group())) is not None
        }
    if isinstance(value, dict):
        return set().union(*(_evidence_numbers(item) for item in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(_evidence_numbers(item) for item in value))
    return set()


def _contains_only_evidence_numbers(answer: str, records: list[dict[str, object]]) -> bool:
    allowed = _evidence_numbers(records)
    claimed = [
        number
        for match in _NUMBER.finditer(answer)
        if (number := _decimal_token(match.group())) is not None
    ]
    return all(number in allowed for number in claimed)


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
        if refusal is not None:
            return QuestionResponse(status=QuestionStatus.REFUSED, answer=refusal)

        try:
            plan = self._analysis_planner.prepare(request.question)
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

        if generated.status == "answered" and not _contains_only_evidence_numbers(
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
