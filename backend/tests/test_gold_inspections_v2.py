from app.core.database import get_analytics_db, get_db
from app.core.order_access import require_orders_write
from app.main import app
from app.models.gold_load import BATCH
from app.models.gold_v2_load import TABLES
from tests.test_gold_http import gold_client  # noqa: F401
from tests.support.database import override_get_db


def publish_fixture():
    dependency = app.dependency_overrides[get_analytics_db]()
    db = next(dependency)
    try:
        for name in ("visao_360_uc", "consumo_mensal_uc", "fila_inspecao"):
            TABLES[name].create(db.get_bind())
        uc = TABLES["visao_360_uc"]
        db.execute(uc.insert(), [
            {"id_uc": "UC-A", "municipio": "Cidade A", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-A"},
            {"id_uc": "UC-B", "municipio": "Cidade A", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-A"},
            {"id_uc": "UC-C", "municipio": "Cidade B", "bairro": "Outro", "classe": "Comercial", "alimentador": "AL-B"},
            {"id_uc": "UC-D", "municipio": "Fora da fila", "bairro": "Ausente", "classe": "Rural", "alimentador": "AL-D"},
        ])
        db.execute(TABLES["consumo_mensal_uc"].insert().values(id_uc="UC-A", competencia="2025-01"))
        common = {"municipio": "Cidade A", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-A",
                  "prioridade_inspecao": "ALTA - HISTORICO IRREGULAR", "motivo_prioridade": "Histórico confirmado",
                  "total_inspecoes_realizadas": 2, "total_inspecoes_irregulares": 1,
                  "estado_media_historica_recuperacao": None, "media_historica_recuperacao_kwh_por_inspecao": None,
                  "intervalo_historico_recuperacao_inferior_kwh": None, "intervalo_historico_recuperacao_superior_kwh": None,
                  "referencia_media_historica_recuperacao": None}
        db.execute(TABLES["fila_inspecao"].insert(), [
            {**common, "id_uc": "UC-A", "posicao_fila_inspecao": 2},
            {**common, "id_uc": "UC-B", "posicao_fila_inspecao": 1,
             "estado_media_historica_recuperacao": "DISPONIVEL_REFERENCIA_HISTORICA",
             "media_historica_recuperacao_kwh_por_inspecao": 20., "intervalo_historico_recuperacao_inferior_kwh": 5.,
             "intervalo_historico_recuperacao_superior_kwh": 40., "referencia_media_historica_recuperacao": "global"},
            {**common, "id_uc": "UC-C", "posicao_fila_inspecao": 3, "municipio": "Cidade B", "bairro": "Outro", "classe": "Comercial", "alimentador": "AL-B"},
        ])
        db.execute(BATCH.update().values(schema_version="gold-csv-v2", publication_id="test-publication"))
        db.commit()
    finally:
        dependency.close()


def test_v2_queue_uses_published_position_and_queue_filter_universe(gold_client):
    client, _ = gold_client
    publish_fixture()
    response = client.get("/api/v1/inspections/queue?page_size=1")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["items"][0]["uc_id"] == "UC-B"
    assert body["data"]["items"][0]["reason"] == "Histórico confirmado"
    assert body["data"]["items"][0]["potential_recoverable_energy_kwh"] is None
    assert "Fora da fila" not in body["data"]["filter_options"]["municipio"]
    assert {(pair["municipio"], pair["bairro"]) for pair in body["data"]["neighborhoods"]} == {("Cidade A", "Centro"), ("Cidade B", "Outro")}
    assert client.get("/api/v1/inspections/queue?page_size=1&page=2").json()["data"]["items"][0]["uc_id"] == "UC-A"
    assert client.get("/api/v1/inspections/queue?direction=asc&page_size=1").json()["data"]["items"][0]["uc_id"] == "UC-C"
    assert client.get("/api/v1/inspections/queue?order_by=uc_id&direction=desc&page_size=1").json()["data"]["items"][0]["uc_id"] == "UC-C"
    assert client.get("/api/v1/inspections/queue?municipio=Cidade%20A&classe=Residencial&alimentador=AL-A").json()["pagination"]["total"] == 2
    assert client.get("/api/v1/inspections/queue?order_by=potential_recoverable_energy_kwh").status_code == 422
    detail = client.get("/api/v1/inspections/queue/UC-B")
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["reason"] == "Histórico confirmado"
    assert detail.json()["data"]["estimate_evidence"]["horizon_months"] is None
    assert detail.json()["data"]["historical_recovery"]["mean_kwh_per_inspection"] == 20
    assert detail.json()["data"]["potential_recoverable_energy_kwh"] is None
    app.dependency_overrides[require_orders_write] = lambda: "test-writer"
    app.dependency_overrides[get_db] = override_get_db
    try:
        order = client.post("/api/v1/inspections/queue/UC-B/orders", headers={"Idempotency-Key": "artificial-key-v2-123"},
                            json={"source_version": body["metadata"]["source"]["version"], "rule_version": "gold-csv-v2"})
        assert order.status_code == 503
    finally:
        app.dependency_overrides.pop(require_orders_write, None)
        app.dependency_overrides.pop(get_db, None)


def test_gold_order_creation_is_blocked_server_side_without_homologation(gold_client):
    client, _ = gold_client
    app.dependency_overrides[require_orders_write] = lambda: "test-writer"
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post("/api/v1/inspections/queue/FAKE-A/orders", headers={"Idempotency-Key": "artificial-key-123456"},
                               json={"source_version": "test", "rule_version": "gold-csv-v1"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "rule_unavailable"
    finally:
        app.dependency_overrides.pop(require_orders_write, None)
        app.dependency_overrides.pop(get_db, None)
