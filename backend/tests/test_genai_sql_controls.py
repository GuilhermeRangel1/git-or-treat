import pytest

from app.schemas.sql_generation import SqlInterpretation
from app.services.gold_domain_controls import ANALYTICAL_CONTROLS
from app.schemas.genai_internal import QuestionPlanRequest
from app.services.genai_sql_context import build_sql_generation_context, requested_sql_metric_id
from app.services.genai_sql_observation import _explicit_control_count_candidate
from app.services.genai_sql_semantics import review_sql_semantics
from app.services.genai_sql_structure import SqlStructureRejected


def test_c05_c06_c07_are_in_the_approved_analytical_control_contract():
    assert {"C05", "C06", "C07"} <= ANALYTICAL_CONTROLS


def test_question_about_units_by_class_resolves_to_a_distinct_metric():
    assert requested_sql_metric_id("Quantas UCs há por classe de consumo?") == (
        "customer.units_by_class"
    )


def test_question_about_inspection_priorities_resolves_to_a_distinct_metric():
    assert requested_sql_metric_id("Quantas UCs há em cada prioridade de inspeção?") == (
        "inspection.units_by_priority"
    )


def test_everyday_phrasing_resolves_specific_class_and_zero_consumption():
    assert requested_sql_metric_id("Quantas UCs residenciais?") == (
        "customer.units_by_class"
    )
    assert requested_sql_metric_id("Quantas UCs tiveram consumo zero?") == (
        "inspection.units_by_priority"
    )


def test_priority_query_contract_supports_grouped_snapshot_and_zero_filter():
    candidate = SqlInterpretation.model_validate(
        {
            "metric_id": "inspection.units_by_priority",
            "operation": "snapshot_total",
            "aggregation": "count_distinct",
            "periods": [],
            "filters": [],
            "group_by": ["inspection_priority"],
            "ranking_direction": None,
            "ranking_limit": None,
        }
    )
    assert candidate.group_by == ("inspection_priority",)


def test_priority_zero_count_can_be_queried_as_snapshot_total():
    candidate = SqlInterpretation.model_validate(
        {
            "metric_id": "inspection.units_by_priority",
            "operation": "snapshot_total",
            "aggregation": "count_distinct",
            "periods": [],
            "filters": [
                {
                    "dimension_id": "inspection.priority",
                    "operator": "eq",
                    "values": ["ALTA - CONSUMO ZERO"],
                }
            ],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        }
    )
    assert candidate.filters[0].values == ("ALTA - CONSUMO ZERO",)


def _request(question, metric, dimension, values):
    return QuestionPlanRequest.model_validate({
        "question": question,
        "context": [],
        "remaining_timeout_ms": 30000,
        "batch_ref": "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "access_scope": {
            "caller_ref": "session:" + "a" * 64,
            "profile_id": "v-energy-grid-360-gold",
            "source_id": "gold.local",
            "allowed_operations": ["read"],
            "allowed_metric_ids": [metric],
            "allowed_dimension_ids": [dimension],
        },
        "temporal_coverage": [{"metric_id": metric, "kind": "none", "competencies": []}],
        "dimension_value_coverage": [{"dimension_id": dimension, "values": values}],
    })


def test_c05_query_is_compiled_and_semantically_verified_by_class():
    request = _request(
        "Quantas UCs há por classe de consumo?",
        "customer.units_by_class",
        "customer.consumption_class",
        ["COMERCIAL", "INDUSTRIAL", "PODER PUBLICO", "RESIDENCIAL", "RURAL"],
    )
    context = build_sql_generation_context(request)
    candidate = _explicit_control_count_candidate(request, context)
    assert candidate is not None
    reviewed = review_sql_semantics(candidate, request)
    assert "GROUP BY classe" in reviewed.canonical_sql
    assert "COUNT(DISTINCT id_uc)" in reviewed.canonical_sql


def test_c05_grouped_output_may_be_ordered_by_its_dimension():
    request = _request(
        "Quantas UCs há por classe de consumo?",
        "customer.units_by_class",
        "customer.consumption_class",
        ["COMERCIAL", "INDUSTRIAL", "PODER PUBLICO", "RESIDENCIAL", "RURAL"],
    )
    context = build_sql_generation_context(request)
    candidate = _explicit_control_count_candidate(request, context)
    ordered = candidate.model_copy(
        update={"sql": candidate.sql + " ORDER BY consumption_class"}
    )
    assert review_sql_semantics(ordered, request).canonical_sql.endswith(
        "ORDER BY consumption_class"
    )


def test_c06_and_c07_query_is_compiled_from_published_priority_vocabulary():
    request = _request(
        "Quantas UCs estão na prioridade alta consumo zero?",
        "inspection.units_by_priority",
        "inspection.priority",
        [
            "ALTA - HISTORICO IRREGULAR", "ALTA - CONSUMO ZERO", "BAIXA",
            "MEDIA - NUNCA INSPECIONADO", "REVISAR - SEM HISTORICO DE CONSUMO",
        ],
    )
    context = build_sql_generation_context(request)
    candidate = _explicit_control_count_candidate(request, context)
    assert candidate is not None
    reviewed = review_sql_semantics(candidate, request)
    assert 'prioridade_inspecao = %(control_value)s' in reviewed.canonical_sql
    assert reviewed.parameter_items == (("control_value", "ALTA - CONSUMO ZERO"),)


def test_c06_grouped_query_uses_priority_not_inspection_events_or_rank():
    request = _request(
        "Quantas UCs há em cada prioridade de inspeção?",
        "inspection.units_by_priority",
        "inspection.priority",
        ["ALTA - HISTORICO IRREGULAR", "BAIXA", "MEDIA - NUNCA INSPECIONADO"],
    )
    context = build_sql_generation_context(request)
    candidate = _explicit_control_count_candidate(request, context)
    assert candidate is not None
    assert candidate.interpretation.group_by == ("inspection_priority",)
    reviewed = review_sql_semantics(candidate, request)
    assert "GROUP BY prioridade_inspecao" in reviewed.canonical_sql


def test_c07_can_return_zero_when_category_is_not_observed_in_the_lot():
    request = _request(
        "Quantas UCs tiveram consumo zero?",
        "inspection.units_by_priority",
        "inspection.priority",
        [
            "ALTA - HISTORICO IRREGULAR", "BAIXA",
            "MEDIA - NUNCA INSPECIONADO", "REVISAR - SEM HISTORICO DE CONSUMO",
        ],
    )
    context = build_sql_generation_context(request)
    candidate = _explicit_control_count_candidate(request, context)
    assert candidate is not None
    reviewed = review_sql_semantics(candidate, request)
    assert "prioridade_inspecao = %(control_value)s" in reviewed.canonical_sql
    assert reviewed.parameter_items == (("control_value", "ALTA - CONSUMO ZERO"),)


def test_c07_question_cannot_be_answered_with_the_no_history_category():
    request = _request(
        "Quantas UCs tiveram consumo zero?",
        "inspection.units_by_priority",
        "inspection.priority",
        ["BAIXA", "REVISAR - SEM HISTORICO DE CONSUMO"],
    )
    context = build_sql_generation_context(request)
    assert "ALTA - CONSUMO ZERO" in context.contents
    candidate = _explicit_control_count_candidate(request, context)
    assert candidate is not None
    invalid_payload = candidate.model_dump(mode="json")
    invalid_payload["parameters"]["control_value"]["value"] = (
        "REVISAR - SEM HISTORICO DE CONSUMO"
    )
    invalid_payload["interpretation"]["filters"] = [{
        "dimension_id": "inspection.priority",
        "operator": "eq",
        "values": ["REVISAR - SEM HISTORICO DE CONSUMO"],
    }]
    invalid = type(candidate).model_validate(invalid_payload)
    with pytest.raises(SqlStructureRejected, match="Consumo zero exige"):
        review_sql_semantics(invalid, request)
