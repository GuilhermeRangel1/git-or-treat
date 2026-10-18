"""Coordena evidência e geração sem acoplar o serviço a um fornecedor."""

import logging

from pydantic import ValidationError

from app.agent.grounding import contains_only_evidence_numbers
from app.agent.planner import AnalysisPlanStatus, QuestionAnalysisPlanner
from app.agent.safety import QuestionSafetyGate, SafetyRefusalCode
from app.ports.evidence import (
    EvidenceAccessDenied,
    EvidenceContractInvalid,
    EvidenceToolUnavailable,
)
from app.providers.protocols import GeneratedAnswer, ModelAdapter, ModelProviderUnavailable
from app.schemas.access import AccessContext
from app.schemas.evidence import EvidenceLookupStatus
from app.schemas.questions import QuestionRequest, QuestionResponse, QuestionStatus
from app.schemas.responses import FailureCode, map_failure

logger = logging.getLogger(__name__)


class QuestionOrchestrator:
    def __init__(
        self,
        analysis_planner: QuestionAnalysisPlanner,
        model_adapter: ModelAdapter,
        safety_gate: QuestionSafetyGate | None = None,
    ) -> None:
        self._analysis_planner = analysis_planner
        self._model_adapter = model_adapter
        self._safety_gate = safety_gate or QuestionSafetyGate()

    async def answer(
        self,
        request: QuestionRequest,
        access_context: AccessContext | None = None,
    ) -> QuestionResponse:
        if access_context is None:
            return self._refused(FailureCode.ACCESS_DENIED)
        refusal = self._safety_gate.refusal_code(request.question)
        for turn in request.context:
            if refusal is not None:
                break
            refusal = self._safety_gate.refusal_code(turn.content)
        if refusal is not None:
            code = (
                FailureCode.OUT_OF_SCOPE
                if refusal is SafetyRefusalCode.OUT_OF_SCOPE
                else FailureCode.SECURITY_VIOLATION
            )
            return self._refused(code)

        try:
            plan = await self._analysis_planner.prepare(
                request.question, request.context, access_context
            )
        except EvidenceAccessDenied:
            return self._refused(FailureCode.ACCESS_DENIED)
        except EvidenceContractInvalid:
            logger.warning("A fonte de evidências retornou um contrato inválido.")
            return self._recoverable_error(FailureCode.INVALID_SOURCE_RESPONSE)
        except EvidenceToolUnavailable:
            logger.warning("Falha ao consultar a fonte de evidências.")
            return self._recoverable_error(FailureCode.SOURCE_UNAVAILABLE)
        if plan.status is AnalysisPlanStatus.NEEDS_CLARIFICATION:
            question = plan.interpretation.clarification_question
            if plan.evidence_result is not None:
                question = plan.evidence_result.message
            return QuestionResponse(
                status=QuestionStatus.NEEDS_CLARIFICATION,
                message=question,
            )
        if plan.status is AnalysisPlanStatus.NO_EVIDENCE:
            assert plan.evidence_result is not None
            return QuestionResponse(
                status=QuestionStatus.NO_EVIDENCE,
                message=plan.evidence_result.message,
                limitations=plan.evidence_result.limitations,
            )
        if (
            plan.evidence_result is None
            or plan.evidence_result.status is not EvidenceLookupStatus.AVAILABLE
            or plan.evidence_result.evidence is None
        ):
            return self._recoverable_error(FailureCode.INVALID_SOURCE_RESPONSE)
        evidence = plan.evidence_result.evidence
        try:
            generated_result = await self._model_adapter.generate(
                request.question,
                request.context,
                evidence,
            )
            generated = GeneratedAnswer.model_validate(
                generated_result.model_dump()
                if isinstance(generated_result, GeneratedAnswer)
                else generated_result
            )
        except ModelProviderUnavailable:
            return self._recoverable_error(FailureCode.MODEL_UNAVAILABLE)
        except (ValidationError, TypeError, ValueError):
            logger.warning("O adaptador de modelo retornou uma resposta inválida.")
            return self._recoverable_error(FailureCode.INVALID_MODEL_OUTPUT)
        except Exception:
            logger.warning("Falha ao gerar resposta pelo adaptador de modelo.")
            return self._recoverable_error(FailureCode.UNEXPECTED)

        if generated.status == "answered" and not contains_only_evidence_numbers(
            generated.answer,
            evidence.records,
        ):
            return QuestionResponse(
                status=QuestionStatus.REFUSED,
                message=map_failure(FailureCode.UNGROUNDED_OUTPUT).message,
                evidence=[evidence.reference],
                limitations=plan.evidence_result.limitations,
                error=map_failure(FailureCode.UNGROUNDED_OUTPUT).error,
            )

        answer = generated.answer if generated.status == "answered" else None
        message = generated.answer if generated.status != "answered" else None
        if answer is not None and evidence.reference.is_demo:
            answer = f"Demonstração sintética: {answer}"

        error = (
            map_failure(FailureCode.POLICY_REFUSAL).error
            if generated.status == "refused"
            else None
        )

        return QuestionResponse(
            status=QuestionStatus(generated.status),
            answer=answer,
            message=(
                map_failure(FailureCode.POLICY_REFUSAL).message
                if error is not None
                else message
            ),
            evidence=[evidence.reference],
            limitations=plan.evidence_result.limitations,
            error=error,
        )

    @staticmethod
    def _recoverable_error(code: FailureCode) -> QuestionResponse:
        failure = map_failure(code)
        return QuestionResponse(
            status=QuestionStatus.RECOVERABLE_ERROR,
            message=failure.message,
            error=failure.error,
        )

    @staticmethod
    def _refused(code: FailureCode) -> QuestionResponse:
        failure = map_failure(code)
        return QuestionResponse(
            status=QuestionStatus.REFUSED,
            message=failure.message,
            error=failure.error,
        )
