"""Coordena a geração de hipóteses a partir de contexto de tela estruturado."""

import asyncio
from contextlib import suppress

from pydantic import ValidationError

from app.agent.access import ReadAccessPolicy
from app.agent.evidence_guard import safe_reference_source
from app.agent.execution import ExecutionController, ExecutionLimitExceeded, RequestBudget
from app.generation.prompts import INSIGHT_TASK
from app.ports.events import (
    AuditUnavailable,
    EventCode,
    EventOutcome,
    EventSink,
    EventStage,
    EventTrace,
    NoopEventSink,
    safe_reference_id,
)
from app.ports.evidence import EvidenceAccessDenied
from app.providers.protocols import (
    GeneratedAnswer,
    ModelAdapter,
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.schemas.access import AccessContext
from app.schemas.evidence import EvidenceReference, EvidenceResult
from app.schemas.insights import (
    InsightContextSummary,
    InsightObservation,
    ScreenContext,
    ScreenInsightResponse,
)
from app.schemas.questions import QuestionStatus
from app.schemas.responses import FailureCode, PublicError, map_failure

SYNTHETIC_INSIGHT_LIMITATIONS = [
    "O contexto e os valores são sintéticos; não representam dados operacionais reais.",
    "A hipótese é uma sugestão de investigação, não uma causa comprovada.",
]


class ScreenInsightOrchestrator:
    """Mantém observações do cliente separadas da hipótese gerada pelo modelo."""

    def __init__(
        self,
        model_adapter: ModelAdapter,
        access_policy: ReadAccessPolicy,
        execution_controller: ExecutionController | None = None,
        event_sink: EventSink | None = None,
        require_durable_audit: bool = False,
    ) -> None:
        self._model_adapter = model_adapter
        self._access_policy = access_policy
        self._execution = execution_controller or ExecutionController()
        self._execution.ensure_model_capacity(model_adapter)
        self._events = event_sink or NoopEventSink()
        self._require_durable_audit = require_durable_audit

    async def generate(
        self,
        screen: ScreenContext,
        access_context: AccessContext | None = None,
        correlation_id: str | None = None,
    ) -> ScreenInsightResponse:
        trace = EventTrace(
            self._events,
            "insight",
            correlation_id or (access_context.correlation_id if access_context else None),
            require_durable=self._require_durable_audit,
        )
        try:
            trace.emit(EventStage.REQUEST, EventCode.STARTED, EventOutcome.STARTED)
            response = await self._execution.run(
                lambda budget: self._generate_with_budget(screen, access_context, budget, trace)
            )
        except AuditUnavailable:
            return self._audit_failure(screen)
        except asyncio.CancelledError:
            with suppress(AuditUnavailable):
                trace.emit(EventStage.RESPONSE, EventCode.CANCELLED, EventOutcome.CANCELLED)
            raise
        except ExecutionLimitExceeded:
            failure = map_failure(FailureCode.EXECUTION_LIMIT)
            response = self._response(
                screen,
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
                expose_context=access_context is not None,
            )
        try:
            trace.emit(
                EventStage.RESPONSE,
                EventCode.COMPLETED
                if response.status is QuestionStatus.ANSWERED
                else EventCode.REFUSED
                if response.status is QuestionStatus.REFUSED
                else EventCode.UNAVAILABLE
                if response.status is QuestionStatus.RECOVERABLE_ERROR
                else EventCode.CLARIFICATION,
                EventOutcome.SUCCESS
                if response.status is QuestionStatus.ANSWERED
                else EventOutcome.REFUSED
                if response.status is QuestionStatus.REFUSED
                else EventOutcome.ERROR
                if response.status is QuestionStatus.RECOVERABLE_ERROR
                else EventOutcome.SUCCESS,
            )
        except AuditUnavailable:
            return self._audit_failure(screen)
        return response

    @classmethod
    def _audit_failure(cls, screen: ScreenContext) -> ScreenInsightResponse:
        failure = map_failure(FailureCode.AUDIT_UNAVAILABLE)
        return cls._response(
            screen,
            status=QuestionStatus.RECOVERABLE_ERROR,
            message=failure.message,
            error=failure.error,
            expose_context=False,
        )

    async def _generate_with_budget(
        self,
        screen: ScreenContext,
        access_context: AccessContext | None,
        budget: RequestBudget,
        trace: EventTrace,
    ) -> ScreenInsightResponse:
        try:
            self._access_policy.authorize_insight(access_context)
        except EvidenceAccessDenied:
            trace.emit(EventStage.POLICY, EventCode.DENIED, EventOutcome.REFUSED)
            failure = map_failure(FailureCode.ACCESS_DENIED)
            return self._response(
                screen,
                status=QuestionStatus.REFUSED,
                message=failure.message,
                error=failure.error,
                expose_context=False,
            )
        trace.emit(EventStage.POLICY, EventCode.ALLOWED, EventOutcome.SUCCESS)
        trace.evidence_ref = safe_reference_id(screen.reference.source)
        trace.row_count = len(screen.observations)
        trace.emit(EventStage.EVIDENCE, EventCode.AVAILABLE, EventOutcome.SUCCESS)
        records: list[dict[str, object]] = [
            {
                "metric": "Indicador demonstrativo da tela",
                "unit": screen.unit,
                "period": screen.period.model_dump(mode="json"),
                "filter_keys": sorted(screen.filters),
                "observations": [
                    {"observation_id": f"row_{index}", "value": item.value}
                    for index, item in enumerate(screen.observations, start=1)
                ],
            }
        ]
        evidence = EvidenceResult(
            reference=EvidenceReference(
                source=safe_reference_source("synthetic.screen", screen.reference.source),
                description="Contexto sintético de tela fornecido pelo cliente.",
                is_demo=True,
            ),
            records=records,
        )
        try:
            trace.model_calls += 1
            trace.emit(EventStage.MODEL, EventCode.STARTED, EventOutcome.STARTED)
            generated_result = await budget.model(
                lambda: self._model_adapter.generate(INSIGHT_TASK, [], evidence)
            )
            generated = GeneratedAnswer.model_validate(
                generated_result.model_dump()
                if isinstance(generated_result, GeneratedAnswer)
                else generated_result
            )
            trace.emit(EventStage.MODEL, EventCode.COMPLETED, EventOutcome.SUCCESS)
        except ModelProviderUnavailable:
            trace.emit(EventStage.MODEL, EventCode.UNAVAILABLE, EventOutcome.ERROR)
            failure = map_failure(FailureCode.MODEL_UNAVAILABLE)
            return self._response(
                screen,
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
            )
        except (ModelProviderRejected, ModelProviderInvalidResponse) as exc:
            trace.emit(EventStage.MODEL, EventCode.INVALID, EventOutcome.ERROR)
            code = (
                FailureCode.MODEL_REJECTED
                if isinstance(exc, ModelProviderRejected)
                else FailureCode.INVALID_MODEL_OUTPUT
            )
            failure = map_failure(code)
            return self._response(
                screen,
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
            )
        except ExecutionLimitExceeded:
            raise
        except AuditUnavailable:
            raise
        except (ValidationError, TypeError, ValueError):
            trace.emit(EventStage.MODEL, EventCode.INVALID, EventOutcome.ERROR)
            failure = map_failure(FailureCode.INVALID_MODEL_OUTPUT)
            return self._response(
                screen,
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
            )
        except Exception:
            trace.emit(EventStage.MODEL, EventCode.UNAVAILABLE, EventOutcome.ERROR)
            failure = map_failure(FailureCode.UNEXPECTED)
            return self._response(
                screen,
                status=QuestionStatus.RECOVERABLE_ERROR,
                message=failure.message,
                error=failure.error,
            )

        observations = {
            f"row_{index}": item for index, item in enumerate(screen.observations, start=1)
        }
        if generated.status == "answered" and (
            not generated.observation_ids
            or len(set(generated.observation_ids)) != len(generated.observation_ids)
            or not set(generated.observation_ids) <= set(observations)
        ):
            failure = map_failure(FailureCode.UNGROUNDED_INSIGHT)
            return self._response(
                screen,
                status=QuestionStatus.REFUSED,
                message=failure.message,
                error=failure.error,
            )
        if generated.status == "answered":
            if len(generated.observation_ids) > 1:
                hypothesis = (
                    f"Investigue a relação entre os recortes selecionados de "
                    f"{screen.metric}. A comparação não comprova uma causa."
                )
            else:
                hypothesis = (
                    f"Investigue a composição de {screen.metric} no recorte "
                    "selecionado. O valor observado não comprova uma causa."
                )
            return self._response(
                screen,
                status=QuestionStatus.ANSWERED,
                hypothesis=hypothesis,
            )
        if generated.status == "needs_clarification":
            return self._response(
                screen,
                status=QuestionStatus.NEEDS_CLARIFICATION,
                message="Esclareça o recorte ou forneça série histórica para investigar a tela.",
            )
        return self._response(
            screen,
            status=QuestionStatus.REFUSED,
            message=map_failure(FailureCode.INSIGHT_REFUSAL).message,
            error=map_failure(FailureCode.INSIGHT_REFUSAL).error,
        )

    @staticmethod
    def _response(
        screen: ScreenContext,
        *,
        status: QuestionStatus,
        hypothesis: str | None = None,
        message: str | None = None,
        error: PublicError | None = None,
        expose_context: bool = True,
    ) -> ScreenInsightResponse:
        return ScreenInsightResponse(
            status=status,
            context=InsightContextSummary(
                metric=screen.metric if expose_context else "Indisponível",
                unit=screen.unit if expose_context else "Indisponível",
                period=screen.period,
                filters=screen.filters if expose_context else {},
            ),
            observation=InsightObservation(values=screen.observations if expose_context else []),
            hypothesis=hypothesis,
            message=message,
            error=error,
            evidence=[
                EvidenceReference(
                    source=safe_reference_source("synthetic.screen", screen.reference.source),
                    description="Contexto sintético de tela fornecido pelo cliente.",
                    is_demo=True,
                )
            ]
            if expose_context
            else [],
            limitations=SYNTHETIC_INSIGHT_LIMITATIONS,
        )
