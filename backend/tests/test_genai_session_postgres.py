"""Sessão real → dependências FastAPI → papel restrito no PostgreSQL descartável."""

import asyncio
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import httpx
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
from app.schemas.genai_audit import BackendAuditEvent
from app.schemas.genai_internal import AccessScope, QuestionPlanResponse
from app.schemas.genai_plan import LogicalReadPlan, QuestionPlanStatus, ReadWindow
from app.schemas.gold_readiness import GoldReadinessReport
from app.services.genai_audit import AuditStore
from app.services.genai_client import GenAIQuestionClient, GenAITimeout
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_executor import GoldExecutionDenied, _query, execute_gold_plan
from app.services.genai_planning import plan_gold_question
from app.services.genai_replay import execution_artifact, verify_audited_execution
from app.services.gold_catalog import load_gold_catalog
from app.services.gold_import import import_gold
from tests.support.audit_runtime import audit_runtime
from tests.support.genai_transport import GENAI_TRANSPORT_EVENTS, dispatch_genai
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
    probe_created = False

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
                    "competencia": "2001-01", "municipio": "Lumenia", "classe_consumo": "RESIDENCIAL",
                    "subgrupo_tarifario": "T", "bandeira_tarifaria": "T", "possui_gd": "Não",
                    "receita_total_reais": 12,
                    "consumo_total_kwh": 30,
                    "receita_base_comparavel_reais": 10,
                    "consumo_base_comparavel_kwh": 4,
                    "qtd_ucs_com_leitura": 2,
                    "qtd_ucs_distintas_faturadas_no_mes": 3,
                })
                write.execute(TABLES["diagnostico_receita"].insert(), {
                    "competencia": "2001-01", "municipio": "Outra Cidade", "classe_consumo": "RESIDENCIAL",
                    "subgrupo_tarifario": "T", "bandeira_tarifaria": "T", "possui_gd": "Não",
                    "receita_total_reais": 999,
                    "qtd_ucs_distintas_faturadas_no_mes": 1,
                })
                write.execute(TABLES["diagnostico_receita"].insert(), {
                    "competencia": "2001-01", "municipio": "Zero Lumenia", "classe_consumo": "RESIDENCIAL",
                    "subgrupo_tarifario": "T", "bandeira_tarifaria": "T", "possui_gd": "Não",
                    "receita_total_reais": 0,
                    "qtd_ucs_distintas_faturadas_no_mes": 1,
                })
                write.execute(TABLES["diagnostico_receita"].insert(), {
                    "competencia": "2001-01", "municipio": "Nulo Lumenia", "classe_consumo": "TESTE",
                    "subgrupo_tarifario": "T", "bandeira_tarifaria": "T", "possui_gd": "Não",
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
                write.execute(TABLES["consumo_receita_bairro"].insert(), {
                    "competencia": "2001-01", "municipio": "Lumenia",
                    "bairro": "Bairro Ficticio", "classe_consumo": "RESIDENCIAL",
                    "receita_total_reais": 7,
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
                probe_created = True
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

            from app.main import app as runtime_app

            api = FastAPI()
            api.include_router(auth_router, prefix="/api/v1/auth")

            @api.middleware("http")
            async def correlation(request, call_next):
                request.state.correlation_id = "4" * 32
                return await call_next(request)

            monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
            async def controlled_readiness(planned):
                # Contrato de integração: aprovação artificial explícita; não
                # substitui a avaliação real dos controles da publicação.
                return GoldReadinessReport(
                    readiness_version="gold-readiness-v2",
                    batch_ref=planned.publication.batch_ref, lot_state="partial",
                    capabilities={key: {"status": "available"} for key in (
                        "faturamento.receita", "faturamento.receita_bairro",
                        "interrupcoes.dec_fec", "consumo.mensal_uc",
                        "atendimento.mensal", "atendimento.uc_acumulado", "consumo.variacao_uc",
                        "interrupcoes.uc_acumulado", "faturamento.preco_volume",
                    )},
                )
            api.dependency_overrides[get_db] = operational_db
            monkeypatch.setitem(runtime_app.dependency_overrides, get_db, operational_db)

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
                        "values": ["Lumenia"],
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
                    AIQuestionRequest(question="Receita em Lumenia em janeiro de 2001"),
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
                        "kind": "bounded", "start": "1995-01-01", "end": "2001-01-31",
                        "granularity": "month",
                    })},
                    {"window": ReadWindow.model_validate({
                        "kind": "bounded", "start": "1900-01-01", "end": "2000-01-31",
                        "granularity": "month",
                    })},
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
                            # Duas execuções reais concorrentes em pools distintos:
                            # ambas devem cancelar no servidor e devolver conexões.
                            parallel_reader = create_genai_gold_engine(scope)
                            created_engines.append(parallel_reader)
                            with ThreadPoolExecutor(max_workers=2) as workers:
                                futures = [workers.submit(
                                    execute_gold_plan, target, planned,
                                    resolve_scope=lambda: scope,
                                ) for target in (reader, parallel_reader)]
                                for future in futures:
                                    with pytest.raises(DBAPIError) as parallel_cancelled:
                                        future.result(timeout=5)
                                    assert parallel_cancelled.value.orig.sqlstate == "57014"
                            assert parallel_reader.pool.checkedout() == 0

                    finally:
                        blocker.rollback()
                assert reader.pool.checkedout() == 0
                recovered = execute_gold_plan(reader, planned, resolve_scope=resolve)
                assert recovered.evidence.records == lookup.evidence.records
                # Controle independente: SQL fixo, sem compilador do plano/modelo.
                with reader.connect() as control:
                    independent = control.execute(text(
                        "SELECT sum(receita_total_reais) FROM gold_v2.diagnostico_receita "
                        "WHERE competencia = :month AND municipio = :city"
                    ), {"month": "2001-01", "city": "Lumenia"}).scalar_one()
                assert float(independent) == lookup.evidence.records[0]["value"] == 12.0
                artifact = execution_artifact(planned, lookup=lookup)
                reference = AuditStore(owner).record(BackendAuditEvent(
                    correlation_id="9" * 32, stage="source", code="completed",
                    outcome="success", duration_ms=0, caller_ref=scope.caller_ref,
                    plan_id=plan.fingerprint(), batch_ref=planned.publication.batch_ref,
                    artifact=artifact,
                ), service="backend")
                assert "Lumenia" not in artifact.model_dump_json()
                assert verify_audited_execution(
                    AuditStore(owner), reference, reader, planned, resolve_scope=resolve,
                ) is True
                with pytest.raises(GoldExecutionDenied):
                    verify_audited_execution(AuditStore(owner), reference, reader, planned,
                        resolve_scope=lambda: scope.model_copy(update={"allowed_metric_ids": frozenset()}))


                scope_checks = 0

                def revoked_after_query():
                    nonlocal scope_checks
                    scope_checks += 1
                    return scope if scope_checks < 3 else scope.model_copy(update={
                        "allowed_metric_ids": frozenset(),
                    })

                with pytest.raises(GoldExecutionDenied):
                    execute_gold_plan(reader, planned, resolve_scope=revoked_after_query)
                assert scope_checks == 3 and reader.pool.checkedout() == 0
                # A verificação pós-materialização recusou a evidência; uma
                # execução autorizada posterior continua saudável.
                assert execute_gold_plan(reader, planned, resolve_scope=resolve).evidence.records == (
                    lookup.evidence.records
                )
                reader_events.clear()
                short_budget = replace(
                    planned, deadline=GenAIRequestDeadline(0.5, lambda: 0.45),
                )
                execute_gold_plan(reader, short_budget, resolve_scope=resolve)
                configured_timeouts = [
                    parameters["timeout"] for statement, parameters in reader_events
                    if "set_config('statement_timeout'" in statement
                    and isinstance(parameters, dict) and "timeout" in parameters
                ]
                assert configured_timeouts
                assert any(0 < int(value.removesuffix("ms")) <= 50
                           for value in configured_timeouts)

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
                        "values": ["Lumenia", "Outra Cidade", "Zero Lumenia"],
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
                ranked_plan = LogicalReadPlan.model_validate({
                    **grouped_plan.model_dump(mode="json"), "limit": 1,
                })
                ranked_planned = await plan_read(ranked_plan, "b" * 32)
                ranked = execute_gold_plan(reader, ranked_planned, resolve_scope=resolve)
                assert ranked.evidence is not None
                assert [row["value"] for row in ranked.evidence.records] == [999.0]
                truncated_plan = LogicalReadPlan.model_validate({
                    **grouped_plan.model_dump(mode="json"), "limit": 1, "order": None,
                })
                truncated_planned = await plan_read(truncated_plan, "f" * 32)
                truncated = execute_gold_plan(reader, truncated_planned, resolve_scope=resolve)
                assert truncated.status.value == "needs_clarification"
                zero_plan = LogicalReadPlan.model_validate({
                    **plan.model_dump(mode="json"),
                    "filters": [{
                        "dimension_id": "geography.municipality",
                        "operator": "eq",
                        "values": ["Zero Lumenia"],
                    }],
                })
                zero_planned = await plan_read(zero_plan, "d" * 32)
                zero = execute_gold_plan(reader, zero_planned, resolve_scope=resolve)
                assert zero.evidence is not None and zero.evidence.records[0]["value"] == 0.0
                empty_plan = LogicalReadPlan.model_validate({
                    **plan.model_dump(mode="json"),
                    "filters": [{"dimension_id": "geography.municipality",
                                 "operator": "eq", "values": ["Sem Dados Lumenia"]}],
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
                        "values": ["Nulo Lumenia"],
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
                    assert read.scalar(text("SHOW lock_timeout")) == "2s"
                    assert read.scalar(text("SHOW idle_in_transaction_session_timeout")) == "5s"
                    assert read.scalar(text("SHOW work_mem")) == "4MB"
                    assert read.scalar(text("SHOW temp_file_limit")) == "16MB"
                assert any(
                    "municipio" in statement.lower()
                    and "Lumenia" not in statement
                    and "Lumenia" in str(parameters)
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
            with (TestClient(api) as client, TestClient(runtime_app) as public_client,
                  audit_runtime(owner_url.render_as_string(hide_password=False)) as audit_url):
                monkeypatch.setenv("GENAI_TEST_AUDIT_URL", audit_url)
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
                assert public_client.post("/api/v1/auth/login", headers=origin, json={
                    "username": "reader", "password": "synthetic-test-password",
                }).status_code == 200
                runtime_http_client = httpx.AsyncClient(
                    transport=httpx.MockTransport(dispatch_genai)
                )
                runtime_genai_client = GenAIQuestionClient(
                    http_client=runtime_http_client,
                    base_url="http://genai",
                    service_token="test-coordination-service-token-0000000000",
                )
                monkeypatch.setattr(
                    runtime_app.state, "genai_question_client", runtime_genai_client
                )
                monkeypatch.setattr(
                    runtime_app.state, "genai_gold_readiness_gate",
                    controlled_readiness, raising=False,
                )
                # GENAI-10B: expectativas literais independentes para FAT-10 e ATE-01/03/04.
                with owner.begin() as domain_write:
                    domain_write.execute(TABLES["atendimentos_uc"].insert(), [
                        {"protocolo": "D1", "id_uc": "DOMAIN1", "data_abertura": datetime.fromisoformat(
                            "2001-02-01T01:00:00+00:00"), "nota_satisfacao": 0.0},
                        {"protocolo": "D2", "id_uc": "DOMAIN1", "data_abertura": datetime.fromisoformat(
                            "2001-02-01T02:00:00+00:00"), "nota_satisfacao": 4.0},
                        {"protocolo": "D3", "id_uc": "DOMAIN2", "data_abertura": None,
                         "nota_satisfacao": None},
                    ])
                    domain_write.execute(TABLES["visao_360_uc"].insert(), [
                        {"id_uc": "DOMAIN1", "total_chamados_callcenter": 2},
                        {"id_uc": "DOMAIN2", "total_chamados_callcenter": 1},
                    ])
                with owner.begin() as gd_write:
                    gd_write.execute(TABLES["variacao_consumo_uc"].insert(), [
                        {"id_uc": key, "municipio": "Lumenia", "possui_gd": "Sim",
                         "consumo_medio_inicial": 100, "consumo_medio_final": 60,
                         "meses_com_leitura_p1": count, "meses_com_leitura_p2": 6,
                         "queda_consumo_superior_30_pct": True}
                        for key, count in (("GD_ELIGIBLE", 6), ("GD_PARTIAL", 5))
                    ])
                with owner.begin() as domain_write:
                    origin_metadata = domain_write.execute(select(BATCH.c.origem)).scalar_one()
                    domain_write.execute(TABLES["ocorrencias_uc"].insert(), [
                        {"id_ocorrencia": "EVENT_SHARED", "id_uc": uc, "alimentador": "AL-TESTE",
                         "data_abertura": datetime.fromisoformat("2001-01-10T00:00:00+00:00")}
                        for uc in ("DOMAIN1", "DOMAIN2")
                    ])
                    domain_write.execute(TABLES["decomposicao_receita"].insert(), {
                        "municipio": "Lumenia", "bairro": "Quadra X", "classe_consumo": "RESIDENCIAL",
                        "inicio_p0": "2000-01", "fim_p0": "2000-12", "inicio_p1": "2001-01", "fim_p1": "2001-12",
                        "metodo": "PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3",
                        "estado_decomposicao": "CALCULADA_BASE_COMUM",
                        "run_id_silver": origin_metadata["run_id_silver"],
                        "lote_bronze_silver": origin_metadata["lote_bronze_silver"],
                        "efeito_volume_reais": 10, "efeito_preco_observado_reais": 5,
                        "efeito_interacao_reais": 5, "variacao_entradas_reais": 0,
                        "variacao_saidas_reais": 0, "variacao_sem_leitura_fora_base_reais": 0,
                        "variacao_outros_fora_base_reais": 0, "variacao_faturamento_total_reais": 20,
                        "faturamento_p0_reais": 100, "faturamento_p1_reais": 120,
                        "residuo_reconciliacao_reais": 0, "qtd_ucs_base_comum": 2, "qtd_ucs_observadas": 2,
                        "qtd_ucs_entrantes": 0, "qtd_ucs_saintes": 0,
                    })
                domain_cases = [
                    ("INT-03", "Quantas interrupções houve no alimentador AL-TESTE em janeiro de 2001?",
                     "network.interruption_events", "1.0 ocorrências"),
                    ("FAT-11", "Quanto da variação da receita residencial em Lumenia foi efeito preço e quanto foi efeito volume?",
                     "billing.price_volume", "Efeito volume: 10.0 R$"),
                    ("CON-08", "Quantas UCs com GD em Lumenia tiveram queda de consumo acima de 30%?",
                     "energy.gd_consumption_drop", "1.0 UCs"),
                    ("ATE-01", "Quantos chamados foram abertos em fevereiro de 2001?",
                     "service.attendance", "2.0 protocolos"),
                    ("ATE-03", "Quantos chamados de atendimento existem no histórico acumulado?",
                     "service.accumulated_attendance", "3.0 protocolos"),
                    ("ATE-04", "Qual é a satisfação média do atendimento no histórico acumulado?",
                     "service.accumulated_satisfaction", "2.0 pontos"),
                    ("FAT-10", "Qual classe mais contribuiu para a receita em Lumenia em janeiro de 2001?",
                     "billing.revenue", "12.0 R$"),
                ]
                for case_id, question, metric_id, expected_text in domain_cases:
                    if case_id == "FAT-10":
                        with owner.begin() as domain_write:
                            domain_write.execute(TABLES["diagnostico_receita"].insert(), {
                                "competencia": "2001-01", "municipio": "Lumenia",
                                "classe_consumo": "COMERCIAL", "subgrupo_tarifario": "T",
                                "bandeira_tarifaria": "T", "possui_gd": "Não",
                                "receita_total_reais": 4,
                            })
                    GENAI_TRANSPORT_EVENTS.clear()
                    result = public_client.post("/api/v1/ai/questions", headers=origin,
                                                json={"question": question})
                    assert result.status_code == 200, case_id
                    body = result.json()
                    assert body["status"] == "answered", (case_id, body)
                    assert body["analysis_context"]["metric"] == metric_id
                    assert expected_text in body["answer"], case_id
                    assert body["audit_reference"] and not body["evidence"][0]["is_demo"]
                    assert [e["path"] for e in GENAI_TRANSPORT_EVENTS] == [
                        "/api/v1/internal/question-plans", "/api/v1/internal/question-syntheses",
                    ]
                    assert GENAI_TRANSPORT_EVENTS[0]["response"]["plan"] == (
                        GENAI_TRANSPORT_EVENTS[1]["request"]["plan"]
                    )
                with owner.begin() as domain_write:
                    domain_write.execute(TABLES["diagnostico_receita"].delete().where(
                        TABLES["diagnostico_receita"].c.municipio == "Lumenia",
                        TABLES["diagnostico_receita"].c.classe_consumo == "COMERCIAL",
                    ))
                # FAT-09/CON-06: o mês intermediário não pertence à comparação.
                with owner.begin() as comparison_write:
                    comparison_write.execute(TABLES["diagnostico_receita"].insert(), [
                        {"competencia": month, "municipio": "Lumenia",
                         "classe_consumo": "RESIDENCIAL", "subgrupo_tarifario": "T",
                         "bandeira_tarifaria": "T", "possui_gd": "Não",
                         "receita_total_reais": value, "consumo_total_kwh": value}
                        for month, value in (("2001-02", 9999), ("2001-04", 24))
                    ])
                try:
                    compared = public_client.post("/api/v1/ai/questions", headers=origin, json={
                        "question": "Quanto cresceu a receita residencial em Lumenia entre janeiro de 2001 e abril de 2001?",
                    })
                    assert compared.status_code == 200
                    compared_body = compared.json()
                    assert compared_body["status"] == "answered", compared_body
                    assert "12.0 R$" in compared_body["answer"]
                    assert "24.0 R$" in compared_body["answer"]
                    assert "100.0 %" in compared_body["answer"]
                    assert "9999" not in compared_body["answer"]
                    consumption = public_client.post("/api/v1/ai/questions", headers=origin, json={
                        "question": "O consumo residencial em Lumenia caiu entre janeiro de 2001 e abril de 2001?",
                    }).json()
                    assert consumption["status"] == "answered", consumption
                    assert "30.0 kWh" in consumption["answer"]
                    assert "24.0 kWh" in consumption["answer"]
                    assert "-6.0 kWh" in consumption["answer"]
                    assert "-20.0 %" in consumption["answer"]
                    with owner.begin() as ranking_write:
                        ranking_write.execute(TABLES["consumo_receita_bairro"].insert(), [
                            {"competencia": month, "municipio": "Luz Clara", "bairro": name,
                             "classe_consumo": "RESIDENCIAL", "consumo_total_kwh": value}
                            for name, month, value in [
                                ("Quadra A", "2001-01", 100), ("Quadra A", "2001-04", 50),
                                ("Quadra B", "2001-01", 1000), ("Quadra B", "2001-04", 990),
                            ]
                        ])
                    ranking = public_client.post("/api/v1/ai/questions", headers=origin, json={
                        "question": "Qual bairro de Luz Clara mais perdeu volume residencial entre janeiro de 2001 e abril de 2001?",
                    }).json()
                    assert ranking["status"] == "answered", ranking
                    assert "Quadra A" in ranking["answer"] and "Quadra B" not in ranking["answer"]
                    assert "-50.0 kWh" in ranking["answer"]
                finally:
                    with owner.begin() as comparison_write:
                        comparison_write.execute(TABLES["consumo_receita_bairro"].delete().where(
                            TABLES["consumo_receita_bairro"].c.municipio == "Luz Clara",
                        ))
                        comparison_write.execute(TABLES["diagnostico_receita"].delete().where(
                            TABLES["diagnostico_receita"].c.municipio == "Lumenia",
                            TABLES["diagnostico_receita"].c.competencia.in_(("2001-02", "2001-04")),
                        ))
                GENAI_TRANSPORT_EVENTS.clear()
                reader_sql.clear()
                public = public_client.post("/api/v1/ai/questions", headers=origin, json={
                    "question": "Qual a receita em Lumenia em janeiro de 2001?",
                })
                assert public.status_code == 200, public.text
                assert public.json()["status"] == "answered", public.text
                correlation_id = public.json()["correlation_id"]
                assert len(correlation_id) == 32
                assert public.headers["X-Correlation-ID"] == correlation_id
                assert public.json()["evidence"]
                persisted = AuditStore(owner).read(correlation_id)
                assert {row["service"] for row in persisted} == {"backend", "genai"}
                assert public.json()["audit_reference"] in {row["id"] for row in persisted}
                final_event = next(row["event"] for row in persisted
                                   if row["id"] == public.json()["audit_reference"])
                assert final_event["row_count"] == 1
                assert final_event["stage"] == "response"
                assert final_event["batch_ref"]
                assert "Lumenia" not in str(persisted)
                artifacts = [row["event"]["artifact"] for row in persisted
                             if row["service"] == "backend" and row["event"].get("artifact")]
                assert len(artifacts) == 2
                assert artifacts[-1]["result_digest"]
                assert "SELECT" in artifacts[-1]["query_template"]
                assert artifacts[-1]["max_rows"] <= 100

                assert [item["path"] for item in GENAI_TRANSPORT_EVENTS] == [
                    "/api/v1/internal/question-plans",
                    "/api/v1/internal/question-syntheses",
                ]
                plan_event, synthesis_event = GENAI_TRANSPORT_EVENTS
                plan_request = plan_event["request"]
                plan_response = plan_event["response"]
                synthesis_request = synthesis_event["request"]
                assert all(
                    item["correlation_id"] == correlation_id
                    for item in GENAI_TRANSPORT_EVENTS
                )
                assert plan_response["correlation_id"] == correlation_id
                assert plan_request["access_scope"] == synthesis_request["access_scope"]
                assert plan_response["plan"]["profile_id"] == "v-energy-grid-360-gold"
                assert plan_response["plan"]["source_id"] == "gold.local"
                assert plan_response["plan"]["catalog_version"] == "v1"
                assert synthesis_request["plan"] == plan_response["plan"]
                assert synthesis_request["plan_fingerprint"] == plan_response["plan_fingerprint"]
                assert synthesis_request["expected_batch_ref"] == plan_request["batch_ref"]
                provenance = synthesis_request["lookup"]["evidence"]["provenance"]
                records = synthesis_request["lookup"]["evidence"]["records"]
                assert records[0]["value"] == 12.0
                assert records[0]["period"] == "2001-01"
                assert records[0]["unit"] == "R$"
                assert provenance["plan_fingerprint"] == plan_response["plan_fingerprint"]
                assert provenance["catalog_version"] == "v1"
                assert provenance["batch_ref"] == plan_request["batch_ref"]
                assert provenance["source_id"] == "gold.local"
                assert provenance["unit"] == "R$"
                assert provenance["filters"] == plan_response["plan"]["filters"]
                assert provenance["filters"][0]["values"] == ["Lumenia"]
                assert provenance["quality"] == {
                    "readiness_version": "gold-readiness-v2",
                    "batch_ref": plan_request["batch_ref"],
                    "lot_state": "partial",
                    "available_capability_ids": ["faturamento.receita"],
                }
                catalog = load_gold_catalog()
                assert (catalog.mapping_version, catalog.dictionary_version, catalog.physical_schema) == (
                    "gold-catalog-v2", "gold-csv-v2", "gold_v2",
                )
                assert any(
                    "gold_v2.diagnostico_receita" in statement.lower()
                    for statement in reader_sql
                )

                monkeypatch.setenv("GENAI_TEST_AUDIT_TOKEN", "invalid-test-token-000000000000000000")
                reader_sql.clear()
                audit_failed = public_client.post("/api/v1/ai/questions", headers=origin, json={
                    "question": "Qual a receita em Lumenia em janeiro de 2001?",
                })
                assert audit_failed.status_code == 200
                assert audit_failed.json()["status"] == "recoverable_error"
                assert audit_failed.json()["error"] == {
                    "code": "service_unavailable", "retryable": True,
                }
                assert not audit_failed.json()["evidence"]
                assert not any("receita_total_reais" in sql.lower() for sql in reader_sql)
                monkeypatch.delenv("GENAI_TEST_AUDIT_TOKEN")

                async def mismatched_batch(planned):
                    prefix, run_id, _publication_id = planned.publication.batch_ref.split(":")
                    return GoldReadinessReport(
                        readiness_version="gold-readiness-v2",
                        batch_ref=f"{prefix}:{run_id}:{uuid4()}",
                        lot_state="partial",
                        capabilities={"faturamento.receita": {"status": "available"}},
                    )

                async def missing_capability(planned):
                    return GoldReadinessReport(
                        readiness_version="gold-readiness-v2",
                        batch_ref=planned.publication.batch_ref,
                        lot_state="partial",
                        capabilities={},
                    )

                for rejected_gate in (mismatched_batch, missing_capability):
                    runtime_app.state.genai_gold_readiness_gate = rejected_gate
                    GENAI_TRANSPORT_EVENTS.clear()
                    reader_sql.clear()
                    rejected = public_client.post("/api/v1/ai/questions", headers=origin, json={
                        "question": "Qual a receita em Lumenia em janeiro de 2001?",
                    })
                    assert rejected.status_code == 503
                    assert not any(
                        "receita_total_reais" in statement.lower()
                        for statement in reader_sql
                    )
                    assert [item["path"] for item in GENAI_TRANSPORT_EVENTS] == [
                        "/api/v1/internal/question-plans",
                    ]
                runtime_app.state.genai_gold_readiness_gate = None
                blocked = public_client.post("/api/v1/ai/questions", headers=origin, json={
                    "question": "Qual a receita em Lumenia em janeiro de 2001?",
                })
                assert blocked.status_code == 503
                del runtime_app.state.genai_gold_readiness_gate
                default_readiness = public_client.post("/api/v1/ai/questions", headers=origin, json={
                    "question": "Qual a receita em Lumenia em janeiro de 2001?",
                })
                assert default_readiness.status_code == 503
                runtime_app.state.genai_gold_readiness_gate = controlled_readiness

                from tests.support.genai_failure_matrix import (
                    assert_first_question_failures,
                )
                assert_first_question_failures(public_client, owner, monkeypatch, origin)

                missing_month = public_client.post("/api/v1/ai/questions", headers=origin, json={
                    "question": "Qual a receita em Lumenia em março de 2001?",
                })
                assert missing_month.status_code == 200
                assert missing_month.json()["status"] == "needs_clarification"
                assert not missing_month.json()["evidence"]
                original_client = runtime_app.state.genai_question_client
                class OfflineClient:
                    async def plan(self, *args, **kwargs):
                        from app.services.genai_client import GenAIServiceUnavailable
                        raise GenAIServiceUnavailable
                    async def ask(self, *args, **kwargs):
                        raise AssertionError("Gold indisponível não ativa demonstração")
                runtime_app.state.genai_question_client = OfflineClient()
                try:
                    offline = public_client.post("/api/v1/ai/questions", headers=origin, json={
                        "question": "Qual a receita em Lumenia em janeiro de 2001?",
                    })
                    assert offline.status_code == 503
                    assert offline.json()["error"]["code"] == "service_unavailable"
                finally:
                    runtime_app.state.genai_question_client = original_client
                assert public_client.post(
                    "/api/v1/auth/logout", headers=origin
                ).status_code == 204
                asyncio.run(runtime_http_client.aclose())
                GENAI_TRANSPORT_EVENTS.clear()

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
                "SELECT * FROM public.genai_audit_events",
                "INSERT INTO public.genai_audit_events DEFAULT VALUES",
                "DELETE FROM public.genai_audit_events",
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
        if probe_created:
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as cleanup:
                cleanup.exec_driver_sql("DROP FUNCTION IF EXISTS public.genai_private_probe()")
        owner.dispose()
        admin.dispose()
