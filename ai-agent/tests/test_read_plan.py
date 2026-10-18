"""Gate de plano lógico: expectativa explícita e executor falso observado."""

import asyncio

import pytest
from pydantic import ValidationError

from app.agent.access import ReadAccessPolicy
from app.agent.interpreter import QuestionInterpreter
from app.agent.planner import AnalysisPlanStatus, QuestionAnalysisPlanner
from app.agent.read_plan import (
    PlanCapabilityUnavailable,
    ReadPlanBuilder,
    ReadPlanValidator,
)
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.ports.evidence import EvidenceAccessDenied
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.domain_profile import DomainProfile
from app.schemas.evidence import EvidenceLookupResult, EvidenceLookupStatus
from app.schemas.interpretation import InterpretationStatus
from app.schemas.read_plan import LogicalReadPlan, ReadWindow

from .test_domain_profile import profile_data

CORRELATION = "0" * 32


class RecordingSource:
    def __init__(self) -> None:
        self.calls: list[LogicalReadPlan] = []

    async def retrieve(self, plan: LogicalReadPlan) -> EvidenceLookupResult:
        self.calls.append(plan)
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.NO_EVIDENCE,
            message="Nenhum registro da fonte artificial.",
        )


def _components(profile: DomainProfile, source: RecordingSource):
    policy = ReadAccessPolicy(profile, SYNTHETIC_SOURCE_ID)
    planner = QuestionAnalysisPlanner(QuestionInterpreter(profile), source, policy)
    validator = ReadPlanValidator(profile, SYNTHETIC_SOURCE_ID, policy)
    context = demo_access_context(profile, CORRELATION)
    return planner, validator, context


def _proposed(profile: DomainProfile, question: str) -> LogicalReadPlan:
    interpretation = QuestionInterpreter(profile).interpret(question)
    assert interpretation.status is InterpretationStatus.READY
    assert interpretation.intent is not None
    return ReadPlanBuilder(profile, SYNTHETIC_SOURCE_ID).build(interpretation.intent)


@pytest.mark.parametrize(
    ("profile", "question", "metric_id", "unit", "filter_value"),
    [
        (
            GRID360_DEMO_PROFILE,
            "Qual foi o consumo em Olinda no período de demonstração?",
            "energy.consumption",
            "unidades fictícias",
            "Olinda",
        ),
        (
            DomainProfile.model_validate(profile_data()),
            "Qual foi a chuva este mês em Recife?",
            "weather.rainfall",
            "milímetros demonstrativos",
            "Recife",
        ),
    ],
)
def test_same_validator_contract_approves_two_catalogs(
    profile: DomainProfile,
    question: str,
    metric_id: str,
    unit: str,
    filter_value: str,
) -> None:
    source = RecordingSource()
    planner, _, context = _components(profile, source)

    result = asyncio.run(planner.prepare(question, access_context=context))

    assert result.status is AnalysisPlanStatus.NO_EVIDENCE
    assert result.read_plan is not None
    assert result.read_plan.operation == "read"
    assert result.read_plan.metric_id == metric_id
    assert result.read_plan.unit == unit
    assert result.read_plan.window.phrase in profile.period_phrases
    assert result.read_plan.filters[0].operator == "eq"
    assert result.read_plan.filters[0].values == (filter_value,)
    assert result.read_plan.limit == 100
    assert source.calls == [result.read_plan]
    assert source.calls[0] is result.read_plan


def test_unsupported_lexical_filter_is_explained_without_source_call() -> None:
    source = RecordingSource()
    planner, _, context = _components(GRID360_DEMO_PROFILE, source)

    result = asyncio.run(
        planner.prepare(
            "Qual foi o consumo com queda acima de 30% no período de demonstração?",
            access_context=context,
        )
    )

    assert result.status is AnalysisPlanStatus.NEEDS_CLARIFICATION
    assert result.evidence_result is not None
    assert "filtro" in (result.evidence_result.message or "")
    assert result.read_plan is None
    assert source.calls == []


def test_unresolved_comparison_window_does_not_execute_partial_plan() -> None:
    source = RecordingSource()
    planner, _, context = _components(GRID360_DEMO_PROFILE, source)

    result = asyncio.run(
        planner.prepare(
            "Compare a receita entre o ano passado e este ano?",
            access_context=context,
        )
    )

    assert result.status is AnalysisPlanStatus.NEEDS_CLARIFICATION
    assert source.calls == []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"operation": "write"}, EvidenceAccessDenied),
        ({"metric_id": "unknown.metric"}, PlanCapabilityUnavailable),
        ({"unit": "kWh"}, PlanCapabilityUnavailable),
        ({"limit": 101}, PlanCapabilityUnavailable),
        ({"source_id": "other.source"}, EvidenceAccessDenied),
        ({"profile_id": "other.profile"}, EvidenceAccessDenied),
    ],
)
def test_proposed_plan_is_revalidated_before_executor(
    mutation: dict[str, object], expected: type[Exception]
) -> None:
    source = RecordingSource()
    planner, _, context = _components(GRID360_DEMO_PROFILE, source)
    proposed = _proposed(
        GRID360_DEMO_PROFILE,
        "Qual foi o consumo no período de demonstração?",
    ).model_dump(mode="python")
    proposed.update(mutation)

    for _ in range(2):
        with pytest.raises(expected):
            asyncio.run(planner.execute_plan(proposed, context))
    assert source.calls == []


def test_unsupported_operator_and_value_are_rejected_before_executor() -> None:
    source = RecordingSource()
    planner, _, context = _components(GRID360_DEMO_PROFILE, source)
    base = _proposed(
        GRID360_DEMO_PROFILE,
        "Qual foi o consumo em Olinda no período de demonstração?",
    ).model_dump(mode="python")

    for field, value in (
        ("operator", "gt"),
        ("values", ("Município inexistente",)),
        ("values", (42,)),
    ):
        proposal = {**base, "filters": [{**base["filters"][0], field: value}]}
        with pytest.raises(PlanCapabilityUnavailable):
            asyncio.run(planner.execute_plan(proposal, context))
    assert source.calls == []


def test_grain_and_order_must_be_supported_by_catalog() -> None:
    profile = DomainProfile.model_validate(profile_data())
    source = RecordingSource()
    planner, _, context = _components(profile, source)
    base = _proposed(profile, "Qual foi a chuva este mês em Recife?").model_dump(mode="python")

    for proposal in (
        {**base, "window": {**base["window"], "granularity": "year"}},
        {**base, "order": {"field_id": "unknown.field", "direction": "desc"}},
    ):
        with pytest.raises(PlanCapabilityUnavailable):
            asyncio.run(planner.execute_plan(proposal, context))
    assert source.calls == []


def test_bounded_window_and_in_filter_are_validated_without_sql() -> None:
    source = RecordingSource()
    planner, _, context = _components(GRID360_DEMO_PROFILE, source)
    base = _proposed(
        GRID360_DEMO_PROFILE,
        "Qual foi o consumo em Olinda no período de demonstração?",
    ).model_dump(mode="python")
    proposed = {
        **base,
        "window": {
            "kind": "bounded",
            "start": "2025-01-01",
            "end": "2025-12-31",
            "granularity": "month",
        },
        "filters": [
            {
                "dimension_id": "geography.municipality",
                "operator": "in",
                "values": ("Olinda", "Jaboatão dos Guararapes"),
            }
        ],
        "order": {"field_id": "energy.consumption", "direction": "desc"},
        "limit": 20,
    }

    approved, result = asyncio.run(planner.execute_plan(proposed, context))

    assert result.status is EvidenceLookupStatus.NO_EVIDENCE
    assert approved.window.start.isoformat() == "2025-01-01"
    assert approved.window.end.isoformat() == "2025-12-31"
    assert approved.filters[0].values == ("Olinda", "Jaboatão dos Guararapes")
    assert approved.order.field_id == "energy.consumption"
    assert approved.limit == 20
    assert source.calls == [approved]


def test_bounded_window_and_filter_limits_block_execution() -> None:
    source = RecordingSource()
    planner, _, context = _components(GRID360_DEMO_PROFILE, source)
    base = _proposed(
        GRID360_DEMO_PROFILE,
        "Qual foi o consumo em Olinda no período de demonstração?",
    ).model_dump(mode="python")
    proposals = (
        {
            **base,
            "window": {
                "kind": "bounded",
                "start": "2010-01-01",
                "end": "2025-12-31",
                "granularity": "month",
            },
        },
        {
            **base,
            "filters": [
                {
                    "dimension_id": "geography.municipality",
                    "operator": "eq",
                    "values": ("X" * 121,),
                }
            ],
        },
    )
    for proposed in proposals:
        with pytest.raises(PlanCapabilityUnavailable):
            asyncio.run(planner.execute_plan(proposed, context))
    assert source.calls == []


def test_a_tighter_scope_blocks_proposal_even_when_schema_is_valid() -> None:
    source = RecordingSource()
    planner, _, context = _components(GRID360_DEMO_PROFILE, source)
    proposal = _proposed(
        GRID360_DEMO_PROFILE,
        "Qual foi o consumo no período de demonstração?",
    )
    restricted = context.model_copy(
        update={"allowed_metric_ids": frozenset({"billing.revenue"})}
    )

    with pytest.raises(EvidenceAccessDenied):
        asyncio.run(planner.execute_plan(proposal, restricted))
    assert source.calls == []


def test_constructed_plan_and_nested_window_are_revalidated() -> None:
    source = RecordingSource()
    planner, _, context = _components(GRID360_DEMO_PROFILE, source)
    valid = _proposed(
        GRID360_DEMO_PROFILE,
        "Qual foi o consumo no período de demonstração?",
    )
    forged = LogicalReadPlan.model_construct(
        **{
            **dict(valid),
            "limit": 1_000,
            "window": ReadWindow.model_construct(
                kind="bounded",
                start=None,
                end=None,
                granularity=None,
            ),
        }
    )

    with pytest.raises(PlanCapabilityUnavailable):
        asyncio.run(planner.execute_plan(forged, context))
    assert source.calls == []


def test_missing_catalog_fails_composition_before_any_executor() -> None:
    with pytest.raises(ValueError, match="catálogo ausente"):
        ReadPlanBuilder(None, SYNTHETIC_SOURCE_ID)  # type: ignore[arg-type]


def test_read_plan_schema_refuses_write_and_incomplete_window() -> None:
    base = _proposed(
        GRID360_DEMO_PROFILE,
        "Qual foi o consumo no período de demonstração?",
    ).model_dump(mode="python")
    with pytest.raises(ValidationError):
        LogicalReadPlan.model_validate({**base, "operation": "write"})
    with pytest.raises(ValidationError):
        LogicalReadPlan.model_validate(
            {**base, "window": {"kind": "bounded", "start": "2025-01-01"}}
        )
