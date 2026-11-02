"""Reconciliação privada e opt-in de UC 360 contra o snapshot Gold v2."""
import os
from datetime import datetime, timezone
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_analytics_db
from app.main import app
from app.models.gold_v2_load import BATCH, TABLES

pytestmark = pytest.mark.skipif(os.getenv("GOLD_UC_REAL") != "1", reason="Exige Gold v2 em banco isolado.")


def test_private_uc_sources_match_public_api(monkeypatch):
    url = os.environ["GOLD_UC_DB_URL"]
    options = {"execution_options": {"schema_translate_map": {"gold": None, "gold_v2": None}}} if url.startswith("sqlite:") else {}
    engine = create_engine(url, hide_parameters=True, **options)
    def database():
        with Session(engine) as session:
            yield session
    monkeypatch.setitem(app.dependency_overrides, get_analytics_db, database)
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    uc, monthly = TABLES["visao_360_uc"], TABLES["consumo_mensal_uc"]
    with engine.connect() as db, TestClient(app) as client:
        assert db.scalar(select(BATCH.c.schema_version)) == "gold-csv-v2"
        sample = db.execute(select(uc.c.id_uc, monthly.c.competencia).join(monthly, monthly.c.id_uc == uc.c.id_uc).limit(1)).one()
        identifier, month = sample
        path = "/api/v1/ucs/" + quote(identifier, safe="")
        search = client.get("/api/v1/ucs", params={"q": identifier})
        assert search.status_code == 200 and any(item["uc_id"] == identifier for item in search.json()["data"]["items"])
        overview = client.get(path + "/overview", params={"start": month, "end": month})
        assert overview.status_code == 200
        data = overview.json()["data"]
        row = db.execute(select(monthly).where(monthly.c.id_uc == identifier, monthly.c.competencia == month)).mappings().one()
        assert data["profile"]["uc_id"] == identifier
        gd = TABLES["gd_uc"]
        invoices = TABLES["faturas_uc"]
        declared = db.execute(select(invoices.c.id_uc, invoices.c.mes_referencia, invoices.c.id_fatura,
                                     invoices.c.status, invoices.c.valor_fatura_declarada_em_aberto_reais)
                              .where(invoices.c.valor_fatura_declarada_em_aberto_reais.is_not(None)).limit(1)).first()
        if declared:
            response = client.get("/api/v1/ucs/" + quote(declared.id_uc, safe="") + "/history/invoices",
                                  params={"start": declared.mes_referencia, "end": declared.mes_referencia, "page_size": 100})
            assert response.status_code == 200
            candidates = response.json()["data"]["items"]
            match = next((item for item in candidates if item["invoice_id"] == declared.id_fatura), None)
            assert match is not None
            assert match["declared_status"] == declared.status
            assert match["declared_open_amount"] == float(declared.valor_fatura_declarada_em_aberto_reais)
            assert match["payment_status"] == "unknown" and match["paid_amount"] is None
        source_gd = db.execute(select(gd.c.potencia_kwp).where(gd.c.id_uc == identifier)).first()
        assert (data["gold_generation"]["capacity_kwp"] if data["gold_generation"] else None) == (source_gd[0] if source_gd else None)
        gd_sample = db.execute(select(gd.c.id_uc, gd.c.potencia_kwp).where(gd.c.potencia_kwp.is_not(None)).limit(1)).first()
        if gd_sample:
            gd_response = client.get("/api/v1/ucs/" + quote(gd_sample.id_uc, safe="") + "/overview")
            assert gd_response.status_code == 200
            assert gd_response.json()["data"]["gold_generation"]["capacity_kwp"] == gd_sample.potencia_kwp
        assert data["comparison"]["initial"]["billed_amount"]["value"] == (float(row["receita_reais"]) if row["receita_reais"] is not None else None)
        history = client.get(path + "/history/consumption", params={"start": month, "end": month})
        assert history.status_code == 200 and history.json()["pagination"]["total"] == 1
        assert history.json()["data"]["items"][0]["competencia"] == month
        year, number = int(month[:4]), int(month[5:])
        start = datetime(year, number, 1, tzinfo=timezone.utc)
        end = datetime(year + (number == 12), number % 12 + 1, 1, tzinfo=timezone.utc)
        for section, name in (("invoices", "faturas_uc"), ("meters", "medidor_uc"), ("calls", "atendimentos_uc"), ("interruptions", "ocorrencias_uc")):
            table = TABLES[name]
            conditions = [table.c.id_uc == identifier]
            if section == "invoices": conditions.append(table.c.mes_referencia == month)
            if section in {"calls", "interruptions"}: conditions.extend([table.c.data_abertura >= start, table.c.data_abertura < end])
            expected = db.scalar(select(func.count()).select_from(table).where(*conditions))
            response = client.get(path + "/history/" + section, params={"start": month, "end": month})
            assert response.status_code == 200
            assert response.json()["pagination"]["total"] == expected
