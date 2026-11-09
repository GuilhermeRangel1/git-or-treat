"""Oráculos SQL manuais; nunca executa candidato do modelo nem usa banco real."""

import json
import os
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

DATA = json.loads((Path(__file__).parent / "fixtures/text_to_sql_f1_reference.json").read_text(
    encoding="utf-8"
))


@pytest.fixture(scope="module")
def connection():
    address = os.environ.get("TEST_TEXT_TO_SQL_URL")
    if not address:
        pytest.skip("Configure PostgreSQL descartável text_to_sql_f1_test.")
    url = make_url(address)
    if url.get_backend_name() != "postgresql" or url.database != "text_to_sql_f1_test":
        pytest.fail("A referência só admite o banco descartável text_to_sql_f1_test.")
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                # Recusa schema existente; não apaga nenhum objeto para preparar a prova.
                conn.execute(text("CREATE SCHEMA gold_v2"))
                conn.execute(text("""CREATE TABLE gold_v2.diagnostico_receita (
                    competencia text NOT NULL, municipio text NOT NULL,
                    classe_consumo text NOT NULL, bandeira_tarifaria text NOT NULL,
                    receita_total_reais numeric(38,2),
                    subgrupo_tarifario text NOT NULL DEFAULT 'B1',
                    possui_gd text NOT NULL DEFAULT 'Não',
                    UNIQUE (competencia, municipio, classe_consumo, subgrupo_tarifario,
                            bandeira_tarifaria, possui_gd))"""))
                conn.execute(text("""INSERT INTO gold_v2.diagnostico_receita
                    (competencia, municipio, classe_consumo, bandeira_tarifaria,
                     receita_total_reais)
                    VALUES (:competencia, :municipio, :classe_consumo,
                            :bandeira_tarifaria, :receita_total_reais)"""), DATA["rows"])
                yield conn
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.mark.parametrize("case", [c for c in DATA["cases"] if c["reference_sql"]],
                         ids=lambda case: case["id"])
def test_handwritten_sql_matches_independent_literal_expectation(connection, case):
    rows = connection.execute(text(case["reference_sql"]), case["parameters"]).mappings().all()
    actual = [{key: format(value, ".2f") if isinstance(value, Decimal) else value
               for key, value in row.items()} for row in rows]
    assert actual == case["expected_rows"]
    if "expected_difference_reais" in case:
        assert rows[1]["revenue"] - rows[0]["revenue"] == Decimal(case["expected_difference_reais"])


def test_incomplete_year_reference_requires_explicit_new_request():
    case = next(c for c in DATA["cases"] if c["id"] == "F1-02")
    missing = sorted(set(case["requested_competencies"]) - set(DATA["coverage"]))
    assert missing == case["expected_missing_competencies"]
    assert case["reference_sql"] is None
    assert case["expected_status"] == "needs_clarification"


def test_complete_year_has_a_distinct_annual_reference(connection):
    savepoint = connection.begin_nested()
    try:
        connection.execute(text("""INSERT INTO gold_v2.diagnostico_receita
            (competencia, municipio, classe_consumo, bandeira_tarifaria, receita_total_reais)
            VALUES (:month, 'Recife', 'RESIDENCIAL', 'BASE', 100)"""),
            [{"month": f"2026-{month:02}"} for month in range(7, 13)])
        total = connection.execute(text("""SELECT SUM(receita_total_reais)
            FROM gold_v2.diagnostico_receita WHERE municipio = 'Recife'
            AND competencia BETWEEN '2026-01' AND '2026-12'""")).scalar_one()
        assert total == Decimal("1550.00")
    finally:
        savepoint.rollback()


@pytest.mark.parametrize("mode,expected", [
    ("empty", None), ("all_null", None), ("zero", Decimal("0.00")),
])
def test_reference_distinguishes_zero_null_and_absence(connection, mode, expected):
    savepoint = connection.begin_nested()
    try:
        if mode != "empty":
            connection.execute(text("""INSERT INTO gold_v2.diagnostico_receita
                (competencia, municipio, classe_consumo, bandeira_tarifaria, receita_total_reais)
                VALUES ('2026-06', 'Controle Especial', 'RESIDENCIAL', 'BASE', :value)"""),
                {"value": 0 if mode == "zero" else None})
        result = connection.execute(text("""SELECT SUM(receita_total_reais)
            FROM gold_v2.diagnostico_receita WHERE municipio = 'Controle Especial'""")).scalar_one()
        assert result == expected
    finally:
        savepoint.rollback()


def test_reference_preserves_negative_adjustments(connection):
    savepoint = connection.begin_nested()
    try:
        connection.execute(text("""INSERT INTO gold_v2.diagnostico_receita
            (competencia, municipio, classe_consumo, bandeira_tarifaria, receita_total_reais)
            VALUES ('2026-06', 'Recife', 'RESIDENCIAL', 'ESTORNO', -20)"""))
        result = connection.execute(text("""SELECT SUM(receita_total_reais)
            FROM gold_v2.diagnostico_receita
            WHERE municipio = 'Recife' AND competencia = '2026-06'""")).scalar_one()
        assert result == Decimal("180.00")
    finally:
        savepoint.rollback()
