"""Opt-in privado: pacote real → importador → banco → Backend → GenAI HTTP.

Não imprime registros, medidas ou referência do lote. Não certifica fechamento.
"""
import asyncio
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, select

from app.models.gold_v2_load import TABLES
from app.services.gold_import_v2 import import_gold_v2
from app.services.gold_readiness import evaluate_attendance_readiness
from tests.support.migrations import migrated_database

PACKAGE = os.getenv("GOLD_CSV_V2_DIR")
SERVICE_URL = os.getenv("GOLD_READINESS_TEST_URL")
TOKEN = os.getenv("GOLD_READINESS_TEST_TOKEN")
pytestmark = pytest.mark.skipif(not (PACKAGE and SERVICE_URL and TOKEN),
    reason="Configure pacote privado e serviço GenAI local para prova integrada real.")


def test_real_publication_is_consumed_by_genai_readiness(tmp_path):
    path = tmp_path / "private_readiness.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}", hide_parameters=True,
                           connect_args={"check_same_thread":False}).execution_options(
                               schema_translate_map={"gold":None,"gold_v2":None})
    try:
        with engine.connect() as connection, migrated_database(connection):
            loaded = import_gold_v2(engine, PACKAGE)
            with engine.connect() as c:
                cov = TABLES["cobertura_dominios"]
                period = c.execute(select(cov.c.competencia).where(
                    cov.c.dominio == "atendimentos", cov.c.recorte == "DOMINIO"
                ).order_by(cov.c.competencia).limit(1)).scalar_one()

            async def run():
                async with httpx.AsyncClient(timeout=35,trust_env=False) as client:
                    return await evaluate_attendance_readiness(engine,http_client=client,
                        base_url=SERVICE_URL,service_token=TOKEN,requested_periods=(period,),
                        approved_controls=frozenset({"C14","C15"}),correlation_id=uuid4().hex)
            report = asyncio.run(run())
            assert report.batch_ref == loaded["batch_ref"]
            assert report.capabilities["atendimento.uc_acumulado"].status == "available"
            # Não presumir fechado; se não certificado, mensal deve permanecer bloqueado.
            with engine.connect() as c:
                state = c.execute(select(cov.c.estado_cobertura).where(
                    cov.c.dominio == "atendimentos",cov.c.recorte == "DOMINIO",
                    cov.c.competencia == period)).scalar_one()
            if state != "FECHADO":
                assert report.capabilities["atendimento.mensal"].status == "unavailable"
                assert "coverage_incomplete" in report.capabilities["atendimento.mensal"].reasons
    finally:
        engine.dispose()
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(str(path)+suffix).unlink(missing_ok=True)
