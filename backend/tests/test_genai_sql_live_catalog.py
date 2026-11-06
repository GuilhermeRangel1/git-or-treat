import pytest
from sqlalchemy import Column, MetaData, Numeric, Table, create_engine

from app.models.gold_v2 import TABLES
from app.services.genai_sql_live_catalog import assert_live_f1_catalog
from app.services.gold_catalog import GoldCatalogIncompatible


def _engine_with_live_table(*, mutate_type: bool = False, mutate_grain: bool = False):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS gold_v2")
        expected = TABLES["diagnostico_receita"]
        metadata = MetaData()
        columns = []
        for column in expected.columns:
            column_type = column.type
            primary_key = column.primary_key
            if mutate_type and column.name == "receita_total_reais":
                column_type = Numeric(38, 0)
            if mutate_grain and column.name == "possui_gd":
                primary_key = False
            columns.append(
                Column(
                    column.name,
                    column_type,
                    nullable=column.nullable,
                    primary_key=primary_key,
                )
            )
        Table(expected.name, metadata, *columns, schema="gold_v2")
        metadata.create_all(connection)
    return engine


def test_live_catalog_accepts_matching_schema_without_reading_gold_rows():
    engine = _engine_with_live_table()
    try:
        with engine.connect() as connection:
            assert_live_f1_catalog(
                connection,
                frozenset({"geography.municipality", "customer.consumption_class"}),
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("mutation", ["type", "grain"])
def test_live_catalog_rejects_schema_and_grain_drift(mutation):
    engine = _engine_with_live_table(
        mutate_type=mutation == "type",
        mutate_grain=mutation == "grain",
    )
    try:
        with engine.connect() as connection, pytest.raises(GoldCatalogIncompatible):
            assert_live_f1_catalog(connection, frozenset())
    finally:
        engine.dispose()
