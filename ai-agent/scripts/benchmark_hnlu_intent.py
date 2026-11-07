"""Compara planos Gemini e determinísticos na amostra ou fixture completa."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import unicodedata
from pathlib import Path
from statistics import median
from time import perf_counter

from app.agent.access import ReadAccessPolicy
from app.agent.temporal import (
    GoldTemporalWindowResolver,
    TemporalResolutionUnavailable,
    normalize_proposed_period_phrase,
)
from app.config import Settings
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.providers.intent_proposer import GeminiIntentProposer
from app.providers.protocols import (
    ModelProviderInvalidResponse,
    ModelProviderRejected,
    ModelProviderUnavailable,
)
from app.schemas.questions import ConversationTurn
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
        expected_reason = expected.get("clarification_reason")
        if expected_reason is None:
            expected_reason = EXPECTED_CLARIFICATION_REASONS.get(case_id)
        if isinstance(expected_reason, str):
            expected_reason = {expected_reason}
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


def _setup_case(case):
    core, request = _setup(case["question"])
    updates = {}
    if "context" in case:
        updates["context"] = [
            ConversationTurn.model_validate(turn) for turn in case["context"]
        ]
    if "coverage_competencies" in case:
        updates["temporal_coverage"] = [
            item.model_copy(update={"competencies": tuple(case["coverage_competencies"])})
            for item in request.temporal_coverage
        ]
    if updates:
        request = request.model_copy(update=updates)
    return core, request


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
        "planner_clarification": ({
            "status": result.clarification.status.value,
            "message": result.clarification.message,
        } if result.clarification is not None else None),
    }


def _proposal_snapshot(proposal):
    intent = proposal.intent
    return {
        "status": proposal.status.value,
        "clarification_reason": (
            proposal.clarification_reason.value
            if proposal.clarification_reason is not None else None
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
    }


def _semantic_matches(proposal, expected, coverage, dimension_coverage=None):
    if proposal.status.value != expected["status"]:
        return False
    if proposal.status.value == "needs_clarification":
        reason = proposal.clarification_reason.value if proposal.clarification_reason else None
        reasons = expected.get("clarification_reasons")
        if reasons is not None:
            return reason in reasons
        return reason == expected.get("clarification_reason")
    intent = proposal.intent
    if intent is None:
        return False
    for key in ("domain", "metric_id", "ranking_direction", "ranking_limit"):
        if key not in expected:
            continue
        if getattr(intent, key) != expected[key]:
            return False
    if "group_by_dimension_ids" in expected and sorted(
        intent.group_by_dimension_ids
    ) != sorted(expected["group_by_dimension_ids"]):
        return False

    actual_dimensions = set(intent.dimension_ids)
    actual_dimensions.update(intent.group_by_dimension_ids)
    actual_filters = dict(intent.filters)
    actual_dimensions.update(actual_filters)
    for field_name, role in (
        ("geography_phrase", "geography"),
        ("class_phrase", "classification"),
    ):
        phrase = getattr(intent, field_name)
        if not phrase:
            continue
        possible = set()
        declared_for_role = {
            dimension_id for dimension_id in actual_dimensions
            if any(
                dimension.id == dimension_id and dimension.role.value == role
                for dimension in GRID360_GOLD_PROFILE.dimensions
            )
        }
        for dimension in GRID360_GOLD_PROFILE.dimensions:
            if dimension.role.value != role:
                continue
            if declared_for_role and dimension.id not in declared_for_role:
                continue
            aliases = [
                alias for item in dimension.values
                for alias in (item.value, *item.aliases)
            ]
            aliases.extend((dimension_coverage or {}).get(dimension.id, ()))
            if any(_same_phrase(phrase, alias) for alias in aliases):
                possible.add(dimension.id)
        if len(possible) == 1:
            actual_dimensions.update(possible)
            dimension_id = next(iter(possible))
            actual_filters.setdefault(dimension_id, phrase)

    if "dimension_ids" in expected and actual_dimensions != set(expected["dimension_ids"]):
        return False
    if "filters" in expected:
        def canonical_value(dimension_id, value):
            dimension = next((item for item in GRID360_GOLD_PROFILE.dimensions
                              if item.id == dimension_id), None)
            if dimension is not None:
                def canonical_scalar(scalar):
                    normalized = _normalize_phrase(str(scalar))
                    for option in dimension.values:
                        if normalized in {
                            _normalize_phrase(alias)
                            for alias in (option.value, *option.aliases)
                        }:
                            return option.value
                    return scalar
                if isinstance(value, (list, tuple)):
                    return tuple(sorted(canonical_scalar(item) for item in value))
                return canonical_scalar(value)
            return value
        normalized_actual = {
            dimension_id: canonical_value(dimension_id, value)
            for dimension_id, value in actual_filters.items()
        }
        normalized_expected = {
            dimension_id: canonical_value(dimension_id, value)
            for dimension_id, value in expected["filters"].items()
        }
        if normalized_actual != normalized_expected:
            return False
    if "period" in expected:
        if not intent.period_phrase or intent.metric_id not in coverage:
            return False
        kind, competencies = coverage[intent.metric_id]
        if kind != "monthly":
            return False
        try:
            window = GoldTemporalWindowResolver().resolve(
                normalize_proposed_period_phrase(intent.period_phrase), competencies,
            )
        except TemporalResolutionUnavailable:
            return False
        actual_bounds = (
            window.start.isoformat() if window.start else None,
            window.end.isoformat() if window.end else None,
        )
        if actual_bounds != (expected["period"]["start"], expected["period"]["end"]):
            return False
    if "comparison_periods" in expected:
        phrases = intent.comparison_period_phrases or []
        if len(phrases) != 2:
            return False
        current_phrase = _normalize_phrase(phrases[0])
        prior_phrase = _normalize_phrase(phrases[1])
        if not any(token in current_phrase for token in ("ultimos 12 meses", "ultimo ano")):
            return False
        previous_window = (
            "periodo anterior" in prior_phrase
            or "ano anterior" in prior_phrase
            or ("12 meses" in prior_phrase and "anteriores" in prior_phrase)
        )
        if not previous_window:
            return False
    return True


def _normalize_phrase(value):
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _same_phrase(left, right):
    return _normalize_phrase(left).strip() == _normalize_phrase(right).strip()


def _proposal_contract_matches(proposal, expected):
    """Strictly score the returned intent shape independently of meaning."""
    if proposal.status.value != expected["status"]:
        return False
    if proposal.status.value == "needs_clarification":
        return _semantic_matches(proposal, expected, {})
    if proposal.intent is None:
        return False
    intent = proposal.intent
    expected_dimensions = set(expected.get("dimension_ids", ()))
    expected_filters = set(expected.get("filters", {}))
    if (
        set(intent.dimension_ids) != expected_dimensions
        or set(intent.group_by_dimension_ids)
        != set(expected.get("group_by_dimension_ids", ()))
        or not set(intent.filters) <= expected_filters
    ):
        return False
    for dimension_id in expected_filters - set(intent.filters):
        dimension = next((
            item for item in GRID360_GOLD_PROFILE.dimensions
            if item.id == dimension_id
        ), None)
        if dimension is None:
            return False
        phrase = (
            intent.geography_phrase if dimension.role.value == "geography" else
            intent.class_phrase if dimension.role.value == "classification" else None
        )
        if not phrase:
            return False
    return True


def _plan_matches_semantics(result, expected, coverage):
    if expected["status"] == "needs_clarification":
        return _matches(result, expected, "")
    plan = result.read_plan
    if plan is None:
        return False
    for key in ("domain", "metric_id"):
        expected_key = "domain_id" if key == "domain" else key
        if key in expected and getattr(plan, expected_key) != expected[key]:
            return False
    if set(plan.dimension_ids) != set(expected.get("dimension_ids", ())):
        return False
    if set(plan.group_by_dimension_ids) != set(expected.get("group_by_dimension_ids", ())):
        return False
    if plan.order is not None and plan.order.direction.value != expected.get("ranking_direction"):
        return False
    if plan.order is None and expected.get("ranking_direction") is not None:
        return False
    if expected.get("ranking_limit") is not None and plan.limit != expected["ranking_limit"]:
        return False
    if "filters" in expected:
        plan_filters = {
            item.dimension_id: item.values for item in plan.filters
        }
        normalized_plan = {
            dimension_id: tuple(sorted(values))
            for dimension_id, values in plan_filters.items()
        }
        normalized_expected = {
            dimension_id: (value,) if isinstance(value, str) else tuple(value)
            for dimension_id, value in expected["filters"].items()
        }
        if normalized_plan != normalized_expected:
            return False
    if "period" in expected:
        window = plan.window
        if (window.start.isoformat() if window.start else None,
                window.end.isoformat() if window.end else None) != (
            expected["period"]["start"], expected["period"]["end"],
        ):
            return False
    return True


def _summary(report_cases):
    provider_errors = sum(case["proposal_status"] == "error" for case in report_cases)
    invalid_provider_responses = sum(
        (case.get("response_diagnostic") or {}).get("kind")
        in {"empty_text", "invalid_json", "schema_validation"}
        for case in report_cases
    )
    recovered_provider_responses = sum(
        bool((case.get("response_diagnostic") or {}).get(
            "recovered_with_catalog_clarification"
        ))
        for case in report_cases
    )
    successful_cases = [case for case in report_cases if case["proposal_status"] != "error"]
    semantic_cases = [case for case in successful_cases if case.get("semantic_correct") is not None]
    if not semantic_cases:
        # Backward-compatible summary for historical fixtures without raw-intent oracles.
        semantic_cases = successful_cases
    semantic_correct = sum(
        case.get("semantic_correct", case.get("gemini_correct", False))
        for case in semantic_cases
    )
    planner_correct = sum(case.get("planner_correct", case.get("gemini_correct", False))
                          for case in report_cases)
    contract_correct = sum(case.get("proposal_contract_correct", False)
                           for case in report_cases)
    successful = len(successful_cases)
    evaluated = len(report_cases)
    latencies = sorted(item["latency_ms"] for item in report_cases)
    return {
        "eligible_case_count": evaluated,
        "model_call_count": evaluated,
        "proposal_success_count": successful,
        "semantic_evaluation_case_count": len(semantic_cases),
        "provider_error_count": provider_errors,
        "invalid_provider_response_count": invalid_provider_responses,
        "provider_response_recovery_count": recovered_provider_responses,
        "deterministic_correct": sum(c["deterministic_correct"] for c in report_cases),
        "gemini_correct": sum(
            c.get("gemini_correct", c.get("planner_correct", False)) for c in report_cases
        ),
        "semantic_correct_count": semantic_correct,
        "semantic_accuracy_percent": round(100 * semantic_correct / len(semantic_cases), 2)
        if semantic_cases else None,
        "planner_outcome_accuracy_percent": round(
            100 * planner_correct / evaluated, 2
        ) if evaluated else None,
        "planner_correct_count": planner_correct,
        "proposal_contract_correct_count": contract_correct,
        "proposal_contract_accuracy_percent": round(100 * contract_correct / evaluated, 2)
        if evaluated else None,
        "sql_execution_count": 0,
        "numeric_reconciliation_count": 0,
        "latency_p50_ms": round(median(latencies)) if latencies else None,
        "latency_p95_ms": latencies[math.ceil(0.95 * len(latencies)) - 1]
        if latencies else None,
        "error_cases": provider_errors,
        "same_plan_as_deterministic": sum(
            bool(c.get("same_plan_as_deterministic")) for c in report_cases
        ),
    }


async def _evaluate(
    settings, sample_ids=SAMPLE_IDS, inter_request_delay_ms=0, fixture_path=FIXTURE,
):
    from google import genai

    client = genai.Client(
        api_key=settings.gemini_api_key.get_secret_value(),
        http_options={"timeout": settings.model_timeout_ms,
                      "retry_options": {"attempts": 1}},
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in fixture["cases"]}
    report_cases = []
    usage = {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    request_fingerprints = []
    for index, case_id in enumerate(sample_ids):
        if index and inter_request_delay_ms:
            await asyncio.sleep(inter_request_delay_ms / 1000)
        case = cases[case_id]
        core, request = _setup_case(case)
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
                "semantic_correct": False if "expected_semantics" in case else None,
                "proposal_contract_correct": False,
                "planner_correct": False,
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
        planner_expected = case.get("expected_planner", case["expected"])
        planner_correct = _matches(proposed, planner_expected, case_id)
        semantic_correct = (
            _semantic_matches(
                proposal, case["expected_semantics"], coverage, dimensions,
            )
            if "expected_semantics" in case else None
        )
        contract_correct = (
            _proposal_contract_matches(proposal, case["expected_semantics"])
            if "expected_semantics" in case else None
        )
        planner_expected = case.get("expected_planner", case["expected"])
        if (
            "expected_semantics" in case
            and planner_expected.get("status") == "planned"
        ):
            planner_correct = _plan_matches_semantics(
                proposed, case["expected_semantics"], coverage,
            )
        report_cases.append({
            "id": case_id,
            "category": case["category"],
            "expected": case["expected"],
            "expected_semantics": case.get("expected_semantics"),
            "deterministic_correct": _matches(deterministic, case["expected"], case_id),
            "gemini_correct": planner_correct,
            "planner_correct": planner_correct,
            "semantic_correct": semantic_correct,
            "proposal_contract_correct": contract_correct,
            "proposal": _proposal_snapshot(proposal),
            "response_diagnostic": proposer.last_response_diagnostic or None,
            "same_correctness": _matches(deterministic, case["expected"], case_id)
            == planner_correct,
            "proposal_status": proposal.status.value,
            "actual": _plan_snapshot(proposed),
            "failure_stage": (
                None if planner_correct else
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
    return {
        "report_type": "hnlu_intent_comparison_v1",
        "provider": "Gemini",
        "model": settings.gemini_model,
        "fixture_name": fixture_path.name,
        "fixture_version": fixture["dataset_version"],
        "sample_ids": list(sample_ids),
        "request_fingerprint": hashlib.sha256(
            "".join(request_fingerprints).encode("ascii")
        ).hexdigest(),
        "case_count": len(report_cases),
        "model_call_count": len(sample_ids),
        "inter_request_delay_ms": inter_request_delay_ms,
        "summary": _summary(report_cases),
        "usage": usage,
        "cases": report_cases,
        "limitations": [
            f"Amostra de {len(sample_ids)} casos sintéticos, sem execução SQL "
            "ou resposta numérica.",
            "Os valores e competências vêm de fixtures e não comprovam cobertura Gold real.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all-fixture",
        action="store_true",
        help="Inclui todos os casos da fixture (cada caso elegível gera uma chamada real).",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Executa somente o caso indicado; pode ser repetido.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=FIXTURE,
        help="Fixture JSON para avaliar; por padrão usa gold_language_eval.json.",
    )
    parser.add_argument(
        "--inter-request-delay-ms",
        type=int,
        default=0,
        choices=range(0, 30_001),
        metavar="MS",
        help="Intervalo entre chamadas para evitar exceder a quota do provedor.",
    )
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()
    if os.environ.get("GENAI_RUN_HNLU") != "1":
        parser.error("Defina GENAI_RUN_HNLU=1 para autorizar chamadas reais ao Gemini.")
    if args.all_fixture and args.case_id:
        parser.error("Use --all-fixture ou --case-id, não ambos.")
    settings = Settings()
    if settings.gemini_api_key is None:
        parser.error("Configure a chave local do Gemini.")
    sample_ids = SAMPLE_IDS
    fixture_path = args.fixture if args.fixture.is_absolute() else ROOT / args.fixture
    if args.all_fixture:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        sample_ids = tuple(case["id"] for case in fixture["cases"])
    elif args.case_id:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        available_ids = {case["id"] for case in fixture["cases"]}
        unknown_ids = sorted(set(args.case_id) - available_ids)
        if unknown_ids:
            parser.error(f"Casos inexistentes na fixture: {', '.join(unknown_ids)}")
        sample_ids = tuple(args.case_id)
    report = asyncio.run(
        _evaluate(settings, sample_ids, args.inter_request_delay_ms, fixture_path)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
