
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.analytics_access import require_gold_analytics_read
from app.core.database import get_analytics_db
from app.main import app
from app.repositories.gold_context import get_optional_gold_context
from app.models.gold_load import ATTEMPTS, BATCH, TABLES
from app.models.gold_v2_load import TABLES as V2_TABLES
from app.services.gold_import import import_gold
from tests.test_gold_import import SAMPLES, write_origin


@pytest.fixture
def gold_client(tmp_path, monkeypatch):
    for name, (header, rows) in SAMPLES.items():
        folder = tmp_path / name
        folder.mkdir()
        if name == "visao_360_uc":
            rows = [*rows, rows[0].replace("FAKE-A;", "FAKE-B;", 1).replace(";FAKE-AL;", ";FAKE-OTHER;")]
        (folder / "part.csv").write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    engine = engine.execution_options(schema_translate_map={"gold": None, "gold_v2": None})
    for table in [ATTEMPTS, BATCH, *TABLES.values()]:
        table.create(engine)
    write_origin(tmp_path, "test-v1")
    import_gold(engine, tmp_path)
    def database():
        with Session(engine) as session:
            yield session
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    original = dict(app.dependency_overrides)
    app.dependency_overrides[get_analytics_db] = database
    # Este conjunto exercita a compatibilidade v1 anterior ao contrato de
    # sessão; as rotas Gold v2 autenticadas têm provas próprias em PostgreSQL.
    app.dependency_overrides[get_optional_gold_context] = lambda: None
    app.dependency_overrides[require_gold_analytics_read] = lambda: None
    statements = []
    event.listen(engine, "before_cursor_execute", lambda conn, cursor, statement, params, context, many: statements.append(statement))
    try:
        with TestClient(app) as client:
            yield client, statements
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)
        engine.dispose()


def test_revenue_uses_gold_sql_aggregates_and_explicit_absence(gold_client):
    client, statements = gold_client
    response = client.get("/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-01")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metadata"]["source"]["kind"] == "gold_csv"
    assert body["metadata"]["source"]["is_demo"] is False
    assert body["metadata"]["status"] == "partial"
    data = body["data"]
    assert data["total_billed_amount"] == 25.50
    assert data["total_measured_energy_kwh"] == 30
    assert data["total_paid_amount"] is None
    assert data["total_billed_energy_kwh"] is None
    assert data["observed_price_brl_per_kwh"] is None
    assert data["price_volume"]["status"] == "unavailable"
    assert sum(item["comparison"]["initial"]["billed_amount"] for item in data["breakdown"]["items"]) == 25.50
    assert any("GROUP BY" in sql for sql in statements)
    assert any("gold_consumo_receita_bairro" in sql and "GROUP BY" in sql for sql in statements)


def test_gold_legacy_journeys_require_read_identity(gold_client, monkeypatch):
    from pydantic import SecretStr
    from app.core import analytics_access
    from app.core.order_access import OrderIdentity

    client, _ = gold_client
    app.dependency_overrides.pop(require_gold_analytics_read)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "service")
    monkeypatch.setattr(settings, "ORDERS_READ_TOKEN", SecretStr("test-read-token-" + "r" * 40))
    for path in ("/api/v1/analytics/options", "/api/v1/revenue", "/api/v1/ucs?q=FAKE"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
        response = client.get(path, headers={"Authorization": "Bearer test-read-token-" + "r" * 40})
        assert response.status_code == 200
    monkeypatch.setattr(analytics_access, "get_order_identity", lambda *_: OrderIdentity("no-read", frozenset(), "session"))
    for path in ("/api/v1/analytics/options", "/api/v1/revenue", "/api/v1/ucs?q=FAKE"):
        assert client.get(path).status_code == 403


def test_gold_legacy_journeys_accept_authenticated_reader_session(gold_client, clean_test_db, monkeypatch):
    from app.core.database import get_db
    from tests.support.database import override_get_db
    from tests.test_order_sessions import create_user

    client, _ = gold_client
    app.dependency_overrides.pop(require_gold_analytics_read)
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")
    create_user("gold-reader")
    assert client.get("/api/v1/revenue").status_code == 401
    login = client.post("/api/v1/auth/login", json={"username": "gold-reader", "password": "correct horse battery staple"}, headers={"Origin": "http://localhost:5173"})
    assert login.status_code == 200
    for path in ("/api/v1/analytics/options", "/api/v1/revenue", "/api/v1/ucs?q=FAKE"):
        assert client.get(path).status_code == 200
    assert client.post("/api/v1/auth/logout", headers={"Origin": "http://localhost:5173"}).status_code == 204
    assert client.get("/api/v1/revenue").status_code == 401


def test_revenue_feeder_uses_monthly_source_with_current_registration(gold_client):
    client, statements = gold_client
    response = client.get("/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-01&alimentador=FAKE-AL")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["total_billed_amount"] == 10.10
    assert response.json()["data"]["total_measured_energy_kwh"] == 10
    assert any("JOIN main.gold_visao_360_uc" in sql and "GROUP BY" in sql for sql in statements)


def test_revenue_combined_filters_reconcile_feeder_and_territory(gold_client):
    client, _ = gold_client
    base = "/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-01&municipio=Cidade%20fict%C3%ADcia&bairro=Bairro%20fict%C3%ADcio&classe=Residencial"
    territory = client.get(base).json()["data"]
    first = client.get(base + "&alimentador=FAKE-AL").json()["data"]
    second = client.get(base + "&alimentador=FAKE-OTHER").json()["data"]
    assert territory["total_billed_amount"] == 25.50
    assert first["total_billed_amount"] == 10.10
    assert second["total_billed_amount"] == 15.40
    assert round(first["total_billed_amount"] + second["total_billed_amount"], 2) == territory["total_billed_amount"]
    assert first["total_measured_energy_kwh"] + second["total_measured_energy_kwh"] == territory["total_measured_energy_kwh"] == 30


def test_missing_month_is_not_zero_and_unknown_filter_is_rejected(gold_client):
    client, _ = gold_client
    data = client.get("/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-02").json()["data"]
    assert data["series"][1]["billed_amount"] is None
    assert data["comparison"]["billed_amount_change_brl"] is None
    assert client.get("/api/v1/revenue?municipio=Unknown").status_code == 422


def test_uc_search_and_history_are_paginated_and_not_fake_invoices(gold_client):
    client, statements = gold_client
    result = client.get("/api/v1/ucs?q=FAKE&page_size=1").json()
    assert result["pagination"]["total"] == 2
    assert len(result["data"]["items"]) == 1
    assert result["data"]["items"][0]["uc_id"] == "FAKE-A"
    response = client.get("/api/v1/ucs/FAKE-A/overview?start=2025-01&end=2025-01")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["comparison"]["initial"]["billed_amount"]["value"] == 10.10
    assert data["current_meter"]["status"] == "unavailable"
    assert data["open_invoices"]["count"] is None
    response = client.get("/api/v1/ucs/FAKE-A/history/consumption?start=2025-01&end=2025-01&page_size=1")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["items"][0]["measured_energy_kwh"] == 10
    assert response.json()["data"]["items"][0]["billed_amount"] == 10.10
    response = client.get("/api/v1/ucs/FAKE-A/history/invoices?start=2025-01&end=2025-01")
    assert response.json()["metadata"]["status"] == "unavailable"
    assert response.json()["data"]["items"] == []
    assert client.get("/api/v1/ucs/DOES-NOT-EXIST/overview").status_code == 404
    assert any("LIMIT" in sql for sql in statements)


def test_queue_preserves_text_priority_and_does_not_estimate(gold_client):
    client, _ = gold_client
    response = client.get("/api/v1/inspections/queue?page_size=1")
    assert response.status_code == 200, response.text
    row = response.json()["data"]["items"][0]
    assert row["priority"] is None
    assert row["priority_label"] == "REVISAR"
    assert row["potential_recoverable_energy_kwh"] is None
    assert row["signals"] == []
    detail = client.get("/api/v1/inspections/queue/FAKE-A")
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["rule_version"] == "gold-csv-v1"


def test_options_are_read_from_database_without_synthetic_values(gold_client):
    client, _ = gold_client
    response = client.get("/api/v1/analytics/options")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["competencias"] == ["2025-01"]
    assert response.json()["data"]["municipio"] == ["Cidade fictícia"]
    assert client.get("/api/v1/analytics/options?unknown=x").status_code == 422


def test_no_fallback_for_unsupported_gold_consumers(gold_client):
    client, _ = gold_client
    assert client.get("/api/v1/panorama").status_code == 503
    assert client.get("/api/v1/operations/summary").status_code == 503


def test_v2_publication_never_labels_old_v1_facts_as_current(gold_client):
    client, _ = gold_client
    dependency = app.dependency_overrides[get_analytics_db]()
    db = next(dependency)
    try:
        for name in ("visao_360_uc", "consumo_mensal_uc", "consumo_receita_bairro"):
            V2_TABLES[name].create(db.get_bind())
        db.execute(V2_TABLES["visao_360_uc"].insert(), [
            {"id_uc": "X", "municipio": "Cidade fictícia", "bairro": "Bairro fictício", "classe": "Residencial", "alimentador": "AL-X"},
            {"id_uc": "Y", "municipio": "Cidade fictícia", "bairro": "Bairro fictício", "classe": "Residencial", "alimentador": "AL-Y"},
            {"id_uc": "Z", "municipio": "Cidade fictícia", "bairro": "Bairro fictício", "classe": "Residencial", "alimentador": "AL-X"},
        ])
        db.execute(V2_TABLES["consumo_mensal_uc"].insert(), [
            {"id_uc": "X", "competencia": "2025-01", "receita_reais": 100, "consumo_kwh": 10, "tem_fatura": True},
            {"id_uc": "Y", "competencia": "2025-01", "receita_reais": 50, "consumo_kwh": 20, "tem_fatura": True},
            {"id_uc": "Z", "competencia": "2025-01", "receita_reais": None, "consumo_kwh": 5, "tem_fatura": False},
        ])
        db.execute(V2_TABLES["consumo_receita_bairro"].insert().values(
            competencia="2025-01", municipio="Cidade fictícia", bairro="Bairro fictício", classe_consumo="Residencial",
            receita_total_reais=150, consumo_total_kwh=35, qtd_ucs_distintas_faturadas_no_mes=2,
        ))
        db.execute(BATCH.update().values(schema_version="gold-csv-v2", publication_id="artificial-publication"))
        db.commit()
    finally:
        dependency.close()
    result = client.get("/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-01")
    assert result.status_code == 200, result.text
    assert result.json()["data"]["total_billed_amount"] == 150
    assert result.json()["metadata"]["source"]["version"].startswith("gold-csv-v2:")
    source = result.json()["metadata"]["source"]
    lote, fingerprint = source["publication_lote"], source["publication_fingerprint"]
    assert lote and len(fingerprint) == 64
    options = client.get("/api/v1/analytics/options").json()["source"]
    assert (options["publication_lote"], options["publication_fingerprint"]) == (lote, fingerprint)
    for path in ("/api/v1/revenue", "/api/v1/ucs?q=X", "/api/v1/analytics/options"):
        separator = "&" if "?" in path else "?"
        assert client.get(path + separator + "expected_lote=" + lote + "&expected_fingerprint=" + fingerprint).status_code == 200
        assert client.get(path + separator + "expected_lote=lote-antigo").status_code == 409
        assert client.get(path + separator + "expected_fingerprint=" + "0" * 64).status_code == 409
        assert client.get(path + separator + "expected_lote=" + lote + "&expected_lote=outro").status_code == 422
    feeder = client.get("/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-01&municipio=Cidade%20fict%C3%ADcia&alimentador=AL-X")
    assert feeder.status_code == 200, feeder.text
    assert feeder.json()["data"]["total_billed_amount"] == 100
    assert feeder.json()["data"]["total_measured_energy_kwh"] == 15
    assert feeder.json()["data"]["comparison"]["initial"]["billed_uc_count"] == 1
    search = client.get("/api/v1/ucs?q=FAKE")
    assert search.status_code == 200
    assert search.json()["data"]["items"] == []
    assert client.get("/api/v1/analytics/options").status_code == 200


@pytest.mark.parametrize("path", [
    "/api/v1/revenue", "/api/v1/ucs?q=FAKE",
    "/api/v1/ucs/FAKE-A/overview", "/api/v1/ucs/FAKE-A/history/consumption",
    "/api/v1/inspections/queue", "/api/v1/inspections/queue/FAKE-A",
])
def test_gold_journeys_preserve_period_lot_and_limits(path, gold_client):
    client, _ = gold_client
    response = client.get(path)
    assert response.status_code == 200
    metadata = response.json()["metadata"]
    assert metadata["period"]["start"] == metadata["period"]["end"] == "2025-01"
    assert metadata["source"]["kind"] == "gold_csv"
    assert metadata["source"]["is_demo"] is False
    assert metadata["source"]["version"].startswith("GOLD_")
    assert len(metadata["source"]["version"].rsplit(":", 1)[-1]) == 64
    assert metadata["source"]["updated_at"]
    assert metadata["limitations"]
    if "inspections" in path:
        assert any("não informam janela temporal própria" in note for note in metadata["limitations"])
    if path.endswith("/overview"):
        assert any("medidores" in note for note in metadata["limitations"])
    if path == "/api/v1/revenue":
        assert any("Receita paga" in note for note in metadata["limitations"])
        assert response.json()["data"]["currency_unit"] == "BRL"
        assert response.json()["data"]["energy_unit"] == "kWh"
