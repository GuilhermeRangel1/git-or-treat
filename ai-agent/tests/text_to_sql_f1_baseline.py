"""Baseline HTTP do planner existente, com perguntas e cobertura artificiais.

Run: python -m tests.text_to_sql_f1_baseline --output reports/text-to-sql-f1-baseline.json
No model provider, SQL execution or synthesis is claimed by this measurement.
"""

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from time import perf_counter

from .conftest import InProcessClient
from .test_gold_planning_http import HEADERS, PLAN_PATH, _application
from .test_gold_question_filters import _setup

FIXTURES = Path(__file__).parent / "fixtures"


def observe(case, coverage, dimensions):
    core, request = _setup(case["question"])
    payload = request.model_dump(mode="json")
    payload["context"] = case["context"]
    payload["access_scope"]["allowed_metric_ids"] = ["billing.revenue"]
    payload["access_scope"]["allowed_dimension_ids"] = [
        "geography.municipality",
        "customer.consumption_class",
    ]
    payload["temporal_coverage"] = [
        {"metric_id": "billing.revenue", "kind": "monthly", "competencies": coverage}
    ]
    payload["dimension_value_coverage"] = dimensions
    with InProcessClient(_application(core)) as client:
        response = client.post(PLAN_PATH, json=payload, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def compare_plan(expected, observed):
    """Compare only observable fields; absent capabilities remain unmeasured."""
    differences = []
    if observed.get("status") != expected["status"]:
        differences.append("status")
    plan = observed.get("plan")
    if expected["status"] != "planned" or plan is None:
        return differences, ["sql", "numbers", "answer_quality", "provider_usage"]
    for field in ("metric_id", "unit", "group_by_dimension_ids", "order"):
        if plan.get(field) != expected[field]:
            differences.append(field)
    actual_filters = {f["dimension_id"]: f["values"] for f in plan.get("filters", [])}
    if actual_filters != expected["filters"]:
        differences.append("filters")
    if expected["limit"] is not None and plan.get("limit") != expected["limit"]:
        differences.append("limit")
    periods = expected["periods"]
    window = plan.get("window", {})
    if len(periods) == 1:
        start, end = periods[0]
        if (window.get("start") or "")[:7] != start or (window.get("end") or "")[:7] != end:
            differences.append("period")
        # Two discrete monthly periods cannot represent a requested interval total.
        if plan.get("comparison_periods"):
            differences.append("operation")
    else:
        # The legacy schema only expresses two individual months, never two windows.
        differences.append("comparison_windows_not_representable")
    # Old logical schema cannot distinguish a total from a monthly series.
    unmeasured = ["sql", "numbers", "answer_quality", "provider_usage"]
    if expected["operation"] in ("total", "monthly_series", "grouped_total", "ranking"):
        unmeasured.append("aggregation_shape")
    return differences, unmeasured


def run():
    benchmark_bytes = (FIXTURES / "text_to_sql_f1_benchmark.json").read_bytes()
    benchmark = json.loads(benchmark_bytes)
    reference_bytes = (FIXTURES / "text_to_sql_f1_reference.json").read_bytes()
    reference = json.loads(reference_bytes)
    results = []
    dimensions = [
        {
            "dimension_id": "geography.municipality",
            "values": sorted({r["municipio"] for r in reference["rows"]}),
        },
        {"dimension_id": "customer.consumption_class", "values": ["COMERCIAL", "RESIDENCIAL"]},
    ]
    for case in benchmark["cases"]:
        started = perf_counter()
        try:
            observed = observe(case, case.get("coverage", reference["coverage"]), dimensions)
            differences, unmeasured = compare_plan(case["expected"], observed)
            results.append(
                {
                    "id": case["id"],
                    "reference_id": case["reference_id"],
                    "outcome": "divergent" if differences else "observed_fields_match",
                    "differences": differences,
                    "unmeasured": unmeasured,
                    "first_divergence": "planning_http" if differences else None,
                    "observed": observed,
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                }
            )
        except Exception as error:
            # No raw exception text, request secrets or provider payloads in reports.
            results.append(
                {
                    "id": case["id"],
                    "outcome": "technical_error",
                    "error_type": type(error).__name__,
                    "first_divergence": "planning_http",
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                }
            )
    return {
        "version": benchmark["version"],
        "boundary": "legacy GenAI ASGI planning; synthetic coverage; fake synthesis adapter unused",
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "working_tree": "local modifications included in source hashes",
        "source_sha256": {
            str(path.relative_to(FIXTURES.parents[2])).replace("\\", "/"): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted((FIXTURES.parents[1] / "app").rglob("*.py"))
        },
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "regressions": "initial baseline; no earlier comparable frozen benchmark",
        "reserve": "8 authorial questions unevaluated; independent holdout count is zero",
        "benchmark_sha256": hashlib.sha256(benchmark_bytes).hexdigest(),
        "reference_sha256": hashlib.sha256(reference_bytes).hexdigest(),
        "domain_review": benchmark["domain_review"],
        "holdout_count": 0,
        "false_refusals": sum(
            c["expected"]["status"] == "planned"
            and r.get("observed", {}).get("status") == "refused"
            for c, r in zip(benchmark["cases"], results, strict=True)
        ),
        "unnecessary_clarifications": sum(
            c["expected"]["status"] == "planned"
            and r.get("observed", {}).get("status") == "needs_clarification"
            for c, r in zip(benchmark["cases"], results, strict=True)
        ),
        "required_clarifications": sum(
            c["expected"]["status"] == "needs_clarification" for c in benchmark["cases"]
        ),
        "denominator": len(results),
        "counts": dict(Counter(r["outcome"] for r in results)),
        "divergence_counts": dict(Counter(d for r in results for d in r.get("differences", []))),
        "provider_calls": 0,
        "provider_tokens": None,
        "provider_cost": None,
        "sql_execution": "not measured",
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: report[k] for k in ("denominator", "counts", "divergence_counts")},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
