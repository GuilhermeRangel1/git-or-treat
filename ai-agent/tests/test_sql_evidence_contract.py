"""Contrato independente dos dois serviços; exemplos inteiramente artificiais."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.sql_evidence import SqlEvidence

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = json.loads((ROOT / "docs/contracts/examples/text-to-sql-f1-evidence-v1.json").read_text(
    encoding="utf-8"))


def _serialized_legacy_payload(payload):
    """v5 adds an explicit quality default while accepting v1-v4 wire vectors."""
    normalized = dict(payload)
    normalized.setdefault("coverage_quality", "certified")
    return normalized


@pytest.mark.parametrize("payload", SAMPLES["valid"])
def test_accepts_exact_evidence_and_roundtrips(payload):
    evidence = SqlEvidence.model_validate(payload)
    assert evidence.model_dump(mode="json") == _serialized_legacy_payload(payload)


@pytest.mark.parametrize("case", SAMPLES["invalid"], ids=lambda case: case["id"])
def test_rejects_invalid_evidence(case):
    with pytest.raises(ValidationError):
        SqlEvidence.model_validate(case["payload"])


def test_backend_independently_accepts_same_vectors_and_schema():
    code = """
import json,sys
from pydantic import ValidationError
from app.schemas.sql_evidence import SqlEvidence
samples=json.load(sys.stdin)
valid=[SqlEvidence.model_validate(p).model_dump(mode='json') for p in samples['valid']]
rejected=[]
for case in samples['invalid']:
    try:
        SqlEvidence.model_validate(case['payload'])
    except ValidationError:
        rejected.append(case['id'])
print(json.dumps({'schema':SqlEvidence.model_json_schema(),'valid':valid,'rejected':rejected}))
"""
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=ROOT / "backend",
        input=json.dumps(SAMPLES), capture_output=True, text=True, encoding="utf-8",
        timeout=30, check=True)
    backend = json.loads(result.stdout)
    assert backend["schema"] == SqlEvidence.model_json_schema()
    assert backend["valid"] == [
        _serialized_legacy_payload(payload) for payload in SAMPLES["valid"]
    ]
    assert backend["rejected"] == [case["id"] for case in SAMPLES["invalid"]]
