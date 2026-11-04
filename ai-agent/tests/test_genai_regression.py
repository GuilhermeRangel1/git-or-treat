"""Avaliação sintética reproduzível pela API pública do agente."""

import argparse
import json
from pathlib import Path

import pytest

from app.api.access import SYNTHETIC_SOURCE_ID
from app.config import Settings
from app.main import create_app
from app.ports.evidence import EvidenceToolUnavailable
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.protocols import GeneratedAnswer, ModelProviderUnavailable
from app.schemas.evidence import EvidenceLookupResult
from app.schemas.read_plan import LogicalReadPlan, WindowKind
from app.tools.synthetic_analytics import SyntheticScenarioTool

from .conftest import InProcessClient

ROOT = Path(__file__).parent
DATASET_PATH = ROOT / "fixtures" / "genai_regression.json"
DATASET = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

PASSED = "passed"
UNEXPECTED_FAILURE = "unexpected_failure"
KNOWN_FAILURE_CONFIRMED = "known_failure_confirmed"
KNOWN_FAILURE_CHANGED = "known_failure_changed"
KNOWN_FAILURE_NOW_PASSING = "known_failure_now_passing"
ACCEPTED_OUTCOMES = {PASSED, KNOWN_FAILURE_CONFIRMED}


class RecordingEvidenceSource:
    """Encapsula a fonte sintética e registra cada plano aprovado que chega a ela."""

    def __init__(self, *, fail: bool = False) -> None:
        self.delegate = SyntheticScenarioTool()
        self.plans: list[LogicalReadPlan] = []
        self.fail = fail

    async def retrieve(self, plan: LogicalReadPlan, access_context) -> EvidenceLookupResult:
        self.plans.append(plan)
        if self.fail:
            raise EvidenceToolUnavailable("private source detail")
        return await self.delegate.retrieve(plan, access_context)


class CaseModelAdapter:
    def __init__(self, case: dict) -> None:
        self.answer = GeneratedAnswer(
            status=case.get("model_status", "answered"),
            answer=case.get("model_answer", "Resposta sintética sem números."),
            observation_ids=tuple(case.get("model_observation_ids", ())),
        )
        self.calls = []
        self.fail = case.get("model_failure", False)

    async def generate(self, question, context, evidence):
        self.calls.append((question, context, evidence))
        if self.fail:
            raise ModelProviderUnavailable("private provider detail")
        return self.answer


def summarize_plan(plan: LogicalReadPlan) -> dict:
    """Projeção do plano no formato de `expected_plan`, sem campos de versão ou limite."""
    if plan.window.kind is WindowKind.CATALOG_PHRASE:
        window = {"phrase": plan.window.phrase}
    else:
        window = {"start": plan.window.start.isoformat(), "end": plan.window.end.isoformat()}
    return {
        "domain_id": plan.domain_id,
        "metric_id": plan.metric_id,
        "dimension_ids": sorted(plan.dimension_ids),
        "window": window,
        "filters": sorted(
            (
                {"dimension_id": item.dimension_id, "values": list(item.values)}
                for item in plan.filters
            ),
            key=lambda item: item["dimension_id"],
        ),
    }


def _normalize_expected_plan(expected: dict) -> dict:
    return {
        **expected,
        "dimension_ids": sorted(expected["dimension_ids"]),
        "filters": sorted(expected["filters"], key=lambda item: item["dimension_id"]),
    }


def classify(case: dict, failing_checks: list[str], actual_status: str) -> str:
    known = case.get("known_failure")
    if known is None:
        return UNEXPECTED_FAILURE if failing_checks else PASSED
    if not failing_checks:
        return KNOWN_FAILURE_NOW_PASSING
    if (
        failing_checks == sorted(known["failing_checks"])
        and actual_status == known["actual_status"]
    ):
        return KNOWN_FAILURE_CONFIRMED
    return KNOWN_FAILURE_CHANGED


def evaluate_case(case: dict) -> dict:
    source = RecordingEvidenceSource(fail=case.get("tool_failure", False))
    model = CaseModelAdapter(case)
    # Caminho oficial: create_app monta o ExecutionController e chama compose_core.
    application = create_app(
        settings=Settings(
            _env_file=None,
            environment="local",
            enable_demo_access=True,
            model_routing_enabled=False,
        ),
        domain_profile=GRID360_DEMO_PROFILE,
        source_id=SYNTHETIC_SOURCE_ID,
        evidence_source=source,
        model_adapter=model,
    )
    with InProcessClient(application) as client:
        if case.get("endpoint") == "insights":
            screen = DATASET["screen_contexts"][case["screen_context_id"]]
            response = client.post("/api/v1/insights", json={"screen": screen})
        else:
            response = client.post(
                "/api/v1/questions",
                json={"question": case["question"], "context": case.get("context", [])},
            )
    body = response.json()

    actual_plan = summarize_plan(source.plans[-1]) if source.plans else None
    actual_domain = actual_plan["domain_id"] if actual_plan else None
    checks = {
        "http_ok": response.status_code == 200,
        "status": body.get("status") == case["expected_status"],
        "tool_calls": len(source.plans) == case["expected_tool_calls"],
        "model_calls": len(model.calls) == case["expected_model_calls"],
        "domain": actual_domain == case["expected_domain"],
    }
    if "expected_plan" in case:
        checks["plan"] = actual_plan == _normalize_expected_plan(case["expected_plan"])
    if "expected_answer_fragment" in case:
        generated_text = " ".join(
            value
            for value in (body.get("answer"), body.get("hypothesis"), body.get("message"))
            if value
        )
        checks["expected_content"] = case["expected_answer_fragment"] in generated_text
    if "expected_evidence_source" in case:
        expected_source = case["expected_evidence_source"]
        is_insight = case.get("endpoint") == "insights"
        checks["evidence_source"] = any(
            (
                item["source"].startswith("synthetic.screen:")
                and len(item["source"].split(":", 1)[1]) == 64
                and item["source"] != expected_source
            )
            if is_insight
            else item["source"].startswith(f"{expected_source}:")
            for item in body.get("evidence", [])
        )
    if "expected_observation_value" in case:
        observed_values = body.get("observation", {}).get("values", [])
        checks["observation_value"] = any(
            item.get("value") == case["expected_observation_value"] for item in observed_values
        )

    failing_checks = sorted(name for name, ok in checks.items() if not ok)
    actual_status = body.get("status", f"http_{response.status_code}")
    known = case.get("known_failure")
    return {
        "id": case["id"],
        "endpoint": case.get("endpoint", "questions"),
        "category": case.get("category", "question_flow"),
        "passed": not failing_checks,
        "outcome": classify(case, failing_checks, actual_status),
        "known_failure": known["reason"] if known else None,
        "failing_checks": failing_checks,
        "checks": checks,
        "actual_status": actual_status,
        "actual_domain": actual_domain,
        "actual_plan": actual_plan,
        "tool_calls": len(source.plans),
        "model_calls": len(model.calls),
    }


@pytest.mark.parametrize("case", DATASET["cases"], ids=lambda case: case["id"])
def test_versioned_synthetic_regression_case_passes(case: dict) -> None:
    result = evaluate_case(case)

    if result["outcome"] == KNOWN_FAILURE_NOW_PASSING:
        pytest.fail(
            f"{case['id']} passou: remova known_failure da fixture. {result}", pytrace=False
        )
    if result["outcome"] == KNOWN_FAILURE_CHANGED:
        expected = case["known_failure"]
        pytest.fail(
            f"{case['id']} falhou de forma diferente da registrada: esperado "
            f"{sorted(expected['failing_checks'])} com status {expected['actual_status']}, "
            f"obtido {result['failing_checks']} com status {result['actual_status']}. {result}",
            pytrace=False,
        )
    assert result["outcome"] in ACCEPTED_OUTCOMES, result


def test_known_failures_declare_reason_checks_and_actual_status() -> None:
    for case in DATASET["cases"]:
        known = case.get("known_failure")
        if known is None:
            continue
        assert set(known) == {"reason", "failing_checks", "actual_status"}, case["id"]
        assert known["reason"] and known["failing_checks"], case["id"]


def test_expected_plan_is_declared_for_every_expected_tool_call() -> None:
    questions = [case for case in DATASET["cases"] if case.get("endpoint") != "insights"]
    for case in questions:
        assert ("expected_plan" in case) == (case["expected_tool_calls"] > 0), case["id"]


def test_insight_fixtures_cover_required_synthetic_outcomes() -> None:
    insight_categories = {
        case.get("category") for case in DATASET["cases"] if case.get("endpoint") == "insights"
    }

    assert insight_categories == {
        "grounded_answer",
        "clarification",
        "refusal",
        "insufficient_evidence",
    }


def test_report_is_repeatable_and_declares_version_scope_and_limitations() -> None:
    first = build_report()
    second = build_report()

    assert first == second
    assert first["synthetic"] is True
    assert first["dataset_version"] == DATASET["dataset_version"]
    assert first["scenario_scope"] == DATASET["scenario_scope"]
    assert first["limitations"] == DATASET["limitations"]


def build_report() -> dict:
    results = [evaluate_case(case) for case in DATASET["cases"]]
    passed = sum(result["passed"] for result in results)

    def count(outcome: str) -> int:
        return sum(result["outcome"] == outcome for result in results)

    return {
        "report_type": "synthetic_regression",
        "synthetic": True,
        "dataset_version": DATASET["dataset_version"],
        "scenario_scope": DATASET["scenario_scope"],
        "provider": "fixed_test_adapter; no Gemini API calls",
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": f"{passed}/{len(results)} ({passed / len(results):.1%})",
            "known_failures_confirmed": count(KNOWN_FAILURE_CONFIRMED),
            "known_failures_changed": count(KNOWN_FAILURE_CHANGED),
            "known_failures_now_passing": count(KNOWN_FAILURE_NOW_PASSING),
            "unexpected_failures": count(UNEXPECTED_FAILURE),
        },
        "limitations": DATASET["limitations"],
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
    )
    parser.add_argument("--gold-language", action="store_true",
                        help="Avalia interpretação Gold v2 com cobertura artificial, sem provedor.")
    parser.add_argument("--language-holdout", action="store_true",
                        help="Usa as 16 formulações separadas; requer --gold-language.")
    parser.add_argument("--expanded", action="store_true")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--real-sample", type=int, default=0,
                        help="Opt-in Gemini: orçamento máximo de seis casos artificiais.")
    parser.add_argument("--backend-junit", type=Path)
    args = parser.parse_args()
    if args.expanded and args.gold_language:
        parser.error("--expanded e --gold-language são escopos distintos")
    if args.backend_junit and (args.expanded or args.gold_language):
        parser.error("--backend-junit é um escopo separado")
    if args.baseline and not (args.expanded or args.backend_junit):
        parser.error("--baseline requer --expanded ou --backend-junit")
    if args.real_sample and not args.expanded:
        parser.error("--real-sample requer --expanded")
    if args.language_holdout and not args.gold_language:
        parser.error("--language-holdout requer --gold-language")
    private_root = ROOT.parents[1] / "work"
    if args.real_sample:
        output = args.output or private_root / "evaluation" / "gemini-artificial.json"
        if not output.resolve().is_relative_to(private_root.resolve()):
            parser.error("O relatório de provedor real deve ficar em work/.")
    else:
        name = ("backend-evaluation" if args.backend_junit else
                "expanded-regression-report" if args.expanded else
                "gold-language-holdout" if args.language_holdout else
                "gold-language-report" if args.gold_language else "synthetic-regression-report")
        output = args.output or Path("reports") / f"{name}.json"
    dataset = "gold_language_holdout.json" if args.language_holdout else "gold_language_eval.json"
    if args.backend_junit:
        from .evaluation_report import summarize_backend_junit
        report = summarize_backend_junit(args.backend_junit)
    elif args.expanded:
        from .expanded_evaluation import build_expanded_report, build_real_report
        report = (build_real_report(args.real_sample) if args.real_sample
                  else build_expanded_report())
    else:
        report = build_gold_language_report(dataset) if args.gold_language else build_report()
    if args.baseline:
        from .evaluation_report import compare_reports
        report["comparison"] = compare_reports(
            json.loads(args.baseline.read_text(encoding="utf-8")), report,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    output.write_text(report_json, encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    if args.baseline and not report["comparison"]["gate_passed"]:
        raise SystemExit(1)
    if any(result["outcome"] not in ACCEPTED_OUTCOMES for result in report["cases"]):
        raise SystemExit(1)


def build_gold_language_report(
    dataset_name: str = "gold_language_eval.json", *, include_checks: bool = False,
) -> dict:
    """Usa a mesma borda HTTP Gold da regressão; expectativas vêm da fixture versionada."""
    from .test_gold_language_http import _plan

    if dataset_name not in {"gold_language_eval.json", "gold_language_holdout.json"}:
        raise ValueError("conjunto de avaliação desconhecido")
    dataset = json.loads((ROOT / "fixtures" / dataset_name).read_text(encoding="utf-8"))
    results = []
    categories = {}
    for case in dataset["cases"]:
        try:
            response = _plan(case["question"])
            actual = {"status": response["status"]}
            if response.get("plan"):
                plan = response["plan"]
                actual.update({key: plan.get(key) for key in case["expected"] if key != "status"})
                assert plan["operation"] == "read"
                assert plan["profile_id"] == "v-energy-grid-360-gold"
                assert plan["source_id"] == "gold.local"
        except Exception:
            if not include_checks:
                raise
            results.append({"id": case["id"], "category": case["category"], "passed": False,
                            "outcome": "evaluator_error", "checks": {"evaluator_execution": False}})
            continue
        failures = sorted(key for key, value in case["expected"].items()
                          if actual.get(key) != value)
        passed = not failures
        results.append({"id": case["id"], "category": case["category"], "passed": passed,
                        "outcome": PASSED if passed else UNEXPECTED_FAILURE,
                        "actual_status": response["status"], "failing_checks": failures})
        if include_checks:
            results[-1]["checks"] = {key: key not in failures for key in case["expected"]}
        group = categories.setdefault(case["category"], {"total": 0, "passed": 0})
        group["total"] += 1
        group["passed"] += int(passed)
    passed = sum(case["passed"] for case in results)
    return {"report_type": "gold_language_planning", "synthetic": True,
            "dataset_version": dataset["dataset_version"], "scenario_scope": dataset["scope"],
            "provider": "none; interpretation only", "limitations": dataset["limitations"],
            "summary": {"total": len(results), "passed": passed, "failed": len(results)-passed},
            "categories": categories, "cases": results}


if __name__ == "__main__":
    main()
