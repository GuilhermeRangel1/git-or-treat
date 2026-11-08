"""Execução PostgreSQL real; metadados/prontidão da admissão são artificiais.

Requer banco novo descartável text_to_sql_f1_test e não reaproveita schemas.
"""

import asyncio
import os
from dataclasses import replace

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.models.gold_v2 import TABLES
from app.services.genai_client import GenAITimeout
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_admission import SqlAdmissionDenied
from app.services.genai_sql_executor import execute_sql_admission
from app.services.genai_sql_pipeline import run_sql_question
from app.services.genai_sql_structure import SqlStructureRejected
from app.services.gold_catalog import GoldCatalogIncompatible
from tests.test_genai_sql_admission import Environment
from tests.test_genai_sql_comparison import comparison
from tests.test_genai_sql_semantics import (
    accumulated_satisfaction_candidate,
    gd_consumption_query,
    gd_units_candidate,
    query,
    satisfaction_candidate,
)
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
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS gold_v2 CASCADE")
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS gold CASCADE")
            connection.exec_driver_sql("DROP ROLE IF EXISTS venergy_genai_reader")
            connection.exec_driver_sql("CREATE SCHEMA gold")
            connection.exec_driver_sql("CREATE SCHEMA gold_v2")
            connection.exec_driver_sql("CREATE TABLE gold.publicacao_atual ("
                "schema_version text, lote text, publication_id text)")
            connection.exec_driver_sql("INSERT INTO gold.publicacao_atual VALUES "
                "('gold-csv-v2', 'GOLD_20000101T000000Z_aaaaaaaa', "
                "'12345678-1234-4123-8123-123456789abc')")
            TABLES["diagnostico_receita"].create(connection)
            TABLES["atendimentos_uc"].create(connection)
            TABLES["variacao_consumo_uc"].create(connection)
            connection.execute(text("INSERT INTO gold_v2.diagnostico_receita "
                "(competencia, municipio, classe_consumo, subgrupo_tarifario, bandeira_tarifaria, possui_gd, receita_total_reais, consumo_total_kwh) VALUES "
                "(:month, :city, :class, 'SINTETICO', 'SINTETICA', :gd, :value, :kwh)"), [
                {"month": "2026-06", "city": "Recife", "class": "RESIDENCIAL",
                 "gd": "Sim", "value": "100.01", "kwh": 12.5},
                {"month": "2026-06", "city": "Recife", "class": "COMERCIAL",
                 "gd": "Não", "value": "50.02", "kwh": 30.0},
                {"month": "2025-06", "city": "Recife", "class": "RESIDENCIAL",
                 "gd": "Sim", "value": "80.00", "kwh": 10.0},
                {"month": "2026-06", "city": "Olinda", "class": "RESIDENCIAL",
                 "gd": "Sim", "value": "900.00", "kwh": 999.0},
            ])
            connection.execute(text(
                "INSERT INTO gold_v2.atendimentos_uc (protocolo, data_abertura, nota_satisfacao) "
                "VALUES (:protocol, :opened, :score)"
            ), [
                {"protocol": "SYN-1", "opened": "2026-06-01T00:00:00+00:00", "score": 4.5},
                {"protocol": "SYN-2", "opened": "2026-06-15T12:00:00+00:00", "score": 0.0},
                {"protocol": "SYN-3", "opened": "2026-06-30T23:59:59+00:00", "score": None},
                {"protocol": "SYN-4", "opened": "2026-07-01T00:00:00+00:00", "score": 1.0},
            ])
            connection.execute(text(
                "INSERT INTO gold_v2.variacao_consumo_uc (id_uc, municipio, possui_gd) "
                "VALUES (:unit, :city, :gd)"
            ), [
                {"unit": "SYN-GD-1", "city": "Recife", "gd": "Sim"},
                {"unit": "SYN-GD-2", "city": "Recife", "gd": "Sim"},
                {"unit": "SYN-GD-3", "city": "Olinda", "gd": "Sim"},
                {"unit": "SYN-GD-4", "city": "Recife", "gd": "Não"},
            ])
            connection.exec_driver_sql("CREATE ROLE venergy_genai_reader LOGIN "
                "NOSUPERUSER NOBYPASSRLS PASSWORD 'synthetic-test-only'")
            connection.exec_driver_sql("GRANT USAGE ON SCHEMA gold, gold_v2 TO venergy_genai_reader")
            connection.exec_driver_sql("GRANT SELECT ON gold.publicacao_atual, "
                "gold_v2.diagnostico_receita, gold_v2.atendimentos_uc TO venergy_genai_reader")
            connection.exec_driver_sql(
                "GRANT SELECT ON gold_v2.variacao_consumo_uc TO venergy_genai_reader"
            )
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
    env.assert_current = publication.assert_current
    env.generated_candidate = candidate
    async def generate_sql_candidate(payload, *, correlation_id):
        from app.schemas.sql_generation import SqlGenerationResponse
        return SqlGenerationResponse(correlation_id=correlation_id,
                                     candidate=env.generated_candidate)
    env.generate_sql_candidate = generate_sql_candidate
    server_cursors = []

    def observe_cursor(connection, cursor, statement, parameters, context, executemany):
        if "SELECT SUM" in statement:
            server_cursors.append(getattr(cursor, "name", None))

    event.listen(reader, "after_cursor_execute", observe_cursor)
    try:
        run = asyncio.run(run_sql_question(
            request, **env.kwargs()))
    finally:
        event.remove(reader, "after_cursor_execute", observe_cursor)
    assert len(server_cursors) == 1 and server_cursors[0]
    assert run.evidence is not None
    with owner.connect() as control:
        independent_total = control.execute(text(
            "SELECT SUM(receita_total_reais) FROM gold_v2.diagnostico_receita "
            "WHERE competencia = '2026-06' AND municipio = 'Recife'"
        )).scalar_one()
    if mode == "comparison":
        assert run.evidence.rows == (("150.03", "80.00", "70.03", "87.54"),)
        with owner.connect() as control:
            independent_previous = control.execute(text(
                "SELECT SUM(receita_total_reais) FROM gold_v2.diagnostico_receita "
                "WHERE competencia = '2025-06' AND municipio = 'Recife'"
            )).scalar_one()
        assert run.evidence.rows[0] == (str(independent_total), str(independent_previous),
                                         str(independent_total - independent_previous),
                                         "87.54")
    else:
        assert run.evidence.rows == ((str(independent_total),),)
    assert run.evidence.batch_ref == request.batch_ref
    assert run.evidence.status == "available"
    assert reader.pool.checkedout() == 0


def test_real_restricted_snapshot_preserves_explicit_gd_consumption_filter(sql_request, engines):
    owner, reader = engines
    candidate, request = gd_consumption_query(sql_request)
    env = Environment(request)
    env.analytic_engine, env.readiness_engine = reader, owner
    publication = GoldPublicationContext.capture(reader)
    env.execution_snapshot = publication.execution_snapshot
    env.assert_current = publication.assert_current
    env.generated_candidate = candidate

    async def generate_sql_candidate(payload, *, correlation_id):
        from app.schemas.sql_generation import SqlGenerationResponse

        assert "possui_gd" in payload.contents
        return SqlGenerationResponse(
            correlation_id=correlation_id,
            generation_contract_version=env.generated_candidate.generation_contract_version,
            candidate=env.generated_candidate,
        )

    env.generate_sql_candidate = generate_sql_candidate
    run = asyncio.run(run_sql_question(request, **env.kwargs()))
    assert run.evidence is not None
    with owner.connect() as control:
        expected = control.execute(text(
            "SELECT SUM(consumo_total_kwh) FROM gold_v2.diagnostico_receita "
            "WHERE competencia = '2026-06' AND municipio = 'Recife' AND possui_gd = 'Sim'"
        )).scalar_one()
    assert run.evidence.rows == ((format(expected, ".2f"),),)
    assert run.evidence.rows == (("12.50",),)
    assert reader.pool.checkedout() == 0


def test_real_restricted_snapshot_averages_satisfaction_including_zero_and_ignoring_null(
    sql_request, engines,
):
    owner, reader = engines
    candidate, request = satisfaction_candidate(sql_request)
    env = Environment(request)
    env.analytic_engine, env.readiness_engine = reader, owner
    publication = GoldPublicationContext.capture(reader)
    env.execution_snapshot = publication.execution_snapshot
    env.assert_current = publication.assert_current
    env.generated_candidate = candidate

    async def generate_sql_candidate(payload, *, correlation_id):
        from app.schemas.sql_generation import SqlGenerationResponse

        return SqlGenerationResponse(
            correlation_id=correlation_id,
            generation_contract_version=env.generated_candidate.generation_contract_version,
            candidate=env.generated_candidate,
        )

    env.generate_sql_candidate = generate_sql_candidate
    run = asyncio.run(run_sql_question(request, **env.kwargs()))
    assert run.evidence is not None
    with owner.connect() as control:
        expected = control.execute(text(
            "SELECT AVG(nota_satisfacao) FROM gold_v2.atendimentos_uc "
            "WHERE data_abertura >= '2026-06-01T00:00:00Z' "
            "AND data_abertura < '2026-07-01T00:00:00Z'"
        )).scalar_one()
    assert run.evidence.metric_id == "service.satisfaction"
    assert run.evidence.evidence_contract_version == "text-to-sql-f1-evidence-v7"
    assert run.evidence.rows == ((format(expected, ".2f"),),) == (("2.25",),)
    assert run.evidence.coverage_quality == "certified"
    assert reader.pool.checkedout() == 0


def test_real_restricted_snapshot_counts_gd_registry_units_once(sql_request, engines):
    owner, reader = engines
    candidate, request = gd_units_candidate(sql_request)
    env = Environment(request)
    env.analytic_engine, env.readiness_engine = reader, owner
    publication = GoldPublicationContext.capture(reader)
    env.execution_snapshot = publication.execution_snapshot
    env.assert_current = publication.assert_current
    env.generated_candidate = candidate

    async def generate_sql_candidate(payload, *, correlation_id):
        from app.schemas.sql_generation import SqlGenerationResponse

        return SqlGenerationResponse(
            correlation_id=correlation_id,
            generation_contract_version=env.generated_candidate.generation_contract_version,
            candidate=env.generated_candidate,
        )

    env.generate_sql_candidate = generate_sql_candidate
    run = asyncio.run(run_sql_question(request, **env.kwargs()))
    assert run.evidence is not None
    with owner.connect() as control:
        expected = control.execute(text(
            "SELECT COUNT(possui_gd) FROM gold_v2.variacao_consumo_uc "
            "WHERE possui_gd = 'Sim'"
        )).scalar_one()
    assert run.evidence.metric_id == "energy.gd_units"
    assert run.evidence.evidence_contract_version == "text-to-sql-f1-evidence-v8"
    assert run.evidence.rows == ((str(expected),),) == (("3",),)
    assert run.evidence.source_table == "gold_v2.variacao_consumo_uc"
    assert reader.pool.checkedout() == 0


def test_real_restricted_snapshot_averages_all_published_satisfaction_notes(
    sql_request, engines,
):
    owner, reader = engines
    candidate, request = accumulated_satisfaction_candidate(sql_request)
    env = Environment(request)
    env.analytic_engine, env.readiness_engine = reader, owner
    publication = GoldPublicationContext.capture(reader)
    env.execution_snapshot = publication.execution_snapshot
    env.assert_current = publication.assert_current
    env.generated_candidate = candidate

    async def generate_sql_candidate(payload, *, correlation_id):
        from app.schemas.sql_generation import SqlGenerationResponse

        return SqlGenerationResponse(
            correlation_id=correlation_id,
            generation_contract_version=env.generated_candidate.generation_contract_version,
            candidate=env.generated_candidate,
        )

    env.generate_sql_candidate = generate_sql_candidate
    run = asyncio.run(run_sql_question(request, **env.kwargs()))
    assert run.evidence is not None
    with owner.connect() as control:
        expected = control.execute(text(
            "SELECT AVG(nota_satisfacao) FROM gold_v2.atendimentos_uc"
        )).scalar_one()
    assert run.evidence.metric_id == "service.accumulated_satisfaction"
    assert run.evidence.evidence_contract_version == "text-to-sql-f1-evidence-v9"
    assert run.evidence.rows == ((format(expected, ".2f"),),)
    assert run.evidence.interpretation.periods == ()
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


@pytest.mark.parametrize("change", ["sql", "parameter", "identity", "publication", "policy", "expiry", "artifact"])
def test_changed_admission_never_sends_candidate_to_postgres(sql_request, engines, monkeypatch, change):
    owner, reader = engines
    candidate = query(sql_request)
    env = Environment(sql_request)
    env.analytic_engine, env.readiness_engine = reader, owner
    publication = GoldPublicationContext.capture(reader)
    env.execution_snapshot = publication.execution_snapshot
    admitted = env.admit(candidate)
    if change == "sql":
        candidate = candidate.model_copy(update={"sql": candidate.sql + " LIMIT 1"})
    elif change == "parameter":
        candidate.parameters["city"] = candidate.parameters["city"].model_copy(update={"value": "Olinda"})
    elif change == "identity":
        env.scope = env.scope.model_copy(update={"caller_ref": "session:" + "b" * 64})
    elif change == "publication":
        env.batch_ref = env.batch_ref.replace("aaaaaaaa", "bbbbbbbb")
    elif change == "policy":
        monkeypatch.setattr("app.services.genai_sql_admission.SQL_ADMISSION_POLICY_VERSION", "changed")
    elif change == "expiry":
        env.now[0] = 21
    else:
        admitted = replace(admitted, digest="0" * 64)
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(reader, "before_cursor_execute", observe)
    try:
        with pytest.raises((SqlAdmissionDenied, SqlStructureRejected)):
            asyncio.run(execute_sql_admission(admitted, candidate, sql_request, **env.kwargs()))
    finally:
        event.remove(reader, "before_cursor_execute", observe)
    assert statements == []
    assert reader.pool.checkedout() == 0


@pytest.mark.parametrize("change", ["grant", "schema"])
def test_physical_drift_after_admission_blocks_business_sql(sql_request, engines, change):
    owner, reader = engines
    candidate = query(sql_request)
    env = Environment(sql_request)
    env.analytic_engine, env.readiness_engine = reader, owner
    env.execution_snapshot = GoldPublicationContext.capture(reader).execution_snapshot
    admitted = env.admit(candidate)
    with owner.begin() as connection:
        if change == "grant":
            connection.exec_driver_sql("REVOKE SELECT ON gold_v2.diagnostico_receita FROM venergy_genai_reader")
        else:
            connection.exec_driver_sql("ALTER TABLE gold_v2.diagnostico_receita ALTER COLUMN consumo_total_kwh TYPE numeric(38,2)")
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(reader, "before_cursor_execute", observe)
    try:
        with pytest.raises(GoldCatalogIncompatible):
            asyncio.run(execute_sql_admission(admitted, candidate, sql_request, **env.kwargs()))
        assert admitted.review.canonical_sql not in statements
        assert reader.pool.checkedout() == 0
    finally:
        event.remove(reader, "before_cursor_execute", observe)
        with owner.begin() as connection:
            if change == "grant":
                connection.exec_driver_sql("GRANT SELECT ON gold_v2.diagnostico_receita TO venergy_genai_reader")
            else:
                connection.exec_driver_sql("ALTER TABLE gold_v2.diagnostico_receita ALTER COLUMN consumo_total_kwh TYPE double precision")
