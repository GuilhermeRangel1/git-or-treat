"""Revalidação do plano recebido, com vetores também exercitados pela GenAI."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from app.services.genai_client import GenAIResponseInvalid
from app.services.genai_plan import validate_genai_plan

VECTORS = json.loads(
    (
        Path(__file__).parents[2] / "docs/contracts/examples/genai-plan-fingerprints-v1.json"
    ).read_text(encoding="utf-8")
)["vectors"]


@pytest.mark.parametrize("vector", VECTORS, ids=lambda vector: vector["id"])
def test_backend_validates_common_genai_vectors(vector):
    plan = validate_genai_plan(vector["plan"], vector["fingerprint"])

    assert plan.fingerprint() == vector["fingerprint"]
    # Confere inclusive defaults, nulos, datas, Unicode e tipos escalares.
    assert plan.model_dump(mode="json") == json.loads(vector["canonical_json"])


def test_key_order_does_not_change_fingerprint():
    vector = VECTORS[0]
    payload = dict(reversed(list(vector["plan"].items())))
    payload["window"] = dict(reversed(list(payload["window"].items())))

    assert (
        validate_genai_plan(payload, vector["fingerprint"]).fingerprint() == vector["fingerprint"]
    )


def test_defaults_and_nulls_are_included_before_hashing():
    vector = VECTORS[1]
    explicit = json.loads(vector["canonical_json"])

    assert validate_genai_plan(explicit, vector["fingerprint"]) == validate_genai_plan(
        vector["plan"], vector["fingerprint"]
    )
    assert explicit["order"] is None
    assert explicit["window"]["phrase"] is None


@pytest.mark.parametrize("field", ["dimension_ids", "group_by_dimension_ids", "filters", "values"])
def test_list_order_is_part_of_fingerprint(field):
    vector = VECTORS[2]
    changed = deepcopy(vector["plan"])
    if field == "values":
        changed["filters"][0]["values"].reverse()
    else:
        changed[field].reverse()

    with pytest.raises(GenAIResponseInvalid):
        validate_genai_plan(changed, vector["fingerprint"])


@pytest.mark.parametrize(
    "overrides",
    [
        {"limit": 99},
        {"metric_id": "outra_metrica"},
        {"source_id": "outra.fonte"},
        {"unit": "MWh"},
        {
            "window": {
                "kind": "bounded",
                "start": "2025-04-01",
                "end": "2025-04-30",
                "granularity": "month",
            }
        },
    ],
)
def test_changed_plan_is_rejected_with_previous_fingerprint(overrides):
    vector = VECTORS[0]
    with pytest.raises(GenAIResponseInvalid):
        validate_genai_plan({**vector["plan"], **overrides}, vector["fingerprint"])


@pytest.mark.parametrize("fingerprint", ["0" * 64, "A" * 64, "abc", None, 123, "a" * 65])
def test_missing_malformed_or_different_fingerprint_is_rejected(fingerprint):
    with pytest.raises(GenAIResponseInvalid):
        validate_genai_plan(VECTORS[0]["plan"], fingerprint)


@pytest.mark.parametrize(
    "overrides",
    [
        {"contract_version": "v2"},
        {"catalog_version": "v2"},
        {"operation": "write"},
        {"sql": "SELECT 1"},
        {"limit": True},
        {"limit": "100"},
        {"limit": 0},
        {"limit": 101},
        {"dimension_ids": ["municipio", "municipio"]},
        {"group_by_dimension_ids": ["classe"]},
        {"order": {"field_id": "classe", "direction": "desc"}},
        {"filters": [{"dimension_id": "classe", "operator": "eq", "values": ["x"]}]},
        {"filters": [{"dimension_id": "municipio", "operator": "eq", "values": ["x", "y"]}]},
        {
            "window": {
                "kind": "bounded",
                "start": "2025-04-01",
                "end": "2025-03-01",
                "granularity": "month",
            }
        },
    ],
)
def test_invalid_plan_is_rejected_even_with_its_raw_json_hash(overrides):
    payload = {**VECTORS[0]["plan"], **overrides}
    raw_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    with pytest.raises(GenAIResponseInvalid):
        validate_genai_plan(payload, raw_hash)


@pytest.mark.parametrize("vector", [VECTORS[1], VECTORS[2]], ids=lambda vector: vector["id"])
def test_raw_json_hash_does_not_replace_canonical_validated_hash(vector):
    raw_hash = hashlib.sha256(
        json.dumps(vector["plan"], sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    with pytest.raises(GenAIResponseInvalid):
        validate_genai_plan(vector["plan"], raw_hash)


@pytest.mark.parametrize("index,value", [(2, 2.0), (3, "1.5"), (4, 1)])
def test_filter_scalar_types_are_part_of_fingerprint(index, value):
    vector = VECTORS[2]
    payload = deepcopy(vector["plan"])
    payload["filters"][index]["values"] = [value]
    with pytest.raises(GenAIResponseInvalid):
        validate_genai_plan(payload, vector["fingerprint"])


@pytest.mark.parametrize("payload", [None, [], "plano"])
def test_non_object_plan_is_rejected(payload):
    with pytest.raises(GenAIResponseInvalid):
        validate_genai_plan(payload, VECTORS[0]["fingerprint"])
