import json

import pytest

from app.schemas.genai_internal import QuestionPlanRequest
from app.services.genai_sql_context import (
    SqlContextUnavailable,
    build_sql_generation_context,
    is_explicit_multi_metric_question,
    is_gd_consumption_drop_question,
    requested_sql_metric_id,
)


def request_payload():
    return {
        "question": "Qual foi o faturamento de Recife em junho de 2026?",
        "context": [],
        "remaining_timeout_ms": 30000,
        "batch_ref": "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "access_scope": {
            "caller_ref": "session:" + "a" * 64,
            "profile_id": "v-energy-grid-360-gold",
            "source_id": "gold.local",
            "allowed_operations": ["read"],
            "allowed_metric_ids": ["billing.revenue", "energy.consumption"],
            "allowed_dimension_ids": [
                "geography.municipality",
                "customer.consumption_class",
                "customer.consumer_unit",
            ],
        },
        "temporal_coverage": [
            {
                "metric_id": "billing.revenue",
                "kind": "monthly",
                "competencies": ["2026-06"],
            }
        ],
        "dimension_value_coverage": [
            {"dimension_id": "geography.municipality", "values": ["Recife"]}
        ],
    }


def test_billing_consumption_class_is_not_misread_as_two_metrics():
    question = "Qual foi o faturamento da classe de consumo residencial?"
    assert requested_sql_metric_id(question) == "billing.revenue"
    assert not is_explicit_multi_metric_question(question)
    assert is_explicit_multi_metric_question(
        "Compare o consumo medido e o faturamento em junho de 2026."
    )


@pytest.mark.parametrize(
    ("question", "metric_id"),
    [
        ("Qual foi o ticket médio por UC faturada em junho de 2026?", "billing.average_ticket"),
        ("Qual foi o preço médio observado por kWh em junho de 2026?", "billing.effective_tariff"),
        ("Qual foi a tarifa média efetiva em junho de 2026?", "billing.effective_tariff"),
    ],
)
def test_billing_ratio_questions_map_to_their_distinct_catalog_metrics(question, metric_id):
    assert requested_sql_metric_id(question) == metric_id


def test_average_consumption_question_maps_to_catalog_ratio_metric():
    assert requested_sql_metric_id(
        "Qual foi o consumo médio por UC com leitura em junho de 2026?"
    ) == "energy.average_consumption_per_uc"

    payload = request_payload()
    payload["question"] = "Qual foi o consumo médio por UC com leitura em junho de 2026?"
    payload["access_scope"]["allowed_metric_ids"].append(
        "energy.average_consumption_per_uc"
    )
    payload["temporal_coverage"] = [{
        "metric_id": "energy.average_consumption_per_uc",
        "kind": "monthly",
        "competencies": ["2026-06"],
    }]
    context = json.loads(build(payload).contents)
    assert context["generation_contract_version"] == "text-to-sql-f1-v11"
    assert context["metric"]["aggregation"] == "ratio_of_sums"
    assert set(context["source"]["columns"]) >= {
        "consumo_total_kwh", "qtd_ucs_com_leitura"
    }


def build(payload):
    return build_sql_generation_context(QuestionPlanRequest.model_validate(payload))


def test_context_separates_recognition_registry_from_authorized_f1_schema():
    context = build(request_payload())
    body = json.loads(context.contents)
    assert body["source"]["table"] == "diagnostico_receita"
    assert set(body["source"]["columns"]) == {
        "competencia",
        "receita_total_reais",
        "municipio",
        "classe_consumo",
    }
    assert "consumer_unit" not in context.contents
    assert "a" * 64 not in context.contents
    assert body["semantic_registry"]["purpose"] == "recognition_only_not_authorization"
    consumption = next(
        item
        for item in body["semantic_registry"]["metrics"]
        if item["metric_id"] == "energy.consumption"
    )
    assert consumption["label"] == "Consumo medido"
    assert consumption["unit"] == "kWh"
    assert set(consumption) == {"metric_id", "label", "definition", "unit"}
    assert "consumo_total_kwh" not in context.contents
    assert "consumption" not in body["dimensions"]
    assert body["metric"]["aggregation"] == "sum"
    assert body["rules"]["annual_requires_all_months"] is True
    assert body["schema_basis"].endswith("not_live_database")
    assert body["context_version"] == context.context_version


def test_consumption_context_selects_measured_kwh_and_aggregate_source_only():
    payload = request_payload()
    payload["question"] = "Qual foi o consumo de Recife em junho de 2026?"
    payload["temporal_coverage"] = [
        {
            "metric_id": "energy.consumption",
            "kind": "monthly",
            "competencies": ["2026-06"],
        }
    ]
    context = build(payload)
    body = json.loads(context.contents)

    assert body["generation_contract_version"] == "text-to-sql-f1-v2"
    assert body["metric"]["id"] == "energy.consumption"
    assert body["metric"]["measure_column"] == "consumo_total_kwh"
    assert body["metric"]["unit"] == "kWh"
    assert body["metric"]["measure_type"] == "double"
    assert body["source"]["table"] == "diagnostico_receita"
    assert "consumo_total_kwh" in body["source"]["columns"]
    assert "receita_total_reais" not in body["source"]["columns"]
    assert "consumer_unit" not in context.contents
    assert context.metric_ids == ("energy.consumption",)


def test_explicit_gd_consumption_adds_only_the_cadastral_filter_dimension():
    payload = request_payload()
    payload["question"] = (
        "Qual foi o consumo das unidades com geração distribuída em Recife "
        "em junho de 2026?"
    )
    payload["access_scope"]["allowed_dimension_ids"].append("generation.distributed")
    payload["temporal_coverage"] = [
        {
            "metric_id": "energy.consumption",
            "kind": "monthly",
            "competencies": ["2026-06"],
        }
    ]
    payload["dimension_value_coverage"].append(
        {
            "dimension_id": "generation.distributed",
            "values": ["Não", "Sim"],
        }
    )
    context = build(payload)
    body = json.loads(context.contents)
    assert body["dimensions"]["generation.distributed"] == "possui_gd"
    assert body["dimension_values"][-1] == {
        "dimension_id": "generation.distributed",
        "values": ["Não", "Sim"],
    }
    assert "possui_gd" in body["source"]["columns"]


def test_gd_consumption_context_fails_closed_without_authorized_vocabulary():
    payload = request_payload()
    payload["question"] = (
        "Qual foi o consumo das UCs sem GD em Recife em junho de 2026?"
    )
    payload["access_scope"]["allowed_dimension_ids"].append("generation.distributed")
    payload["temporal_coverage"] = [
        {
            "metric_id": "energy.consumption",
            "kind": "monthly",
            "competencies": ["2026-06"],
        }
    ]
    with pytest.raises(SqlContextUnavailable, match="Vocabulário GD"):
        build(payload)


def test_gd_filter_is_inherited_only_by_an_elliptical_followup():
    payload = request_payload()
    payload["question"] = "E em Olinda?"
    payload["context"] = [
        {
            "role": "user",
            "content": "Qual foi o consumo das UCs com geração distribuída em Recife?",
        }
    ]
    payload["access_scope"]["allowed_dimension_ids"].append("generation.distributed")
    payload["temporal_coverage"] = [
        {
            "metric_id": "energy.consumption",
            "kind": "monthly",
            "competencies": ["2026-06"],
        }
    ]
    payload["dimension_value_coverage"].append(
        {
            "dimension_id": "generation.distributed",
            "values": ["Não", "Sim"],
        }
    )
    context = build(payload)
    assert (
        json.loads(context.contents)["dimensions"]["generation.distributed"]
        == "possui_gd"
    )

    payload["question"] = "Qual foi o consumo em Olinda em junho de 2026?"
    context = build(payload)
    assert "generation.distributed" not in json.loads(context.contents)["dimensions"]


def test_ambiguous_gd_mention_does_not_authorize_a_filter():
    payload = request_payload()
    payload["question"] = (
        "Qual foi o consumo associado a GD em Recife em junho de 2026?"
    )
    payload["access_scope"]["allowed_dimension_ids"].append("generation.distributed")
    payload["temporal_coverage"] = [
        {
            "metric_id": "energy.consumption",
            "kind": "monthly",
            "competencies": ["2026-06"],
        }
    ]
    payload["dimension_value_coverage"].append(
        {
            "dimension_id": "generation.distributed",
            "values": ["Não", "Sim"],
        }
    )
    context = build(payload)
    assert "generation.distributed" not in json.loads(context.contents)["dimensions"]


def test_revenue_neighborhood_request_selects_controlled_source_and_dimension():
    payload = request_payload()
    payload["question"] = "Qual foi a receita por bairro em Recife em junho de 2026?"
    payload["access_scope"]["allowed_dimension_ids"].append("geography.neighborhood")
    payload["dimension_value_coverage"].append(
        {
            "dimension_id": "geography.neighborhood",
            "values": ["Boa Vista"],
        }
    )
    context = build(payload)
    body = json.loads(context.contents)
    assert body["source"]["capability_id"] == "faturamento.receita_bairro"
    assert body["source"]["table"] == "consumo_receita_bairro"
    assert body["dimensions"]["geography.neighborhood"] == "bairro"
    assert "bairro" in body["source"]["columns"]


def test_revenue_neighborhood_source_requires_profile_dimension_permission():
    payload = request_payload()
    payload["question"] = "Qual foi a receita do bairro Boa Vista em junho de 2026?"
    with pytest.raises(SqlContextUnavailable, match="bairro"):
        build(payload)


def test_attendance_context_uses_monthly_protocol_source_without_uc_dimension():
    payload = request_payload()
    payload["question"] = (
        "Quantos protocolos de atendimento foram abertos em junho de 2026?"
    )
    payload["access_scope"]["allowed_metric_ids"] = ["service.attendance"]
    payload["access_scope"]["allowed_dimension_ids"] = []
    payload["dimension_value_coverage"] = []
    payload["temporal_coverage"] = [
        {
            "metric_id": "service.attendance",
            "kind": "monthly",
            "competencies": ["2026-06"],
        }
    ]
    context = build(payload)
    body = json.loads(context.contents)
    assert body["generation_contract_version"] == "text-to-sql-f1-v3"
    assert body["metric"]["id"] == "service.attendance"
    assert body["metric"]["aggregation"] == "count_non_null"
    assert body["metric"]["measure_column"] == "protocolo"
    assert body["metric"]["measure_type"] == "integer"
    assert body["metric"]["unit"] == "protocolos"
    assert body["source"]["table"] == "atendimentos_uc"
    assert set(body["source"]["columns"]) == {"data_abertura", "protocolo"}


def test_satisfaction_context_uses_average_of_monthly_non_null_scores():
    payload = request_payload()
    payload["question"] = "Qual foi a nota média de satisfação em junho de 2026?"
    payload["access_scope"]["allowed_metric_ids"] = ["service.satisfaction"]
    payload["access_scope"]["allowed_dimension_ids"] = []
    payload["dimension_value_coverage"] = []
    payload["temporal_coverage"] = [
        {
            "metric_id": "service.satisfaction",
            "kind": "monthly",
            "competencies": ["2026-06"],
        }
    ]
    context = build(payload)
    body = json.loads(context.contents)
    assert body["generation_contract_version"] == "text-to-sql-f1-v7"
    assert body["metric"]["id"] == "service.satisfaction"
    assert body["metric"]["aggregation"] == "average_non_null"
    assert body["metric"]["measure_column"] == "nota_satisfacao"
    assert body["metric"]["measure_type"] == "double"
    assert body["metric"]["unit"] == "pontos"
    assert body["source"]["table"] == "atendimentos_uc"
    assert body["source"]["temporal_column"] == "data_abertura"
    assert set(body["source"]["columns"]) == {"data_abertura", "nota_satisfacao"}
    assert body["rules"]["satisfaction_definition"].endswith(
        "NULL é ignorado, zero é válido"
    )


def test_accumulated_attendance_context_has_no_invented_period_or_uc_filter():
    payload = request_payload()
    payload["question"] = "Quantos chamados no histórico acumulado?"
    payload["access_scope"]["allowed_metric_ids"] = ["service.accumulated_attendance"]
    payload["access_scope"]["allowed_dimension_ids"] = []
    payload["dimension_value_coverage"] = []
    payload["temporal_coverage"] = [
        {
            "metric_id": "service.accumulated_attendance",
            "kind": "none",
        }
    ]
    context = build(payload)
    body = json.loads(context.contents)
    assert body["generation_contract_version"] == "text-to-sql-f1-v5"
    assert body["metric"]["id"] == "service.accumulated_attendance"
    assert body["source"]["table"] == "visao_360_uc"
    assert body["source"]["temporal_column"] is None
    assert body["source"]["columns"] == {"total_chamados_callcenter": "BIGINT"}
    assert body["rules"]["accumulated_period_is_unknown"] is True


def test_gd_units_context_is_a_non_temporal_lot_snapshot():
    payload = request_payload()
    payload["question"] = "Quantas UCs têm GD?"
    payload["access_scope"]["allowed_metric_ids"] = ["energy.gd_units"]
    payload["access_scope"]["allowed_dimension_ids"] = [
        "geography.municipality",
        "generation.distributed",
    ]
    payload["temporal_coverage"] = [{"metric_id": "energy.gd_units", "kind": "none"}]
    payload["dimension_value_coverage"] = [
        {"dimension_id": "generation.distributed", "values": ["Não", "Sim"]},
    ]

    context = build(payload)
    body = json.loads(context.contents)

    assert body["generation_contract_version"] == "text-to-sql-f1-v8"
    assert body["source"]["table"] == "variacao_consumo_uc"
    assert body["source"]["temporal_column"] is None
    assert body["metric"]["measure_column"] == "possui_gd"
    assert body["metric"]["measure_type"] == "integer"
    assert body["metric"]["unit"] == "UCs"
    assert body["rules"]["snapshot_period_phrase"] == "cadastro de GD no lote"
    assert requested_sql_metric_id(payload["question"]) == "energy.gd_units"


def test_gd_consumption_drop_is_not_misclassified_as_a_registry_count():
    question = "Quantas UCs com GD tiveram queda de consumo superior a 30%?"
    assert is_gd_consumption_drop_question(question)
    assert requested_sql_metric_id(question) != "energy.gd_units"
    assert is_gd_consumption_drop_question("Quantas UCs com GD tiveram queda?")


def test_gd_consumption_drop_context_uses_approved_fixed_window_metric():
    payload = request_payload()
    payload["question"] = "Quantas UCs com GD em Olinda tiveram queda acima de 30%?"
    payload["access_scope"]["allowed_metric_ids"] = ["energy.gd_consumption_drop"]
    payload["access_scope"]["allowed_dimension_ids"] = [
        "geography.municipality",
        "generation.distributed",
    ]
    payload["temporal_coverage"] = [
        {
            "metric_id": "energy.gd_consumption_drop",
            "kind": "none",
        }
    ]
    payload["dimension_value_coverage"] = [
        {"dimension_id": "geography.municipality", "values": ["Olinda"]},
        {"dimension_id": "generation.distributed", "values": ["Sim", "Não"]},
    ]
    request = QuestionPlanRequest.model_validate(payload)

    context = build_sql_generation_context(request)
    body = json.loads(context.contents)

    assert context.metric_ids == ("energy.gd_consumption_drop",)
    assert body["generation_contract_version"] == "text-to-sql-f1-v10"
    assert body["source"]["capability_id"] == "consumo.variacao_uc"
    assert {
        "meses_com_leitura_p1",
        "meses_com_leitura_p2",
    } <= body["source"]["columns"].keys()
    assert body["rules"]["gd_drop_windows"] == [
        {"start": "2022-07", "end": "2023-06"},
        {"start": "2025-07", "end": "2026-06"},
    ]


def test_accumulated_satisfaction_context_has_no_period_or_personal_dimensions():
    payload = request_payload()
    payload["question"] = "Qual foi a nota média de satisfação no histórico acumulado?"
    payload["access_scope"]["allowed_metric_ids"] = ["service.accumulated_satisfaction"]
    payload["access_scope"]["allowed_dimension_ids"] = []
    payload["dimension_value_coverage"] = []
    payload["temporal_coverage"] = [
        {
            "metric_id": "service.accumulated_satisfaction",
            "kind": "none",
        }
    ]

    context = build(payload)
    body = json.loads(context.contents)

    assert body["generation_contract_version"] == "text-to-sql-f1-v9"
    assert body["metric"]["id"] == "service.accumulated_satisfaction"
    assert body["metric"]["measure_column"] == "nota_satisfacao"
    assert body["metric"]["measure_type"] == "double"
    assert body["metric"]["unit"] == "pontos"
    assert body["source"]["table"] == "atendimentos_uc"
    assert body["source"]["temporal_column"] is None
    assert body["source"]["columns"] == {"nota_satisfacao": "FLOAT"}
    assert body["dimensions"] == {}
    assert body["rules"]["accumulated_satisfaction_period_is_unknown"] is True


@pytest.mark.parametrize(
    ("code", "metric_id", "column", "unit"),
    [
        ("DEC", "network.equivalent_interruption_duration", "DEC", "horas por UC"),
        (
            "FEC",
            "network.equivalent_interruption_frequency",
            "FEC",
            "interrupções por UC",
        ),
    ],
)
def test_continuity_context_exposes_only_feeder_month_measure(
    code, metric_id, column, unit
):
    payload = request_payload()
    payload["question"] = f"Qual foi o {code} do alimentador ALIM-01 em junho de 2026?"
    payload["access_scope"]["allowed_metric_ids"] = [metric_id]
    payload["access_scope"]["allowed_dimension_ids"] = ["network.feeder"]
    payload["temporal_coverage"] = [
        {
            "metric_id": metric_id,
            "kind": "monthly",
            "competencies": ["2026-06"],
        }
    ]
    payload["dimension_value_coverage"] = [
        {
            "dimension_id": "network.feeder",
            "values": ["ALIM-01"],
        }
    ]
    context = build(payload)
    body = json.loads(context.contents)
    assert body["generation_contract_version"] == "text-to-sql-f1-v4"
    assert body["metric"]["id"] == metric_id
    assert body["metric"]["aggregation"] == "key_grain_read"
    assert body["metric"]["measure_column"] == column
    assert body["metric"]["unit"] == unit
    assert body["source"]["table"] == "indicadores_dec_fec"
    assert set(body["source"]["columns"]) == {"competencia", column, "id_alimentador"}


def test_explicit_metric_overrides_followup_metric():
    payload = request_payload()
    payload["question"] = "E qual foi a receita?"
    payload["context"] = [{"role": "user", "content": "E o consumo em kWh?"}]
    context = build(payload)
    assert json.loads(context.contents)["metric"]["id"] == "billing.revenue"


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
    payload["context"] = [
        {
            "role": "user",
            "content": "E no mês anterior, mantendo Recife?",
        }
    ]
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


@pytest.mark.parametrize(
    "caller_ref", ["caller", "user:" + "a" * 64, "session:" + "z" * 64]
)
def test_context_requires_backend_session_pseudonym(caller_ref):
    payload = request_payload()
    payload["access_scope"]["caller_ref"] = caller_ref
    with pytest.raises(SqlContextUnavailable, match="Escopo"):
        build(payload)


def test_context_never_silently_truncates_large_essential_context():
    payload = request_payload()
    payload["dimension_value_coverage"] = [
        {
            "dimension_id": "geography.municipality",
            "values": [f"Municipio{i:04}" + "x" * 100 for i in range(700)],
        }
    ]
    with pytest.raises(SqlContextUnavailable, match="limite"):
        build(payload)
