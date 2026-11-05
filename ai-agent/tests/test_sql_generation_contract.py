"""Contratos independentes dos serviços e estados adversariais do candidato."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.sql_generation import SqlGenerationCandidate, SqlParameter, SqlPeriod

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs/contracts/examples/text-to-sql-f1-v1.json"


@pytest.fixture
def examples():
    return json.loads(EXAMPLES.read_text(encoding="utf-8"))["valid"]


def test_independent_backend_contract_matches_schema_and_shared_examples(examples):
    invalid = json.loads(EXAMPLES.read_text(encoding="utf-8"))["invalid"]
    code = """
import json, sys
from pydantic import ValidationError
from app.schemas.sql_generation import SqlGenerationCandidate
payload = json.load(sys.stdin)
rejected = []
for row in payload['invalid']:
    try:
        SqlGenerationCandidate.model_validate(row['payload'])
    except ValidationError:
        rejected.append(row['id'])
print(json.dumps({'schema': SqlGenerationCandidate.model_json_schema(),
    'examples': [SqlGenerationCandidate.model_validate(x).model_dump(mode='json')
                 for x in payload['valid']], 'rejected': rejected}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code], input=json.dumps({"valid": examples, "invalid": invalid}),
        cwd=ROOT / "backend",
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=30,
    )
    backend = json.loads(result.stdout)
    assert backend["schema"] == SqlGenerationCandidate.model_json_schema()
    assert backend["examples"] == [
        SqlGenerationCandidate.model_validate(row).model_dump(mode="json") for row in examples
    ]
    assert backend["rejected"] == [row["id"] for row in invalid]
    for row in invalid:
        with pytest.raises(ValidationError):
            SqlGenerationCandidate.model_validate(row["payload"])


@pytest.mark.parametrize("state_index", [1, 2])
@pytest.mark.parametrize("field,value", [
    ("sql", "SELECT 1"),
    ("parameters", {"x": {"type": "integer", "value": 1}}),
])
def test_non_candidate_cannot_smuggle_partial_query(examples, state_index, field, value):
    payload = copy.deepcopy(examples[state_index])
    payload[field] = value
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(payload)


@pytest.mark.parametrize("mutation", [
    {"validated": True}, {"status": "authorized"}, {"sql": " "},
    {"interpretation": None}, {"result_columns": []},
    {"context_version": "not-a-version"},
    {"clarification": {"question": "Qual mês?", "missing_fields": ["period"]}},
])
def test_candidate_rejects_incoherent_or_extra_fields(examples, mutation):
    payload = {**examples[0], **mutation}
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(payload)


@pytest.mark.parametrize("kind,value", [
    ("integer", True), ("integer", "12"), ("boolean", 1),
    ("number", float("nan")), ("number", float("inf")),
    ("decimal", "Infinity"), ("decimal", "NaN"),
    ("date", "2026-02-30"), ("date", "20260601"), ("string", "x" * 1001),
])
def test_parameter_rejects_coercion_nonfinite_and_invalid_dates(kind, value):
    with pytest.raises(ValidationError):
        SqlParameter(type=kind, value=value)


@pytest.mark.parametrize("start,end", [
    ("2026-06-02", "2026-06-30"), ("2026-06-01", "2026-06-29"),
    ("2026-07-01", "2026-06-30"), (0, 2678400),
])
def test_monthly_period_rejects_partial_inverted_or_timestamp(start, end):
    with pytest.raises(ValidationError):
        SqlPeriod(start=start, end=end)


def test_contract_does_not_pretend_to_validate_or_authorize_sql(examples):
    payload = {**examples[0], "sql": "DELETE FROM gold_v2.diagnostico_receita"}
    candidate = SqlGenerationCandidate.model_validate(payload)
    assert candidate.status == "sql_candidate"
    assert not hasattr(candidate, "validated")
    # AST/política Backend ainda deve rejeitar este conteúdo antes de qualquer execução.


def test_result_columns_and_ranking_cannot_lose_required_semantics(examples):
    payload = copy.deepcopy(examples[0])
    payload["result_columns"] *= 2
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(payload)
    payload = copy.deepcopy(examples[0])
    payload["interpretation"].update(operation="ranking", group_by=["municipality"])
    with pytest.raises(ValidationError):
        SqlGenerationCandidate.model_validate(payload)
