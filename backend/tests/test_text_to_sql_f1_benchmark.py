"""Provas do avaliador: SQL plausível pode representar a pergunta errada."""

import json
import os
from pathlib import Path

import pytest
from app.schemas.sql_generation import SqlGenerationCandidate

from tests.text_to_sql_f1_baseline import run
from tests.text_to_sql_f1_candidates import context_for_case, intent_differences

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "ai-agent/tests/fixtures"
BENCHMARK = json.loads(
    (FIXTURES / "text_to_sql_f1_benchmark.json").read_text(encoding="utf-8")
)
DATA = json.loads(
    (FIXTURES / "text_to_sql_f1_reference.json").read_text(encoding="utf-8")
)
CASE = BENCHMARK["cases"][0]


def payload(city="Recife"):
    value = json.loads(
        (ROOT / "docs/contracts/examples/text-to-sql-f1-v1.json").read_text(
            encoding="utf-8"
        )
    )["valid"][0]
    value.update(
        context_version=context_for_case(CASE, DATA).context_version,
        sql="SELECT SUM(receita_total_reais) AS revenue FROM gold_v2.diagnostico_receita WHERE competencia = :month AND municipio = :city",
        parameters={
            "month": {"type": "string", "value": "2026-06"},
            "city": {"type": "string", "value": city},
        },
    )
    value["interpretation"]["filters"] = [
        {"dimension_id": "geography.municipality", "operator": "eq", "values": [city]}
    ]
    return value


def test_detects_wrong_question_even_when_sql_matches_model_declared_intent():
    candidate = SqlGenerationCandidate.model_validate(payload("Olinda"))
    assert intent_differences(candidate, CASE["expected"]) == ["filters"]
    assert (
        intent_differences(
            SqlGenerationCandidate.model_validate(payload()), CASE["expected"]
        )
        == []
    )


def test_rejects_real_database_before_connecting():
    with pytest.raises(ValueError, match="descartável"):
        run("postgresql+psycopg://unused:unused@localhost/production", {})


@pytest.mark.parametrize("mode", ["correct", "wrong_city", "unsafe"])
def test_captured_candidate_is_measured_against_independent_reference(mode):
    address = os.environ.get("TEST_TEXT_TO_SQL_URL")
    if not address:
        pytest.skip("Requer PostgreSQL descartável text_to_sql_f1_test.")
    baseline = json.loads(
        (ROOT / "ai-agent/reports/text-to-sql-f1-baseline.json").read_text(
            encoding="utf-8"
        )
    )
    value = payload("Olinda" if mode == "wrong_city" else "Recife")
    if mode == "unsafe":
        value["sql"] = "DELETE FROM gold_v2.diagnostico_receita"
    report = run(address, baseline, {CASE["id"]: value})
    observed = next(r for r in report["results"] if r["id"] == CASE["id"])
    if mode == "correct":
        assert observed["outcome"] == "exact_reference_match"
    elif mode == "wrong_city":
        assert observed["outcome"] == "divergent"
        assert observed["differences"] == ["filters", "compiled_result"]
    else:
        assert observed["outcome"] == "technical_error"
        assert observed["error_type"] == "SqlStructureRejected"
    assert report["counts"]["not_executed_missing_candidate"] == 39
