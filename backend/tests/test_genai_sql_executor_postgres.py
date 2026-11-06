"""Execução PostgreSQL real; metadados/prontidão da admissão são artificiais.

Requer banco novo descartável text_to_sql_f1_test e não reaproveita schemas.
"""

import asyncio
import os
from decimal import Decimal

import pytest
from app.services.genai_client import GenAITimeout
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_evidence import build_sql_evidence
from app.services.genai_sql_executor import execute_sql_admission
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from tests.test_genai_sql_admission import Environment
from tests.test_genai_sql_comparison import comparison
from tests.test_genai_sql_semantics import query
from tests.test_genai_sql_structure import sql_request as fixture_sql_request

sql_request = fixture_sql_request


@pytest.fixture(scope="module")
def engines():
    address = os.getenv("TEST_TEXT_TO_SQL_URL")
    if not address:
        pytest.skip("Configure PostgreSQL novo descartável text_to_sql_f1_test.")
    url = make_url(address)
    assert url.drivername == "postgresql+psycopg" and url.database == "text_to_sql_f1_test"
    owner = create_engine(url, hide_parameters=True)
    reader = None
    try:
        with owner.begin() as connection:
            connection.exec_driver_sql("CREATE SCHEMA gold")
            connection.exec_driver_sql("CREATE SCHEMA gold_v2")
            connection.exec_driver_sql("CREATE TABLE gold.publicacao_atual ("
                "schema_version text, lote text, publication_id text)")
            connection.exec_driver_sql("INSERT INTO gold.publicacao_atual VALUES "
                "('gold-csv-v2', 'GOLD_20000101T000000Z_aaaaaaaa', "
                "'12345678-1234-4123-8123-123456789abc')")
            connection.exec_driver_sql("CREATE TABLE gold_v2.diagnostico_receita ("
                "competencia text, municipio text, classe_consumo text, receita_total_reais numeric(38,2))")
            connection.execute(text("INSERT INTO gold_v2.diagnostico_receita VALUES "
                "(:month, :city, :class, :value)"), [
                {"month": "2026-06", "city": "Recife", "class": "RESIDENCIAL", "value": "100.01"},
                {"month": "2026-06", "city": "Recife", "class": "COMERCIAL", "value": "50.02"},
                {"month": "2025-06", "city": "Recife", "class": "RESIDENCIAL", "value": "80.00"},
                {"month": "2026-06", "city": "Olinda", "class": "RESIDENCIAL", "value": "900.00"},
            ])
            connection.exec_driver_sql("CREATE ROLE venergy_genai_reader LOGIN "
                "NOSUPERUSER NOBYPASSRLS PASSWORD 'synthetic-test-only'")
            connection.exec_driver_sql("GRANT USAGE ON SCHEMA gold, gold_v2 TO venergy_genai_reader")
            connection.exec_driver_sql("GRANT SELECT ON gold.publicacao_atual, "
                "gold_v2.diagnostico_receita TO venergy_genai_reader")
        reader = create_engine(url.set(username="venergy_genai_reader", password="synthetic-test-only"),
                               hide_parameters=True, echo=False, pool_size=1, max_overflow=0)
        yield owner, reader
    finally:
        if reader is not None:
            reader.dispose()
        owner.dispose()


@pytest.mark.parametrize("mode", ["total", "comparison"])
def test_real_restricted_snapshot_executes_canonical_candidate(sql_request, engines, mode):
    owner, reader = engines
    request, candidate = comparison(sql_request) if mode == "comparison" else (
        sql_request, query(sql_request))
    env = Environment(request)
    env.analytic_engine = reader
    env.readiness_engine = owner
    publication = GoldPublicationContext.capture(reader)
    assert publication.batch_ref == request.batch_ref
    env.execution_snapshot = publication.execution_snapshot
    admitted = env.admit(candidate)
    server_cursors = []

    def observe_cursor(connection, cursor, statement, parameters, context, executemany):
        if statement == admitted.review.canonical_sql:
            server_cursors.append(getattr(cursor, "name", None))

    event.listen(reader, "after_cursor_execute", observe_cursor)
    try:
        executed = asyncio.run(execute_sql_admission(admitted, candidate, request, **env.kwargs()))
    finally:
        event.remove(reader, "after_cursor_execute", observe_cursor)
    assert len(server_cursors) == 1 and server_cursors[0]
    if mode == "comparison":
        assert executed.result.rows == ((Decimal("150.03"), Decimal("80.00"), Decimal("70.03")),)
    else:
        assert executed.result.rows == ((Decimal("150.03"),),)
    assert executed.batch_ref == request.batch_ref
    assert executed.result.status == "available"
    evidence = build_sql_evidence(executed, admitted, candidate, request,
                                  resolve_scope=lambda: env.scope, deadline=env.deadline)
    expected_rows = (("150.03", "80.00", "70.03"),) if mode == "comparison" else (("150.03",),)
    assert evidence.rows == expected_rows
    assert evidence.result_digest == executed.result_digest
    assert reader.pool.checkedout() == 0


def test_reader_database_role_rejects_writes(engines):
    _, reader = engines
    with pytest.raises(DBAPIError) as exc, reader.begin() as connection:
        connection.execute(text("DELETE FROM gold_v2.diagnostico_receita"))
    assert exc.value.orig.sqlstate == "42501"
    assert reader.pool.checkedout() == 0


def test_lock_timeout_rolls_back_and_returns_reader_connection(sql_request, engines):
    owner, reader = engines
    candidate = query(sql_request)
    env = Environment(sql_request)
    env.analytic_engine, env.readiness_engine = reader, owner
    env.deadline = GenAIRequestDeadline.start(2)
    publication = GoldPublicationContext.capture(reader)
    env.execution_snapshot = publication.execution_snapshot
    admitted = env.admit(candidate)
    with owner.begin() as blocker:
        blocker.exec_driver_sql("LOCK TABLE gold_v2.diagnostico_receita IN ACCESS EXCLUSIVE MODE")
        with pytest.raises((DBAPIError, GenAITimeout)) as exc:
            asyncio.run(execute_sql_admission(admitted, candidate, sql_request, **env.kwargs()))
        if isinstance(exc.value, DBAPIError):
            assert exc.value.orig.sqlstate == "57014"
    assert reader.pool.checkedout() == 0
    with reader.connect() as connection:
        assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1
