"""Execute with python -m tests.p0_case_review; planning diagnostics, not real answers."""
import json
from pathlib import Path

from .test_gold_language_http import _plan


def main():
    root = Path(__file__).resolve().parents[1]
    dataset_path = root / "tests/fixtures/gold_p0_case_review.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    results = []
    for case in dataset["cases"]:
        response = _plan(
            case["question"],
            context=case.get("context", ()),
            competencies=dataset["coverage"],
        )
        plan = response.get("plan")
        plan_fields = (
            "metric_id", "unit", "window", "filters", "group_by_dimension_ids", "order", "limit"
        )
        results.append(
            {
                **case,
                "actual_status": response["status"],
                "message": (response.get("response") or {}).get("message"),
                "plan": {key: plan.get(key) for key in plan_fields} if plan else None,
            }
        )
    statuses = sorted({row["actual_status"] for row in results})
    report = {
        "reference": "748376c plus local diagnostics",
        "dataset_version": dataset["dataset_version"],
        "scope": dataset["scope"],
        "coverage": dataset["coverage"],
        "limitations": dataset["limitations"],
        "summary": {
            status: sum(row["actual_status"] == status for row in results)
            for status in statuses
        },
        "cases": results,
    }
    report_path = root / "reports/genai-p0-case-review.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
