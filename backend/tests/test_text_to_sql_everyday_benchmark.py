"""Bateria cotidiana no contrato Text-to-SQL F1, sem chamada ao provedor.

Os 578 rótulos são uma tradução inicial das expectativas anotadas nos testes
legados para o escopo F1. Os testes exercitam o novo contexto, contrato,
admissão semântica e execução sintética; não medem entendimento do Gemini.
"""

import json
from calendar import monthrange
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from app.schemas.genai_internal import QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationCandidate
from app.services.genai_sql_context import (
    build_sql_generation_context,
    requested_sql_metric_id,
)
from app.services.genai_sql_semantics import review_sql_semantics
from app.services.genai_sql_structure import SqlStructureRejected

ROOT = Path(__file__).resolve().parents[2]
CORPUS = json.loads(
    (ROOT / "ai-agent/tests/fixtures/text_to_sql_everyday_language.json")
    .read_text(encoding="utf-8")
)
CASES = CORPUS["cases"]
MONTHS = [
    f"{year:04d}-{month:02d}"
    for year in range(2024, 2027)
    for month in range(1, 13)
    if (year, month) <= (2026, 6)
]
MUNICIPALITIES = ["Jaboatão dos Guararapes", "Olinda", "Recife"]
CLASSES = ["COMERCIAL", "INDUSTRIAL", "PODER PUBLICO", "RESIDENCIAL", "RURAL"]
DIMENSIONS = {
    "municipality": ("geography.municipality", "municipio"),
    "consumption_class": ("customer.consumption_class", "classe_consumo"),
}


def _request(case):
    turns = [SimpleNamespace(**turn) for turn in case["context"]]
    metric = requested_sql_metric_id(case["question"], turns)
    return QuestionPlanRequest.model_validate({
        "question": case["question"],
        "context": case["context"],
        "remaining_timeout_ms": 30000,
        "batch_ref": (
            "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:"
            "12345678-1234-4123-8123-123456789abc"
        ),
        "access_scope": {
            "caller_ref": "session:" + "a" * 64,
            "profile_id": "v-energy-grid-360-gold",
            "source_id": "gold.local",
            "allowed_operations": ["read"],
            "allowed_metric_ids": [metric],
            "allowed_dimension_ids": [
                "geography.municipality", "customer.consumption_class",
                "geography.neighborhood", "network.feeder",
            ],
        },
        "temporal_coverage": [{
            "metric_id": metric,
            "kind": "none" if metric in {
                "service.accumulated_attendance", "service.accumulated_satisfaction",
                "energy.gd_units", "energy.gd_consumption_drop",
            } else "monthly",
            **({} if metric in {
                "service.accumulated_attendance", "service.accumulated_satisfaction",
                "energy.gd_units", "energy.gd_consumption_drop",
            } else {"competencies": MONTHS}),
        }],
        "dimension_value_coverage": [
            {"dimension_id": "geography.municipality", "values": MUNICIPALITIES},
            {"dimension_id": "customer.consumption_class", "values": CLASSES},
        ],
    })


def _period_date(value, *, end=False):
    year, month = map(int, value.split("-"))
    day = monthrange(year, month)[1] if end else 1
    return date(year, month, day)


def _make_candidate(case, context_version):
    expected = case["expected_f1"]
    turns = [SimpleNamespace(**turn) for turn in case["context"]]
    metric = requested_sql_metric_id(case["question"], turns)
    generation_version = {
        "energy.consumption": "text-to-sql-f1-v2",
        "service.attendance": "text-to-sql-f1-v3",
        "service.satisfaction": "text-to-sql-f1-v7",
        "service.accumulated_attendance": "text-to-sql-f1-v5",
        "service.accumulated_satisfaction": "text-to-sql-f1-v9",
        "energy.gd_units": "text-to-sql-f1-v8",
        "energy.gd_consumption_drop": "text-to-sql-f1-v10",
        "energy.average_consumption_per_uc": "text-to-sql-f1-v11",
        "billing.average_ticket": "text-to-sql-f1-v13",
        "billing.effective_tariff": "text-to-sql-f1-v13",
        "network.equivalent_interruption_duration": "text-to-sql-f1-v4",
        "network.equivalent_interruption_frequency": "text-to-sql-f1-v4",
        "billing.effective_tariff": "text-to-sql-f1-v13",
    }.get(metric, "text-to-sql-f1-v1")
    common = {
        "generation_contract_version": generation_version,
        "context_version": context_version,
        "status": expected["status"],
    }
    if expected["status"] == "needs_clarification":
        return SqlGenerationCandidate.model_validate({
            **common,
            "clarification": {
                "question": "Qual indicador você quer consultar?",
                "missing_fields": expected["missing_fields"],
            },
        })
    if expected["status"] == "unsupported":
        return SqlGenerationCandidate.model_validate({
            **common,
            "unsupported_reason": {
                "code": expected["reason_code"],
                "message": "A métrica ou operação pedida não está disponível na F1.",
            },
        })

    parameters = {}
    predicates = []
    for index, (start, end) in enumerate(expected["periods"]):
        parameters[f"period{index}_start"] = {"type": "string", "value": start}
        parameters[f"period{index}_end"] = {"type": "string", "value": end}
        predicates.append(
            f"competencia BETWEEN :period{index}_start AND :period{index}_end"
        )

    filters = []
    for filter_index, (dimension_id, values) in enumerate(expected["filters"].items()):
        name = "municipality" if dimension_id == "geography.municipality" else "consumption_class"
        physical_column = DIMENSIONS[name][1]
        parameter_names = []
        for value_index, value in enumerate(values):
            parameter = f"filter{filter_index}_value{value_index}"
            parameter_names.append(f":{parameter}")
            parameters[parameter] = {"type": "string", "value": value}
        predicate = (
            f"{physical_column} = {parameter_names[0]}"
            if len(parameter_names) == 1
            else f"{physical_column} IN ({', '.join(parameter_names)})"
        )
        predicates.append(predicate)
        filters.append({
            "dimension_id": dimension_id,
            "operator": "eq" if len(values) == 1 else "in",
            "values": values,
        })

    group_by = expected["group_by"]
    projections = []
    result_columns = []
    for dimension in group_by:
        _, physical_column = DIMENSIONS[dimension]
        projections.append(f"{physical_column} AS {dimension}")
        result_columns.append({
            "name": dimension, "role": "dimension", "value_type": "string",
        })
    projections.append("SUM(receita_total_reais) AS revenue")
    result_columns.append({
        "name": "revenue", "role": "measure", "value_type": "decimal", "unit": "R$",
    })
    sql = (
        "SELECT " + ", ".join(projections)
        + " FROM gold_v2.diagnostico_receita WHERE "
        + " AND ".join(f"({item})" for item in predicates)
    )
    if group_by:
        physical_groups = [DIMENSIONS[item][1] for item in group_by]
        sql += " GROUP BY " + ", ".join(physical_groups)
        if expected["operation"] == "ranking":
            dimension = group_by[0]
            sql += f" ORDER BY revenue DESC NULLS LAST, {dimension} ASC"
            sql += f" LIMIT {expected['ranking_limit']}"
        else:
            sql += " ORDER BY " + ", ".join(group_by)

    interpretation = {
        "metric_id": "billing.revenue",
        "operation": expected["operation"],
        "aggregation": "sum",
        "periods": [{
            "start": _period_date(start).isoformat(),
            "end": _period_date(end, end=True).isoformat(),
        } for start, end in expected["periods"]],
        "filters": filters,
        "group_by": group_by,
        "ranking_direction": expected["ranking_direction"],
        "ranking_limit": expected["ranking_limit"],
    }
    return SqlGenerationCandidate.model_validate({
        **common, "sql": sql, "parameters": parameters,
        "interpretation": interpretation, "result_columns": result_columns,
    })


def _synthetic_rows():
    rows = []
    for month_index, month in enumerate(MONTHS, start=1):
        for city_index, municipality in enumerate(MUNICIPALITIES, start=1):
            for class_index, consumption_class in enumerate(CLASSES, start=1):
                revenue = 1000 + month_index * 17 + city_index * 101 + class_index * 13
                rows.append({
                    "competencia": month,
                    "municipio": municipality,
                    "classe_consumo": consumption_class,
                    "receita_total_reais": revenue,
                })
    return rows


@pytest.fixture(scope="session")
def synthetic_gold():
    """Banco SQLite em memória; apenas dados artificiais, sem Gold publicada."""
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS gold_v2")
        connection.exec_driver_sql("""
            CREATE TABLE gold_v2.diagnostico_receita (
                competencia TEXT NOT NULL,
                municipio TEXT NOT NULL,
                classe_consumo TEXT NOT NULL,
                receita_total_reais NUMERIC NOT NULL
            )
        """)
        rows = _synthetic_rows()
        connection.execute(text("""
            INSERT INTO gold_v2.diagnostico_receita
                (competencia, municipio, classe_consumo, receita_total_reais)
            VALUES (:competencia, :municipio, :classe_consumo, :receita_total_reais)
        """), rows)
        yield connection, rows
    engine.dispose()


def _independent_reference(case, source_rows):
    expected = case["expected_f1"]
    filters = expected["filters"]
    start, end = (item for item in expected["periods"][0])
    selected = [
        row for row in source_rows
        if start <= row["competencia"] <= end
        and all(
            row[DIMENSIONS[
                "municipality" if dimension == "geography.municipality"
                else "consumption_class"
            ][1]] in values
            for dimension, values in filters.items()
        )
    ]
    grouped = {}
    if expected["group_by"]:
        dimension = expected["group_by"][0]
        physical = DIMENSIONS[dimension][1]
        for row in selected:
            grouped.setdefault(row[physical], Decimal(0))
            grouped[row[physical]] += Decimal(str(row["receita_total_reais"]))
        result = [
            {dimension: value, "revenue": amount}
            for value, amount in grouped.items()
        ]
        if expected["operation"] == "ranking":
            result.sort(key=lambda row: (-row["revenue"], row[dimension]))
            return result[:expected["ranking_limit"]]
        return sorted(result, key=lambda row: row[dimension])
    return [{
        "revenue": sum(
            (Decimal(str(row["receita_total_reais"])) for row in selected),
            Decimal(0),
        ) if selected else None,
    }]


def _normalize_results(rows):
    return [
        {
            key: Decimal(str(value)) if key == "revenue" and value is not None else value
            for key, value in row.items()
        }
        for row in rows
    ]


def _expected_difference(candidate, expected):
    status = candidate.status
    if status != expected["status"]:
        return ["status"]
    if status != "sql_candidate":
        return []
    intent = candidate.interpretation
    differences = []
    if intent.metric_id != expected["metric_id"]:
        differences.append("metric")
    if intent.operation != expected["operation"]:
        differences.append("operation")
    periods = [
        (item.start.strftime("%Y-%m"), item.end.strftime("%Y-%m"))
        for item in intent.periods
    ]
    if periods != [tuple(item) for item in expected["periods"]]:
        differences.append("periods")
    filters = {item.dimension_id: list(item.values) for item in intent.filters}
    if filters != expected["filters"]:
        differences.append("filters")
    if list(intent.group_by) != expected["group_by"]:
        differences.append("group_by")
    if (intent.ranking_direction, intent.ranking_limit) != (
        expected["ranking_direction"], expected["ranking_limit"],
    ):
        differences.append("ranking")
    return differences


def test_everyday_corpus_is_complete_and_explicit_about_its_oracle_limits():
    assert CORPUS["case_count"] == 578
    assert len(CASES) == 578
    assert len({case["id"] for case in CASES}) == 578
    assert all(
        case.get("source_file")
        and case.get("source_test")
        and isinstance(case.get("context"), list)
        for case in CASES
    )
    assert CORPUS["human_review_status"] == "pending"
    assert "parâmetros esperados declarados" in CORPUS["oracle_provenance"]
    assert "capturas reais do Gemini" in CORPUS["model_evaluation"]
    prompt_oracles = {}
    for case in CASES:
        prompt_context = (
            case["question"],
            json.dumps(case["context"], sort_keys=True, ensure_ascii=False),
        )
        oracle = json.dumps(
            {"expected_intent": case["expected_intent"], "expected_f1": case["expected_f1"]},
            sort_keys=True,
            ensure_ascii=False,
        )
        assert prompt_oracles.setdefault(prompt_context, oracle) == oracle
    assert sum(case["source_file"] == "test_conventional_language_matrix.py" for case in CASES) == 486
    assert sum(case["source_file"] == "test_gold_conventional_language_benchmark.py" for case in CASES) == 92
    assert sum(
        case["source_test"] == "test_everyday_billing_language_preserves_revenue_class_city_and_month"
        for case in CASES
    ) == 240
    assert sum(
        case["source_test"] == "test_everyday_consumption_language_preserves_measure_class_city_and_month"
        for case in CASES
    ) == 156
    assert sum(
        case["expected_f1"]["status"] == "sql_candidate" for case in CASES
    ) == 251
    assert sum(
        case["expected_f1"]["status"] == "unsupported" for case in CASES
    ) == 296
    assert sum(
        case["expected_f1"]["status"] == "needs_clarification" for case in CASES
    ) == 31
    assert all(case["question"].strip() and "expected_f1" in case for case in CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_f1_oracle_matches_the_full_expected_semantic_intent(case):
    intent = case["expected_intent"]
    expected = case["expected_f1"]
    assert set(intent) == {
        "metric_id", "concept", "unit", "periods", "filters", "group_by",
        "operation", "ranking_direction", "ranking_limit", "ambiguity",
    }
    assert all(start <= end for start, end in intent["periods"])
    assert all(values for values in intent["filters"].values())
    assert all("." in dimension for dimension in intent["filters"])
    assert all("." in dimension for dimension in intent["group_by"])

    ambiguity = intent["ambiguity"]
    metric = intent["metric_id"]
    operation = intent["operation"]
    if ambiguity is not None and "metric" in ambiguity.get("missing_fields", []):
        assert expected == {
            "status": "needs_clarification",
            "missing_fields": ambiguity["missing_fields"],
        }
    elif metric != "billing.revenue":
        assert expected["status"] == "unsupported"
        assert expected["reason_code"] == "metric_outside_f1"
        assert expected.get("intended_metric") == metric
    elif operation not in {"total", "grouped_total", "ranking", "monthly_series", "comparison"}:
        assert expected == {
            "status": "unsupported",
            "reason_code": "operation_outside_f1",
            "intended_metric": "billing.revenue",
        }
    else:
        assert expected["status"] == "sql_candidate"
        expected_groups = [
            "municipality" if item == "geography.municipality" else
            "consumption_class" if item == "customer.consumption_class" else item
            for item in intent["group_by"]
        ]
        assert expected["metric_id"] == metric
        assert expected["operation"] == operation
        assert expected["periods"] == intent["periods"]
        assert expected["filters"] == intent["filters"]
        assert expected["group_by"] == expected_groups
        assert expected["ranking_direction"] == intent["ranking_direction"]
        assert expected["ranking_limit"] == intent["ranking_limit"]


def test_everyday_volume_uses_context_and_keeps_energy_distinct_from_billing():
    by_question = {case["question"]: case for case in CASES}
    generic = by_question["Qual foi o volume em Recife em março de 2025?"]
    assert generic["expected_f1"]["status"] == "needs_clarification"
    assert generic["expected_intent"]["unit"] == "kWh"
    assert generic["expected_intent"]["ambiguity"]["alternatives"] == [
        "energy.consumption", "energy.billed",
    ]

    consumed = by_question["Quanto foi o volume consumido pelas casas em Recife em março de 2025?"]
    assert consumed["expected_intent"]["metric_id"] == "energy.consumption"
    assert consumed["expected_intent"]["unit"] == "kWh"
    assert consumed["expected_f1"]["status"] == "unsupported"

    billed = by_question["Qual foi o volume faturado em Recife em março de 2025?"]
    assert billed["expected_intent"]["concept"] == "billed_energy_volume"
    assert billed["expected_intent"]["unit"] == "kWh"
    assert billed["expected_f1"]["status"] == "needs_clarification"

    calls = by_question["Qual foi o volume de chamados abertos em março de 2025?"]
    assert calls["expected_intent"]["metric_id"] == "service.attendance"
    assert calls["expected_intent"]["unit"] == "protocolos"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_all_578_questions_use_new_context_and_f1_contract(case, synthetic_gold):
    request = _request(case)
    context = build_sql_generation_context(request)
    contents = json.loads(context.contents)
    assert contents["question"] == case["question"]
    assert contents["context"] == case["context"]
    turns = [SimpleNamespace(**turn) for turn in case["context"]]
    metric = requested_sql_metric_id(case["question"], turns)
    expected_version = {
        "energy.consumption": "text-to-sql-f1-v2",
        "service.attendance": "text-to-sql-f1-v3",
        "service.satisfaction": "text-to-sql-f1-v7",
        "service.accumulated_attendance": "text-to-sql-f1-v5",
        "service.accumulated_satisfaction": "text-to-sql-f1-v9",
        "energy.gd_units": "text-to-sql-f1-v8",
        "energy.gd_consumption_drop": "text-to-sql-f1-v10",
        "energy.average_consumption_per_uc": "text-to-sql-f1-v11",
        "billing.average_ticket": "text-to-sql-f1-v13",
        "billing.effective_tariff": "text-to-sql-f1-v13",
        "network.equivalent_interruption_duration": "text-to-sql-f1-v4",
        "network.equivalent_interruption_frequency": "text-to-sql-f1-v4",
        "billing.effective_tariff": "text-to-sql-f1-v13",
    }.get(metric, "text-to-sql-f1-v1")
    assert contents["generation_contract_version"] == expected_version
    assert contents["source"]["schema"] == "gold_v2"
    neighborhood_question = "bairro" in case["question"].casefold() or any(
        "bairro" in turn["content"].casefold() for turn in case["context"]
        if turn["role"] == "user"
    )
    expected_table = {
        "service.attendance": "atendimentos_uc",
        "service.satisfaction": "atendimentos_uc",
        "energy.gd_units": "variacao_consumo_uc",
        "energy.gd_consumption_drop": "variacao_consumo_uc",
        "network.equivalent_interruption_duration": "indicadores_dec_fec",
        "network.equivalent_interruption_frequency": "indicadores_dec_fec",
    }.get(
        metric,
        "consumo_receita_bairro"
        if metric in {"billing.revenue", "energy.consumption"}
        and neighborhood_question
        else "diagnostico_receita",
    )
    assert contents["source"]["table"] == expected_table
    assert set(context.column_names) == set(contents["source"]["columns"])
    assert set(contents["source"]["columns"]) == set(context.column_names)
    assert context.context_version == contents["context_version"]

    candidate = _make_candidate(case, context.context_version)
    expected = case["expected_f1"]
    assert _expected_difference(candidate, expected) == []

    if expected["status"] != "sql_candidate":
        assert candidate.sql is None
        assert candidate.interpretation is None
        assert candidate.parameters == {}
        assert candidate.result_columns == ()
        if expected["status"] == "needs_clarification":
            assert set(candidate.clarification.missing_fields) == set(expected["missing_fields"])
        else:
            assert candidate.unsupported_reason.code == expected["reason_code"]
        return

    reviewed = review_sql_semantics(candidate, request)
    connection, rows = synthetic_gold
    actual = [
        dict(row) for row in connection.execute(
            text(candidate.sql),
            {key: value.value for key, value in candidate.parameters.items()},
        ).mappings()
    ]
    reference = _independent_reference(case, rows)
    assert _normalize_results(actual) == reference, case["id"]
    assert "receita_total_reais" in reviewed.source_columns


@pytest.mark.parametrize(
    "case", [case for case in CASES if case["expected_f1"]["status"] == "sql_candidate"],
    ids=lambda case: case["id"],
)
def test_every_supported_case_rejects_a_temporal_parameter_drift(case):
    request = _request(case)
    context = build_sql_generation_context(request)
    candidate = _make_candidate(case, context.context_version)
    payload = candidate.model_dump(mode="json")
    payload["parameters"]["period0_start"]["value"] = "2099-01"
    drifted = SqlGenerationCandidate.model_validate(payload)
    with pytest.raises(SqlStructureRejected):
        review_sql_semantics(drifted, request)


@pytest.mark.parametrize(
    "case", [case for case in CASES if case["expected_f1"]["status"] == "sql_candidate"
             and case["expected_f1"]["filters"]],
    ids=lambda case: case["id"],
)
def test_every_filtered_case_rejects_a_filter_parameter_drift(case):
    request = _request(case)
    context = build_sql_generation_context(request)
    candidate = _make_candidate(case, context.context_version)
    payload = candidate.model_dump(mode="json")
    parameter = next(name for name in payload["parameters"] if name.startswith("filter"))
    payload["parameters"][parameter]["value"] = "Cidade Controle"
    drifted = SqlGenerationCandidate.model_validate(payload)
    with pytest.raises(SqlStructureRejected):
        review_sql_semantics(drifted, request)


@pytest.mark.parametrize(
    "case", [case for case in CASES if case["expected_f1"]["status"] == "sql_candidate"],
    ids=lambda case: case["id"],
)
def test_oracle_detects_wrong_but_internally_consistent_intent(case):
    request = _request(case)
    context = build_sql_generation_context(request)
    candidate = _make_candidate(case, context.context_version)
    payload = candidate.model_dump(mode="json")
    original = case["expected_f1"]
    if original["filters"]:
        dimension = next(iter(original["filters"]))
        value = original["filters"][dimension][0]
        candidates = MUNICIPALITIES if dimension == "geography.municipality" else CLASSES
        alternate = next(item for item in candidates if item != value)
        # Change both the declared interpretation and SQL parameter: semantically
        # valid SQL can still answer the wrong user question.
        filter_index = list(original["filters"]).index(dimension)
        parameter = f"filter{filter_index}_value0"
        payload["parameters"][parameter]["value"] = alternate
        for filter_item in payload["interpretation"]["filters"]:
            if filter_item["dimension_id"] == dimension:
                filter_item["values"] = [alternate]
        mutated = SqlGenerationCandidate.model_validate(payload)
        assert review_sql_semantics(mutated, request)
        assert _expected_difference(mutated, original) == ["filters"]
    else:
        original_start = original["periods"][0][0]
        alternate_month = "2024-02" if original_start == "2024-01" else "2024-01"
        payload["interpretation"]["periods"][0]["start"] = f"{alternate_month}-01"
        payload["interpretation"]["periods"][0]["end"] = (
            f"{alternate_month}-{monthrange(*map(int, alternate_month.split('-')))[1]:02d}"
        )
        payload["parameters"]["period0_start"]["value"] = alternate_month
        payload["parameters"]["period0_end"]["value"] = alternate_month
        mutated = SqlGenerationCandidate.model_validate(payload)
        assert review_sql_semantics(mutated, request)
        assert _expected_difference(mutated, original) == ["periods"]
