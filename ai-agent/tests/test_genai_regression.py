"""Avaliação sintética reproduzível pela API pública do agente."""

import argparse
import json
from pathlib import Path

import pytest

from app.agent.insights import ScreenInsightOrchestrator
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.config import Settings
from app.main import create_app
from app.ports.evidence import EvidenceToolUnavailable
from app.providers.protocols import GeneratedAnswer, ModelProviderUnavailable
from app.schemas.analysis import AnalysisIntent
from app.tools.synthetic_analytics import SyntheticScenarioTool

from .conftest import InProcessClient

ROOT = Path(__file__).parent
DATASET_PATH = ROOT / "fixtures" / "genai_regression.json"
DATASET = json.loads(DATASET_PATH.read_text(encoding="utf-8"))


class CountingInterpreter:
    def __init__(self) -> None:
        self.delegate = QuestionInterpreter()
        self.results = []

    def interpret(self, question, context=None):
        result = self.delegate.interpret(question, context)
        self.results.append(result)
        return result


class CountingScenarioTool:
    def __init__(self, *, fail: bool = False) -> None:
        self.delegate = SyntheticScenarioTool()
        self.calls = []
        self.fail = fail

    async def retrieve(self, intent: AnalysisIntent):
        self.calls.append(intent)
        if self.fail:
            raise EvidenceToolUnavailable("private source detail")
        return await self.delegate.retrieve(intent)


class CaseModelAdapter:
    def __init__(self, case: dict) -> None:
        self.answer = GeneratedAnswer(
            status=case.get("model_status", "answered"),
            answer=case.get("model_answer", "Resposta sintética sem números."),
        )
        self.calls = []
        self.fail = case.get("model_failure", False)

    async def generate(self, question, context, evidence):
        self.calls.append((question, context, evidence))
        if self.fail:
            raise ModelProviderUnavailable("private provider detail")
        return self.answer


def evaluate_case(case: dict) -> dict:
    interpreter = CountingInterpreter()
    tool = CountingScenarioTool(fail=case.get("tool_failure", False))
    model = CaseModelAdapter(case)
    orchestrator = QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(interpreter, tool),
        model_adapter=model,
    )
    application = create_app(
        settings=Settings(_env_file=None),
        question_orchestrator=orchestrator,
        insight_orchestrator=ScreenInsightOrchestrator(model),
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

    actual_domain = None
    if interpreter.results and interpreter.results[-1].intent is not None:
        actual_domain = interpreter.results[-1].intent.domain.value
    checks = {
        "http_ok": response.status_code == 200,
        "status": body.get("status") == case["expected_status"],
        "tool_calls": len(tool.calls) == case["expected_tool_calls"],
        "model_calls": len(model.calls) == case["expected_model_calls"],
        "domain": actual_domain == case["expected_domain"],
    }
    if "expected_answer_fragment" in case:
        generated_text = " ".join(
            value
            for value in (body.get("answer"), body.get("hypothesis"), body.get("message"))
            if value
        )
        checks["expected_content"] = case["expected_answer_fragment"] in generated_text
    if "expected_evidence_source" in case:
        checks["evidence_source"] = any(
            item["source"] == case["expected_evidence_source"] for item in body.get("evidence", [])
        )
    if "expected_observation_value" in case:
        observed_values = body.get("observation", {}).get("values", [])
        checks["observation_value"] = any(
            item.get("value") == case["expected_observation_value"]
            for item in observed_values
        )
    return {
        "id": case["id"],
        "endpoint": case.get("endpoint", "questions"),
        "category": case.get("category", "question_flow"),
        "passed": all(checks.values()),
        "checks": checks,
        "actual_status": body.get("status", f"http_{response.status_code}"),
        "actual_domain": actual_domain,
        "tool_calls": len(tool.calls),
        "model_calls": len(model.calls),
    }


@pytest.mark.parametrize("case", DATASET["cases"], ids=lambda case: case["id"])
def test_versioned_synthetic_regression_case_passes(case: dict) -> None:
    result = evaluate_case(case)

    assert result["passed"], result


def test_insight_fixtures_cover_required_synthetic_outcomes() -> None:
    insight_categories = {
        case.get("category")
        for case in DATASET["cases"]
        if case.get("endpoint") == "insights"
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
    return {
        "report_type": "synthetic_regression",
        "synthetic": True,
        "dataset_version": DATASET["dataset_version"],
        "scenario_scope": DATASET["scenario_scope"],
        "provider": "fixed_test_adapter; no Gemini API calls",
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed},
        "limitations": DATASET["limitations"],
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/synthetic-regression-report.json"),
    )
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    args.output.write_text(report_json, encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    if report["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
