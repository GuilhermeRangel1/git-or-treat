"""O avaliador mede o plano completo e detecta filtros perdidos."""

from .test_genai_regression import build_gold_language_report


def test_gold_language_report_is_repeatable_and_all_expected_plans_match():
    first = build_gold_language_report()
    assert first == build_gold_language_report()
    assert first["summary"] == {"total": 32, "passed": 32, "failed": 0}
    assert first["synthetic"] is True
    assert {"canonical", "passive", "plural", "service", "network", "unknown_entity"} <= (
        first["categories"].keys()
    )


def test_separate_formulations_remain_correct_after_the_recorded_passive_fix():
    assert build_gold_language_report("gold_language_holdout.json")["summary"] == {
        "total": 16, "passed": 16, "failed": 0,
    }


def test_evaluator_detects_a_valid_status_with_a_lost_filter(monkeypatch):
    from . import test_gold_language_http

    original = test_gold_language_http._plan

    def lose_filter(*args, **kwargs):
        result = original(*args, **kwargs)
        if result.get("plan"):
            result["plan"]["filters"] = []
        return result

    monkeypatch.setattr(test_gold_language_http, "_plan", lose_filter)
    report = build_gold_language_report()
    assert report["summary"]["failed"] > 0
    assert any("filters" in case["failing_checks"] for case in report["cases"])
