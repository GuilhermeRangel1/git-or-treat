"""Compara interpretação Gemini e determinística em até seis casos sintéticos."""

import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import median
from time import perf_counter

from app.agent.access import ReadAccessPolicy
from app.config import Settings
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.providers.intent_proposer import GeminiIntentProposer
from app.providers.protocols import (
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from tests.test_gold_question_filters import _setup

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "gold_language_eval.json"
REPORT = ROOT / "reports" / "hnlu-gemini-sample.json"
SAMPLE_IDS = ("REV-02", "ENE-02", "RANK-03", "DEC-01", "GUARD-04", "GUARD-07")
EXPECTED_CLARIFICATION_REASONS = {
    # O oráculo de GUARD-04 requer esclarecimento, não um rótulo interno
    # específico: a pergunta combina faturamento e recebimento (pagamento).
    "GUARD-04": {"ambiguous_metric", "multiple_metrics"},
    "GUARD-07": {"ambiguous_metric"},
}


def _matches(result, expected, case_id):
    expected_status = expected["status"]
    actual_status = "planned" if result.read_plan is not None else "needs_clarification"
    if actual_status != expected_status:
        return False
    if result.read_plan is None:
        expected_reason = EXPECTED_CLARIFICATION_REASONS.get(case_id)
        actual_reason = (
            result.interpretation.clarification_reason.value
            if result.interpretation.clarification_reason is not None else None
        )
        return expected_reason is None or actual_reason in expected_reason
    actual = result.read_plan.model_dump(mode="json")
    for key, value in expected.items():
        if key == "status":
            continue
        actual_value = actual.get(key)
        if key in {"dimension_ids", "group_by_dimension_ids"}:
            actual_value = sorted(actual_value or [])
            value = sorted(value or [])
        elif key == "filters":
            actual_value = sorted(actual_value or [], key=lambda item: item["dimension_id"])
            value = sorted(value or [], key=lambda item: item["dimension_id"])
        if actual_value != value:
            return False
    return True


def _plan_snapshot(result):
    """Retorna campos estruturados mínimos para diagnosticar divergências sem prompt."""
    interpretation = result.interpretation
    plan = result.read_plan
    intent = interpretation.intent
    return {
        "status": "planned" if plan is not None else interpretation.status.value,
        "clarification_reason": (
            interpretation.clarification_reason.value
            if interpretation.clarification_reason is not None else None
        ),
        "intent": ({
            "domain": intent.domain,
            "metric_id": intent.metric_id,
            "dimension_ids": sorted(intent.dimension_ids),
            "group_by_dimension_ids": sorted(intent.group_by_dimension_ids),
            "filters": {key: intent.filters[key] for key in sorted(intent.filters)},
            "comparison_period_phrases": intent.comparison_period_phrases,
            "ranking_direction": intent.ranking_direction,
            "ranking_limit": intent.ranking_limit,
            "metric_phrase": intent.metric_phrase,
            "period_phrase": intent.period_phrase,
            "geography_phrase": intent.geography_phrase,
            "class_phrase": intent.class_phrase,
        } if intent is not None else None),
        "plan": ({
            "metric_id": plan.metric_id,
            "unit": plan.unit,
            "dimension_ids": list(plan.dimension_ids),
            "group_by_dimension_ids": list(plan.group_by_dimension_ids),
            "window": plan.window.model_dump(mode="json"),
            "filters": [item.model_dump(mode="json") for item in plan.filters],
            "comparison_periods": plan.comparison_periods,
            "order": plan.order.model_dump(mode="json") if plan.order is not None else None,
            "limit": plan.limit,
            "fingerprint": plan.fingerprint(),
        } if plan is not None else None),
    }


async def _evaluate(settings):
    from google import genai

    client = genai.Client(
        api_key=settings.gemini_api_key.get_secret_value(),
        http_options={"timeout": settings.model_timeout_ms,
                      "retry_options": {"attempts": 1}},
    )
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in fixture["cases"]}
    report_cases = []
    usage = {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    request_fingerprints = []
    for case_id in SAMPLE_IDS:
        case = cases[case_id]
        core, request = _setup(case["question"])
        coverage = {
            item.metric_id: (item.kind, item.competencies)
            for item in request.temporal_coverage
        }
        dimensions = {
            item.dimension_id: item.values for item in request.dimension_value_coverage
        }
        context = request.access_scope.to_context("00000000000040008000000000000001")
        deterministic = core.question._analysis_planner.plan(
            request.question, request.context, context,
            temporal_coverage=coverage, dimension_value_coverage=dimensions,
        )
        proposer = GeminiIntentProposer(
            client=client,
            model=settings.gemini_model,
            profile=GRID360_GOLD_PROFILE,
            request=request,
            access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
        )
        request_fingerprints.append(hashlib.sha256(
            json.dumps({
                "question": request.question,
                "context": [turn.model_dump(mode="json") for turn in request.context],
                "metric_ids": sorted(request.access_scope.allowed_metric_ids),
                "dimension_ids": sorted(request.access_scope.allowed_dimension_ids),
                "coverage": {key: list(value) for key, value in sorted(coverage.items())},
                "dimension_values": {key: list(value) for key, value in sorted(dimensions.items())},
            }, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest())
        started = perf_counter()
        try:
            proposal = await proposer.propose()
        except Exception as exc:
            elapsed_ms = round((perf_counter() - started) * 1000)
            error_category = (
                "provider_unavailable" if isinstance(exc, ModelProviderUnavailable) else
                "provider_rejected" if isinstance(exc, ModelProviderRejected) else
                "invalid_provider_response" if isinstance(exc, ModelProviderInvalidResponse) else
                "catalog_validation" if isinstance(exc, ValueError) else "unexpected"
            )
            report_cases.append({
                "id": case_id,
                "category": case["category"],
                "deterministic_correct": _matches(deterministic, case["expected"], case_id),
                "gemini_correct": False,
                "same_outcome": False,
                "proposal_status": "error",
                "error_category": error_category,
                "exception_class": type(exc).__name__,
                "response_diagnostic": proposer.last_response_diagnostic or None,
                "failure_stage": "provider",
                "latency_ms": elapsed_ms,
            })
            continue
        elapsed_ms = round((perf_counter() - started) * 1000)
        proposed = core.question._analysis_planner.plan(
            request.question, request.context, context,
            temporal_coverage=coverage, dimension_value_coverage=dimensions,
            interpretation_override=proposal,
        )
        prompt_tokens = proposer.usage.get("prompt_tokens")
        output_tokens = proposer.usage.get("output_tokens")
        total_tokens = proposer.usage.get("total_tokens")
        for key, value in (("prompt_tokens", prompt_tokens),
                           ("output_tokens", output_tokens),
                           ("total_tokens", total_tokens)):
            if isinstance(value, int):
                usage[key] += value
        report_cases.append({
            "id": case_id,
            "category": case["category"],
            "expected": case["expected"],
            "deterministic_correct": _matches(deterministic, case["expected"], case_id),
            "gemini_correct": _matches(proposed, case["expected"], case_id),
            "same_correctness": _matches(deterministic, case["expected"], case_id)
            == _matches(proposed, case["expected"], case_id),
            "proposal_status": proposal.status.value,
            "actual": _plan_snapshot(proposed),
            "failure_stage": (
                None if _matches(proposed, case["expected"], case_id) else
                "nlu_clarification" if proposal.intent is None else
                "planner_capability_or_coverage" if proposed.read_plan is None else
                "plan_mismatch"
            ),
            "same_plan_as_deterministic": (
                deterministic.read_plan is not None and proposed.read_plan is not None
                and deterministic.read_plan.fingerprint() == proposed.read_plan.fingerprint()
            ) or (
                deterministic.read_plan is None and proposed.read_plan is None
                and deterministic.interpretation.status == proposed.interpretation.status
                and deterministic.interpretation.clarification_reason
                == proposed.interpretation.clarification_reason
            ),
            "latency_ms": elapsed_ms,
        })
    latencies = sorted(item["latency_ms"] for item in report_cases)
    return {
        "report_type": "hnlu_intent_comparison_v1",
        "provider": "Gemini",
        "model": settings.gemini_model,
        "fixture_version": fixture["dataset_version"],
        "sample_ids": list(SAMPLE_IDS),
        "request_fingerprint": hashlib.sha256(
            "".join(request_fingerprints).encode("ascii")
        ).hexdigest(),
        "case_count": len(report_cases),
        "model_call_count": len(SAMPLE_IDS),
        "summary": {
            "deterministic_correct": sum(c["deterministic_correct"] for c in report_cases),
            "gemini_correct": sum(c["gemini_correct"] for c in report_cases),
            "latency_p50_ms": round(median(latencies)) if latencies else None,
            "latency_p95_ms": latencies[math.ceil(0.95 * len(latencies)) - 1]
            if latencies else None,
            "error_cases": sum(c["proposal_status"] == "error" for c in report_cases),
            "same_plan_as_deterministic": sum(
                bool(c.get("same_plan_as_deterministic")) for c in report_cases
            ),
        },
        "usage": usage,
        "cases": report_cases,
        "limitations": [
            "Amostra de seis casos sintéticos, sem execução SQL ou resposta numérica.",
            "Os valores e competências vêm de fixtures e não comprovam cobertura Gold real.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=6, choices=[6])
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    if os.environ.get("GENAI_RUN_HNLU") != "1":
        parser.error("Defina GENAI_RUN_HNLU=1 para autorizar as seis chamadas reais.")
    settings = Settings()
    if settings.gemini_api_key is None:
        parser.error("Configure a chave local do Gemini.")
    report = asyncio.run(_evaluate(settings))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
