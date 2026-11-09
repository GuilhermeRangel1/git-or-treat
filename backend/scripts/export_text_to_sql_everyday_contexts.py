"""Exporta contextos sintéticos para avaliar o gerador, sem ler linhas Gold."""

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.genai_internal import QuestionPlanRequest
from app.services.genai_sql_context import build_sql_generation_context

FIXTURE = ROOT / "ai-agent/tests/fixtures/text_to_sql_everyday_language.json"
FIRST_MONTH = "2022-07"
LAST_MONTH = "2026-06"
SCOPE = {
    "caller_ref": "session:" + "a" * 64,
    "profile_id": "v-energy-grid-360-gold",
    "source_id": "gold.local",
    "allowed_operations": ["read"],
    "allowed_metric_ids": ["billing.revenue"],
    "allowed_dimension_ids": [
        "geography.municipality", "customer.consumption_class",
    ],
}
BATCH_REF = (
    "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:"
    "12345678-1234-4123-8123-123456789abc"
)


def _months(start: str, end: str) -> list[str]:
    first = date.fromisoformat(start + "-01")
    last = date.fromisoformat(end + "-01")
    result = []
    while first <= last:
        result.append(first.strftime("%Y-%m"))
        first = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return result


def _dimension_values(cases, dimension_id: str) -> list[str]:
    values = {
        value
        for case in cases
        for value in case.get("expected_intent", {}).get("filters", {}).get(
            dimension_id, []
        )
    }
    if dimension_id == "geography.municipality":
        values.update({"Jaboatão dos Guararapes", "Olinda", "Recife"})
    if dimension_id == "customer.consumption_class":
        values.update({"COMERCIAL", "INDUSTRIAL", "PODER PUBLICO", "RESIDENCIAL", "RURAL"})
    return sorted(values, key=lambda value: (value.casefold(), value))


def export_contexts(*, case_ids: list[str] | None = None) -> dict:
    fixture_bytes = FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    cases = fixture["cases"]
    selected = cases if case_ids is None else [
        case for case in cases if case["id"] in set(case_ids)
    ]
    if case_ids is not None and {case["id"] for case in selected} != set(case_ids):
        raise ValueError("Seleção contém ID ausente do fixture.")
    if len({case["id"] for case in selected}) != len(selected):
        raise ValueError("Fixture contém IDs repetidos na seleção.")

    dimensions = [
        {
            "dimension_id": dimension_id,
            "values": _dimension_values(cases, dimension_id),
        }
        for dimension_id in SCOPE["allowed_dimension_ids"]
    ]
    request_metadata = {
        "remaining_timeout_ms": 30_000,
        "batch_ref": BATCH_REF,
        "access_scope": SCOPE,
        "temporal_coverage": [{
            "metric_id": "billing.revenue",
            "kind": "monthly",
            "competencies": _months(FIRST_MONTH, LAST_MONTH),
        }],
        "dimension_value_coverage": dimensions,
    }
    contexts = []
    for case in selected:
        request = QuestionPlanRequest.model_validate({
            "question": case["question"],
            "context": case.get("context", []),
            **request_metadata,
        })
        context = build_sql_generation_context(request)
        contexts.append({
            "id": case["id"],
            "context_version": context.context_version,
            "contents": context.contents,
        })
    return {
        "benchmark_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "context_source": "synthetic fixture and versioned metadata; no Gold rows",
        "contexts": contexts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "work/tsql11-gemini-contexts.json",
    )
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit deve ser positivo")
    case_ids = args.case_id
    if args.limit is not None:
        fixture_cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
        limited_ids = [case["id"] for case in fixture_cases[:args.limit]]
        case_ids = limited_ids if case_ids is None else case_ids[:args.limit]
    bundle = export_contexts(case_ids=case_ids)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "context_count": len(bundle["contexts"]),
        "benchmark_sha256": bundle["benchmark_sha256"],
        "output": str(args.output),
        "source": bundle["context_source"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
