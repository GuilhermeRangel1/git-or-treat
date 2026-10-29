
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_analytics_db
from app.main import app
from app.models.gold_load import ATTEMPTS, BATCH, TABLES
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
    engine = engine.execution_options(schema_translate_map={"gold": None})
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


def test_revenue_feeder_uses_monthly_source_with_current_registration(gold_client):
    client, statements = gold_client
    response = client.get("/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-01&alimentador=FAKE-AL")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["total_billed_amount"] == 10.10
    assert response.json()["data"]["total_measured_energy_kwh"] == 10
    assert any("JOIN main.gold_visao_360_uc" in sql and "GROUP BY" in sql for sql in statements)


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
