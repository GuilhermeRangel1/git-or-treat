"""Gera contextos e avalia a matriz de follow-up F1 sem executar SQL."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from app.schemas.genai_internal import QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_sql_context import build_sql_generation_context
from app.services.genai_sql_semantics import review_sql_semantics
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "ai-agent/tests/fixtures/text_to_sql_f1_continuity.json"
MONTHS = [f"{year}-{month:02d}" for year in (2025, 2026) for month in range(1, 13)]
MUNICIPALITIES = ["Jaboatão dos Guararapes", "Olinda", "Recife"]
CLASSES = ["COMERCIAL", "INDUSTRIAL", "RESIDENCIAL", "RURAL", "PODER_PUBLICO"]
GROUP_BY = {
    "geography.municipality": "municipality",
    "customer.consumption_class": "consumption_class",
}


def load_fixture(path=FIXTURE):
    raw = path.read_bytes()
    fixture = json.loads(raw)
    ids = [case["id"] for case in fixture["cases"]]
    if len(ids) != len(set(ids)) or not fixture["cases"]:
        raise ValueError("Fixture de continuidade vazia ou com IDs repetidos.")
    return fixture, hashlib.sha256(raw).hexdigest()


def request_for_case(case):
    return QuestionPlanRequest.model_validate({
        "question": case["question"],
        "context": case["context"],
        "remaining_timeout_ms": 30000,
        "batch_ref": (
            "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:"
            "12345678-1234-4123-8123-123456789abc"
        ),
        "access_scope": {
            "caller_ref": "session:" + "a" * 64,
            "profile_id": "v-energy-grid-360-gold",
            "source_id": "gold.local",
            "allowed_operations": ["read"],
            "allowed_metric_ids": ["billing.revenue", "energy.consumption"],
            "allowed_dimension_ids": [
                "geography.municipality", "customer.consumption_class",
            ],
        },
        "temporal_coverage": [
            {"metric_id": metric_id, "kind": "monthly", "competencies": MONTHS}
            for metric_id in ("billing.revenue", "energy.consumption")
        ],
        "dimension_value_coverage": [
            {"dimension_id": "geography.municipality", "values": MUNICIPALITIES},
            {"dimension_id": "customer.consumption_class", "values": CLASSES},
        ],
    })


def export_contexts(output, fixture_path=FIXTURE):
    fixture, digest = load_fixture(fixture_path)
    contexts = []
    for case in fixture["cases"]:
        context = build_sql_generation_context(request_for_case(case))
        contexts.append({
            "id": case["id"],
            "context_version": context.context_version,
            "contents": context.contents,
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "benchmark_sha256": digest,
        "contexts": contexts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _candidate_differences(candidate, expected):
    differences = []
    if candidate.status != expected["status"]:
        return ["status"]
    if candidate.status != "sql_candidate":
        if (candidate.status == "unsupported" and expected.get("reason_code")
                and candidate.unsupported_reason.code != expected["reason_code"]):
            differences.append("reason_code")
        if candidate.status == "unsupported" and expected.get("metric_id"):
            intent = candidate.semantic_intent
            if intent is None:
                differences.append("semantic_intent_missing")
            else:
                if intent.metric_id != expected["metric_id"]:
                    differences.append("metric_id")
                periods = [[item.start.strftime("%Y-%m"), item.end.strftime("%Y-%m")]
                           for item in intent.periods]
                if periods != expected["periods"]:
                    differences.append("periods")
                filters = {item.dimension_id: list(item.values) for item in intent.filters}
                if filters != expected["filters"]:
                    differences.append("filters")
        return differences

    intent = candidate.interpretation
    if intent.metric_id != expected["metric_id"]:
        differences.append("metric_id")
    if intent.operation != expected["operation"]:
        differences.append("operation")
    periods = [[item.start.strftime("%Y-%m"), item.end.strftime("%Y-%m")]
               for item in intent.periods]
    if periods != expected["periods"]:
        differences.append("periods")
    filters = {item.dimension_id: list(item.values) for item in intent.filters}
    if filters != expected["filters"]:
        differences.append("filters")
    expected_groups = [GROUP_BY[item] for item in expected["group_by"]]
    if list(intent.group_by) != expected_groups:
        differences.append("group_by")
    if intent.ranking_limit != expected["ranking_limit"]:
        differences.append("ranking_limit")
    return differences


def evaluate_capture(capture_path, output_path, fixture_path=FIXTURE):
    fixture, digest = load_fixture(fixture_path)
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    if capture.get("benchmark_sha256") != digest:
        raise ValueError("A captura foi feita com outra versão da fixture de continuidade.")
    if capture.get("prompt_version") is None:
        raise ValueError("A captura não registra versão de prompt.")
    cases = {case["id"]: case for case in fixture["cases"]}
    results = []
    for case_id in sorted(set(capture.get("candidates", {})) | {
        item["id"] for item in capture.get("observations", [])
    }):
        case = cases.get(case_id)
        if case is None:
            raise ValueError("Captura contém ID desconhecido para a fixture.")
        raw_candidate = capture.get("candidates", {}).get(case_id)
        if raw_candidate is None:
            observation = next(row for row in capture["observations"] if row["id"] == case_id)
            results.append({
                "id": case_id,
                "outcome": "provider_or_contract_error",
                "error_type": observation.get("error_type"),
            })
            continue
        try:
            candidate = SqlGenerationCandidate.model_validate(raw_candidate)
        except ValidationError:
            results.append({"id": case_id, "outcome": "invalid_candidate"})
            continue
        differences = _candidate_differences(candidate, case["expected"])
        reviewed = False
        review_error = None
        if candidate.status == "sql_candidate":
            try:
                review_sql_semantics(candidate, request_for_case(case))
                reviewed = True
            except Exception as exc:  # noqa: BLE001 - report only exception class
                review_error = type(exc).__name__
                differences.append("sql_semantic_review")
        semantic_exact = not differences
        if "semantic_intent_unobservable" in differences:
            outcome = "correct_capacity_state_semantics_unobservable"
        elif semantic_exact and candidate.status == "sql_candidate" and reviewed:
            outcome = "exact_intent_and_sql_review"
        elif semantic_exact:
            outcome = "exact_nonquery_state"
        else:
            outcome = "divergent"
        results.append({
            "id": case_id,
            "outcome": outcome,
            "differences": sorted(set(differences)),
            "observed_status": candidate.status,
            "sql_review_passed": reviewed,
            "sql_review_error_type": review_error,
            "semantic_intent_observable": "semantic_intent_unobservable" not in differences,
        })
    report = {
        "version": "text-to-sql-f1-continuity-evaluation-v1",
        "boundary": "real Gemini candidate capture reviewed against synthetic intent; no SQL execution or Gold reads",
        "benchmark_sha256": digest,
        "model": capture.get("model"),
        "prompt_version": capture.get("prompt_version"),
        "requested_denominator": len(fixture["cases"]),
        "observed_denominator": len(results),
        "counts": dict(Counter(item["outcome"] for item in results)),
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--fixture", type=Path, default=FIXTURE)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--capture", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--fixture", type=Path, default=FIXTURE)
    args = parser.parse_args()
    if args.command == "export":
        export_contexts(args.output, args.fixture)
    else:
        evaluate_capture(args.capture, args.output, args.fixture)


if __name__ == "__main__":
    main()
