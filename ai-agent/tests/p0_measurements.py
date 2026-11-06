"""Diagnóstico reproduzível: planejamento HTTP e síntese artificial, sem Gold real."""

import json
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

from app.agent.planner import QuestionAnalysisPlanner

from .gold_evaluation import DATASET_PATH, evaluate_gold_case
from .test_gold_language_http import _plan

ROOT = Path(__file__).resolve().parents[1]
DATASETS = (
    "gold_p0_diagnostic.json",
    "gold_p0_user_reported.json",
    "gold_p0_noncanonical.json",
)


def measure_dataset(name):
    dataset = json.loads((ROOT / "tests/fixtures" / name).read_text(encoding="utf-8"))
    rows = []
    for case in dataset["cases"]:
        started = perf_counter()
        interpretations = []
        original = QuestionAnalysisPlanner.plan

        def capture(planner, *args, original=original, interpretations=interpretations, **kwargs):
            result = original(planner, *args, **kwargs)
            interpretations.append(result.interpretation.model_dump(mode="json"))
            return result

        try:
            with patch.object(QuestionAnalysisPlanner, "plan", capture):
                response = _plan(case["question"], context=case.get("context", ()),
                                 competencies=case.get("competencies"))
        except Exception as exc:
            rows.append({"id": case["id"], "outcome": "evaluator_error",
                         "error_type": type(exc).__name__})
            continue
        actual = {"status": response["status"], **(response.get("plan") or {})}
        checks = {key: actual.get(key) == value for key, value in case["expected"].items()}
        interpretation = interpretations[0] if interpretations else None
        intent_checks = {}
        if interpretation is not None:
            expected_status = case["expected"]["status"]
            if expected_status in {"planned", "needs_clarification"}:
                intent_checks["status"] = interpretation["status"] == (
                    "ready" if expected_status == "planned" else "needs_clarification"
                )
            intent = interpretation.get("intent") or {}
            for key in ("metric_id", "group_by_dimension_ids"):
                if key in case["expected"]:
                    intent_checks[key] = intent.get(key) == case["expected"][key]
        message = (response.get("response") or {}).get("message", "")
        if case.get("expected_message_any"):
            checks["clarification_reason"] = any(
                term.casefold() in message.split("\n\n")[0].casefold()
                for term in case["expected_message_any"]
            )
        rows.append({
            "id": case["id"], "question": case["question"],
            "context": case.get("context", []), "expected": case["expected"],
            "expected_business_intent": case.get("expected_business_intent"),
            "actual": {key: actual.get(key) for key in case["expected"]},
            "interpretation": interpretation, "intent_checks": intent_checks,
            "message": message, "checks": checks,
            "outcome": "match" if all(checks.values()) else "mismatch",
            "first_observed_divergence": (
                None if all(checks.values())
                else "selected_interpretation" if intent_checks and not all(intent_checks.values())
                else "planning_http"
            ),
            "root_cause": "not_inferred_from_status_alone",
            "elapsed_ms": round((perf_counter() - started) * 1000, 3),
        })
    observed = [row for row in rows if "checks" in row]
    slots = sorted({key for row in observed for key in row["checks"]})
    durations = sorted(row["elapsed_ms"] for row in observed)
    # Capacidades ausentes explicitamente anotadas no diagnóstico, não bloqueios de acesso.
    missing_capabilities = {"P0-35", "P0-36", "P0-37", "P0-38"}
    supported = [row for row in observed if row["expected"]["status"] == "planned"
                 and row["id"] not in missing_capabilities]
    expected_clarifications = [row for row in observed
                               if row["expected"]["status"] == "needs_clarification"]
    baseline_path = ROOT / "reports/genai-diagnostic-recheck.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    old_cases = {row["id"]: row for row in baseline.get(name, {}).get("cases", [])}
    return {
        "dataset": name, "dataset_version": dataset["dataset_version"],
        "outcomes": dict(Counter(row["outcome"] for row in rows)),
        "slots": {key: {
            "evaluated": sum(key in row["checks"] for row in observed),
            "correct": sum(row["checks"].get(key, False) for row in observed),
        } for key in slots},
        "business_plan_expected_but_clarified": sum(
            row["expected"]["status"] == "planned"
            and row["actual"]["status"] == "needs_clarification" for row in observed
        ),
        "latency": {"p50_ms": median(durations) if durations else None,
                    "p95_ms": durations[max(0, (95 * len(durations) + 99) // 100 - 1)]
                    if durations else None},
        "cases": rows,
        "clarification_measurement": {
            "scope": "annotated capability controls; not a security refusal rate",
            "supported_controls": len(supported),
            "unnecessary_in_supported_controls": sum(
                row["actual"]["status"] == "needs_clarification" for row in supported
            ),
            "expected_necessary": len(expected_clarifications),
            "expected_necessary_observed": sum(
                row["actual"]["status"] == "needs_clarification"
                for row in expected_clarifications
            ),
            "reason_evaluated": sum("clarification_reason" in row["checks"]
                                    for row in expected_clarifications),
            "reason_correct": sum(row["checks"].get("clarification_reason", False)
                                  for row in expected_clarifications),
            "missing_capability_ids": [row["id"] for row in observed
                                       if row["id"] in missing_capabilities],
        },
        "regression_comparison": {
            "baseline": "genai-diagnostic-recheck.json",
            "comparable_cases": len(old_cases),
            "new_cases": [row["id"] for row in rows if row["id"] not in old_cases],
            "regressions": [row["id"] for row in rows
                            if old_cases.get(row["id"], {}).get("passed")
                            and row["outcome"] != "match"],
        },
        "intent_measurement": {
            "scope": "selected planner interpretation, status/metric/grouping when annotated",
            "evaluated": sum(bool(row.get("intent_checks")) for row in observed),
            "matching_checked_fields": sum(
                bool(row.get("intent_checks")) and all(row["intent_checks"].values())
                for row in observed
            ),
        },
    }


def main():
    numeric = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    numeric_rows = [evaluate_gold_case(case) for case in numeric["cases"]]
    report = {
        "scope": "Gold v2 artificial HTTP planning and injected numeric evidence",
        "limitations": [
            "No SQL or real provider calls; no portal acceptance.",
            "Planning latency includes fixture construction, not production latency.",
            "Expected plans are business oracles, not proof every capability exists.",
            "Planning output alone does not isolate the interpreter's root cause.",
            "Reserved questions are not loaded or executed.",
        ],
        "provider": {"kind": "fake_or_none", "external_calls": 0,
                     "tokens": None, "cost": None},
        "planning": [measure_dataset(name) for name in DATASETS],
        "numeric": numeric_rows,
        "numeric_summary": {
            "total": len(numeric_rows),
            "passed": sum(all(row["checks"].values()) for row in numeric_rows),
        },
    }
    target = ROOT / "reports/genai-p0-measurements.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"planning": [
        {"dataset": item["dataset"], "outcomes": item["outcomes"]}
        for item in report["planning"]
    ], "numeric": report["numeric_summary"]}))
    if (any("evaluator_error" in item["outcomes"] for item in report["planning"])
            or report["numeric_summary"]["passed"] != len(numeric_rows)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
