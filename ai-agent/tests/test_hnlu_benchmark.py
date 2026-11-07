"""O benchmark compara planos completos e razões de esclarecimento esperadas."""

import json

from app.agent.planner import PlannedQuestion
from app.schemas.interpretation import (
    ClarificationReason,
    IntentInterpretation,
    InterpretationStatus,
)
from scripts.benchmark_hnlu_intent import (
    FIXTURE,
    SAMPLE_IDS,
    _matches,
    _plan_snapshot,
)
from tests.test_gold_question_filters import _setup


def test_selected_benchmark_cases_match_full_deterministic_oracles():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in fixture["cases"]}
    for case_id in SAMPLE_IDS:
        case = cases[case_id]
        core, request = _setup(case["question"])
        coverage = {
            item.metric_id: (item.kind, item.competencies)
            for item in request.temporal_coverage
        }
        dimensions = {
            item.dimension_id: item.values
            for item in request.dimension_value_coverage
        }
        result = core.question._analysis_planner.plan(
            request.question,
            request.context,
            request.access_scope.to_context("00000000000040008000000000000001"),
            temporal_coverage=coverage,
            dimension_value_coverage=dimensions,
        )
        assert _matches(result, case["expected"], case_id), case_id
        diagnostic = _plan_snapshot(result)
        assert diagnostic["status"] in {"planned", "needs_clarification"}
        if result.read_plan is not None:
            assert diagnostic["plan"]["metric_id"] == result.read_plan.metric_id
        else:
            assert diagnostic["plan"] is None


def test_composite_revenue_and_payment_question_accepts_both_valid_clarifications():
    result = PlannedQuestion(
        interpretation=IntentInterpretation(
            status=InterpretationStatus.NEEDS_CLARIFICATION,
            clarification_reason=ClarificationReason.MULTIPLE_METRICS,
            clarification_question="Qual medida deseja consultar?",
            intent=None,
        ),
        read_plan=None,
    )

    assert _matches(result, {"status": "needs_clarification"}, "GUARD-04")
    result.interpretation.clarification_reason = ClarificationReason.AMBIGUOUS_METRIC
    assert _matches(result, {"status": "needs_clarification"}, "GUARD-04")
    result.interpretation.clarification_reason = ClarificationReason.MISSING_PERIOD
    assert not _matches(result, {"status": "needs_clarification"}, "GUARD-04")
