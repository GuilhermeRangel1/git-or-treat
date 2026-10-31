"""Liga a interpretação a uma fonte de evidências sem gerar texto natural."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.agent.access import ReadAccessPolicy
from app.agent.evidence_guard import EvidenceGuard
from app.agent.execution import ExecutionLimitExceeded, RequestBudget
from app.agent.interpreter import QuestionInterpreter, _normalize
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
from app.schemas.domain_profile import DimensionValue, DomainProfile
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


class PlannedQuestion(BaseModel):
    """Resultado de planejar, sem fonte: plano aprovado ou o motivo do esclarecimento."""

    model_config = ConfigDict(extra="forbid")

    interpretation: IntentInterpretation
    read_plan: LogicalReadPlan | None = None
    clarification: EvidenceLookupResult | None = None

    @model_validator(mode="after")
    def validate_single_outcome(self) -> Self:
        ambiguous = self.interpretation.status is InterpretationStatus.NEEDS_CLARIFICATION
        if ambiguous + (self.read_plan is not None) + (self.clarification is not None) != 1:
            raise ValueError("planejamento exige um único resultado")
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
        self._access_policy = access_policy
        self._plan_builder = ReadPlanBuilder(
            access_policy.profile, access_policy.source_id, default_limit=max_rows
        )
        self._plan_validator = ReadPlanValidator(
            access_policy.profile, access_policy.source_id, access_policy, max_rows=max_rows
        )
        self._evidence_guard = EvidenceGuard(
            access_policy.profile, max_bytes=max_evidence_bytes
        )

    async def prepare(
        self,
        question: str,
        context: list[ConversationTurn] | None = None,
        access_context: AccessContext | None = None,
        budget: RequestBudget | None = None,
        trace: EventTrace | None = None,
    ) -> AnalysisPlan:
        planned = self.plan(question, context, access_context, trace)
        if planned.read_plan is None:
            return AnalysisPlan(
                status=AnalysisPlanStatus.NEEDS_CLARIFICATION,
                interpretation=planned.interpretation,
                evidence_result=planned.clarification,
            )
        evidence_result = await self.retrieve(planned.read_plan, access_context, budget, trace)
        return AnalysisPlan(
            status=self._status_for(evidence_result),
            interpretation=planned.interpretation,
            evidence_result=evidence_result,
            read_plan=planned.read_plan,
        )

    def plan(
        self,
        question: str,
        context: list[ConversationTurn] | None = None,
        access_context: AccessContext | None = None,
        trace: EventTrace | None = None,
        temporal_coverage: Mapping[str, tuple[str, tuple[str, ...]]] | None = None,
        dimension_value_coverage: Mapping[str, tuple[str, ...]] | None = None,
    ) -> PlannedQuestion:
        """Interpreta, monta e aprova o plano; nunca chama a fonte nem o modelo."""

        profile = self._profile_with_dimension_values(dimension_value_coverage)
        interpreter = (
            self._interpreter
            if profile is self._access_policy.profile
            else QuestionInterpreter(profile)
        )
        plan_builder = (
            self._plan_builder
            if profile is self._access_policy.profile
            else ReadPlanBuilder(profile, self._access_policy.source_id)
        )
        plan_validator = (
            self._plan_validator
            if profile is self._access_policy.profile
            else ReadPlanValidator(profile, self._access_policy.source_id, self._access_policy)
        )
        interpretation = interpreter.interpret(question, context)
        if interpretation.status is InterpretationStatus.NEEDS_CLARIFICATION:
            if trace is not None:
                trace.emit(EventStage.PLAN, EventCode.CLARIFICATION, EventOutcome.SUCCESS)
            return PlannedQuestion(interpretation=interpretation)

        assert interpretation.intent is not None
        try:
            proposed = plan_builder.build(interpretation.intent, temporal_coverage)
            approved = self._approve(proposed, access_context, trace, plan_validator)
        except PlanCapabilityUnavailable as exc:
            if trace is not None:
                trace.emit(EventStage.PLAN, EventCode.CLARIFICATION, EventOutcome.SUCCESS)
            return PlannedQuestion(
                interpretation=interpretation,
                clarification=EvidenceLookupResult(
                    status=EvidenceLookupStatus.NEEDS_CLARIFICATION,
                    message=str(exc),
                ),
            )
        return PlannedQuestion(interpretation=interpretation, read_plan=approved)

    def _profile_with_dimension_values(
        self, coverage: Mapping[str, tuple[str, ...]] | None
    ) -> DomainProfile:
        if not coverage:
            return self._access_policy.profile

        dimensions = []
        for dimension in self._access_policy.profile.dimensions:
            additions = coverage.get(dimension.id, ())
            if not additions:
                dimensions.append(dimension)
                continue
            known = {
                _normalize(alias)
                for value in dimension.values
                for alias in (value.value, *value.aliases)
            }
            values = list(dimension.values)
            for raw in additions:
                normalized = _normalize(raw)
                if normalized in known:
                    # O perfil oferece sinônimos; a publicação fornece o valor
                    # canônico que será usado no filtro parametrizado do Backend.
                    for index, value in enumerate(values):
                        if normalized in {
                            _normalize(alias) for alias in (value.value, *value.aliases)
                        }:
                            values[index] = DimensionValue(
                                value=raw, aliases=value.aliases
                            )
                            break
                    continue
                values.append(DimensionValue(value=raw, aliases=(raw,)))
                known.add(normalized)
            dimensions.append(dimension.model_copy(update={"values": tuple(values)}))
        profile_data = self._access_policy.profile.model_dump(mode="python")
        profile_data["dimensions"] = tuple(dimensions)
        return DomainProfile.model_validate(profile_data)

    async def execute_plan(
        self,
        proposed: LogicalReadPlan | dict[str, object],
        access_context: AccessContext | None,
        budget: RequestBudget | None = None,
        trace: EventTrace | None = None,
    ) -> tuple[LogicalReadPlan, EvidenceLookupResult]:
        """Ponto único de validação, inclusive para planos propostos futuramente por LLM."""

        approved = self._approve(proposed, access_context, trace)
        return approved, await self.retrieve(approved, access_context, budget, trace)

    def accept_lookup(
        self,
        plan: LogicalReadPlan,
        plan_fingerprint: str,
        lookup: EvidenceLookupResult,
        access_context: AccessContext | None,
        *,
        expected_batch_ref: str | None = None,
        trace: EventTrace | None = None,
    ) -> tuple[LogicalReadPlan, EvidenceLookupResult]:
        """Confere o resultado recebido de quem executou o plano; nunca chama a fonte.

        Reaprova o plano no escopo atual e exige o mesmo fingerprint do planejamento. A
        publicação esperada vem do chamador confiável, nunca do próprio lookup.
        """

        approved = self._approve(plan, access_context, trace)
        try:
            if plan_fingerprint != approved.fingerprint():
                raise EvidenceContractInvalid("fingerprint divergente do plano aprovado")
            evidence_result = self._check_lookup(approved, lookup, expected_batch_ref)
        except EvidenceContractInvalid:
            if trace is not None:
                trace.emit(EventStage.EVIDENCE, EventCode.INVALID, EventOutcome.ERROR)
            raise
        except (TypeError, ValidationError) as exc:
            if trace is not None:
                trace.emit(EventStage.EVIDENCE, EventCode.INVALID, EventOutcome.ERROR)
            raise EvidenceContractInvalid("Evidence source returned an invalid result.") from exc
        self._emit_evidence(evidence_result, trace)
        return approved, evidence_result

    def _approve(
        self,
        proposed: LogicalReadPlan | dict[str, object],
        access_context: AccessContext | None,
        trace: EventTrace | None,
        validator: ReadPlanValidator | None = None,
    ) -> LogicalReadPlan:
        try:
            if access_context is None:
                raise EvidenceAccessDenied("Contexto de acesso ausente.")
            approved = (validator or self._plan_validator).approve(proposed, access_context)
        except EvidenceAccessDenied:
            if trace is not None:
                trace.emit(EventStage.POLICY, EventCode.DENIED, EventOutcome.REFUSED)
            raise
        if trace is not None:
            trace.plan_id = approved.fingerprint()
            trace.catalog_version = approved.catalog_version
            trace.emit(EventStage.POLICY, EventCode.ALLOWED, EventOutcome.SUCCESS)
            trace.emit(EventStage.PLAN, EventCode.READY, EventOutcome.SUCCESS)
        return approved

    def _check_lookup(
        self,
        approved: LogicalReadPlan,
        evidence_result: object,
        expected_batch_ref: str | None,
    ) -> EvidenceLookupResult:
        if not isinstance(evidence_result, EvidenceLookupResult):
            raise TypeError("Evidence source returned an unsupported result type.")
        evidence_result = EvidenceLookupResult.model_validate(evidence_result.model_dump())
        return self._evidence_guard.validate(
            approved, evidence_result, expected_batch_ref=expected_batch_ref
        )

    @staticmethod
    def _emit_evidence(evidence_result: EvidenceLookupResult, trace: EventTrace | None) -> None:
        if trace is None:
            return
        if evidence_result.evidence is not None:
            trace.evidence_ref = safe_reference_id(evidence_result.evidence.reference.source)
            trace.row_count = len(evidence_result.evidence.records)
            trace.emit(EventStage.EVIDENCE, EventCode.AVAILABLE, EventOutcome.SUCCESS)
        elif evidence_result.status is EvidenceLookupStatus.NO_EVIDENCE:
            trace.emit(EventStage.EVIDENCE, EventCode.NO_EVIDENCE, EventOutcome.SUCCESS)
        else:
            trace.emit(EventStage.EVIDENCE, EventCode.CLARIFICATION, EventOutcome.SUCCESS)

    async def retrieve(
        self,
        approved: LogicalReadPlan,
        access_context: AccessContext | None,
        budget: RequestBudget | None = None,
        trace: EventTrace | None = None,
    ) -> EvidenceLookupResult:
        """Consulta a fonte local com um plano já aprovado e confere o resultado."""

        if trace is not None:
            trace.source_calls += 1
            trace.emit(EventStage.SOURCE, EventCode.STARTED, EventOutcome.STARTED)
        try:
            evidence_result = (
                await budget.source(
                    lambda: self._evidence_source.retrieve(approved, access_context)
                )
                if budget is not None
                else await self._evidence_source.retrieve(approved, access_context)
            )
            evidence_result = self._check_lookup(approved, evidence_result, None)
            if trace is not None:
                trace.emit(EventStage.SOURCE, EventCode.COMPLETED, EventOutcome.SUCCESS)
            self._emit_evidence(evidence_result, trace)
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
        return evidence_result

    @staticmethod
    def _status_for(result: EvidenceLookupResult) -> AnalysisPlanStatus:
        if result.status is EvidenceLookupStatus.AVAILABLE:
            return AnalysisPlanStatus.READY
        if result.status is EvidenceLookupStatus.NEEDS_CLARIFICATION:
            return AnalysisPlanStatus.NEEDS_CLARIFICATION
        return AnalysisPlanStatus.NO_EVIDENCE
