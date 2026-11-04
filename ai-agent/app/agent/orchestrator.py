"""Coordena evidência e geração sem acoplar o serviço a um fornecedor."""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import TypeVar

from pydantic import ValidationError

from app.agent.documentation import DocumentationResponder, conceptual_question
from app.agent.execution import (
    ExecutionController,
    ExecutionLimitExceeded,
    RequestBudget,
    authorized_cache_scope,
)
from app.agent.grounding import has_unsupported_claims
from app.agent.planner import PlannedQuestion, QuestionAnalysisPlanner
from app.agent.read_plan import PlanCapabilityUnavailable
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
from app.schemas.evidence import EvidenceLookupResult, EvidenceLookupStatus, EvidenceResult
from app.schemas.internal import (
    QuestionPlanRequest,
    QuestionPlanResponse,
    QuestionPlanStatus,
    QuestionSynthesisRequest,
)
from app.schemas.questions import (
    AppliedQueryContext,
    QuestionRequest,
    QuestionResponse,
    QuestionStatus,
)
from app.schemas.read_plan import LogicalReadPlan
from app.schemas.responses import FailureCode, map_failure

logger = logging.getLogger(__name__)
_Outcome = TypeVar("_Outcome", QuestionResponse, QuestionResponse | PlannedQuestion)
_PT_BR_SEPARATORS = str.maketrans({",": ".", ".": ","})


def _format_pt_br_number(value: int | float) -> str:
    """Usa milhar com ponto e decimal com vírgula, preservando até quatro casas."""

    formatted = f"{value:,.4f}".rstrip("0").rstrip(".")
    return ("0" if formatted == "-0" else formatted).translate(_PT_BR_SEPARATORS)


def _lowercase_title(title: str) -> str:
    """Minusculiza só a primeira letra, preservando siglas como UC e kWh."""

    first = title.split(maxsplit=1)[0] if title else ""
    return title if any(c.isupper() for c in first[1:]) else title[:1].lower() + title[1:]


def _describe_observation(
    observation: dict[str, object],
    dimension_labels: dict[str, str] | None = None,
    *,
    human_readable: bool = False,
) -> str:
    labels: list[str] = []
    if "period" in observation:
        labels.append(str(observation["period"]))
    if "label" in observation:
        labels.append(str(observation["label"]))
    dimensions = observation.get("dimensions", {})
    if isinstance(dimensions, dict):
        for dimension_id, dimension_value in dimensions.items():
            label = (dimension_labels or {}).get(dimension_id, dimension_id)
            labels.append(f"{label}: {dimension_value}")
    value = observation["value"]
    unit = str(observation["unit"])
    is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    if unit in {"BRL", "R$"} and is_number:
        formatted = f"{abs(value):,.2f}".translate(_PT_BR_SEPARATORS)
        sign = "-" if value < 0 and formatted != "0,00" else ""
        value_with_unit = f"{sign}R$ {formatted}"
    elif (
        human_readable
        and unit in {"protocolos", "UCs", "ocorrências"}
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and float(value).is_integer()
    ):
        count = f"{value:,.0f}".replace(",", ".")
        singular = float(value) == 1
        label = {
            "protocolos": "chamado de atendimento" if singular else "chamados de atendimento",
            "UCs": "UC" if singular else "UCs",
            "ocorrências": "ocorrência" if singular else "ocorrências",
        }[unit]
        value_with_unit = f"{count} {label}"
    elif human_readable and is_number:
        separator = "" if unit == "%" else " "
        value_with_unit = f"{_format_pt_br_number(value)}{separator}{unit}"
    else:
        value_with_unit = f"{value} {unit}"
    if human_readable:
        period = str(observation.get("period", ""))
        months = (
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        )
        if (
            len(period) == 7
            and period[4] == "-"
            and period[:4].isdigit()
            and period[5:].isdigit()
            and 1 <= int(period[5:]) <= 12
        ):
            period = f"{months[int(period[5:]) - 1]} de {period[:4]}"
        details = labels[1:] if "period" in observation else labels
        suffix = f" ({'; '.join(details)})" if details else ""
        return f"{value_with_unit}{' em ' + period if period else ''}{suffix}"
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
        documentation_responder: DocumentationResponder | None = None,
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
        self._documentation = documentation_responder

    async def answer(
        self,
        request: QuestionRequest,
        access_context: AccessContext | None = None,
        correlation_id: str | None = None,
    ) -> QuestionResponse:
        trace = self._trace(
            correlation_id or (access_context.correlation_id if access_context else None)
        )
        return await self._run(
            trace,
            lambda budget: self._answer_with_budget(request, access_context, budget, trace),
        )

    async def plan(self, request: QuestionPlanRequest, correlation_id: str) -> QuestionPlanResponse:
        """Planeja números sem SQL/modelo; conceitos podem recuperar documentação autorizada."""

        access_context = request.access_scope.to_context(correlation_id)
        trace = self._trace(correlation_id)
        documentation_reference = None

        async def plan_only(_budget: RequestBudget) -> QuestionResponse | PlannedQuestion:
            nonlocal documentation_reference
            if self._documentation is not None and conceptual_question(request.question):
                refusal = await asyncio.to_thread(self._safety_refusal, request, trace)
                if refusal is not None:
                    return refusal
                result = await self._documentation.respond(
                    request.question, access_context, _budget, trace
                )
                documentation_reference = result.reference
                return result.response
            return await asyncio.to_thread(
                self._plan_step,
                request,
                access_context,
                trace,
                preserve_clarification=True,
            )

        outcome = await self._run(
            trace, plan_only, timeout_seconds=request.remaining_timeout_ms / 1000
        )
        if isinstance(outcome, PlannedQuestion):
            if outcome.read_plan is None:
                message = (outcome.clarification.message if outcome.clarification
                           else outcome.interpretation.clarification_question)
                return QuestionPlanResponse(
                    correlation_id=correlation_id, status=QuestionPlanStatus.NEEDS_CLARIFICATION,
                    pending_question=outcome.pending_question,
                    response=QuestionResponse(status=QuestionStatus.NEEDS_CLARIFICATION,
                                              correlation_id=correlation_id, message=message),
                )
            assert outcome.read_plan is not None
            return QuestionPlanResponse(
                correlation_id=correlation_id,
                status=QuestionPlanStatus.PLANNED,
                plan=outcome.read_plan,
                plan_fingerprint=outcome.read_plan.fingerprint(),
            )
        return QuestionPlanResponse(
            correlation_id=correlation_id,
            status=QuestionPlanStatus(outcome.status.value),
            response=outcome.model_copy(update={"correlation_id": correlation_id}),
            documentation_reference=(documentation_reference
                                     if outcome.status is QuestionStatus.ANSWERED else None),
        )

    async def synthesize(
        self,
        request: QuestionSynthesisRequest,
        correlation_id: str,
    ) -> QuestionResponse:
        """Operação sintetizar: confere o lookup recebido e gera a resposta, sem chamar a fonte.

        `request.expected_batch_ref` vem do Backend confiável e é independente do lookup.
        """

        access_context = request.access_scope.to_context(correlation_id)
        trace = self._trace(correlation_id)
        return await self._run(
            trace,
            lambda budget: self._synthesize_with_budget(
                request, access_context, request.expected_batch_ref, budget, trace
            ),
            timeout_seconds=request.remaining_timeout_ms / 1000,
        )

    def _trace(self, correlation_id: str | None) -> EventTrace:
        return EventTrace(
            self._events,
            "question",
            correlation_id,
            require_durable=self._require_durable_audit,
        )

    async def _run(
        self,
        trace: EventTrace,
        action: Callable[[RequestBudget], Awaitable[_Outcome]],
        *,
        timeout_seconds: float | None = None,
    ) -> _Outcome | QuestionResponse:
        try:
            await trace.emit_async(EventStage.REQUEST, EventCode.STARTED, EventOutcome.STARTED)
            response = await self._execution.run(action, timeout_seconds=timeout_seconds)
        except AuditUnavailable:
            return self._recoverable_error(FailureCode.AUDIT_UNAVAILABLE)
        except asyncio.CancelledError:
            with suppress(AuditUnavailable):
                await trace.emit_async(
                    EventStage.RESPONSE,
                    EventCode.CANCELLED,
                    EventOutcome.CANCELLED,
                )
            raise
        except ExecutionLimitExceeded:
            response = self._recoverable_error(FailureCode.EXECUTION_LIMIT)
        try:
            if isinstance(response, PlannedQuestion):
                await trace.emit_async(
                    EventStage.RESPONSE,
                    EventCode.READY if response.read_plan else EventCode.CLARIFICATION,
                    EventOutcome.SUCCESS,
                )
                return response
            await trace.emit_async(
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
        if (
            self._documentation is not None
            and access_context is not None
            and conceptual_question(request.question)
        ):
            refusal = await asyncio.to_thread(self._safety_refusal, request, trace)
            if refusal is not None:
                return refusal
            result = await self._documentation.respond(
                request.question, access_context, budget, trace
            )
            return result.response
        planned = await asyncio.to_thread(self._plan_step, request, access_context, trace)
        if isinstance(planned, QuestionResponse):
            return planned
        assert planned.read_plan is not None
        try:
            lookup = await self._analysis_planner.retrieve(
                planned.read_plan, access_context, budget, trace
            )
        except EvidenceAccessDenied:
            return self._refused(FailureCode.ACCESS_DENIED)
        except EvidenceContractInvalid:
            logger.warning("A fonte de evidências retornou um contrato inválido.")
            return self._recoverable_error(FailureCode.INVALID_SOURCE_RESPONSE)
        except EvidenceToolUnavailable:
            logger.warning("Falha ao consultar a fonte de evidências.")
            return self._recoverable_error(FailureCode.SOURCE_UNAVAILABLE)
        assert access_context is not None
        return await self._respond(
            request, planned.read_plan, lookup, access_context, budget, trace
        )

    async def _synthesize_with_budget(
        self,
        request: QuestionSynthesisRequest,
        access_context: AccessContext,
        expected_batch_ref: str | None,
        budget: RequestBudget,
        trace: EventTrace,
    ) -> QuestionResponse:
        refusal = await asyncio.to_thread(self._safety_refusal, request, trace)
        if refusal is not None:
            return refusal
        try:
            read_plan, lookup = await asyncio.to_thread(
                self._analysis_planner.accept_lookup,
                request.plan,
                request.plan_fingerprint,
                request.lookup,
                access_context,
                expected_batch_ref=expected_batch_ref,
                trace=trace,
                dimension_value_coverage={
                    item.dimension_id: item.values for item in request.dimension_value_coverage
                },
            )
        except EvidenceAccessDenied:
            return self._refused(FailureCode.ACCESS_DENIED)
        except (PlanCapabilityUnavailable, EvidenceContractInvalid):
            logger.warning("O plano ou o resultado recebido para síntese é inválido.")
            return self._recoverable_error(FailureCode.INVALID_SOURCE_RESPONSE)
        return await self._respond(request, read_plan, lookup, access_context, budget, trace)

    def _plan_step(
        self,
        request: QuestionRequest,
        access_context: AccessContext | None,
        trace: EventTrace,
        *,
        preserve_clarification: bool = False,
    ) -> QuestionResponse | PlannedQuestion:
        """Plano aprovado ou a resposta final de recusa ou esclarecimento; sem fonte."""

        if access_context is None:
            trace.emit(EventStage.POLICY, EventCode.DENIED, EventOutcome.REFUSED)
            return self._refused(FailureCode.ACCESS_DENIED)
        refusal = self._safety_refusal(request, trace)
        if refusal is not None:
            return refusal

        try:
            planned = self._analysis_planner.plan(
                request.question,
                request.context,
                access_context,
                trace,
                temporal_coverage=(
                    {
                        item.metric_id: (item.kind, item.competencies)
                        for item in request.temporal_coverage
                    }
                    if isinstance(request, QuestionPlanRequest)
                    and request.access_scope.source_id.startswith("gold.")
                    and request.access_scope.profile_id == "v-energy-grid-360-gold"
                    else None
                ),
                dimension_value_coverage=(
                    {item.dimension_id: item.values for item in request.dimension_value_coverage}
                    if isinstance(request, QuestionPlanRequest)
                    and request.access_scope.source_id.startswith("gold.")
                    and request.access_scope.profile_id == "v-energy-grid-360-gold"
                    else None
                ),
            )
        except EvidenceAccessDenied:
            return self._refused(FailureCode.ACCESS_DENIED)
        if planned.read_plan is None:
            if preserve_clarification:
                return planned
            question = planned.interpretation.clarification_question
            if planned.clarification is not None:
                question = planned.clarification.message
            return QuestionResponse(
                status=QuestionStatus.NEEDS_CLARIFICATION,
                message=question,
            )
        return planned

    def _safety_refusal(
        self, request: QuestionRequest, trace: EventTrace
    ) -> QuestionResponse | None:
        refusal = self._safety_gate.refusal_code(request.question)
        for turn in request.context:
            if refusal is not None:
                break
            refusal = self._safety_gate.refusal_code(turn.content)
        if refusal is None:
            return None
        trace.emit(EventStage.POLICY, EventCode.DENIED, EventOutcome.REFUSED)
        code = (
            FailureCode.OUT_OF_SCOPE
            if refusal is SafetyRefusalCode.OUT_OF_SCOPE
            else FailureCode.SECURITY_VIOLATION
        )
        return self._refused(code)

    async def _respond(
        self,
        request: QuestionRequest,
        read_plan: LogicalReadPlan,
        lookup: EvidenceLookupResult,
        access_context: AccessContext,
        budget: RequestBudget,
        trace: EventTrace,
    ) -> QuestionResponse:
        """Resposta a partir de um lookup já conferido; só chama o modelo com evidência."""

        if lookup.status is EvidenceLookupStatus.NEEDS_CLARIFICATION:
            return QuestionResponse(
                status=QuestionStatus.NEEDS_CLARIFICATION,
                message=lookup.message,
            )
        if lookup.status is EvidenceLookupStatus.NO_EVIDENCE:
            return QuestionResponse(
                status=QuestionStatus.NO_EVIDENCE,
                message=lookup.message,
                limitations=lookup.limitations,
            )
        if lookup.status is not EvidenceLookupStatus.AVAILABLE or lookup.evidence is None:
            return self._recoverable_error(FailureCode.INVALID_SOURCE_RESPONSE)
        evidence = lookup.evidence.model_copy(
            update={"cache_scope": authorized_cache_scope(access_context, read_plan)}
        )
        observations = {row["observation_id"]: row for row in evidence.records}
        tier: ModelTier | None = None
        adapter = self._model_adapter
        if self._model_router is not None:
            # O builder copia o domínio da intenção para o plano aprovado.
            tier, adapter = self._model_router.route(
                intent=read_plan.domain_id,
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
        if evidence.provenance and evidence.provenance.published_windows:
            period = evidence.provenance.published_windows.describe()
        filters = {
            item.dimension_id: item.values[0] if len(item.values) == 1 else list(item.values)
            for item in read_plan.filters
        }
        filter_operators = {item.dimension_id: item.operator for item in read_plan.filters}
        numeric_mismatch = has_unsupported_claims(
            generated,
            observations,
            metric=read_plan.metric_id,
            period=period,
            filters=filters,
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
            generated,
            observations,
            metric=read_plan.metric_id,
            period=period,
            filters=filters,
            filter_operators=filter_operators,
        ):
            return QuestionResponse(
                status=QuestionStatus.REFUSED,
                message=map_failure(FailureCode.UNGROUNDED_OUTPUT).message,
                evidence=[evidence.reference],
                limitations=lookup.limitations,
                error=map_failure(FailureCode.UNGROUNDED_OUTPUT).error,
                model_tier=tier,
            )

        profile = self._analysis_planner.profile
        metric = next(item for item in profile.metrics if item.id == read_plan.metric_id)
        labels = {item.id: item.label for item in profile.dimensions}
        answer = None
        if generated.status == "answered":
            answer_observation_ids = (
                tuple(observations)
                if read_plan.comparison_periods or read_plan.group_by_dimension_ids
                or evidence.provenance.published_windows is not None
                else generated.observation_ids
            )
            values = ", ".join(
                _describe_observation(
                    {key: value for key, value in observations[item].items()
                     if key != "period" or not metric.accumulated_period_phrases},
                    labels, human_readable=not evidence.reference.is_demo,
                )
                for item in answer_observation_ids
            )
            prefix = "Demonstração sintética: " if evidence.reference.is_demo else ""
            title = metric.label or "Resultado da consulta"
            if evidence.reference.is_demo:
                answer = f"{prefix}{title} — {period}: {values}."
            elif (len(answer_observation_ids) == 1
                  and read_plan.metric_id == "service.accumulated_attendance"):
                answer = f"No histórico acumulado, foram registrados {values}."
            elif len(answer_observation_ids) == 1:
                answer = f"Para {_lowercase_title(title)}, o resultado foi de {values}."
            elif read_plan.comparison_periods:
                first = _describe_observation(observations["row_1"], labels, human_readable=True)
                last = _describe_observation(observations["row_2"], labels, human_readable=True)
                delta = _describe_observation(
                    {key: value for key, value in observations["row_3"].items()
                     if key not in {"period", "dimensions"}}, human_readable=True,
                )
                answer = f"{title}: {first}; {last}. Variação absoluta: {delta}"
                if "row_4" in observations:
                    percentage = _describe_observation(
                        {"value": observations["row_4"]["value"], "unit": "%"},
                        human_readable=True,
                    )
                    answer += f" ({percentage})"
                answer += "."
            elif read_plan.group_by_dimension_ids and not read_plan.comparison_periods:
                rows = list(observations.values())
                smallest = read_plan.order is not None and read_plan.order.direction.value == "asc"
                if read_plan.order is not None and read_plan.limit > 1:
                    group_label = " e ".join(
                        labels.get(dimension_id, dimension_id).lower()
                        for dimension_id in read_plan.group_by_dimension_ids
                    )
                    heading = (
                        f"{'menores' if smallest else 'maiores'} valores de "
                        f"{_lowercase_title(title)} por {group_label} foram:\n"
                    )
                    lines = []
                    # Reserva cabeçalho e aviso de tabela/CSV dentro de ResponseText.
                    remaining = 4000 - len(heading) - 200
                    for row in rows[:10]:
                        line = _describe_observation(row, labels, human_readable=True)
                        if len(line) + 3 > remaining:
                            break
                        lines.append(line)
                        remaining -= len(line) + 3
                    answer = (
                        f"Os {len(lines)} {heading}"
                        + "\n".join(f"• {line}" for line in lines)
                    )
                    if not lines:
                        answer = f"Foram encontrados {len(rows)} resultados de {title.lower()}."
                    if len(rows) > len(lines):
                        answer += (
                            f"\nExibidos {len(lines)} de {len(rows)} resultados. "
                            "Consulte os demais na tabela ou baixe os dados em CSV."
                        )
                else:
                    extreme = (min if smallest else max)(rows, key=lambda row: row["value"])
                    described = _describe_observation(extreme, labels, human_readable=True)
                    extreme_label = "menor" if smallest else "maior"
                    answer = (
                        f"Entre os {len(rows)} grupos retornados, o {extreme_label} "
                        f"valor de {_lowercase_title(title)} foi de {described}."
                    )
            else:
                lines = [
                    _describe_observation(observations[item], labels, human_readable=True)
                    for item in answer_observation_ids
                ]
                answer = (
                    f"Resultados de {_lowercase_title(title)} no período solicitado:\n"
                    + "\n".join(f"• {line}" for line in lines)
                )
            if read_plan.comparison_periods and "row_4" not in observations:
                answer += " Variação percentual indisponível: a base inicial não é positiva."
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
            limitations=lookup.limitations,
            error=error,
            model_tier=tier,
            analysis_context=AppliedQueryContext(
                batch_reference=(evidence.provenance.batch_ref if evidence.provenance else None),
                metric=read_plan.metric_id,
                metric_label=metric.label,
                metric_definition=metric.definition,
                filter_labels={
                    item.dimension_id: labels[item.dimension_id] for item in read_plan.filters
                },
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
            await trace.emit_async(EventStage.MODEL, start_code, EventOutcome.STARTED)
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
                await trace.emit_async(EventStage.MODEL, EventCode.REFUSED, EventOutcome.REFUSED)
            else:
                await trace.emit_async(EventStage.MODEL, EventCode.COMPLETED, EventOutcome.SUCCESS)
        except ModelProviderUnavailable:
            await trace.emit_async(EventStage.MODEL, EventCode.UNAVAILABLE, EventOutcome.ERROR)
            return self._recoverable_error(FailureCode.MODEL_UNAVAILABLE)
        except ModelProviderRejected:
            await trace.emit_async(EventStage.MODEL, EventCode.REFUSED, EventOutcome.REFUSED)
            return self._recoverable_error(FailureCode.MODEL_REJECTED)
        except ModelProviderInvalidResponse:
            await trace.emit_async(EventStage.MODEL, EventCode.INVALID, EventOutcome.ERROR)
            return self._recoverable_error(FailureCode.INVALID_MODEL_OUTPUT)
        except ExecutionLimitExceeded:
            raise
        except AuditUnavailable:
            raise
        except (ValidationError, TypeError, ValueError):
            await trace.emit_async(EventStage.MODEL, EventCode.INVALID, EventOutcome.ERROR)
            logger.warning("O adaptador de modelo retornou uma resposta inválida.")
            return self._recoverable_error(FailureCode.INVALID_MODEL_OUTPUT)
        except Exception:
            await trace.emit_async(EventStage.MODEL, EventCode.UNAVAILABLE, EventOutcome.ERROR)
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
