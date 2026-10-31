"""Contrato físico disponibilizado ao Backend, sem banco ou imports GenAI."""

from copy import deepcopy
from datetime import date, timedelta

import pytest
from sqlalchemy import BigInteger, DateTime, Float, MetaData, Numeric

from app.models import gold_v2
from app.services.gold_catalog import load_gold_catalog, select_catalog_source


def test_loads_current_catalog_against_fifteen_table_schema():
    catalog = load_gold_catalog()
    assert catalog.mapping_version == "gold-catalog-v2"
    assert len(catalog.metrics) == 11
    assert (
        select_catalog_source(
            catalog,
            "service.attendance",
            set(),
            {"atendimento.mensal"},
            {
                "kind": "bounded",
                "start": "2000-01-01",
                "end": "2000-01-31",
                "granularity": "month",
            },
        ).table
        == "atendimentos_uc"
    )


def test_catalog_provides_business_names_and_definitions_for_consumers():
    catalog = load_gold_catalog()
    revenue = next(m for m in catalog.metrics if m.metric_id == "billing.revenue")
    assert revenue.label == "Receita faturada"
    assert "sem leitura" in revenue.definition
    assert all(m.label.strip() and m.definition.strip() for m in catalog.metrics)
    assert all(s.table not in m.definition for m in catalog.metrics for s in m.sources)


def test_identical_versioned_payload_remains_compatible():
    catalog = load_gold_catalog()
    assert load_gold_catalog(catalog.model_dump(mode="json")) == catalog


def test_catalog_declares_filter_operators_without_granting_values():
    catalog = load_gold_catalog()
    attendance = next(m for m in catalog.metrics if m.metric_id == "service.attendance")
    assert attendance.dimension_operators == {"customer.consumer_unit": ("eq", "in")}


def test_source_selection_enforces_metric_window_limit_and_accumulated_has_none():
    catalog = load_gold_catalog()
    attendance = next(m for m in catalog.metrics if m.metric_id == "service.attendance")
    accumulated = next(
        m for m in catalog.metrics if m.metric_id == "service.accumulated_attendance"
    )
    assert attendance.max_window_days == 366 * 5
    assert accumulated.max_window_days is None
    with pytest.raises(ValueError, match="limite"):
        select_catalog_source(
            catalog,
            "service.attendance",
            set(),
            {"atendimento.mensal"},
            {
                "kind": "bounded",
                "start": date(2000, 1, 1),
                "end": date(2000, 1, 1) + timedelta(days=attendance.max_window_days + 1),
                "granularity": "month",
            },
        )


@pytest.mark.parametrize(
    "metric_id,numerator,denominator",
    [
        ("billing.average_ticket", "receita_total_reais", "qtd_ucs_distintas_faturadas_no_mes"),
        ("energy.average_consumption_per_uc", "consumo_total_kwh", "qtd_ucs_com_leitura"),
        ("billing.effective_tariff", "receita_base_comparavel_reais", "consumo_base_comparavel_kwh"),
    ],
)
def test_ratios_use_the_population_defined_by_gold_contract(metric_id, numerator, denominator):
    metric = next(m for m in load_gold_catalog().metrics if m.metric_id == metric_id)
    assert metric.aggregation == "ratio_of_sums"
    assert all(s.numerator_column == numerator and s.denominator_column == denominator
               for s in metric.sources)


@pytest.mark.parametrize(
    "mutation", ["schema", "table", "column", "type", "grain", "period", "dependency"]
)
def test_rejects_incompatible_catalog(mutation):
    data = deepcopy(load_gold_catalog().model_dump(mode="json"))
    source = data["metrics"][0]["sources"][0]
    if mutation == "schema":
        data["physical_schema"] = "public"
    if mutation == "table":
        source["table"] = "cadastro_titulares"
    if mutation == "column":
        source["measure_column"] = "cpf"
    if mutation == "type":
        data["metrics"][0]["measure_type"] = "string"
    if mutation == "grain":
        source["grain"] = ["competencia"]
    if mutation == "period":
        source["temporal_column"] = "data_processamento_gold"
    if mutation == "dependency":
        data["metrics"][0]["required_capability_ids"] = ["unknown.capacity"]
    with pytest.raises(ValueError):
        load_gold_catalog(data)


@pytest.mark.parametrize(
    "table_name,column_name,column_type",
    [
        ("indicadores_dec_fec", "municipio", Float()),
        ("indicadores_dec_fec", "competencia", BigInteger()),
        ("diagnostico_receita", "receita_total_reais", Numeric(38, 0)),
        ("atendimentos_uc", "data_abertura", DateTime(timezone=False)),
    ],
)
def test_rejects_physical_schema_type_drift(
    monkeypatch, table_name, column_name, column_type
):
    table = gold_v2.TABLES[table_name].to_metadata(MetaData())
    table.c[column_name].type = column_type
    monkeypatch.setitem(gold_v2.TABLES, table_name, table)

    with pytest.raises(ValueError):
        load_gold_catalog()


@pytest.mark.parametrize("mutation", ["dimension_columns", "dimension_operators"])
def test_source_selection_revalidates_mutated_catalog(mutation):
    catalog = load_gold_catalog()
    attendance = next(m for m in catalog.metrics if m.metric_id == "service.attendance")
    if mutation == "dimension_columns":
        attendance.sources[0].dimension_columns["customer.consumer_unit"] = "protocolo"
    else:
        attendance.dimension_operators["customer.consumer_unit"] = ("eq",)

    with pytest.raises(ValueError, match="diverge da definição semântica"):
        select_catalog_source(
            catalog,
            "service.attendance",
            {"customer.consumer_unit"},
            {"atendimento.mensal"},
            {
                "kind": "bounded",
                "start": "2000-01-01",
                "end": "2000-01-31",
                "granularity": "month",
            },
        )


def test_accumulated_rejects_dates_and_monthly_rejects_accumulated():
    catalog = load_gold_catalog()
    with pytest.raises(ValueError):
        select_catalog_source(
            catalog,
            "service.accumulated_attendance",
            set(),
            {"atendimento.uc_acumulado"},
            {
                "kind": "bounded",
                "start": "2000-01-01",
                "end": "2000-01-31",
                "granularity": "month",
            },
        )
    with pytest.raises(ValueError):
        select_catalog_source(
            catalog,
            "service.attendance",
            set(),
            {"atendimento.mensal"},
            {"kind": "catalog_phrase", "phrase": "histórico acumulado"},
        )


@pytest.mark.parametrize(
    "metric,available,filters",
    [
        ("billing.revenue", {"consumo.mensal_uc"}, {"customer.consumer_unit"}),
        ("energy.consumption", {"faturamento.receita"}, set()),
        ("service.attendance", {"atendimento.uc_acumulado"}, set()),
        ("network.equivalent_interruption_duration", {"interrupcoes.dec_fec"}, set()),
    ],
)
def test_select_does_not_bypass_readiness_or_required_filters(
    metric, available, filters
):
    assert (
        select_catalog_source(
            load_gold_catalog(),
            metric,
            filters,
            available,
            {
                "kind": "bounded",
                "start": "2000-01-01",
                "end": "2000-01-31",
                "granularity": "month",
            },
        )
        is None
    )


def test_accumulated_selection_has_no_date_and_satisfaction_uses_protocol_notes():
    catalog = load_gold_catalog()
    selected = select_catalog_source(
        catalog,
        "service.accumulated_satisfaction",
        set(),
        {"atendimento.uc_acumulado"},
        {"kind": "catalog_phrase", "phrase": "histórico acumulado"},
    )
    assert selected.temporal_column is None
    assert (
        selected.table == "atendimentos_uc"
        and selected.measure_column == "nota_satisfacao"
    )


@pytest.mark.parametrize("mutation", ["null_rule", "ratio", "utc", "duplicate"])
def test_rejects_incoherent_measure_rules(mutation):
    data = load_gold_catalog().model_dump(mode="json")
    if mutation == "null_rule":
        data["metrics"][0]["null_rule"] = "read_null_is_absent"
    if mutation == "ratio":
        data["metrics"][0]["aggregation"] = "ratio_of_sums"
    if mutation == "utc":
        source = next(
            m for m in data["metrics"] if m["metric_id"] == "service.attendance"
        )["sources"][0]
        source["temporal_column"] = "data_fechamento"
    if mutation == "duplicate":
        data["metrics"].append(data["metrics"][0])
    with pytest.raises(ValueError):
        load_gold_catalog(data)


def test_rejects_average_of_text_even_when_declared_type_matches_column():
    data = load_gold_catalog().model_dump(mode="json")
    metric = next(
        m for m in data["metrics"] if m["metric_id"] == "service.satisfaction"
    )
    metric["measure_type"] = "string"
    metric["sources"][0]["measure_column"] = "protocolo"
    with pytest.raises(ValueError):
        load_gold_catalog(data)


def test_rejects_yearly_dec_even_with_feeder():
    with pytest.raises(ValueError):
        select_catalog_source(
            load_gold_catalog(),
            "network.equivalent_interruption_duration",
            {"network.feeder"},
            {"interrupcoes.dec_fec"},
            {
                "kind": "bounded",
                "start": "2000-01-01",
                "end": "2000-12-31",
                "granularity": "year",
            },
        )


@pytest.mark.parametrize("mutation", ["unit", "denominator", "aggregation", "dependency"])
def test_rejects_semantic_drift_even_when_columns_and_types_are_valid(mutation):
    data = load_gold_catalog().model_dump(mode="json")
    metric = next(m for m in data["metrics"] if m["metric_id"] == "billing.effective_tariff")
    if mutation == "unit":
        metric["unit"] = "kWh"
    elif mutation == "denominator":
        metric["sources"][0]["denominator_column"] = "consumo_total_kwh"
    elif mutation == "aggregation":
        metric = next(m for m in data["metrics"] if m["metric_id"] == "service.satisfaction")
        metric["aggregation"] = "sum"
        metric["null_rule"] = "sum_ignores_null_all_null_is_absent"
    else:
        metric["required_capability_ids"] = ["faturamento.receita"]
    with pytest.raises(ValueError):
        load_gold_catalog(data)


def test_accumulated_does_not_accept_invented_granularity():
    with pytest.raises(ValueError):
        select_catalog_source(
            load_gold_catalog(),
            "service.accumulated_attendance",
            set(),
            {"atendimento.uc_acumulado"},
            {
                "kind": "catalog_phrase",
                "phrase": "histórico acumulado",
                "granularity": "year",
            },
        )
