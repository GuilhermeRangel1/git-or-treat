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
    _plan_matches_semantics,
    _plan_snapshot,
    _proposal_contract_matches,
    _semantic_matches,
    _setup_case,
    _summary,
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


def test_all_fixture_cases_match_the_deterministic_baseline():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in fixture["cases"]:
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
        assert _matches(result, case["expected"], case["id"]), case["id"]


def test_benchmark_reports_semantic_accuracy_separately_from_provider_errors():
    summary = _summary([
        {"proposal_status": "ready", "gemini_correct": True,
         "proposal_contract_correct": True,
         "deterministic_correct": True, "latency_ms": 100,
         "same_plan_as_deterministic": True},
        {"proposal_status": "needs_clarification", "gemini_correct": True,
         "proposal_contract_correct": True,
         "deterministic_correct": True, "latency_ms": 200,
         "same_plan_as_deterministic": False},
        {"proposal_status": "error", "gemini_correct": False,
         "deterministic_correct": True, "latency_ms": 300},
    ])

    assert summary["eligible_case_count"] == 3
    assert summary["model_call_count"] == 3
    assert summary["proposal_success_count"] == 2
    assert summary["provider_error_count"] == 1
    assert summary["semantic_accuracy_percent"] == 100
    assert summary["planner_outcome_accuracy_percent"] == 66.67
    assert summary["sql_execution_count"] == 0
    assert summary["numeric_reconciliation_count"] == 0


def test_benchmark_keeps_semantic_and_planner_denominators_separate():
    summary = _summary([
        {"proposal_status": "ready", "semantic_correct": True,
         "proposal_contract_correct": True,
         "planner_correct": True, "deterministic_correct": True, "latency_ms": 100},
        {"proposal_status": "ready", "semantic_correct": True,
         "proposal_contract_correct": True,
         "planner_correct": False, "deterministic_correct": True, "latency_ms": 200},
        {"proposal_status": "error", "semantic_correct": False,
         "planner_correct": False, "deterministic_correct": True, "latency_ms": 300},
    ])

    assert summary["semantic_evaluation_case_count"] == 2
    assert summary["semantic_accuracy_percent"] == 100
    assert summary["planner_outcome_accuracy_percent"] == 33.33
    assert summary["proposal_contract_accuracy_percent"] == 66.67
    assert summary["provider_error_count"] == 1


def test_expanded_language_fixture_matches_deterministic_planner_oracles():
    fixture_path = FIXTURE.parent / "hnlu_language_expansion.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        core, request = _setup_case(case)
        coverage = {
            item.metric_id: (item.kind, item.competencies)
            for item in request.temporal_coverage
        }
        dimensions = {
            item.dimension_id: item.values for item in request.dimension_value_coverage
        }
        context = request.access_scope.to_context("00000000000040008000000000000001")
        result = core.question._analysis_planner.plan(
            request.question,
            request.context,
            context,
            temporal_coverage=coverage,
            dimension_value_coverage=dimensions,
        )
        assert _matches(result, case["expected"], case["id"]), (
            case["id"], _plan_snapshot(result)
        )


def test_semantic_score_accepts_explicit_aliases_but_contract_score_stays_strict():
    proposal = IntentInterpretation.model_validate({
        "status": "ready",
        "intent": {
            "domain": "revenue",
            "metric_id": "billing.revenue",
            "period_phrase": "2025-03",
            "geography_phrase": "Recife",
            "class_phrase": "familias",
        },
    })
    expected = {
        "status": "ready",
        "domain": "revenue",
        "metric_id": "billing.revenue",
        "dimension_ids": ["customer.consumption_class", "geography.municipality"],
        "filters": {
            "customer.consumption_class": "RESIDENCIAL",
            "geography.municipality": "Recife",
        },
        "period": {"start": "2025-03-01", "end": "2025-03-31"},
    }
    coverage = {"billing.revenue": ("monthly", ("2025-03",))}

    assert _semantic_matches(
        proposal, expected, coverage,
        {"geography.municipality": ("Recife",)},
    )
    assert not _proposal_contract_matches(proposal, expected)


def test_semantic_score_accepts_previous_equal_length_window_wording():
    proposal = IntentInterpretation.model_validate({
        "status": "ready",
        "intent": {
            "domain": "consumption",
            "metric_id": "energy.consumption",
            "dimension_ids": ["geography.neighborhood"],
            "group_by_dimension_ids": ["geography.neighborhood"],
            "ranking_direction": "asc",
            "period_phrase": "últimos 12 meses",
            "comparison_period_phrases": [
                "últimos 12 meses", "12 meses imediatamente anteriores",
            ],
        },
    })
    expected = {
        "status": "ready",
        "domain": "consumption",
        "metric_id": "energy.consumption",
        "dimension_ids": ["geography.neighborhood"],
        "group_by_dimension_ids": ["geography.neighborhood"],
        "ranking_direction": "asc",
        "comparison_periods": {"prior_months": 12},
        "period": {"start": "2025-07-01", "end": "2026-06-30"},
    }
    coverage = {
        "energy.consumption": (
            "monthly", tuple(
                f"{year}-{month:02d}"
                for year, first, last in ((2024, 7, 12), (2025, 1, 12), (2026, 1, 6))
                for month in range(first, last + 1)
            ),
        ),
    }

    assert _semantic_matches(proposal, expected, coverage)


def test_planner_score_checks_filters_and_period_not_only_created_plan_status():
    fixture_path = FIXTURE.parent / "hnlu_language_expansion.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    case = next(item for item in fixture["cases"] if item["id"] == "FUP-03")
    core, request = _setup_case(case)
    coverage = {
        item.metric_id: (item.kind, item.competencies)
        for item in request.temporal_coverage
    }
    dimensions = {
        item.dimension_id: item.values for item in request.dimension_value_coverage
    }
    context = request.access_scope.to_context("00000000000040008000000000000001")
    result = core.question._analysis_planner.plan(
        request.question, request.context, context,
        temporal_coverage=coverage, dimension_value_coverage=dimensions,
    )

    assert _plan_matches_semantics(result, case["expected_semantics"], coverage)
    incorrect = {**case["expected_semantics"], "period": {
        "start": "2025-01-01", "end": "2025-01-31",
    }}
    assert not _plan_matches_semantics(result, incorrect, coverage)


def test_model_derived_month_in_follow_up_is_admitted_only_when_coverage_proves_it():
    fixture_path = FIXTURE.parent / "hnlu_language_expansion.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    case = next(item for item in fixture["cases"] if item["id"] == "FUP-03")
    core, request = _setup_case(case)
    coverage = {
        item.metric_id: (item.kind, item.competencies)
        for item in request.temporal_coverage
    }
    dimensions = {
        item.dimension_id: item.values for item in request.dimension_value_coverage
    }
    proposal = IntentInterpretation.model_validate({
        "status": "ready",
        "intent": {
            "domain": "revenue",
            "metric_id": "billing.revenue",
            "dimension_ids": [
                "customer.consumption_class", "geography.municipality",
            ],
            "geography_phrase": "Recife",
            "class_phrase": "RESIDENCIAL",
            "period_phrase": "fevereiro de 2025",
        },
    })

    result = core.question._analysis_planner.plan(
        request.question,
        request.context,
        request.access_scope.to_context("00000000000040008000000000000001"),
        temporal_coverage=coverage,
        dimension_value_coverage=dimensions,
        interpretation_override=proposal,
    )

    assert result.read_plan is not None
    assert result.read_plan.window.start.isoformat() == "2025-02-01"
    assert result.read_plan.window.end.isoformat() == "2025-02-28"


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


def test_summary_counts_recovered_invalid_response_without_counting_provider_error():
    summary = _summary([{
        "proposal_status": "needs_clarification",
        "response_diagnostic": {
            "kind": "schema_validation",
            "recovered_with_catalog_clarification": True,
        },
        "deterministic_correct": True,
        "gemini_correct": True,
        "semantic_correct": True,
        "planner_correct": True,
        "proposal_contract_correct": True,
        "latency_ms": 100,
    }])

    assert summary["provider_error_count"] == 0
    assert summary["invalid_provider_response_count"] == 1
    assert summary["provider_response_recovery_count"] == 1


def test_summary_accepts_missing_response_diagnostics():
    summary = _summary([{
        "proposal_status": "ready",
        "deterministic_correct": True,
        "gemini_correct": True,
        "planner_correct": True,
        "proposal_contract_correct": True,
        "latency_ms": 100,
    }])

    assert summary["invalid_provider_response_count"] == 0
    assert summary["provider_response_recovery_count"] == 0
