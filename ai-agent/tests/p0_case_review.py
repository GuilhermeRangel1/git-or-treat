"""Execute with python -m tests.p0_case_review; planning diagnostics, not real answers."""
import json
from pathlib import Path
from .test_gold_language_http import _plan


def main():
    root = Path(__file__).resolve().parents[1]
    dataset = json.loads((root / "tests/fixtures/gold_p0_case_review.json").read_text(encoding="utf-8"))
    results = []
    for case in dataset["cases"]:
        response = _plan(case["question"], context=case.get("context", ()), competencies=dataset["coverage"])
        plan = response.get("plan")
        results.append({**case, "actual_status": response["status"],
            "message": (response.get("response") or {}).get("message"),
            "plan": {key: plan.get(key) for key in ("metric_id", "unit", "window", "filters", "group_by_dimension_ids", "order", "limit")} if plan else None})
    report = {"reference": "748376c plus local diagnostics", "dataset_version": dataset["dataset_version"],
        "scope": dataset["scope"], "coverage": dataset["coverage"], "limitations": dataset["limitations"],
        "summary": {status: sum(row["actual_status"] == status for row in results) for status in sorted({row["actual_status"] for row in results})},
        "cases": results}
    (root / "reports/genai-p0-case-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
