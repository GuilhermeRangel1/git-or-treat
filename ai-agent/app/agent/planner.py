"""Liga a interpretação a uma fonte de evidências sem gerar texto natural."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.agent.access import ReadAccessPolicy
from app.agent.evidence_guard import EvidenceGuard
from app.agent.execution import ExecutionLimitExceeded, RequestBudget
from app.agent.interpreter import QuestionInterpreter
from app.agent.read_plan import (
    PlanCapabilityUnavailable,
    ReadPlanBuilder,
    ReadPlanValidator,
)
from app.ports.events import (
    AuditUnavailable,
    EventCode,
    EventOutcome,
    EventStage,
    EventTrace,
    safe_reference_id,
)
from app.ports.evidence import (
    EvidenceAccessDenied,
    EvidenceContractInvalid,
    EvidenceSource,
    EvidenceToolUnavailable,
)
from app.schemas.access import AccessContext
from app.schemas.evidence import EvidenceLookupResult, EvidenceLookupStatus
from app.schemas.interpretation import IntentInterpretation, InterpretationStatus
from app.schemas.questions import ConversationTurn
from app.schemas.read_plan import LogicalReadPlan


class AnalysisPlanStatus(StrEnum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    NO_EVIDENCE = "no_evidence"


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AnalysisPlanStatus
    interpretation: IntentInterpretation
    evidence_result: EvidenceLookupResult | None = None
    read_plan: LogicalReadPlan | None = None

    @model_validator(mode="after")
    def validate_source_was_called_only_for_ready_intent(self) -> Self:
        if self.interpretation.status is InterpretationStatus.NEEDS_CLARIFICATION:
            if (
                self.status is not AnalysisPlanStatus.NEEDS_CLARIFICATION
                or self.evidence_result is not None
                or self.read_plan is not None
            ):
                raise ValueError("pergunta ambígua deve parar antes da fonte de evidências")
        elif self.evidence_result is None:
            raise ValueError("intenção pronta exige resultado da fonte de evidências")
        elif (
            self.status is AnalysisPlanStatus.NEEDS_CLARIFICATION
            and self.evidence_result.status is not EvidenceLookupStatus.NEEDS_CLARIFICATION
        ):
            raise ValueError("esclarecimento da fonte precisa ser preservado no plano")
        elif (
            self.status is AnalysisPlanStatus.READY
            and self.evidence_result.status is not EvidenceLookupStatus.AVAILABLE
        ):
            raise ValueError("plano pronto exige evidência disponível")
        elif (
            self.status is AnalysisPlanStatus.NO_EVIDENCE
            and self.evidence_result.status is not EvidenceLookupStatus.NO_EVIDENCE
        ):
            raise ValueError("plano sem evidência exige resultado correspondente da fonte")
        if (
            self.status in (AnalysisPlanStatus.READY, AnalysisPlanStatus.NO_EVIDENCE)
            and self.read_plan is None
        ):
            raise ValueError("consulta à fonte exige plano de leitura aprovado")
        return self


class QuestionAnalysisPlanner:
    """Prepara a interpretação e consulta a fonte só após resolver ambiguidades."""

    def __init__(
        self,
        interpreter: QuestionInterpreter,
        evidence_source: EvidenceSource,
        access_policy: ReadAccessPolicy,
        *,
        max_rows: int = 100,
        max_evidence_bytes: int = 16_384,
    ) -> None:
        self._interpreter = interpreter
        self._evidence_source = evidence_source
        self._plan_builder = ReadPlanBuilder(
            access_policy.profile, access_policy.source_id, default_limit=max_rows
        )
        self._plan_validator = ReadPlanValidator(
            access_policy.profile, access_policy.source_id, access_policy, max_rows=max_rows
        )
        self._evidence_guard = EvidenceGuard(access_policy.profile, max_bytes=max_evidence_bytes)

    async def prepare(
        self,
        question: str,
        context: list[ConversationTurn] | None = None,
        access_context: AccessContext | None = None,
        budget: RequestBudget | None = None,
        trace: EventTrace | None = None,
    ) -> AnalysisPlan:
        interpretation = self._interpreter.interpret(question, context)
        if interpretation.status is InterpretationStatus.NEEDS_CLARIFICATION:
            if trace is not None:
                trace.emit(EventStage.PLAN, EventCode.CLARIFICATION, EventOutcome.SUCCESS)
            return AnalysisPlan(
                status=AnalysisPlanStatus.NEEDS_CLARIFICATION,
                interpretation=interpretation,
            )

        assert interpretation.intent is not None
        try:
            proposed = self._plan_builder.build(interpretation.intent)
        except PlanCapabilityUnavailable as exc:
            if trace is not None:
                trace.emit(EventStage.PLAN, EventCode.CLARIFICATION, EventOutcome.SUCCESS)
            result = EvidenceLookupResult(
                status=EvidenceLookupStatus.NEEDS_CLARIFICATION,
                message=str(exc),
            )
            return AnalysisPlan(
                status=AnalysisPlanStatus.NEEDS_CLARIFICATION,
                interpretation=interpretation,
                evidence_result=result,
            )
        try:
            approved, evidence_result = await self.execute_plan(
                proposed, access_context, budget, trace
            )
        except PlanCapabilityUnavailable as exc:
            if trace is not None:
                trace.emit(EventStage.PLAN, EventCode.CLARIFICATION, EventOutcome.SUCCESS)
            result = EvidenceLookupResult(
                status=EvidenceLookupStatus.NEEDS_CLARIFICATION,
                message=str(exc),
            )
            return AnalysisPlan(
                status=AnalysisPlanStatus.NEEDS_CLARIFICATION,
                interpretation=interpretation,
                evidence_result=result,
            )
        return AnalysisPlan(
            status=self._status_for(evidence_result),
            interpretation=interpretation,
            evidence_result=evidence_result,
            read_plan=approved,
        )

    async def execute_plan(
        self,
        proposed: LogicalReadPlan | dict[str, object],
        access_context: AccessContext | None,
        budget: RequestBudget | None = None,
        trace: EventTrace | None = None,
    ) -> tuple[LogicalReadPlan, EvidenceLookupResult]:
        """Ponto único de validação, inclusive para planos propostos futuramente por LLM."""

        try:
            approved = self._plan_validator.approve(proposed, access_context)
        except EvidenceAccessDenied:
            if trace is not None:
                trace.emit(EventStage.POLICY, EventCode.DENIED, EventOutcome.REFUSED)
            raise
        if trace is not None:
            trace.plan_id = approved.fingerprint()
            trace.catalog_version = approved.catalog_version
            trace.emit(EventStage.POLICY, EventCode.ALLOWED, EventOutcome.SUCCESS)
            trace.emit(EventStage.PLAN, EventCode.READY, EventOutcome.SUCCESS)
            trace.source_calls += 1
            trace.emit(EventStage.SOURCE, EventCode.STARTED, EventOutcome.STARTED)
        try:
            evidence_result = (
                await budget.source(lambda: self._evidence_source.retrieve(approved))
                if budget is not None
                else await self._evidence_source.retrieve(approved)
            )
            if not isinstance(evidence_result, EvidenceLookupResult):
                raise TypeError("Evidence source returned an unsupported result type.")
            evidence_result = EvidenceLookupResult.model_validate(evidence_result.model_dump())
            evidence_result = self._evidence_guard.validate(approved, evidence_result)
            if trace is not None:
                trace.emit(EventStage.SOURCE, EventCode.COMPLETED, EventOutcome.SUCCESS)
                if evidence_result.evidence is not None:
                    trace.evidence_ref = safe_reference_id(
                        evidence_result.evidence.reference.source
                    )
                    trace.row_count = len(evidence_result.evidence.records)
                    trace.emit(EventStage.EVIDENCE, EventCode.AVAILABLE, EventOutcome.SUCCESS)
                elif evidence_result.status is EvidenceLookupStatus.NO_EVIDENCE:
                    trace.emit(EventStage.EVIDENCE, EventCode.NO_EVIDENCE, EventOutcome.SUCCESS)
                else:
                    trace.emit(EventStage.EVIDENCE, EventCode.CLARIFICATION, EventOutcome.SUCCESS)
        except AuditUnavailable:
            raise
        except EvidenceToolUnavailable:
            if trace is not None:
                trace.emit(EventStage.SOURCE, EventCode.UNAVAILABLE, EventOutcome.ERROR)
            raise
        except EvidenceAccessDenied:
            if trace is not None:
                trace.emit(EventStage.SOURCE, EventCode.DENIED, EventOutcome.REFUSED)
            raise
        except EvidenceContractInvalid:
            if trace is not None:
                trace.emit(EventStage.EVIDENCE, EventCode.INVALID, EventOutcome.ERROR)
            raise
        except ExecutionLimitExceeded:
            raise
        except (TypeError, ValidationError) as exc:
            if trace is not None:
                trace.emit(EventStage.EVIDENCE, EventCode.INVALID, EventOutcome.ERROR)
            raise EvidenceContractInvalid("Evidence source returned an invalid result.") from exc
        except Exception as exc:
            if trace is not None:
                trace.emit(EventStage.SOURCE, EventCode.UNAVAILABLE, EventOutcome.ERROR)
            raise EvidenceToolUnavailable("Evidence source failed.") from exc
        return approved, evidence_result

    @staticmethod
    def _status_for(result: EvidenceLookupResult) -> AnalysisPlanStatus:
        if result.status is EvidenceLookupStatus.AVAILABLE:
            return AnalysisPlanStatus.READY
        if result.status is EvidenceLookupStatus.NEEDS_CLARIFICATION:
            return AnalysisPlanStatus.NEEDS_CLARIFICATION
        return AnalysisPlanStatus.NO_EVIDENCE
