import asyncio
from dataclasses import replace
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.sql_evidence import SqlEvidence, sql_evidence_digest
from app.services.genai_client import GenAITimeout
from app.services.genai_sql_admission import SqlAdmissionDenied
from app.services.genai_sql_evidence import build_sql_evidence
from app.services.genai_sql_presentation import present_sql_evidence
from app.services.genai_sql_executor import execute_sql_admission
from tests.test_genai_sql_comparison import comparison, grouped_comparison
from tests.test_genai_sql_executor import environment
from tests.test_genai_sql_result import Cursor
from tests.test_genai_sql_semantics import accumulated_attendance_query, query, ranking
from tests.test_genai_sql_structure import sql_request as fixture_sql_request

sql_request = fixture_sql_request


def evidence_case(request, mode="total", rows=None):
    if mode == "accumulated":
        candidate, request = accumulated_attendance_query(request)
        default, columns = [(Decimal("42"),)], ("attendance",)
    elif mode in {"comparison", "grouped_comparison"}:
        request, candidate = (
            grouped_comparison(request) if mode == "grouped_comparison"
            else comparison(request)
        )
        default = [(Decimal("150.03"), Decimal("80.00"), Decimal("70.03"))]
        columns = ("a", "b", "delta")
        if mode == "grouped_comparison":
            default = [("Recife", *default[0])]
            columns = ("municipality", *columns)
    elif mode == "ranking":
        candidate = ranking(request)
        default, columns = [("Recife", Decimal("150.03"))], ("city", "revenue")
    else:
        candidate = query(request)
        default, columns = [(Decimal("150.03"),)], ("revenue",)
    env, connection = environment(request)
    connection.cursor = Cursor(default if rows is None else rows, columns)
    admitted = env.admit(candidate)
    executed = asyncio.run(execute_sql_admission(admitted, candidate, request, **env.kwargs()))
    return env, candidate, admitted, executed


def build(case):
    env, candidate, admitted, executed = case
    return build_sql_evidence(executed, admitted, candidate, env.request,
                              resolve_scope=lambda: env.scope, deadline=env.deadline)


@pytest.mark.parametrize("mode", ["total", "comparison", "ranking"])
def test_execution_becomes_exact_evidence_without_legacy_plan(sql_request, mode):
    evidence = build(evidence_case(sql_request, mode))
    assert evidence.status == "available"
    assert "150.03" in evidence.rows[0]
    assert SqlEvidence.model_validate_json(evidence.model_dump_json()) == evidence
    assert "sql" not in SqlEvidence.model_fields and "plan" not in SqlEvidence.model_fields
    if mode == "ranking":
        assert evidence.dimension_semantics == {"city": "municipality"}
    if mode == "comparison":
        assert evidence.measure_semantics == {"a": "period_0_total", "b": "period_1_total",
                                              "delta": "period_0_minus_period_1",
                                              "period_0_growth_percent": "period_0_growth_percent"}
        assert evidence.evidence_contract_version == "text-to-sql-f1-evidence-v2"
        assert evidence.columns[-1].unit == "%"
        assert evidence.rows[0][-1] == "87.54"


def test_accumulated_attendance_evidence_preserves_unknown_history_window(sql_request):
    evidence = build(evidence_case(sql_request, mode="accumulated"))
    presentation = present_sql_evidence(evidence)
    assert evidence.source_table == "gold_v2.visao_360_uc"
    assert evidence.metric_id == "service.accumulated_attendance"
    assert evidence.evidence_contract_version == "text-to-sql-f1-evidence-v6"
    assert evidence.interpretation.periods == ()
    assert evidence.rows == (("42",),)
    assert presentation.period == "Histórico acumulado"
    assert "intervalo nem certifica a completude histórica" in presentation.answer
    assert "sem intervalo conhecido" in presentation.limitations[0]


def test_grouped_comparison_derives_percentage_for_each_gold_group(sql_request):
    evidence = build(evidence_case(
        sql_request,
        mode="grouped_comparison",
        rows=[
            ("Recife", Decimal("150.03"), Decimal("80.00"), Decimal("70.03")),
            ("Olinda", Decimal("180.00"), Decimal("0.00"), Decimal("180.00")),
        ],
    ))

    assert evidence.dimension_semantics == {"municipality": "municipality"}
    assert evidence.rows == (
        ("Recife", "150.03", "80.00", "70.03", "87.54"),
        ("Olinda", "180.00", "0.00", "180.00", None),
    )


@pytest.mark.parametrize("current,baseline,expected", [
    (Decimal("80.00"), Decimal("0.00"), None),
    (Decimal("80.00"), Decimal("-10.00"), None),
    (Decimal("80.00"), Decimal("40.00"), "100.00"),
    (None, Decimal("40.00"), None),
])
def test_comparison_growth_requires_positive_available_baseline(
    sql_request, current, baseline, expected,
):
    evidence = build(evidence_case(
        sql_request,
        mode="comparison",
        rows=[(current, baseline, None if current is None else current - baseline)],
    ))

    assert evidence.rows[0][-1] == expected


@pytest.mark.parametrize("rows,status,value", [
    ([], "empty", None), ([(None,)], "all_measures_null", None),
    ([(Decimal("0.00"),)], "available", "0.00"),
    ([(Decimal("-12345678901234567890.01"),)], "available", "-12345678901234567890.01"),
])
def test_evidence_preserves_numeric_states(sql_request, rows, status, value):
    evidence = build(evidence_case(sql_request, rows=rows))
    assert evidence.status == status
    if evidence.rows:
        assert evidence.rows[0][0] == value


def test_changed_executed_values_invalidate_execution_digest(sql_request):
    env, candidate, admitted, executed = evidence_case(sql_request)
    tampered = replace(executed, result=replace(executed.result, rows=((Decimal("999.00"),),)))
    with pytest.raises(SqlAdmissionDenied):
        build((env, candidate, admitted, tampered))


def test_changed_scope_prevents_evidence_disclosure(sql_request):
    case = evidence_case(sql_request)
    env = case[0]
    env.scope = env.scope.model_copy(update={"allowed_metric_ids": frozenset()})
    with pytest.raises(SqlAdmissionDenied):
        build(case)


def test_expired_result_cannot_become_current_evidence(sql_request):
    case = evidence_case(sql_request)
    case[0].now[0] = 21
    with pytest.raises((SqlAdmissionDenied, GenAITimeout)):
        build(case)


@pytest.mark.parametrize("mutation", [
    {"rows": [[1.23]]}, {"rows": [["NaN"]]}, {"rows": [["1e3"]]},
    {"rows": [["private-value"]]}, {"status": "empty"}, {"sql": "SELECT private"},
    {"measure_semantics": {"revenue": "period_0_total"}},
    {"dimension_semantics": {"invented": "municipality"}},
])
def test_evidence_contract_rejects_invalid_content_even_with_new_hash(sql_request, mutation):
    payload = build(evidence_case(sql_request)).model_dump(mode="json")
    payload.update(mutation)
    payload["evidence_digest"] = sql_evidence_digest({
        key: value for key, value in payload.items() if key != "evidence_digest"})
    with pytest.raises(ValidationError):
        SqlEvidence.model_validate(payload)


def test_changed_evidence_content_requires_new_digest(sql_request):
    payload = build(evidence_case(sql_request)).model_dump(mode="json")
    payload["rows"] = [["999.00"]]
    with pytest.raises(ValidationError, match="digest"):
        SqlEvidence.model_validate(payload)
