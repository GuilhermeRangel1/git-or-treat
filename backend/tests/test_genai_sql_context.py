import json

import pytest

from app.schemas.genai_internal import QuestionPlanRequest
from app.services.genai_sql_context import (
    SqlContextUnavailable,
    build_sql_generation_context,
)


def request_payload():
    return {
        "question": "Qual foi o faturamento de Recife em junho de 2026?",
        "context": [], "remaining_timeout_ms": 30000,
        "batch_ref": "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "access_scope": {
            "caller_ref": "session:" + "a" * 64,
            "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
            "allowed_operations": ["read"],
            "allowed_metric_ids": ["billing.revenue", "energy.consumption"],
            "allowed_dimension_ids": ["geography.municipality", "customer.consumption_class",
                                      "customer.consumer_unit"],
        },
        "temporal_coverage": [
            {"metric_id": "billing.revenue", "kind": "monthly", "competencies": ["2026-06"]}
        ],
        "dimension_value_coverage": [
            {"dimension_id": "geography.municipality", "values": ["Recife"]}
        ],
    }


def build(payload):
    return build_sql_generation_context(QuestionPlanRequest.model_validate(payload))


def test_context_contains_only_authorized_f1_schema_not_other_gold_sources():
    context = build(request_payload())
    body = json.loads(context.contents)
    assert body["source"]["table"] == "diagnostico_receita"
    assert set(body["source"]["columns"]) == {
        "competencia", "receita_total_reais", "municipio", "classe_consumo",
    }
    assert "consumer_unit" not in context.contents
    assert "energy.consumption" not in context.contents
    assert "a" * 64 not in context.contents
    assert body["metric"]["aggregation"] == "sum"
    assert body["rules"]["annual_requires_all_months"] is True
    assert body["schema_basis"].endswith("not_live_database")
    assert body["context_version"] == context.context_version


def test_dimension_revocation_removes_column_and_values_and_changes_version():
    payload = request_payload()
    previous = build(payload)
    payload["access_scope"]["allowed_dimension_ids"] = ["customer.consumption_class"]
    payload["dimension_value_coverage"] = []
    current = build(payload)
    body = json.loads(current.contents)
    assert "municipio" not in body["source"]["columns"]
    assert "geography.municipality" not in body["dimensions"]
    assert body["dimension_values"] == []
    assert current.context_version != previous.context_version


@pytest.mark.parametrize("change", ["caller", "coverage", "question", "scope"])
def test_context_digest_binds_request_and_scope(change):
    payload = request_payload()
    previous = build(payload)
    if change == "caller":
        payload["access_scope"]["caller_ref"] = "session:" + "b" * 64
    elif change == "coverage":
        payload["temporal_coverage"][0]["competencies"] = ["2026-05", "2026-06"]
    elif change == "question":
        payload["question"] = "Qual foi o faturamento em Olinda?"
    else:
        payload["access_scope"]["allowed_metric_ids"] = ["billing.revenue"]
    assert build(payload).context_version != previous.context_version


def test_context_digest_is_repeatable_for_set_order_and_budget_change():
    payload = request_payload()
    previous = build(payload)
    payload["access_scope"]["allowed_dimension_ids"].reverse()
    payload["access_scope"]["allowed_metric_ids"].reverse()
    payload["remaining_timeout_ms"] = 20000
    assert build(payload) == previous


def test_context_includes_resolved_turns_and_versions_them_into_digest():
    payload = request_payload()
    payload["context"] = [{
        "role": "user",
        "content": "E no mês anterior, mantendo Recife?",
    }]
    previous = build(payload)
    body = json.loads(previous.contents)
    assert body["context"] == payload["context"]

    payload["context"][0]["content"] = "E no mês seguinte, mantendo Recife?"
    current = build(payload)
    assert current.context_version != previous.context_version


def test_context_refuses_absent_metric_and_empty_coverage():
    payload = request_payload()
    payload["access_scope"]["allowed_metric_ids"] = []
    payload["temporal_coverage"] = []
    with pytest.raises(SqlContextUnavailable):
        build(payload)
    payload = request_payload()
    payload["temporal_coverage"][0]["competencies"] = []
    with pytest.raises(SqlContextUnavailable):
        build(payload)


@pytest.mark.parametrize("caller_ref", ["caller", "user:" + "a" * 64,
                                        "session:" + "z" * 64])
def test_context_requires_backend_session_pseudonym(caller_ref):
    payload = request_payload()
    payload["access_scope"]["caller_ref"] = caller_ref
    with pytest.raises(SqlContextUnavailable, match="Escopo"):
        build(payload)


def test_context_never_silently_truncates_large_essential_context():
    payload = request_payload()
    payload["dimension_value_coverage"] = [{
        "dimension_id": "geography.municipality",
        "values": [f"Municipio{i:04}" + "x" * 100 for i in range(700)],
    }]
    with pytest.raises(SqlContextUnavailable, match="limite"):
        build(payload)
