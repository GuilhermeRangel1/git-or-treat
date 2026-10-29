"""Mapeamento físico do catálogo Gold contra perfil, prontidão e ``dictionary_gold.toml``.

Os testes de contrato alteram cópias em memória do dicionário e da prontidão; nada lê lote real.
"""

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.profiles.grid360_gold_mapping import (
    DICTIONARY_VERSION,
    GRID360_GOLD_MAPPING,
    Aggregation,
    CatalogMappingError,
    DictionarySchema,
    DictionaryTable,
    MetricMapping,
    select_source,
    validate_mapping,
)
from app.readiness import CAPABILITY_REQUIREMENTS, GoldTable
from app.sql.dictionary import load_dictionary

GOLD_DICTIONARY_PATH = Path(__file__).parents[1] / "app" / "sql" / "dictionary_gold.toml"
APPROVED = frozenset(
    {"faturamento.receita", "faturamento.receita_bairro", "consumo.mensal_uc",
     "interrupcoes.dec_fec"}
)
RATIO_COLUMNS = {"ticket_medio_reais_por_uc", "tarifa_media_efetiva", "consumo_medio_kwh_por_uc"}


def _raw() -> dict:
    return tomllib.loads(GOLD_DICTIONARY_PATH.read_text(encoding="utf-8"))


def _schema(raw: dict | None = None) -> DictionarySchema:
    """Dicionário carregado por ``load_dictionary`` mais chave e período dos metadados."""

    raw = raw if raw is not None else _raw()
    dictionary = load_dictionary(GOLD_DICTIONARY_PATH)
    return DictionarySchema(
        version=raw["version"],
        sensitive_columns=dictionary.sensitive_columns,
        tables={
            name: DictionaryTable(
                columns=dict(spec["columns"]),
                key=tuple(spec["key"]),
                period_column=spec.get("period_column"),
            )
            for name, spec in raw["tables"].items()
        },
    )


def _validate(schema=None, requirements=CAPABILITY_REQUIREMENTS, mapping=GRID360_GOLD_MAPPING):
    validate_mapping(
        mapping,
        profile=GRID360_GOLD_PROFILE,
        dictionary=schema if schema is not None else _schema(),
        requirements=requirements,
    )


# --- coerência ----------------------------------------------------------------------------


def test_mapping_validates_against_profile_readiness_and_dictionary() -> None:
    dictionary = load_dictionary(GOLD_DICTIONARY_PATH)

    assert GRID360_GOLD_MAPPING.mapping_version == "gold-catalog-v1"
    assert GRID360_GOLD_MAPPING.profile_id == GRID360_GOLD_PROFILE.profile_id
    assert GRID360_GOLD_MAPPING.dictionary_version == DICTIONARY_VERSION == dictionary.version
    _validate()


def test_each_profile_metric_has_one_mapping_and_an_approved_capability() -> None:
    requirements = {requirement.id: requirement for requirement in CAPABILITY_REQUIREMENTS}
    profile_ids = [metric.id for metric in GRID360_GOLD_PROFILE.metrics]
    mapping_ids = [metric.metric_id for metric in GRID360_GOLD_MAPPING.metrics]

    assert sorted(profile_ids) == sorted(mapping_ids)
    for metric in GRID360_GOLD_MAPPING.metrics:
        for source in metric.sources:
            requirement = requirements[source.capability_id]
            assert requirement.definition_approved, metric.metric_id
            assert not requirement.source_not_in_gold, metric.metric_id
            assert source.table in requirement.tables, metric.metric_id
            assert source.temporal_column == requirement.temporal_column, metric.metric_id
        assert metric.capability_id == metric.sources[0].capability_id


def test_every_referenced_column_exists_in_its_table_and_is_not_sensitive() -> None:
    dictionary = load_dictionary(GOLD_DICTIONARY_PATH)
    raw = _raw()["tables"]

    for metric in GRID360_GOLD_MAPPING.metrics:
        for source in metric.sources:
            columns = dictionary.tables[source.table.value].columns
            assert source.referenced_columns() <= set(columns), metric.metric_id
            assert not source.referenced_columns() & dictionary.sensitive_columns
            assert source.temporal_column == raw[source.table.value].get("period_column")
            assert list(source.grain) == raw[source.table.value]["key"]
            assert set(source.nullable_columns) <= set(
                raw[source.table.value]["nullable_columns"]
            )
            assert set(source.measure_columns()) <= set(source.nullable_columns)


def test_column_types_match_aggregation_and_unit() -> None:
    dictionary = load_dictionary(GOLD_DICTIONARY_PATH)
    raw_metrics = {name: spec["metrics"] for name, spec in _raw()["tables"].items()}

    for metric in GRID360_GOLD_MAPPING.metrics:
        logical = next(item for item in GRID360_GOLD_PROFILE.metrics if item.id == metric.metric_id)
        assert metric.unit_kind in logical.accepted_unit_kinds, metric.metric_id
        for source in metric.sources:
            columns = dictionary.tables[source.table.value].columns
            declared = raw_metrics[source.table.value]
            if metric.aggregation is Aggregation.RATIO_OF_SUMS:
                pairs = (
                    (source.numerator_column, metric.numerator_type),
                    (source.denominator_column, metric.denominator_type),
                )
                expected_aggregation = "sum"
            else:
                pairs = ((source.measure_column, metric.measure_type),)
                expected_aggregation = (
                    "sum" if metric.aggregation is Aggregation.SUM else "ratio"
                )
            for column, column_type in pairs:
                assert columns[column].startswith(column_type.value), (metric.metric_id, column)
                assert declared[column]["aggregation"] == expected_aggregation, column


def test_dimensions_of_each_metric_are_supported_by_its_source_tables() -> None:
    dictionary = load_dictionary(GOLD_DICTIONARY_PATH)
    raw = _raw()["tables"]

    for metric in GRID360_GOLD_MAPPING.metrics:
        logical = next(item for item in GRID360_GOLD_PROFILE.metrics if item.id == metric.metric_id)
        assert metric.dimension_ids() == set(logical.dimension_ids), metric.metric_id
        for source in metric.sources:
            columns = set(dictionary.tables[source.table.value].columns)
            assert set(source.dimension_columns.values()) <= columns
            assert set(source.dimension_columns.values()) <= set(
                raw[source.table.value]["dimensions"]
            ) | set(raw[source.table.value]["key"])


def test_ratios_are_ratios_of_sums_and_never_reuse_a_precomputed_ratio() -> None:
    ratios = {"billing.average_ticket", "billing.effective_tariff",
              "energy.average_consumption_per_uc"}

    for metric in GRID360_GOLD_MAPPING.metrics:
        for source in metric.sources:
            assert not set(source.measure_columns()) & RATIO_COLUMNS, metric.metric_id
        if metric.metric_id in ratios:
            assert metric.aggregation is Aggregation.RATIO_OF_SUMS
            assert all(source.measure_column is None for source in metric.sources)


def test_dec_and_fec_are_read_only_at_feeder_and_month_grain() -> None:
    profile = {metric.id: metric for metric in GRID360_GOLD_PROFILE.metrics}

    for metric_id in (
        "network.equivalent_interruption_duration",
        "network.equivalent_interruption_frequency",
    ):
        metric = GRID360_GOLD_MAPPING.metric(metric_id)
        assert metric.aggregation is Aggregation.KEY_GRAIN_READ
        assert metric.required_dimension_ids == ("network.feeder",)
        assert [source.table for source in metric.sources] == [GoldTable.INDICADORES_DEC_FEC]
        assert [granularity.value for granularity in profile[metric_id].granularities] == [
            "month"
        ]
        assert select_source(metric, set(), APPROVED) is None
        assert select_source(metric, {"geography.municipality"}, APPROVED) is None
        assert select_source(metric, {"network.feeder"}, APPROVED) is not None


def test_mapping_models_are_frozen_and_forbid_extra_fields() -> None:
    metric = GRID360_GOLD_MAPPING.metric("billing.revenue")

    with pytest.raises(ValidationError):
        metric.aggregation = Aggregation.RATIO_OF_SUMS
    with pytest.raises(ValidationError, match="extra"):
        MetricMapping.model_validate({**metric.model_dump(), "formula": "x"})


@pytest.mark.parametrize(
    "change",
    [
        {"aggregation": "sum", "null_rule": "ratio_absent_on_null_or_zero_denominator"},
        {"aggregation": "key_grain_read"},
    ],
)
def test_a_ratio_cannot_be_declared_as_sum_or_plain_read(change) -> None:
    ticket = GRID360_GOLD_MAPPING.metric("billing.average_ticket").model_dump()

    with pytest.raises(ValidationError):
        MetricMapping.model_validate({**ticket, **change})


# --- escolha de fonte ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("metric_id", "dimensions", "table"),
    [
        ("billing.revenue", set(), "diagnostico_receita"),
        ("billing.revenue", {"tariff.flag", "generation.distributed"}, "diagnostico_receita"),
        ("billing.revenue", {"geography.neighborhood"}, "consumo_receita_bairro"),
        ("billing.revenue", {"customer.consumer_unit"}, "consumo_mensal_uc"),
        ("energy.consumption", {"customer.consumer_unit"}, "consumo_mensal_uc"),
        ("billing.average_ticket", {"geography.neighborhood"}, "consumo_receita_bairro"),
        ("billing.revenue", {"geography.neighborhood", "tariff.flag"}, None),
        ("billing.revenue", {"customer.consumer_unit", "geography.municipality"}, None),
        ("billing.average_ticket", {"customer.consumer_unit"}, None),
    ],
)
def test_one_source_covers_the_query_or_none_does(metric_id, dimensions, table) -> None:
    source = select_source(GRID360_GOLD_MAPPING.metric(metric_id), dimensions, APPROVED)

    assert (source.table.value if source else None) == table


def test_unavailable_capability_of_a_source_is_skipped_never_combined() -> None:
    revenue = GRID360_GOLD_MAPPING.metric("billing.revenue")

    without_diagnostico = APPROVED - {"faturamento.receita"}
    assert select_source(revenue, set(), without_diagnostico).table.value == (
        "consumo_receita_bairro"
    )
    assert select_source(revenue, {"tariff.flag"}, without_diagnostico) is None
    assert select_source(revenue, set(), frozenset()) is None


# --- contrato catálogo-esquema ------------------------------------------------------------


def _mutated(change) -> DictionarySchema:
    raw = _raw()
    change(raw["tables"])
    return _schema(raw)


def _rename(tables):
    columns = tables["diagnostico_receita"]["columns"]
    columns["receita_total"] = columns.pop("receita_total_reais")


def _retype(tables):
    tables["consumo_mensal_uc"]["columns"]["receita_reais"] = "double"


def _regrain(tables):
    tables["consumo_receita_bairro"]["key"] = ["competencia", "municipio", "bairro"]


def _drop_table(tables):
    del tables["indicadores_dec_fec"]


def _drop_period(tables):
    del tables["consumo_mensal_uc"]["period_column"]


def _retype_denominator(tables):
    tables["diagnostico_receita"]["columns"]["qtd_ucs_distintas_faturadas_no_mes"] = "text"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_rename, "coluna receita_total_reais ausente do dicionário"),
        (_retype, "coluna receita_reais tem tipo double, esperado decimal"),
        (_regrain, "grão difere da chave do dicionário"),
        (_drop_table, "indicadores_dec_fec: tabela ausente do dicionário"),
        (_drop_period, "coluna temporal difere do period_column do dicionário"),
        (_retype_denominator, "qtd_ucs_distintas_faturadas_no_mes tem tipo text"),
    ],
)
def test_dictionary_drift_makes_mapping_validation_fail(change, message) -> None:
    with pytest.raises(CatalogMappingError, match=message):
        _validate(_mutated(change))


def test_dictionary_version_drift_fails() -> None:
    raw = _raw()
    raw["version"] = "gold-v1-outra"

    with pytest.raises(CatalogMappingError, match="versão do dicionário"):
        _validate(_schema(raw))


def _with_requirement(capability_id: str, **update) -> tuple:
    return tuple(
        requirement.model_copy(update=update) if requirement.id == capability_id else requirement
        for requirement in CAPABILITY_REQUIREMENTS
    )


@pytest.mark.parametrize(
    ("requirements", "message"),
    [
        (
            _with_requirement("faturamento.receita", tables=(GoldTable.CONSUMO_MENSAL_UC,)),
            "diagnostico_receita: tabela fora das tabelas da capacidade faturamento.receita",
        ),
        (
            _with_requirement(
                "interrupcoes.dec_fec", tables=(), temporal_column=None, source_not_in_gold=True
            ),
            "capacidade interrupcoes.dec_fec não está aprovada",
        ),
        (
            _with_requirement("consumo.mensal_uc", definition_approved=False),
            "capacidade consumo.mensal_uc não está aprovada",
        ),
        (
            tuple(r for r in CAPABILITY_REQUIREMENTS if r.id != "faturamento.receita_bairro"),
            "capacidade faturamento.receita_bairro inexistente na prontidão",
        ),
    ],
)
def test_incomplete_capability_is_never_approved_silently(requirements, message) -> None:
    with pytest.raises(CatalogMappingError, match=message):
        _validate(requirements=requirements)


def test_unavailable_capability_must_be_declared_with_the_readiness_reason() -> None:
    missing = GRID360_GOLD_MAPPING.model_copy(
        update={"unavailable": GRID360_GOLD_MAPPING.unavailable[1:]}
    )
    with pytest.raises(CatalogMappingError, match="faturamento.preco_volume: capacidade sem"):
        _validate(mapping=missing)

    wrong = GRID360_GOLD_MAPPING.unavailable[0].model_copy(
        update={"reasons": GRID360_GOLD_MAPPING.unavailable[1].reasons}
    )
    changed = GRID360_GOLD_MAPPING.model_copy(
        update={"unavailable": (wrong, *GRID360_GOLD_MAPPING.unavailable[1:])}
    )
    with pytest.raises(CatalogMappingError, match="motivo difere da prontidão"):
        _validate(mapping=changed)


def test_open_backend_points_are_recorded_not_resolved() -> None:
    dec = GRID360_GOLD_MAPPING.metric("network.equivalent_interruption_duration").sources[0]

    assert dec.measure_column == "dec"
    assert dec.table.value == "indicadores_dec_fec"
    assert any('"DEC"' in point for point in GRID360_GOLD_MAPPING.open_points)
    assert any("gold_<nome>" in point for point in GRID360_GOLD_MAPPING.open_points)
