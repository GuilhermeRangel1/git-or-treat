"""Sessão real → dependências FastAPI → papel restrito no PostgreSQL descartável."""

import os
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import router as auth_router
from app.core.config import settings
from app.core.database import get_db
from app.core.genai_gold_access import get_genai_gold_access_resolver
from app.core.genai_gold_database import (
    GOLD_READER_ROLE,
    create_genai_gold_engine,
    get_genai_gold_engine,
)
from app.core.passwords import hash_password
from app.models.auth import AuthSession, AuthUser
from app.models.gold_load import BATCH
from app.models.gold_v2_load import TABLES
from app.schemas.ai import AIQuestionRequest
from app.schemas.genai_internal import AccessScope, QuestionPlanResponse
from app.schemas.genai_plan import LogicalReadPlan, QuestionPlanStatus, ReadWindow
from app.services.genai_client import GenAITimeout
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_executor import GoldExecutionDenied, _query, execute_gold_plan
from app.services.genai_planning import plan_gold_question
from app.services.gold_catalog import load_gold_catalog
from app.services.gold_import import import_gold
from tests.support.migrations import migrated_database
from tests.test_gold_import import batch  # noqa: F401 - fixture compartilhada


def test_session_selects_reader_and_database_denies_prohibited_access(batch, monkeypatch):  # noqa: F811
    admin_url = os.getenv("TEST_GOLD_READER_ADMIN_URL")
    migrator_url = os.getenv("TEST_POSTGRES_URL")
    if not admin_url or not migrator_url:
        pytest.skip("Configure PostgreSQL descartável com gold_reader_test.")
    address = make_url(admin_url)
    migrator = make_url(migrator_url)
    assert address.database == "gold_reader_test" and address.get_backend_name() == "postgresql"
    assert (address.host, address.port) == (migrator.host, migrator.port)
    owner_url = migrator.set(database="gold_reader_test")
    owner = create_engine(owner_url, hide_parameters=True)
    admin = create_engine(address, hide_parameters=True)
    created_engines = []
    scopes = []
    revoked = {"after_admission": False}
    reader_sql = []
    reader_events = []

    def observe_sql(conn, _cursor, statement, _parameters, _context, _many):
        if conn.engine.url.username == GOLD_READER_ROLE:
            reader_sql.append(statement)
            reader_events.append((statement, _parameters))

    event.listen(Engine, "before_cursor_execute", observe_sql)
    try:
        with owner.connect() as connection, migrated_database(connection):
            import_gold(owner, batch)
            with owner.begin() as write:
                write.execute(BATCH.update().values(schema_version="gold-csv-v2"))
                write.execute(TABLES["diagnostico_receita"].insert(), {
                    "competencia": "2001-01", "municipio": "Cidade Teste", "classe_consumo": "TESTE",
                    "subgrupo_tarifario": "T", "bandeira_tarifaria": "T", "possui_gd": "N",
                    "receita_total_reais": 12,
                    "consumo_total_kwh": 30,
                    "receita_base_comparavel_reais": 10,
                    "consumo_base_comparavel_kwh": 4,
                    "qtd_ucs_com_leitura": 2,
                    "qtd_ucs_distintas_faturadas_no_mes": 3,
                })
                write.execute(TABLES["diagnostico_receita"].insert(), {
                    "competencia": "2001-01", "municipio": "Outra Cidade", "classe_consumo": "TESTE",
                    "subgrupo_tarifario": "T", "bandeira_tarifaria": "T", "possui_gd": "N",
                    "receita_total_reais": 999,
                    "qtd_ucs_distintas_faturadas_no_mes": 1,
                })
                write.execute(TABLES["diagnostico_receita"].insert(), {
                    "competencia": "2001-01", "municipio": "Zero Teste", "classe_consumo": "TESTE",
                    "subgrupo_tarifario": "T", "bandeira_tarifaria": "T", "possui_gd": "N",
                    "receita_total_reais": 0,
                    "qtd_ucs_distintas_faturadas_no_mes": 1,
                })
                write.execute(TABLES["diagnostico_receita"].insert(), {
                    "competencia": "2001-01", "municipio": "Nulo Teste", "classe_consumo": "TESTE",
                    "subgrupo_tarifario": "T", "bandeira_tarifaria": "T", "possui_gd": "N",
                    "receita_total_reais": None,
                    "qtd_ucs_distintas_faturadas_no_mes": 1,
                })
                write.execute(TABLES["indicadores_dec_fec"].insert(), {
                    "id_alimentador": "AL-TESTE",
                    "municipio": "Cidade Teste",
                    "competencia": "2001-01",
                    "total_ucs_alimentador": 2,
                    "DEC": 1.5,
                    "FEC": 0.5,
                })
            # Prova do compilador, não autorização do papel leitor: dados
            # artificiais isolados são consultados apenas pela conexão de teste.
            catalog = load_gold_catalog()
            with owner.begin() as compiler_db:
                compiler_db.execute(TABLES["atendimentos_uc"].delete())
                compiler_db.execute(TABLES["visao_360_uc"].delete())
                compiler_db.execute(TABLES["atendimentos_uc"].insert(), [
                    {"protocolo": "P1", "data_abertura": datetime.fromisoformat(
                        "2001-01-31T22:00:00-03:00"), "nota_satisfacao": 0.0},
                    {"protocolo": "P2", "data_abertura": datetime.fromisoformat(
                        "2001-02-01T01:00:00+00:00"), "nota_satisfacao": 4.0},
                    {"protocolo": "P3", "data_abertura": None, "nota_satisfacao": None},
                ])
                compiler_db.execute(TABLES["visao_360_uc"].insert(), [
                    {"id_uc": "COMPILER1", "total_chamados_callcenter": 2},
                    {"id_uc": "COMPILER2", "total_chamados_callcenter": 3},
                ])
                for metric_id, expected in (
                    ("service.attendance", 2), ("service.satisfaction", 2.0),
                    ("service.accumulated_attendance", 5),
                    ("service.accumulated_satisfaction", 2.0),
                ):
                    metric = next(m for m in catalog.metrics if m.metric_id == metric_id)
                    window = (
                        {"kind": "catalog_phrase", "phrase": metric.accumulated_period_phrases[0]}
                        if metric.accumulated_period_phrases else
                        {"kind": "bounded", "start": "2001-02-01", "end": "2001-02-28",
                         "granularity": "month"}
                    )
                    compiler_plan = LogicalReadPlan.model_validate({
                        "catalog_version": "v1", "operation": "read",
                        "profile_id": catalog.profile_id, "source_id": "gold.local",
                        "domain_id": "service", "metric_id": metric_id,
                        "unit": metric.unit, "window": window, "limit": 10,
                    })
                    statement = _query(compiler_plan, metric.sources[0], metric)
                    rows = compiler_db.execute(statement).mappings().all()
                    assert len(rows) == 1 and rows[0]["value"] == expected
                    assert rows[0]["period"] == (
                        window.get("phrase") or "2001-02"
                    )
                compiler_db.execute(TABLES["atendimentos_uc"].delete())
                compiler_db.execute(TABLES["visao_360_uc"].delete())
            with Session(owner) as db:
                for name in ("reader", "operator"):
                    db.add(AuthUser(
                        id=str(uuid4()), username=name,
                        password_hash=hash_password("synthetic-test-password"),
                        permissions=["orders:read"] if name == "reader" else ["orders:write"],
                        is_active=True,
                    ))
                db.commit()
            sql = (Path(__file__).parents[1] / "scripts/provision_genai_gold_reader.sql").read_text(encoding="utf-8")
            sql = "\n".join(line for line in sql.splitlines() if not line.startswith("\\"))
            password = uuid4().hex
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as administrator:
                # A revisão de PUBLIC é explícita e ocorre apenas no banco descartável.
                administrator.exec_driver_sql("REVOKE TEMP ON DATABASE gold_reader_test FROM PUBLIC")
                administrator.exec_driver_sql(
                    "CREATE FUNCTION public.genai_private_probe() RETURNS integer "
                    "LANGUAGE SQL SECURITY DEFINER AS "
                    "'SELECT count(*)::integer FROM public.auth_users'"
                )
                administrator.exec_driver_sql("REVOKE EXECUTE ON FUNCTION public.genai_private_probe() FROM PUBLIC")
                administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql(f"ALTER ROLE {GOLD_READER_ROLE} PASSWORD '{password}'")
            reader_url = address.set(username=GOLD_READER_ROLE, password=password)
            monkeypatch.setattr(settings, "DATABASE_URL", owner_url.render_as_string(hide_password=False))
            monkeypatch.setattr(settings, "GENAI_GOLD_DATABASE_URL", SecretStr(reader_url.render_as_string(hide_password=False)))
            monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")

            def operational_db():
                with Session(owner) as db:
                    yield db

            api = FastAPI()
            api.include_router(auth_router, prefix="/api/v1/auth")
            api.dependency_overrides[get_db] = operational_db

            class PlannedClient:
                def __init__(self, next_plan):
                    self.next_plan = next_plan

                async def plan(self, _request, *, correlation_id):
                    return QuestionPlanResponse(
                        correlation_id=correlation_id,
                        status=QuestionPlanStatus.PLANNED,
                        plan=self.next_plan,
                        plan_fingerprint=self.next_plan.fingerprint(),
                    )

            @api.get("/api/v1/probe")
            async def probe(
                reader: Annotated[Engine, Depends(get_genai_gold_engine)],
                resolve: Annotated[Callable[[], AccessScope], Depends(get_genai_gold_access_resolver)],
            ):
                created_engines.append(reader)
                if revoked["after_admission"]:
                    with owner.begin() as write:
                        write.execute(update(AuthUser).values(permissions=[]))
                scope = resolve()
                scopes.append(scope)
                plan = LogicalReadPlan.model_validate({
                    "catalog_version": "v1",
                    "operation": "read",
                    "profile_id": "v-energy-grid-360-gold",
                    "source_id": "gold.local",
                    "domain_id": "revenue",
                    "metric_id": "billing.revenue",
                    "dimension_ids": ["geography.municipality"],
                    "filters": [{
                        "dimension_id": "geography.municipality",
                        "operator": "eq",
                        "values": ["Cidade Teste"],
                    }],
                    "unit": "R$",
                    "window": {
                        "kind": "bounded",
                        "start": "2001-01-01",
                        "end": "2001-01-31",
                        "granularity": "month",
                    },
                    "limit": 10,
                })
                planned = await plan_gold_question(
                    reader,
                    PlannedClient(plan),
                    AIQuestionRequest(question="Receita em Cidade Teste em janeiro de 2001"),
                    resolve_scope=resolve,
                    correlation_id="a" * 32,
                )
                async def plan_read(next_plan, correlation_id):
                    return await plan_gold_question(
                        reader,
                        PlannedClient(next_plan),
                        AIQuestionRequest(question="Consulta sintética de evidência"),
                        resolve_scope=resolve,
                        correlation_id=correlation_id,
                    )

                # Adulteração após planejar também falha antes de abrir snapshot/SQL.
                for changes in (
                    {"metric_id": "billing.reserved"},
                    {"limit": 101},
                    {"unit": "unidade adulterada"},
                    {"window": ReadWindow.model_validate({
                        "kind": "catalog_phrase", "phrase": "último ano",
                    })},
                ):
                    tampered_plan = plan.model_copy(update=changes)
                    tampered_response = planned.response.model_copy(update={
                        "plan": tampered_plan,
                        "plan_fingerprint": tampered_plan.fingerprint(),
                    })
                    before_sql = len(reader_events)
                    with pytest.raises(GoldExecutionDenied):
                        execute_gold_plan(
                            reader, replace(planned, response=tampered_response),
                            resolve_scope=resolve,
                        )
                    assert len(reader_events) == before_sql

                before_expired = len(reader_events)
                with pytest.raises(GenAITimeout):
                    execute_gold_plan(
                        reader,
                        replace(planned, deadline=GenAIRequestDeadline(0, lambda: 1)),
                        resolve_scope=resolve,
                    )
                assert len(reader_events) == before_expired
                lookup = execute_gold_plan(reader, planned, resolve_scope=resolve)
                assert lookup.status.value == "available"
                assert lookup.evidence is not None
                assert lookup.evidence.records == [
                    {"value": 12.0, "unit": "R$", "period": "2001-01"}
                ]
                # Contenção real: o servidor cancela o SQL, e o snapshot devolve
                # a conexão sem deixar transação abortada no pool.
                with owner.connect() as blocker:
                    blocker.exec_driver_sql(
                        "LOCK TABLE gold_v2.diagnostico_receita IN ACCESS EXCLUSIVE MODE"
                    )
                    try:
                        with monkeypatch.context() as timeout_patch:
                            timeout_patch.setattr(
                                "app.services.genai_executor.SQL_STATEMENT_TIMEOUT", "25ms"
                            )
                            with pytest.raises(DBAPIError) as cancelled:
                                execute_gold_plan(reader, planned, resolve_scope=resolve)
                            assert cancelled.value.orig.sqlstate == "57014"
                    finally:
                        blocker.rollback()
                assert reader.pool.checkedout() == 0
                recovered = execute_gold_plan(reader, planned, resolve_scope=resolve)
                assert recovered.evidence.records == lookup.evidence.records

                ticket_plan = LogicalReadPlan.model_validate({
                    **plan.model_dump(mode="json"),
                    "metric_id": "billing.average_ticket",
                    "unit": "R$ por UC faturada no mês",
                    "order": {"field_id": "billing.average_ticket", "direction": "desc"},
                })
                ticket_planned = await plan_read(ticket_plan, "b" * 32)
                ticket_result = execute_gold_plan(reader, ticket_planned, resolve_scope=resolve)
                assert ticket_result.evidence is not None
                assert ticket_result.evidence.records == [{
                    "value": 4.0,
                    "unit": "R$ por UC faturada no mês",
                    "period": "2001-01",
                }]
                # Esperados literais independentes das expressões do compilador.
                for metric_id, domain_id, unit, expected in (
                    ("energy.consumption", "consumption", "kWh", 30.0),
                    ("billing.effective_tariff", "revenue", "R$/kWh", 2.5),
                    ("energy.average_consumption_per_uc", "consumption",
                     "kWh por UC com leitura no mês", 15.0),
                ):
                    metric_plan = LogicalReadPlan.model_validate({
                        **plan.model_dump(mode="json"),
                        "metric_id": metric_id, "domain_id": domain_id, "unit": unit,
                    })
                    metric_planned = await plan_read(metric_plan, "2" * 32)
                    metric_result = execute_gold_plan(reader, metric_planned, resolve_scope=resolve)
                    assert metric_result.evidence.records == [{
                        "value": expected, "unit": unit, "period": "2001-01",
                    }]
                dec_plan = LogicalReadPlan.model_validate({
                    "catalog_version": "v1",
                    "operation": "read",
                    "profile_id": "v-energy-grid-360-gold",
                    "source_id": "gold.local",
                    "domain_id": "network",
                    "metric_id": "network.equivalent_interruption_duration",
                    "dimension_ids": ["network.feeder"],
                    "filters": [{
                        "dimension_id": "network.feeder",
                        "operator": "eq",
                        "values": ["AL-TESTE"],
                    }],
                    "unit": "horas por UC",
                    "window": {
                        "kind": "bounded",
                        "start": "2001-01-01",
                        "end": "2001-01-31",
                        "granularity": "month",
                    },
                    "limit": 10,
                })
                dec_planned = await plan_read(dec_plan, "1" * 32)
                dec = execute_gold_plan(reader, dec_planned, resolve_scope=resolve)
                assert dec.evidence is not None
                assert dec.evidence.records == [{
                    "value": 1.5,
                    "unit": "horas por UC",
                    "period": "2001-01",
                    "feeder": "AL-TESTE",
                }]
                fec_plan = LogicalReadPlan.model_validate({
                    **dec_plan.model_dump(mode="json"),
                    "metric_id": "network.equivalent_interruption_frequency",
                    "unit": "interrupções por UC",
                })
                fec_planned = await plan_read(fec_plan, "3" * 32)
                fec = execute_gold_plan(reader, fec_planned, resolve_scope=resolve)
                assert fec.evidence.records == [{
                    "value": 0.5, "unit": "interrupções por UC",
                    "period": "2001-01", "feeder": "AL-TESTE",
                }]
                grouped_plan = LogicalReadPlan.model_validate({
                    **plan.model_dump(mode="json"),
                    "filters": [{
                        "dimension_id": "geography.municipality",
                        "operator": "in",
                        "values": ["Cidade Teste", "Outra Cidade", "Zero Teste"],
                    }],
                    "group_by_dimension_ids": ["geography.municipality"],
                    "order": {"field_id": "billing.revenue", "direction": "desc"},
                    "limit": 10,
                })
                grouped_planned = await plan_read(grouped_plan, "c" * 32)
                grouped = execute_gold_plan(reader, grouped_planned, resolve_scope=resolve)
                assert grouped.evidence is not None
                assert [item["value"] for item in grouped.evidence.records] == [
                    999.0, 12.0, 0.0,
                ]
                assert grouped.evidence.records[0]["municipality"] == "Outra Cidade"
                truncated_plan = LogicalReadPlan.model_validate({
                    **grouped_plan.model_dump(mode="json"), "limit": 1,
                })
                truncated_planned = await plan_read(truncated_plan, "f" * 32)
                truncated = execute_gold_plan(reader, truncated_planned, resolve_scope=resolve)
                assert truncated.status.value == "needs_clarification"
                zero_plan = LogicalReadPlan.model_validate({
                    **plan.model_dump(mode="json"),
                    "filters": [{
                        "dimension_id": "geography.municipality",
                        "operator": "eq",
                        "values": ["Zero Teste"],
                    }],
                })
                zero_planned = await plan_read(zero_plan, "d" * 32)
                zero = execute_gold_plan(reader, zero_planned, resolve_scope=resolve)
                assert zero.evidence is not None and zero.evidence.records[0]["value"] == 0.0
                empty_plan = LogicalReadPlan.model_validate({
                    **plan.model_dump(mode="json"),
                    "filters": [{"dimension_id": "geography.municipality",
                                 "operator": "eq", "values": ["Sem Dados Teste"]}],
                })
                empty_response = planned.response.model_copy(update={
                    "plan": empty_plan, "plan_fingerprint": empty_plan.fingerprint(),
                })
                empty = execute_gold_plan(
                    reader, replace(planned, response=empty_response), resolve_scope=resolve,
                )
                assert empty.status.value == "no_evidence" and empty.evidence is None
                null_plan = LogicalReadPlan.model_validate({
                    **plan.model_dump(mode="json"),
                    "filters": [{
                        "dimension_id": "geography.municipality",
                        "operator": "eq",
                        "values": ["Nulo Teste"],
                    }],
                })
                null_planned = await plan_read(null_plan, "e" * 32)
                null_result = execute_gold_plan(reader, null_planned, resolve_scope=resolve)
                assert null_result.status.value == "needs_clarification"
                assert "nula" in null_result.message
                with reader.connect() as read:
                    assert read.scalar(text("SELECT current_user")) == GOLD_READER_ROLE
                    assert read.scalar(text("SELECT SUM(receita_total_reais) FROM gold_v2.diagnostico_receita")) == 1011
                    assert read.scalar(text("SHOW statement_timeout")) == "5s"
                assert any(
                    "municipio" in statement.lower()
                    and "Cidade Teste" not in statement
                    and "Cidade Teste" in str(parameters)
                    for statement, parameters in reader_events
                )
                executor_queries = [
                    statement.lower()
                    for statement, _parameters in reader_events
                    if "select" in statement.lower()
                    and "gold_v2.diagnostico_receita" in statement.lower()
                ]
                assert executor_queries
                assert all(
                    " join " not in statement
                    and " with " not in statement
                    and ";" not in statement
                    for statement in executor_queries
                )
                return {
                    "caller": scope.caller_ref,
                    "read_only": scope.allowed_operations == {"read"},
                    "cache_scopes": [
                        lookup.evidence.cache_scope,
                        ticket_result.evidence.cache_scope,
                    ],
                }

            origin = {"Origin": "http://localhost:5173"}
            with TestClient(api) as client:
                assert client.get("/api/v1/probe").status_code == 401
                callers = []
                cache_scopes = []
                for name in ("reader", "operator"):
                    assert client.post("/api/v1/auth/login", headers=origin, json={
                        "username": name, "password": "synthetic-test-password",
                    }).status_code == 200
                    result = client.get("/api/v1/probe?session_id=admin&scope=all", headers={"X-Access-Scope": "admin"})
                    assert result.status_code == 200
                    assert result.json()["read_only"] is True
                    callers.append(result.json()["caller"])
                    cache_scopes.append(result.json()["cache_scopes"])
                assert callers[0] != callers[1]
                assert all(
                    first != second
                    for first, second in zip(cache_scopes[0], cache_scopes[1], strict=True)
                )
                assert cache_scopes[0][0] != cache_scopes[0][1]
                # Retirada de permissão depois de criar o engine não admite a leitura.
                revoked["after_admission"] = True
                reader_sql.clear()
                assert client.get("/api/v1/probe").status_code == 403
                assert reader_sql == []
                revoked["after_admission"] = False
                with owner.begin() as write:
                    write.execute(update(AuthUser).values(permissions=["orders:read"]))
                assert client.post("/api/v1/auth/logout", headers=origin).status_code == 204
                assert client.get("/api/v1/probe").status_code == 401

            # Contorna a aplicação e o default READ ONLY: ACL efetiva ainda bloqueia.
            engine = created_engines[0]
            forbidden = [
                "SELECT id_uc FROM gold_v2.consumo_mensal_uc",
                "SELECT receita_reais FROM gold_v2.consumo_mensal_uc",
                "SELECT receita_sem_leitura_reais FROM gold_v2.diagnostico_receita",
                "SELECT * FROM gold_v2.atendimentos_uc",
                "SELECT * FROM public.auth_users",
                "SELECT * FROM public.auth_sessions",
                "SELECT * FROM public.operational_inspection_orders",
                "SELECT * FROM public.gold_carga_atual",
                "SELECT public.genai_private_probe()",
                "INSERT INTO gold_v2.diagnostico_receita DEFAULT VALUES",
                "CREATE TABLE gold_v2.forbidden (id integer)",
                "CREATE TEMP TABLE forbidden (id integer)",
                "ALTER TABLE gold_v2.diagnostico_receita ADD COLUMN forbidden integer",
            ]
            for statement in forbidden:
                with engine.connect() as read:
                    read.exec_driver_sql("SET TRANSACTION READ WRITE")
                    with pytest.raises(DBAPIError) as error:
                        read.exec_driver_sql(statement)
                    assert error.value.orig.sqlstate == "42501"
            # O teto do papel vale entre pools distintos, como em requisições
            # concorrentes; saturação não pode deixar conexões emprestadas.
            for existing_engine in created_engines:
                existing_engine.dispose()
            concurrent_engines = [create_genai_gold_engine(scopes[0]) for _ in range(9)]
            created_engines.extend(concurrent_engines)
            held_connections = []
            try:
                for concurrent_engine in concurrent_engines[:8]:
                    held_connections.append(concurrent_engine.connect())
                with pytest.raises(DBAPIError):
                    concurrent_engines[8].connect()
                assert concurrent_engines[8].pool.checkedout() == 0
                with admin.connect() as inspect:
                    assert inspect.scalar(text(
                        "SELECT count(*) FROM pg_stat_activity WHERE usename = :role"
                    ), {"role": GOLD_READER_ROLE}) == 8
                held_connections.pop(0).close()
                concurrent_engines[0].dispose()
                with concurrent_engines[8].connect() as recovered_connection:
                    assert recovered_connection.scalar(text("SELECT 1")) == 1
            finally:
                for held_connection in held_connections:
                    held_connection.close()
                for concurrent_engine in concurrent_engines:
                    concurrent_engine.dispose()
            assert all(item.pool.checkedout() == 0 for item in concurrent_engines)

            # Rotação real no banco descartável: a senha antiga não abre conexão
            # nova; o segredo atualizado volta a usar o mesmo papel restrito.
            new_password = uuid4().hex
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as administrator:
                administrator.exec_driver_sql(f"ALTER ROLE {GOLD_READER_ROLE} PASSWORD '{new_password}'")
            engine.dispose()
            with pytest.raises(DBAPIError) as authentication:
                engine.connect()
            assert password not in str(authentication.value)
            monkeypatch.setattr(settings, "GENAI_GOLD_DATABASE_URL", SecretStr(
                reader_url.set(password=new_password).render_as_string(hide_password=False),
            ))
            rotated_reader = create_genai_gold_engine(scopes[0])
            created_engines.append(rotated_reader)
            with rotated_reader.connect() as read:
                assert read.scalar(text("SELECT current_user")) == GOLD_READER_ROLE
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as administrator:
                administrator.exec_driver_sql("GRANT EXECUTE ON FUNCTION public.genai_private_probe() TO PUBLIC")
                try:
                    with pytest.raises(DBAPIError):
                        administrator.exec_driver_sql(sql)
                    administrator.exec_driver_sql("ROLLBACK")
                finally:
                    administrator.exec_driver_sql("REVOKE EXECUTE ON FUNCTION public.genai_private_probe() FROM PUBLIC")
                administrator.exec_driver_sql("GRANT SELECT ON public.auth_users TO PUBLIC")
                try:
                    with pytest.raises(DBAPIError):
                        administrator.exec_driver_sql(sql)
                    administrator.exec_driver_sql("ROLLBACK")
                finally:
                    administrator.exec_driver_sql("REVOKE SELECT ON public.auth_users FROM PUBLIC")
                administrator.exec_driver_sql("GRANT TEMP ON DATABASE gold_reader_test TO PUBLIC")
                try:
                    with pytest.raises(DBAPIError):
                        administrator.exec_driver_sql(sql)
                    administrator.exec_driver_sql("ROLLBACK")
                finally:
                    administrator.exec_driver_sql("REVOKE TEMP ON DATABASE gold_reader_test FROM PUBLIC")
                administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql("DROP FUNCTION public.genai_private_probe()")
            with owner.connect() as read:
                assert len(read.execute(select(AuthUser.id)).all()) == 2
                assert not read.execute(select(AuthSession.id)).all()
    finally:
        event.remove(Engine, "before_cursor_execute", observe_sql)
        for engine in created_engines:
            engine.dispose()
        owner.dispose()
        admin.dispose()
