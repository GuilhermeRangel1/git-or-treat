"""Contrato físico disponibilizado ao Backend, sem banco ou imports GenAI."""

from copy import deepcopy

import pytest

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
