import json
from pathlib import Path

import pytest

from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_sql_context import build_sql_generation_context
from tests.text_to_sql_f1_continuity import (
    _candidate_differences,
    export_contexts,
    load_fixture,
    request_for_case,
)


def test_continuity_fixture_exports_versioned_context_for_every_followup(tmp_path):
    fixture, _digest = load_fixture()
    output = tmp_path / "contexts.json"
    export_contexts(output)
    bundle = json.loads(output.read_text(encoding="utf-8"))
    assert len(bundle["contexts"]) == len(fixture["cases"]) == 10
    for case, context in zip(fixture["cases"], bundle["contexts"], strict=True):
        assert context["id"] == case["id"]
        assert context["context_version"] == build_sql_generation_context(
            request_for_case(case)
        ).context_version
        body = json.loads(context["contents"])
        assert body["question"] == case["question"]
        assert body["context"] == case["context"]


def test_prompt_13_fixture_keeps_the_two_corrected_continuity_oracles():
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "ai-agent/tests/fixtures/text_to_sql_f1_continuity_prompt13.json"
    )
    fixture, _digest = load_fixture(fixture_path)
    cases = {case["id"]: case for case in fixture["cases"]}

    assert set(cases) == {"F1-CONT-10", "F1-CONT-11"}
    assert cases["F1-CONT-10"]["expected"]["status"] == "needs_clarification"
    assert cases["F1-CONT-11"]["expected"]["operation"] == "comparison"
    assert cases["F1-CONT-11"]["expected"]["periods"] == [
        ["2026-01", "2026-12"], ["2025-01", "2025-12"],
    ]


def test_f1_14_regression_fixture_merges_thirteen_unique_continuity_cases():
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "ai-agent/tests/fixtures/text_to_sql_f1_continuity_f14.json"
    )
    fixture, _digest = load_fixture(fixture_path)
    cases = {case["id"]: case for case in fixture["cases"]}

    assert len(cases) == len(fixture["cases"]) == 13
    assert set(cases) == {f"F1-CONT-{number:02d}" for number in range(1, 14)}
    assert cases["F1-CONT-08"]["expected"]["metric_id"] == "energy.consumption"
    assert cases["F1-CONT-10"]["expected"]["status"] == "needs_clarification"
    assert cases["F1-CONT-11"]["expected"]["operation"] == "comparison"


def test_out_of_scope_case_keeps_semantic_recognition_without_sql():
    fixture, _digest = load_fixture()
    case = next(item for item in fixture["cases"] if item["id"] == "F1-CONT-08")
    candidate = SqlGenerationCandidate(
        generation_contract_version="text-to-sql-f1-v1",
        status="unsupported",
        context_version="a" * 64,
        unsupported_reason={
            "code": "metric_outside_f1",
            "message": "Consumo medido ainda não está disponível na F1.",
        },
        semantic_intent={
            "metric_id": "energy.consumption",
            "periods": [{"start": "2026-06-01", "end": "2026-06-30"}],
            "filters": [{
                "dimension_id": "geography.municipality",
                "operator": "eq",
                "values": ["Recife"],
            }],
        },
    )
    differences = _candidate_differences(candidate, case["expected"])
    assert "status" not in differences
    assert "reason_code" not in differences
    assert differences == []
    assert candidate.sql is None


def test_out_of_scope_semantic_intent_cannot_become_an_executable_candidate():
    payload = {
        "generation_contract_version": "text-to-sql-f1-v1",
        "status": "unsupported",
        "context_version": "a" * 64,
        "unsupported_reason": {
            "code": "metric_outside_f1",
            "message": "Consumo ainda não está disponível na F1.",
        },
        "semantic_intent": {
            "metric_id": "energy.consumption",
            "periods": [{"start": "2026-06-01", "end": "2026-06-30"}],
            "filters": [],
        },
    }
    payload["sql"] = "SELECT 1"

    with pytest.raises(ValueError, match="estado sem candidato"):
        SqlGenerationCandidate.model_validate(payload)
