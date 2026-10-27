"""Coordena evidência e geração sem acoplar o serviço a um fornecedor."""

import asyncio
import json
import logging
from contextlib import suppress

from pydantic import ValidationError

from app.agent.execution import (
    ExecutionController,
    ExecutionLimitExceeded,
    RequestBudget,
    authorized_cache_scope,
)
from app.agent.grounding import has_unsupported_claims
from app.agent.planner import AnalysisPlanStatus, QuestionAnalysisPlanner
from app.agent.safety import QuestionSafetyGate, SafetyRefusalCode
from app.ports.events import (
    AuditUnavailable,
    EventCode,
    EventOutcome,
    EventSink,
    EventStage,
    EventTrace,
    NoopEventSink,
)
from app.ports.evidence import (
    EvidenceAccessDenied,
    EvidenceContractInvalid,
    EvidenceToolUnavailable,
)
from app.providers.protocols import (
    GeneratedAnswer,
    ModelAdapter,
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.providers.routing import ModelRouter, ModelTier, escalate
from app.schemas.access import AccessContext
from app.schemas.evidence import EvidenceLookupStatus, EvidenceResult
from app.schemas.questions import (
    AppliedQueryContext,
    QuestionRequest,
    QuestionResponse,
    QuestionStatus,
)
from app.schemas.responses import FailureCode, map_failure

logger = logging.getLogger(__name__)


def _describe_observation(observation: dict[str, object]) -> str:
    labels: list[str] = []
    if "period" in observation:
        labels.append(str(observation["period"]))
    dimensions = observation.get("dimensions", {})
    if isinstance(dimensions, dict):
        for dimension_id, dimension_value in dimensions.items():
            labels.append(f"{dimension_id}={dimension_value}")
    value_with_unit = f"{observation['value']} {observation['unit']}"
    return f"{', '.join(labels)}: {value_with_unit}" if labels else value_with_unit


def _is_ungrounded(generated: GeneratedAnswer, observation_ids: set[str]) -> bool:
    """Resposta ``answered`` sem IDs, com IDs repetidos ou fora da evidência enviada."""

    return generated.status == "answered" and (
        not generated.observation_ids
        or len(set(generated.observation_ids)) != len(generated.observation_ids)
        or not set(generated.observation_ids) <= observation_ids
    )


def _serialized_evidence_chars(evidence: EvidenceResult) -> int:
    """Tamanho da evidência como os adaptadores a serializam para o provedor."""

    return len(json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False))


class QuestionOrchestrator:
    """Responde perguntas com um único adaptador ou com um roteador de níveis de modelo.

    Informe ``model_adapter`` ou ``model_router``, nunca os dois. Com roteador, o nível é
    escolhido depois da redução da evidência; uma saída leve sem referências válidas ou com
    números sem suporte na evidência é refeita uma vez pelo nível forte, no mesmo orçamento.
    """

    def __init__(
        self,
        analysis_planner: QuestionAnalysisPlanner,
        model_adapter: ModelAdapter | None = None,
        safety_gate: QuestionSafetyGate | None = None,
        execution_controller: ExecutionController | None = None,
        event_sink: EventSink | None = None,
        require_durable_audit: bool = False,
        model_router: ModelRouter | None = None,
    ) -> None:
        if (model_adapter is None) == (model_router is None):
            raise ValueError("Informe exatamente um entre model_adapter e model_router.")
        self._analysis_planner = analysis_planner
        self._model_adapter = model_adapter
        self._model_router = model_router
        self._safety_gate = safety_gate or QuestionSafetyGate()
        self._execution = execution_controller or ExecutionController()
        if model_router is None:
            self._execution.ensure_model_capacity(model_adapter)
        else:
            # Pior caso: o nível leve inteiro seguido da escalada para o forte.
            self._execution.ensure_model_capacity(
                *(model_router.adapter_for(tier) for tier in sorted(model_router.tiers))
            )
        self._events = event_sink or NoopEventSink()
        self._require_durable_audit = require_durable_audit

    async def answer(
        self,
        request: QuestionRequest,
        access_context: AccessContext | None = None,
        correlation_id: str | None = None,
    ) -> QuestionResponse:
        trace = EventTrace(
            self._events,
            "question",
            correlation_id or (access_context.correlation_id if access_context else None),
            require_durable=self._require_durable_audit,
        )
        try:
            trace.emit(EventStage.REQUEST, EventCode.STARTED, EventOutcome.STARTED)
            response = await self._execution.run(
                lambda budget: self._answer_with_budget(request, access_context, budget, trace)
            )
        except AuditUnavailable:
            return self._recoverable_error(FailureCode.AUDIT_UNAVAILABLE)
        except asyncio.CancelledError:
            with suppress(AuditUnavailable):
                trace.emit(EventStage.RESPONSE, EventCode.CANCELLED, EventOutcome.CANCELLED)
            raise
        except ExecutionLimitExceeded:
            response = self._recoverable_error(FailureCode.EXECUTION_LIMIT)
        try:
            trace.emit(
                EventStage.RESPONSE,
                EventCode.COMPLETED
                if response.status is QuestionStatus.ANSWERED
                else EventCode.REFUSED
                if response.status is QuestionStatus.REFUSED
                else EventCode.LIMIT
                if response.error and response.error.code.value == "limit_exceeded"
                else EventCode.UNAVAILABLE
                if response.status is QuestionStatus.RECOVERABLE_ERROR
                else EventCode.CLARIFICATION
                if response.status is QuestionStatus.NEEDS_CLARIFICATION
                else EventCode.NO_EVIDENCE,
                EventOutcome.SUCCESS
                if response.status is QuestionStatus.ANSWERED
                else EventOutcome.REFUSED
                if response.status is QuestionStatus.REFUSED
                else EventOutcome.ERROR
                if response.status is QuestionStatus.RECOVERABLE_ERROR
                else EventOutcome.SUCCESS,
            )
        except AuditUnavailable:
            return self._recoverable_error(FailureCode.AUDIT_UNAVAILABLE)
        return response

    async def _answer_with_budget(
        self,
        request: QuestionRequest,
        access_context: AccessContext | None,
        budget: RequestBudget,
        trace: EventTrace,
    ) -> QuestionResponse:
        if access_context is None:
            trace.emit(EventStage.POLICY, EventCode.DENIED, EventOutcome.REFUSED)
            return self._refused(FailureCode.ACCESS_DENIED)
        refusal = self._safety_gate.refusal_code(request.question)
        for turn in request.context:
            if refusal is not None:
                break
            refusal = self._safety_gate.refusal_code(turn.content)
        if refusal is not None:
            trace.emit(EventStage.POLICY, EventCode.DENIED, EventOutcome.REFUSED)
            code = (
                FailureCode.OUT_OF_SCOPE
                if refusal is SafetyRefusalCode.OUT_OF_SCOPE
                else FailureCode.SECURITY_VIOLATION
            )
            return self._refused(code)

        try:
            plan = await self._analysis_planner.prepare(
                request.question, request.context, access_context, budget, trace
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
        read_plan = plan.read_plan
        assert read_plan is not None
        assert access_context is not None
        evidence = evidence.model_copy(
            update={"cache_scope": authorized_cache_scope(access_context, read_plan)}
        )
        observations = {row["observation_id"]: row for row in evidence.records}
        tier: ModelTier | None = None
        adapter = self._model_adapter
        if self._model_router is not None:
            intent = plan.interpretation.intent
            tier, adapter = self._model_router.route(
                intent=intent.domain if intent is not None else None,
                evidence_records=len(evidence.records),
                evidence_chars=_serialized_evidence_chars(evidence),
            )
        assert adapter is not None
        generated = await self._generate(adapter, request, evidence, budget, trace)
        if isinstance(generated, QuestionResponse):
            return generated

        allow_deterministic_answer_after_refusal = generated.status == "refused"
        stronger = escalate(tier) if tier is not None else None
        period = (
            read_plan.window.phrase
            if read_plan.window.phrase is not None
            else f"{read_plan.window.start} a {read_plan.window.end}"
        )
        filters = {
            item.dimension_id: item.values[0] if len(item.values) == 1 else list(item.values)
            for item in read_plan.filters
        }
        filter_operators = {item.dimension_id: item.operator for item in read_plan.filters}
        numeric_mismatch = has_unsupported_claims(
            generated, observations, metric=read_plan.metric_id, period=period, filters=filters,
            filter_operators=filter_operators,
        )
        needs_stronger = (
            generated.status == "refused"
            or _is_ungrounded(generated, set(observations))
            or numeric_mismatch
        )
        if stronger is not None and needs_stronger:
            # Recusa ou saída sem fundamento no nível leve recebe uma tentativa forte.
            assert self._model_router is not None
            generated = await self._generate(
                self._model_router.adapter_for(stronger),
                request,
                evidence,
                budget,
                trace,
                start_code=EventCode.ESCALATED,
            )
            if isinstance(generated, QuestionResponse):
                return generated
            tier = stronger

        if (
            generated.status == "refused"
            and allow_deterministic_answer_after_refusal
            and 0 < len(observations) <= 10
        ):
            # A recusa inicial pode ser substituída apenas por observações autorizadas.
            # Se a primeira saída era infundada e a nova tentativa recusa, preservamos a recusa.
            generated = GeneratedAnswer(
                status="answered",
                answer="Resposta montada a partir das observações autorizadas.",
                observation_ids=tuple(observations),
            )

        if _is_ungrounded(generated, set(observations)) or has_unsupported_claims(
            generated, observations, metric=read_plan.metric_id, period=period, filters=filters,
            filter_operators=filter_operators,
        ):
            return QuestionResponse(
                status=QuestionStatus.REFUSED,
                message=map_failure(FailureCode.UNGROUNDED_OUTPUT).message,
                evidence=[evidence.reference],
                limitations=plan.evidence_result.limitations,
                error=map_failure(FailureCode.UNGROUNDED_OUTPUT).error,
                model_tier=tier,
            )

        answer = None
        if generated.status == "answered":
            values = ", ".join(
                _describe_observation(observations[item])
                for item in generated.observation_ids
            )
            prefix = "Demonstração sintética: " if evidence.reference.is_demo else ""
            answer = f"{prefix}{read_plan.metric_id} — {period}: {values}."

        error = (
            map_failure(FailureCode.POLICY_REFUSAL).error if generated.status == "refused" else None
        )

        return QuestionResponse(
            status=QuestionStatus(generated.status),
            answer=answer,
            message=(
                map_failure(FailureCode.POLICY_REFUSAL).message
                if error is not None
                else "Esclareça o indicador ou recorte para que eu possa consultar a fonte."
                if generated.status == "needs_clarification"
                else None
            ),
            evidence=[evidence.reference],
            limitations=plan.evidence_result.limitations,
            error=error,
            model_tier=tier,
            analysis_context=AppliedQueryContext(
                metric=read_plan.metric_id,
                unit=read_plan.unit,
                period=period,
                filters={
                    item.dimension_id: (
                        item.values[0]
                        if len(item.values) == 1
                        else ", ".join(str(value) for value in item.values)
                    )
                    for item in read_plan.filters
                },
            ),
        )

    async def _generate(
        self,
        adapter: ModelAdapter,
        request: QuestionRequest,
        evidence: EvidenceResult,
        budget: RequestBudget,
        trace: EventTrace,
        *,
        start_code: EventCode = EventCode.STARTED,
    ) -> GeneratedAnswer | QuestionResponse:
        """Chama o modelo pelo orçamento; falhas viram a resposta de erro correspondente."""

        try:
            trace.model_calls += 1
            trace.emit(EventStage.MODEL, start_code, EventOutcome.STARTED)
            generated_result = await budget.model(
                lambda: adapter.generate(
                    request.question,
                    request.context,
                    evidence,
                )
            )
            generated = GeneratedAnswer.model_validate(
                generated_result.model_dump()
                if isinstance(generated_result, GeneratedAnswer)
                else generated_result
            )
            if generated.status == "refused":
                trace.emit(EventStage.MODEL, EventCode.REFUSED, EventOutcome.REFUSED)
            else:
                trace.emit(EventStage.MODEL, EventCode.COMPLETED, EventOutcome.SUCCESS)
        except ModelProviderUnavailable:
            trace.emit(EventStage.MODEL, EventCode.UNAVAILABLE, EventOutcome.ERROR)
            return self._recoverable_error(FailureCode.MODEL_UNAVAILABLE)
        except ModelProviderRejected:
            trace.emit(EventStage.MODEL, EventCode.REFUSED, EventOutcome.REFUSED)
            return self._recoverable_error(FailureCode.MODEL_REJECTED)
        except ModelProviderInvalidResponse:
            trace.emit(EventStage.MODEL, EventCode.INVALID, EventOutcome.ERROR)
            return self._recoverable_error(FailureCode.INVALID_MODEL_OUTPUT)
        except ExecutionLimitExceeded:
            raise
        except AuditUnavailable:
            raise
        except (ValidationError, TypeError, ValueError):
            trace.emit(EventStage.MODEL, EventCode.INVALID, EventOutcome.ERROR)
            logger.warning("O adaptador de modelo retornou uma resposta inválida.")
            return self._recoverable_error(FailureCode.INVALID_MODEL_OUTPUT)
        except Exception:
            trace.emit(EventStage.MODEL, EventCode.UNAVAILABLE, EventOutcome.ERROR)
            logger.warning("Falha ao gerar resposta pelo adaptador de modelo.")
            return self._recoverable_error(FailureCode.UNEXPECTED)
        return generated

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
