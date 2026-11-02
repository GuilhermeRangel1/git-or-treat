"""Verificação privada opt-in da fila Gold no banco isolado."""
import os
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import and_, case, create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_analytics_db
from app.main import app
from app.models.gold_v2_load import BATCH, TABLES

pytestmark = pytest.mark.skipif(os.getenv("GOLD_INSPECTIONS_REAL") != "1", reason="Exige publicação privada em banco isolado.")


def test_queue_matches_published_positions_options_and_detail(monkeypatch):
    url = os.environ["GOLD_INSPECTIONS_DB_URL"]
    kwargs = {"execution_options": {"schema_translate_map": {"gold": None, "gold_v2": None}}} if url.startswith("sqlite:") else {}
    engine = create_engine(url, hide_parameters=True, **kwargs)
    def database():
        with Session(engine) as session:
            yield session
    monkeypatch.setitem(app.dependency_overrides, get_analytics_db, database)
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    queue = TABLES["fila_inspecao"]
    with engine.connect() as db, TestClient(app) as client:
        assert db.scalar(select(BATCH.c.schema_version)) == "gold-csv-v2"
        response = client.get("/api/v1/inspections/queue?page_size=3")
        assert response.status_code == 200
        body = response.json()
        expected = db.execute(select(queue.c.id_uc, queue.c.motivo_prioridade).order_by(queue.c.posicao_fila_inspecao).limit(3)).all()
        assert [r["uc_id"] for r in body["data"]["items"]] == [r.id_uc for r in expected]
        assert [r["reason"] for r in body["data"]["items"]] == [r.motivo_prioridade for r in expected]
        assert body["pagination"]["total"] == db.scalar(select(func.count()).select_from(queue))
        conds = [queue.c.total_inspecoes_irregulares > 0, queue.c.media_consumo_historico.is_(None),
                 and_(queue.c.media_consumo_historico == 0, queue.c.possui_geracao_solar == "Não"),
                 queue.c.total_inspecoes_realizadas == 0]
        labels = ["ALTA - HISTORICO IRREGULAR", "REVISAR - SEM HISTORICO DE CONSUMO",
                  "ALTA - CONSUMO ZERO", "MEDIA - NUNCA INSPECIONADO"]
        reasons = ["Inspeção anterior com irregularidade confirmada", "Sem consumo válido no histórico de leituras",
                   "Consumo médio zero sem vínculo cadastral de GD", "Nenhuma inspeção anterior registrada"]
        expected_label = case(*zip(conds, labels), else_="BAIXA")
        expected_reason = case(*zip(conds, reasons), else_="Não atende a uma condição específica de maior prioridade")
        mismatch = db.scalar(select(func.count()).select_from(queue).where(
            (queue.c.prioridade_inspecao != expected_label) | (queue.c.motivo_prioridade != expected_reason)))
        assert mismatch == 0
        expected_rank = case((expected_label == labels[0], 1), (expected_label == labels[2], 2),
                             (expected_label == labels[3], 3), (expected_label == "BAIXA", 4), else_=None)
        assert db.scalar(select(func.count()).select_from(queue).where(queue.c.ordem_prioridade_inspecao.is_distinct_from(expected_rank))) == 0
        rank = func.row_number().over(order_by=(queue.c.ordem_prioridade_inspecao.asc().nulls_last(),
            queue.c.total_inspecoes_irregulares.desc(), queue.c.media_consumo_historico.desc().nulls_last(), queue.c.id_uc.asc()))
        positions = select(queue.c.posicao_fila_inspecao.label("position"), rank.label("expected")).subquery()
        assert db.scalar(select(func.count()).select_from(positions).where(positions.c.position != positions.c.expected)) == 0
        assert set(body["data"]["filter_options"]["municipio"]) == set(db.scalars(select(queue.c.municipio).distinct()))
        sample = db.execute(select(queue.c.municipio, queue.c.bairro, queue.c.classe, queue.c.alimentador).limit(1)).one()
        filters = dict(zip(("municipio", "bairro", "classe", "alimentador"), sample))
        scoped = client.get("/api/v1/inspections/queue", params=filters)
        assert scoped.status_code == 200
        assert scoped.json()["pagination"]["total"] == db.scalar(select(func.count()).select_from(queue).where(
            *(queue.c[key] == value for key, value in filters.items())))
        second = client.get("/api/v1/inspections/queue?page_size=3&page=2").json()
        assert not set(r["uc_id"] for r in body["data"]["items"]) & set(r["uc_id"] for r in second["data"]["items"])
        item = body["data"]["items"][0]
        detail = client.get("/api/v1/inspections/queue/" + quote(item["uc_id"], safe=""))
        assert detail.status_code == 200
        assert detail.json()["data"]["reason"] == item["reason"]
        assert detail.json()["data"]["estimate_evidence"]["horizon_months"] is None
        reference = db.execute(select(queue.c.estado_media_historica_recuperacao,
                                      queue.c.media_historica_recuperacao_kwh_por_inspecao)
                               .where(queue.c.id_uc == item["uc_id"])).one()
        if reference.estado_media_historica_recuperacao == "DISPONIVEL_REFERENCIA_HISTORICA":
            assert detail.json()["data"]["historical_recovery"]["mean_kwh_per_inspection"] == reference.media_historica_recuperacao_kwh_por_inspecao
        assert detail.json()["data"]["potential_recoverable_energy_kwh"] is None
        assert client.get("/api/v1/inspections/queue?order_by=potential_recoverable_energy_kwh").status_code == 422
