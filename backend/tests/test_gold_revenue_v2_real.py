"""Opt-in: reconcilia a publicação privada carregada sem divulgar seus valores."""
import os
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.database import get_analytics_db
from app.core.config import settings
from app.main import app
from app.models.gold_v2_load import BATCH, TABLES

pytestmark = pytest.mark.skipif(
    os.getenv("GOLD_REVENUE_REAL") != "1",
    reason="Validação privada opt-in exige publicação Gold v2 em banco isolado.",
)


def test_revenue_v2_matches_database_with_combined_feeder_filters(monkeypatch):
    url = os.environ["GOLD_REVENUE_DB_URL"]
    kwargs = {"execution_options": {"schema_translate_map": {"gold": None, "gold_v2": None}}} if url.startswith("sqlite:") else {}
    engine = create_engine(url, hide_parameters=True, **kwargs)
    def database():
        with Session(engine) as session:
            yield session
    monkeypatch.setitem(app.dependency_overrides, get_analytics_db, database)
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monthly = TABLES["consumo_mensal_uc"]
    territory = TABLES["consumo_receita_bairro"]
    uc = TABLES["visao_360_uc"]
    with engine.connect() as db, TestClient(app) as client:
        assert db.execute(select(BATCH.c.schema_version)).scalar_one() == "gold-csv-v2"
        response = client.get("/api/v1/revenue")
        assert response.status_code == 200
        result = response.json()
        start, end = result["metadata"]["period"]["start"], result["metadata"]["period"]["end"]
        control = db.execute(select(
            func.sum(territory.c.receita_total_reais), func.sum(territory.c.consumo_total_kwh),
        ).where(territory.c.competencia.between(start, end))).one()
        assert abs(Decimal(str(result["data"]["total_billed_amount"])) - control[0]) < Decimal("0.01")
        assert abs(result["data"]["total_measured_energy_kwh"] - control[1]) < 0.01
        assert result["data"]["total_paid_amount"] is None
        assert result["data"]["total_billed_energy_kwh"] is None
        comparable = db.execute(select(func.sum(territory.c.receita_base_comparavel_reais),
                                       func.sum(territory.c.consumo_base_comparavel_kwh))
                                .where(territory.c.competencia.between(start, end))).one()
        if result["data"]["observed_price_brl_per_kwh"] is not None:
            assert abs(result["data"]["observed_price_brl_per_kwh"] - float(comparable[0]) / comparable[1]) < 1e-8
        decomposition = result["data"]["window_decomposition"]
        source = TABLES["decomposicao_receita"]
        assert decomposition["status"] in {"available", "partial"}
        assert decomposition["group_count"] == db.scalar(select(func.count()).select_from(source))
        for key, column in {"volume": source.c.efeito_volume_reais, "preco": source.c.efeito_preco_observado_reais,
                            "entradas": source.c.variacao_entradas_reais}.items():
            expected = db.scalar(select(func.sum(column)))
            assert abs(decomposition["components"][key] - expected) < max(0.01, abs(expected) * 1e-9)
        chosen = db.execute(select(source.c.municipio, source.c.bairro, source.c.classe_consumo)
                            .where(source.c.estado_decomposicao == "CALCULADA_BASE_COMUM").limit(1)).one()
        scoped = client.get("/api/v1/revenue", params={"municipio": chosen[0], "bairro": chosen[1], "classe": chosen[2]})
        assert scoped.status_code == 200
        segment = scoped.json()["data"]["window_decomposition"]
        expected = db.scalar(select(func.sum(source.c.efeito_preco_observado_reais)).where(
            source.c.municipio == chosen[0], source.c.bairro == chosen[1], source.c.classe_consumo == chosen[2]))
        assert segment["status"] == "available"
        assert abs(segment["components"]["preco"] - expected) < max(0.01, abs(expected) * 1e-9)

        scope = db.execute(select(uc.c.municipio, uc.c.bairro, uc.c.classe, uc.c.alimentador).where(
            uc.c.municipio.is_not(None), uc.c.bairro.is_not(None), uc.c.classe.is_not(None), uc.c.alimentador.is_not(None),
        ).limit(1)).one()
        filters = dict(zip(("municipio", "bairro", "classe", "alimentador"), scope))
        filtered = client.get("/api/v1/revenue", params={
            "competencia_inicio": start, "competencia_fim": end, **filters,
        })
        assert filtered.status_code == 200
        control = db.execute(select(func.sum(monthly.c.receita_reais), func.sum(monthly.c.consumo_kwh)).select_from(
            monthly.join(uc, monthly.c.id_uc == uc.c.id_uc),
        ).where(monthly.c.competencia.between(start, end), *(uc.c[key] == value for key, value in filters.items()))).one()
        data = filtered.json()["data"]
        assert data["window_decomposition"]["status"] == "unavailable"
        for actual, expected in ((data["total_billed_amount"], control[0]), (data["total_measured_energy_kwh"], control[1])):
            if expected is None:
                assert actual is None
            else:
                assert abs(Decimal(str(actual)) - Decimal(str(expected))) < Decimal("0.01")
