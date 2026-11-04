"""O relatório precisa revelar regressões mesmo com acerto agregado alto."""

import copy

import pytest

from .evaluation_report import compare_reports, summarize_cases


def test_comparison_reveals_regression_omission_and_known_failure_changes():
    before = summarize_cases([
        {"id": "A", "category": "consumption", "checks": {"plan": True}},
        {"id": "B", "category": "privacy", "checks": {"privacy": False},
         "outcome": "known_failure_confirmed"},
        {"id": "C", "category": "network", "checks": {"status": True}},
    ])
    after = copy.deepcopy(before)
    after["cases"][0]["checks"]["plan"] = False
    after["cases"][1]["checks"]["privacy"] = True
    after["cases"].pop()
    delta = compare_reports(before, after)
    assert delta["regressions"] == [{"id": "A", "checks": ["plan"]}]
    assert delta["removed"] == ["C"]
    assert delta["known_failure_changes"] == ["B"]
    assert delta["gate_passed"] is False
    assert before["categories"]["privacy"] == {"total": 1, "passed": 0, "failed": 1}


def test_report_does_not_copy_sensitive_free_text_and_rejects_duplicate_ids():
    case = {"id": "SAFE-01", "category": "privacy", "checks": {"privacy": True},
            "question": "private prompt", "answer": "private answer", "token": "secret"}
    report = summarize_cases([case])
    assert "private" not in str(report) and "secret" not in str(report)
    with pytest.raises(ValueError, match="duplicado"):
        summarize_cases([case, case])


def test_expanded_report_is_repeatable_and_matches_the_frozen_baseline():
    import json
    from pathlib import Path

    from .expanded_evaluation import build_expanded_report

    report = build_expanded_report()
    assert report == build_expanded_report()
    baseline_path = Path(__file__).parents[1] / "reports" / "expanded-regression-baseline.json"
    baseline = json.loads(baseline_path.read_text("utf-8"))
    assert compare_reports(baseline, report)["gate_passed"]
    assert report["summary"]["total"] >= 160
    assert report["summary"]["failed"] == report["summary"]["known_failures"]
    assert {"observed_continuity", "authorization", "metric_semantics", "provenance"} <= (
        report["categories"].keys()
    )


def test_new_failed_check_and_evaluator_error_cannot_hide_in_passing_case():
    before = summarize_cases([
        {"id": "A", "category": "revenue", "checks": {"numeric": True}},
    ])
    after = copy.deepcopy(before)
    after["cases"][0]["checks"]["grounding"] = False
    assert not compare_reports(before, after)["gate_passed"]
    with pytest.raises(ValueError, match="booleanos"):
        summarize_cases([{"id": "A", "category": "revenue", "checks": {"numeric": 1}}])


def test_junit_import_discards_messages_and_requires_all_boundary_suites(tmp_path):
    from .evaluation_report import summarize_backend_junit

    path = tmp_path / "private.xml"
    path.write_text('<testsuite><testcase classname="tests.test_genai_profile_access" '
                    'name="private prompt"><failure>secret</failure></testcase></testsuite>')
    report = summarize_backend_junit(path)
    assert report["summary"]["failed"] == 2
    assert "private prompt" not in str(report) and "secret" not in str(report)


def test_synthesis_detects_mutated_numeric_provenance(monkeypatch):
    from . import gold_evaluation

    original = gold_evaluation._lookup

    def corrupt(*args, **kwargs):
        result = original(*args, **kwargs)
        result.evidence.provenance = result.evidence.provenance.model_copy(
            update={"unit": "wrong_unit"}
        )
        return result

    monkeypatch.setattr(gold_evaluation, "_lookup", corrupt)
    row = gold_evaluation.evaluate_gold_case(gold_evaluation.load_cases()[0])
    assert row["category"] == "revenue"
    assert not all(row["checks"].values())


def test_numeric_check_rejects_a_different_amount_with_the_same_suffix():
    from .gold_evaluation import evaluate_gold_case, load_cases

    case = copy.deepcopy(load_cases()[0])
    case["inputs"] = [120]
    result = evaluate_gold_case(case)
    assert result["checks"]["status"]
    assert not result["checks"]["numeric"]


def test_evaluator_error_uses_case_id_and_never_exception_content(monkeypatch):
    from . import expanded_evaluation

    def fail(*args, **kwargs):
        raise RuntimeError("private prompt should never appear")

    monkeypatch.setattr(expanded_evaluation, "evaluate_gold_case", fail)
    report = expanded_evaluation.build_expanded_report(adapter=object(), live_limit=1)
    assert report["summary"]["failed"] == 1
    assert report["cases"][0]["outcome"] == "evaluator_error"
    assert "private prompt" not in str(report)


@pytest.mark.parametrize("response", [
    {},
    {"status": "planned", "plan": {"operation": "write"}},
])
def test_language_evaluator_records_malformed_envelopes_without_losing_cases(
    monkeypatch, response,
):
    from . import test_gold_language_http
    from .test_genai_regression import build_gold_language_report

    monkeypatch.setattr(test_gold_language_http, "_plan", lambda question: response)
    report = build_gold_language_report(include_checks=True)
    assert report["summary"]["total"] == 32
    assert report["summary"]["failed"] == 32
    assert all(case["outcome"] == "evaluator_error" for case in report["cases"])
