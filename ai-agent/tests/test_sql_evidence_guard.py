"""Revalidação de evidência Text-to-SQL sem depender do plano determinístico legado."""

import json
from pathlib import Path

import pytest

from app.agent.evidence_guard import EvidenceGuard
from app.ports.evidence import EvidenceContractInvalid
from app.profiles.grid360_gold_catalog import GRID360_GOLD_RUNTIME_PROFILE
from app.schemas.sql_evidence import SqlEvidence

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = json.loads((ROOT / "docs/contracts/examples/text-to-sql-f1-evidence-v1.json").read_text(
    encoding="utf-8"))
ALLOWED_METRICS = frozenset({"billing.revenue"})
ALLOWED_DIMENSIONS = frozenset({
    "geography.municipality", "customer.consumption_class",
})


def _validate(evidence, **overrides):
    options = {
        "expected_batch_ref": evidence.batch_ref,
        "expected_context_version": evidence.context_version,
        "allowed_metric_ids": ALLOWED_METRICS,
        "allowed_dimension_ids": ALLOWED_DIMENSIONS,
        **overrides,
    }
    return EvidenceGuard(GRID360_GOLD_RUNTIME_PROFILE).validate_sql_evidence(evidence, **options)


@pytest.mark.parametrize("payload", SAMPLES["valid"])
def test_guard_accepts_sql_evidence_operations_without_legacy_read_plan(payload):
    evidence = SqlEvidence.model_validate(payload)

    assert _validate(evidence) == evidence


@pytest.mark.parametrize("change", ["batch", "context", "metric", "municipality"])
def test_guard_rejects_sql_evidence_outside_current_context(change):
    evidence = SqlEvidence.model_validate(SAMPLES["valid"][0])
    options = {
        "batch": {
            "expected_batch_ref": "gold-csv-v2:GOLD_20000101T000000Z_bbbbbbbb:"
            "12345678-1234-4123-8123-123456789abc",
        },
        "context": {"expected_context_version": "c" * 64},
        "metric": {"allowed_metric_ids": frozenset()},
        "municipality": {"allowed_dimension_ids": frozenset({"customer.consumption_class"})},
    }[change]

    with pytest.raises(EvidenceContractInvalid):
        _validate(evidence, **options)


def test_guard_revalidates_mutated_evidence_digest():
    evidence = SqlEvidence.model_validate(SAMPLES["valid"][0])
    mutated = evidence.model_copy(update={"rows": (("999.00",),)})

    with pytest.raises(EvidenceContractInvalid):
        _validate(mutated)
