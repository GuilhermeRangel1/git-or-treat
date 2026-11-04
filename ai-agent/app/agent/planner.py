"""Liga a interpretação a uma fonte de evidências sem gerar texto natural."""

import asyncio
import re
from collections.abc import Iterator, Mapping
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.agent.access import ReadAccessPolicy
from app.agent.evidence_guard import EvidenceGuard
from app.agent.execution import ExecutionLimitExceeded, RequestBudget
from app.agent.interpreter import QuestionInterpreter, _find_phrases, _normalize
from app.agent.language_recovery import intent_question, pending_year_answer, spelling_suggestions
from app.agent.read_plan import (
    PlanCapabilityUnavailable,
    ReadPlanBuilder,
    ReadPlanValidator,
    TemporalCoverageUnavailable,
)
from app.agent.temporal import (
    complete_contextual_period,
    expand_short_calendar_year,
    explicit_monthly_phrases,
    monthly_period_label,
    normalize_calendar_phrases,
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
from app.schemas.interpretation import (
    ClarificationReason,
    IntentInterpretation,
    InterpretationStatus,
)
from app.schemas.questions import ConversationTurn
from app.schemas.read_plan import LogicalReadPlan

# Calendário que o interpretador não reconheceu como período ("em jun/26", "em 2026"):
# sai do exemplo junto com a preposição para não ficar ao lado do período sugerido.
_UNRECOGNIZED_CALENDAR = re.compile(
    r"\b(?:em|no|na|de)\s+(?:(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)"
    r"\.?/(?:[0-9]{4}|[0-9]{2})|(?:19|20)[0-9]{2})(?![\w/-])(?!\s*(?:%|kwh|mwh|r\$|reais))",
    re.IGNORECASE,
)
# Uma troca ao lado destes conectores deixaria a comparação pela metade.
_DANGLING_CONNECTORS = {"versus", "vs", "e", "ou"}


def _replace_in_place(question: str, phrases: tuple[str, ...], replacement: str) -> str | None:
    """Troca o único trecho ambíguo no lugar; sem exemplo se a frase ficar quebrada."""
    matches = _find_phrases(question, phrases)
    if len(matches) != 1:
        return None
    start, end, _ = matches[0]
    before = re.search(r"([\w.]+)\s*$", question[:start])
    after = re.match(r"\s*([\w.]+)", question[end:])
    # A confirmação pode conter a mesma preposição já escrita antes do termo.
    if (before is not None and _normalize(before[1]) == "com"
            and _normalize(replacement).startswith("com ")):
        start = before.start(1)

    if any(match is not None and _normalize(match[1]).rstrip(".") in _DANGLING_CONNECTORS
           for match in (before, after)):
        return None
    if before is not None and _normalize(before[1]) in {"o", "a", "os", "as"}:
        # O artigo acompanha a substituição: "a energia faturada" vira "o consumo".
        word = _normalize(replacement.split()[0])
        article = "a" if re.search(r"(?:a|cao|dade|agem)s?$", word) else "o"
        if word.endswith("s"):
            article += "s"
        start = before.start(1)
        replacement = (article.upper() if before[1][0].isupper() else article) + " " + replacement
    return question[:start] + replacement + question[end:]


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
    pending_question: str | None = None

    @model_validator(mode="after")
    def validate_single_outcome(self) -> Self:
        ambiguous = self.interpretation.status is InterpretationStatus.NEEDS_CLARIFICATION
        if ambiguous + (self.read_plan is not None) + (self.clarification is not None) != 1:
            raise ValueError("planejamento exige um único resultado")
        return self


class QuestionAnalysisPlanner:
    """Prepara a interpretação e consulta a fonte só após resolver ambiguidades."""

    @property
    def profile(self) -> DomainProfile:
        return self._access_policy.profile

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
        self._max_evidence_bytes = max_evidence_bytes
        self._max_rows = max_rows
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
        planned = await asyncio.to_thread(self.plan, question, context, access_context, trace)
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
        """Acrescenta uma formulação aprovada, sem consultar fonte nem modelo."""
        separator = "\n\nExemplo de pergunta: "
        clean_context = [
            turn.model_copy(update={"content": turn.content.split(separator, 1)[0]})
            if turn.role == "assistant" and self.profile.structured_dimension_filters else turn
            for turn in context or []
        ]
        result = self._plan(
            question, clean_context, access_context, trace,
            temporal_coverage, dimension_value_coverage,
        )
        if not self.profile.structured_dimension_filters or result.read_plan is not None:
            return result
        if result.interpretation.clarification_reason is ClarificationReason.MISSING_YEAR:
            # Os meses já foram informados: um exemplo com outro período atrapalha
            # a resposta curta e mudaria o recorte que a pessoa está construindo.
            return result
        for candidate in self._clarification_examples(
            result.pending_question or question, temporal_coverage, dimension_value_coverage,
        ):
            try:
                example = self._plan(
                    candidate, None, access_context, None,
                    temporal_coverage, dimension_value_coverage,
                )
            except (EvidenceAccessDenied, ValueError):
                continue
            if example.read_plan is None:
                continue
            suffix = f'{separator}“{candidate}”'
            if result.clarification is not None:
                return result.model_copy(update={"clarification": result.clarification.model_copy(
                    update={"message": result.clarification.message + suffix},
                )})
            return result.model_copy(update={"interpretation": result.interpretation.model_copy(
                update={"clarification_question":
                        result.interpretation.clarification_question + suffix},
            )})
        return result

    def _clarification_examples(
        self, question: str,
        coverage: Mapping[str, tuple[str, tuple[str, ...]]] | None,
        dimensions: Mapping[str, tuple[str, ...]] | None,
    ) -> Iterator[str]:
        """Os exemplos usam somente competências recebidas; nenhum mês é presumido."""
        if not coverage:
            return
        contextual_profile = self._profile_with_dimension_values(dimensions)
        yield from spelling_suggestions(question, contextual_profile)
        normalized = _normalize(question)
        for rule in self.profile.ambiguities:
            if not any(_normalize(phrase) in normalized for phrase in rule.phrases):
                continue
            replacement = rule.confirmation_phrase
            alternative = None
            if replacement is None and len(rule.alternative_metric_ids) == 1:
                alternative = next(m for m in self.profile.metrics
                                   if m.id == rule.alternative_metric_ids[0])
                replacement = alternative.aliases[0]
            candidate = (_replace_in_place(question, rule.phrases, replacement)
                         if replacement else None)
            # O mesmo indicador duas vezes ("receita faturada versus receita") não é exemplo.
            if candidate is not None and (
                alternative is None or len(_find_phrases(candidate, alternative.aliases)) == 1
            ):
                yield candidate
        recognized_metrics = [metric for metric in self.profile.metrics
                              if _find_phrases(question, metric.aliases)]
        metrics = recognized_metrics or self.profile.metrics
        compare = any(_normalize(term) in normalized for term in self.profile.comparison_terms)
        for metric in metrics:
            kind, competencies = coverage.get(metric.id, (None, ()))
            if kind != "monthly" or not competencies:
                continue
            periods = [monthly_period_label(period) for period in sorted(competencies)]
            alias = metric.label.lower() if metric.label else metric.aliases[0]
            original = normalize_calendar_phrases(question)
            temporal_phrases = (*self.profile.period_phrases, *explicit_monthly_phrases(original))
            for start, end, _ in reversed(_find_phrases(original, temporal_phrases)):
                original = original[:start] + " " * (end - start) + original[end:]
            original = _UNRECOGNIZED_CALENDAR.sub(" ", original)
            original = " ".join(original.split()).rstrip(" ?.")
            original = re.sub(
                r"\b(?:entre\s+e|de\s+(?:a|para)|em|no|na|nos|nas|de)\s*$",
                "", original,
            ).strip()
            constraints = tuple(
                phrase for dimension in contextual_profile.dimensions
                for phrase in (*dimension.aliases,
                               *(a for value in dimension.values for a in value.aliases))
            ) + tuple(phrase for rule in self.profile.detail_rules for phrase in rule.phrases)
            has_constraint = bool(
                _find_phrases(original, constraints) or re.search(r"\d", original)
                or re.search(r"\b(?:em|no|na|para)\s+\w+", _normalize(original))
            )
            period = (f"entre {periods[-2]} e {periods[-1]}"
                      if compare and metric.supports_comparison and len(periods) >= 2
                      else f"em {periods[-1]}")
            yield f"{original} {period}?"
            parents = {dimension.parent_dimension_id for dimension in self.profile.dimensions}
            for dimension in self.profile.dimensions:
                values = (dimensions or {}).get(dimension.id, ())
                if dimension.id in parents and values:
                    for child in self.profile.dimensions:
                        matches = _find_phrases(original, child.aliases)
                        if child.parent_dimension_id == dimension.id and matches:
                            end = matches[0][1]
                            yield (f"{original[:end]} de {values[0]}{original[end:]} "
                                   f"{period}?")
                    yield (f"{original} no {dimension.aliases[0]} de {values[0]} "
                           f"{period}?")
            if not has_constraint and compare and metric.supports_comparison and len(periods) >= 2:
                yield f"Compare {alias} entre {periods[-2]} e {periods[-1]}."
            if not has_constraint:
                yield f"Quero consultar {alias} em {periods[-1]}."

    def _plan(
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
        if profile.structured_dimension_filters:
            completed = pending_year_answer(question, context or [], profile)
            if completed is not None:
                question, context = completed, []
            competencies = tuple(period for _, periods in (temporal_coverage or {}).values()
                                 for period in periods)
            question = expand_short_calendar_year(question, competencies)
            question = normalize_calendar_phrases(question)
            context = [
                turn.model_copy(update={"content": normalize_calendar_phrases(
                    expand_short_calendar_year(turn.content, competencies),
                )})
                if turn.role == "user" else turn
                for turn in context or []
            ]
            question = complete_contextual_period(question, context)
            phrases = tuple(dict.fromkeys(
                phrase for text in (question, *(turn.content for turn in context or []))
                for phrase in explicit_monthly_phrases(text)
            ))
            if phrases:
                data = profile.model_dump(mode="python")
                data["period_phrases"] = tuple(dict.fromkeys((*profile.period_phrases, *phrases)))
                profile = DomainProfile.model_validate(data)
        interpreter = (
            self._interpreter
            if profile is self._access_policy.profile
            else QuestionInterpreter(profile, max_rows=self._max_rows)
        )
        plan_builder = (
            self._plan_builder
            if profile is self._access_policy.profile
            else ReadPlanBuilder(
                profile, self._access_policy.source_id, default_limit=self._max_rows
            )
        )
        plan_validator = (
            self._plan_validator
            if profile is self._access_policy.profile
            else ReadPlanValidator(
                profile, self._access_policy.source_id, self._access_policy,
                max_rows=self._max_rows,
            )
        )
        pending_temporal = None
        if (temporal_coverage is not None and context and len(context) >= 2
                and context[-2].role == "user" and context[-1].role == "assistant"):
            previous = interpreter.interpret(context[-2].content, context[:-2])
            if previous.intent is not None:
                try:
                    plan_builder.build(previous.intent, temporal_coverage)
                except TemporalCoverageUnavailable:
                    pending_temporal = previous.intent
                except PlanCapabilityUnavailable:
                    pass
        interpretation = interpreter.interpret(
            question, context, pending_temporal_intent=pending_temporal,
        )
        if interpretation.status is InterpretationStatus.NEEDS_CLARIFICATION:
            if trace is not None:
                trace.emit(EventStage.PLAN, EventCode.CLARIFICATION, EventOutcome.SUCCESS)
            return PlannedQuestion(
                interpretation=interpretation, pending_question=interpretation.pending_question,
            )

        assert interpretation.intent is not None
        try:
            proposed = plan_builder.build(interpretation.intent, temporal_coverage)
            approved = self._approve(proposed, access_context, trace, plan_validator)
        except PlanCapabilityUnavailable as exc:
            if trace is not None:
                trace.emit(EventStage.PLAN, EventCode.CLARIFICATION, EventOutcome.SUCCESS)
            return PlannedQuestion(
                interpretation=interpretation,
                pending_question=intent_question(interpretation.intent, profile),
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

        approved = await asyncio.to_thread(self._approve, proposed, access_context, trace)
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
        dimension_value_coverage: Mapping[str, tuple[str, ...]] | None = None,
    ) -> tuple[LogicalReadPlan, EvidenceLookupResult]:
        """Confere o resultado recebido de quem executou o plano; nunca chama a fonte.

        Reaprova o plano no escopo atual e exige o mesmo fingerprint do planejamento. A
        publicação esperada vem do chamador confiável, nunca do próprio lookup.
        """

        profile = self._profile_with_dimension_values(dimension_value_coverage)
        validator = ReadPlanValidator(
            profile, self._access_policy.source_id, self._access_policy,
            max_rows=self._max_rows,
        )
        approved = self._approve(plan, access_context, trace, validator)
        try:
            if plan_fingerprint != approved.fingerprint():
                raise EvidenceContractInvalid("fingerprint divergente do plano aprovado")
            evidence_result = self._check_lookup(
                approved, lookup, expected_batch_ref, profile=profile
            )
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
        *, profile: DomainProfile | None = None,
    ) -> EvidenceLookupResult:
        if not isinstance(evidence_result, EvidenceLookupResult):
            raise TypeError("Evidence source returned an unsupported result type.")
        evidence_result = EvidenceLookupResult.model_validate(evidence_result.model_dump())
        guard = (self._evidence_guard if profile is None else EvidenceGuard(
            profile, max_bytes=self._max_evidence_bytes,
        ))
        return guard.validate(approved, evidence_result, expected_batch_ref=expected_batch_ref)

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
            await trace.emit_async(EventStage.SOURCE, EventCode.STARTED, EventOutcome.STARTED)
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
                await trace.emit_async(EventStage.SOURCE, EventCode.COMPLETED, EventOutcome.SUCCESS)
            await asyncio.to_thread(self._emit_evidence, evidence_result, trace)
        except AuditUnavailable:
            raise
        except EvidenceToolUnavailable:
            if trace is not None:
                await trace.emit_async(EventStage.SOURCE, EventCode.UNAVAILABLE, EventOutcome.ERROR)
            raise
        except EvidenceAccessDenied:
            if trace is not None:
                await trace.emit_async(EventStage.SOURCE, EventCode.DENIED, EventOutcome.REFUSED)
            raise
        except EvidenceContractInvalid:
            if trace is not None:
                await trace.emit_async(EventStage.EVIDENCE, EventCode.INVALID, EventOutcome.ERROR)
            raise
        except ExecutionLimitExceeded:
            raise
        except (TypeError, ValidationError) as exc:
            if trace is not None:
                await trace.emit_async(EventStage.EVIDENCE, EventCode.INVALID, EventOutcome.ERROR)
            raise EvidenceContractInvalid("Evidence source returned an invalid result.") from exc
        except Exception as exc:
            if trace is not None:
                await trace.emit_async(EventStage.SOURCE, EventCode.UNAVAILABLE, EventOutcome.ERROR)
            raise EvidenceToolUnavailable("Evidence source failed.") from exc
        return evidence_result

    @staticmethod
    def _status_for(result: EvidenceLookupResult) -> AnalysisPlanStatus:
        if result.status is EvidenceLookupStatus.AVAILABLE:
            return AnalysisPlanStatus.READY
        if result.status is EvidenceLookupStatus.NEEDS_CLARIFICATION:
            return AnalysisPlanStatus.NEEDS_CLARIFICATION
        return AnalysisPlanStatus.NO_EVIDENCE
