"""Opt-in privado: PostgreSQL já carregado → Backend → GenAI HTTP real → fonte.

Exige banco descartável *_test e leitor provisionado; nunca imprime dados do lote.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from calendar import monthrange
from datetime import UTC
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url

from app.models.gold_v2 import TABLES
from app.schemas.ai import AIQuestionRequest
from app.schemas.genai_internal import AccessScope
from app.services.genai_client import GenAIQuestionClient
from app.services.genai_planning import plan_gold_question
from app.services.genai_publication import GoldPublicationContext

DATABASE = os.getenv("GOLD_PLANNING_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE, reason="Configure leitor PostgreSQL do lote privado.")


def test_real_gold_question_reaches_selected_source_and_operational_entrypoint(tmp_path):
    address = make_url(DATABASE)
    assert address.get_backend_name() == "postgresql" and address.database.endswith("_test")
    assert address.username == "venergy_gold_reader"
    engine = create_engine(address, hide_parameters=True, connect_args={"connect_timeout": 5})
    process = None
    try:
        table = TABLES["consumo_receita_bairro"]
        with engine.connect() as connection:
            row = connection.execute(select(
                table.c.competencia, table.c.municipio, table.c.bairro, table.c.classe_consumo
            ).where(table.c.municipio.is_not(None), table.c.bairro.is_not(None),
                    table.c.classe_consumo.in_(["RESIDENCIAL", "Residencial"])
            ).order_by(table.c.competencia.desc()).limit(1)).one()
            assert connection.exec_driver_sql("SHOW default_transaction_read_only").scalar_one() == "on"
        scope = AccessScope(
            caller_ref="operator.private", profile_id="v-energy-grid-360-gold",
            source_id="gold.local", allowed_operations={"read"},
            allowed_metric_ids={"billing.revenue"},
            allowed_dimension_ids={"geography.municipality", "geography.neighborhood",
                                   "customer.consumption_class"},
        )
        request = AIQuestionRequest(question=(
            f"Receita residencial em {row.municipio} no bairro {row.bairro} em {row.competencia}?"
        ))
        publication = GoldPublicationContext.capture(engine)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        token = "private-local-planning-token-0000000000"
        server_code = r"""
import json, os, sys
from dataclasses import asdict
import uvicorn
from app.config import Settings
from app.main import create_app
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
class NoExternalCalls:
    async def retrieve(self, *args, **kwargs):
        raise AssertionError("Planning cannot call evidence")
    async def generate(self, *args, **kwargs):
        raise AssertionError("Planning cannot call model")
class LocalAudit:
    durable = True
    def record(self, event):
        with open(sys.argv[3], "a", encoding="utf-8") as output:
            output.write(json.dumps(asdict(event)) + "\n")
            output.flush()
            os.fsync(output.fileno())
app = create_app(settings=Settings(_env_file=None, enable_demo_access=False,
    service_api_token=sys.argv[2]), domain_profile=GRID360_GOLD_PROFILE,
    source_id="gold.local", source_mode="external", evidence_source=NoExternalCalls(),
    model_adapter=NoExternalCalls(), access_context_resolver=lambda request: None,
    event_sink=LocalAudit(), require_durable_audit=True)
uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]), log_level="critical", access_log=False)
"""
        genai_root = Path(__file__).resolve().parents[2] / "ai-agent"
        process = subprocess.Popen(
            [sys.executable, "-c", server_code, str(port), token, str(tmp_path / "audit.jsonl")],
            cwd=genai_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        base = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                assert process.poll() is None, "O serviço de planejamento não iniciou."
                time.sleep(0.1)
        else:
            pytest.fail("O serviço de planejamento não iniciou no prazo.")

        async def run():
            async with httpx.AsyncClient(timeout=35, trust_env=False) as transport:
                client = GenAIQuestionClient(http_client=transport, base_url=base, service_token=token)
                result = await plan_gold_question(
                    engine, client, request, resolve_scope=lambda: scope, correlation_id="a" * 32,
                    expected_batch_ref=publication.batch_ref,
                )
                relative = await plan_gold_question(
                    engine, client,
                    AIQuestionRequest(question=(
                        f"Receita residencial em {row.municipio} no bairro {row.bairro} no último ano?"
                    )), resolve_scope=lambda: scope, correlation_id="c" * 32,
                    expected_batch_ref=publication.batch_ref,
                )
                with engine.connect() as connection:
                    # Controle independente: meses das três fontes físicas, sem usar o produtor.
                    latest = max(connection.scalar(select(func.max(TABLES[name].c.competencia)))
                                 for name in ("diagnostico_receita", "consumo_receita_bairro",
                                              "consumo_mensal_uc"))
                    observed = set(connection.execute(select(table.c.competencia).where(
                        table.c.municipio == row.municipio, table.c.bairro == row.bairro,
                        table.c.classe_consumo == row.classe_consumo,
                    )).scalars())
                anchor_year, anchor_month = map(int, latest.split("-"))
                anchor = anchor_year * 12 + anchor_month - 1
                expected = {f"{index // 12:04d}-{index % 12 + 1:02d}"
                            for index in range(anchor - 11, anchor + 1)}
                assert relative.response.status.value == (
                    "planned" if expected <= observed else "needs_clarification"
                )
                if relative.response.plan is not None:
                    assert relative.response.plan.window.start.isoformat() == min(expected) + "-01"
                    assert relative.response.plan.window.end.isoformat() == (
                        f"{latest}-{monthrange(anchor_year, anchor_month)[1]:02d}"
                    )
                # A chamada pública recebe escopo atual, não o histórico como permissão.
                calls = 0
                def revoked_scope():
                    nonlocal calls
                    calls += 1
                    return scope if calls == 1 else scope.model_copy(update={"allowed_metric_ids": frozenset()})
                revoked = await plan_gold_question(
                    engine, client, request, resolve_scope=revoked_scope, correlation_id="b" * 32,
                    expected_batch_ref=publication.batch_ref,
                )
                assert revoked.response.status.value == "refused"
                assert revoked.source is None and revoked.response.plan is None
                return result
        result = asyncio.run(run())
        assert result.response.status.value == "planned"
        assert result.source.table == "consumo_receita_bairro"
        assert result.publication.batch_ref == publication.batch_ref
        plan = result.response.plan
        year, month = map(int, row.competencia.split("-"))
        assert plan.window.start.isoformat() == f"{row.competencia}-01"
        assert plan.window.end.day == monthrange(year, month)[1]
        assert {item.dimension_id: item.values for item in plan.filters} == {
            "geography.municipality": (row.municipio,),
            "geography.neighborhood": (row.bairro,),
            "customer.consumption_class": (row.classe_consumo,),
        }
        assert plan.limit == 100 and plan.order is None and plan.group_by_dimension_ids == ()
        # UTC conferido por timestamps reais convertidos em Python, sem IDs/protocolos.
        attendance_scope = scope.model_copy(update={"allowed_metric_ids": frozenset({"service.attendance"})})
        fields = publication.planning_fields(engine, attendance_scope)
        with engine.connect() as connection:
            timestamps = connection.execution_options(yield_per=1000).execute(
                select(TABLES["atendimentos_uc"].c.data_abertura).where(
                    TABLES["atendimentos_uc"].c.data_abertura.is_not(None)
                )
            ).scalars()
            utc_months = {value.astimezone(UTC).strftime("%Y-%m") for value in timestamps}
        assert set(fields["temporal_coverage"][0]["competencies"]) == utc_months
        # O chamador operacional usa o mesmo serviço e sua saída não contém dados privados.
        request_file, scope_file = tmp_path / "request.json", tmp_path / "scope.json"
        request_file.write_text(request.model_dump_json(), encoding="utf-8")
        scope_file.write_text(scope.model_dump_json(), encoding="utf-8")
        cli = subprocess.run(
            [sys.executable, "scripts/plan_gold_question.py", "--request-file", str(request_file),
             "--scope-file", str(scope_file)], cwd=Path(__file__).parents[1],
            env={**os.environ, "GOLD_READINESS_DATABASE_URL": DATABASE,
                 "AI_AGENT_BASE_URL": base, "AI_AGENT_SERVICE_API_TOKEN": token},
            capture_output=True, text=True, timeout=40, check=False,
        )
        assert cli.returncode == 0, "A operação de planejamento falhou."
        assert json.loads(cli.stdout) == {"status": "planned", "plan_admitted": True}
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)
        engine.dispose()
        for artifact in ("request.json", "scope.json", "audit.jsonl"):
            (tmp_path / artifact).unlink(missing_ok=True)
