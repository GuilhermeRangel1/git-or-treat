"""Vetores v1 compartilhados com o Backend, sem importar código desse serviço."""

import json
import re
from pathlib import Path

import pytest

from app.schemas.read_plan import LogicalReadPlan

CONTRACTS = Path(__file__).parents[2] / "docs/contracts"
VECTORS = json.loads(
    (CONTRACTS / "examples/genai-plan-fingerprints-v1.json").read_text(encoding="utf-8")
)["vectors"]


@pytest.mark.parametrize("vector", VECTORS, ids=lambda vector: vector["id"])
def test_genai_fingerprint_matches_shared_backend_vector(vector):
    plan = LogicalReadPlan.model_validate(vector["plan"])

    assert plan.fingerprint() == vector["fingerprint"]
    assert (
        json.dumps(plan.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        == vector["canonical_json"]
    )


def test_shared_ready_vector_is_the_existing_contract_example():
    text = (CONTRACTS / "genai-query-execution.md").read_text(encoding="utf-8")
    section = text.split("### Válido — plano pronto (planejar)", 1)[1]
    envelope = json.loads(re.search(r"```json\n(.*?)\n```", section, re.DOTALL).group(1))

    assert VECTORS[0]["plan"] == envelope["plan"]
    assert VECTORS[0]["fingerprint"] == envelope["plan_fingerprint"]


def test_contract_scope_and_shared_plans_use_agreed_gold_identity():
    text = (CONTRACTS / "genai-query-execution.md").read_text(encoding="utf-8")
    section = text.split("### Requisição (proposta: `QuestionPlanRequest`)", 1)[1]
    envelope = json.loads(re.search(r"```json\n(.*?)\n```", section, re.DOTALL).group(1))
    scope = envelope["access_scope"]

    assert scope["source_id"] == "gold.local"
    assert scope["profile_id"] == "v-energy-grid-360-gold"
    assert all(
        (vector["plan"]["source_id"], vector["plan"]["profile_id"])
        == (scope["source_id"], scope["profile_id"])
        for vector in VECTORS
    )
