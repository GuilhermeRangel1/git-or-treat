"""HTTP characterization for the Gold v2 revenue contract used by the RMR map."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_analytics_db
from app.main import app
from app.models.gold_load import BATCH
from app.models.gold_v2_load import TABLES
from tests.support.platform_auth import login_as_profile


START, MIDDLE, END = "2025-01", "2025-02", "2025-03"


@pytest.fixture
def gold_v2_revenue_db(monkeypatch):
    """Compose the real Gold repository over a small, isolated v2 publication."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"gold": None, "gold_v2": None}},
        poolclass=StaticPool,
    )
    tables = [BATCH, TABLES["visao_360_uc"], TABLES["consumo_mensal_uc"], TABLES["consumo_receita_bairro"]]
    for table in tables:
        table.create(engine)

    units = [
        ("R-1", "Recife", "Centro", "Residencial"),
        ("R-2", "Recife", "Jardins", "Residencial"),
        ("R-3", "Recife", "Várzea", "Comercial"),
        ("O-1", "Olinda", "Bairro Novo", "Comercial"),
    ]
    municipalities = TABLES["visao_360_uc"]
    monthly = TABLES["consumo_mensal_uc"]
    territory = TABLES["consumo_receita_bairro"]
    with engine.begin() as connection:
        connection.execute(insert(BATCH).values(
            id=1,
            lote="territory-map-controlled-v2",
            fingerprint="a" * 64,
            importado_em=datetime(2026, 11, 3, tzinfo=timezone.utc),
            manifesto={},
            schema_version="gold-csv-v2",
            publication_id="territory-map-controlled-publication",
            origem={"preco_volume_configuracao": {"estado": "NAO_CONFIGURADA"}},
        ))
        connection.execute(insert(municipalities), [
            {"id_uc": uc_id, "municipio": city, "bairro": neighborhood, "classe": usage_class,
             "uf": "PE", "status": "ATIVA", "possui_gd": "false"}
            for uc_id, city, neighborhood, usage_class in units
        ])
        connection.execute(insert(monthly), [
            {"id_uc": uc_id, "competencia": month, "tem_fatura": True}
            for uc_id, *_ in units for month in (START, MIDDLE, END)
        ])
        # Rows model monthly facts at municipality / neighborhood / class grain.
        # Centro changes 100 -> 80; Jardins has a known zero base then 20;
        # Várzea is absent in the final month and must stay null, not zero.
        facts = [
            (START, "Recife", "Centro", "Residencial", 100, 10, 5),
            (MIDDLE, "Recife", "Centro", "Residencial", 90, 9, 5),
            (END, "Recife", "Centro", "Residencial", 80, 7, 5),
            (START, "Recife", "Jardins", "Residencial", 0, 0, 5),
            (MIDDLE, "Recife", "Jardins", "Residencial", 10, 2, 5),
            (END, "Recife", "Jardins", "Residencial", 20, 3, 5),
            (START, "Recife", "Várzea", "Comercial", 50, 6, 5),
            (MIDDLE, "Recife", "Várzea", "Comercial", 40, 5, 5),
            (START, "Olinda", "Bairro Novo", "Comercial", 200, 25, 5),
            (MIDDLE, "Olinda", "Bairro Novo", "Comercial", 220, 26, 5),
            (END, "Olinda", "Bairro Novo", "Comercial", 240, 28, 5),
        ]
        connection.execute(insert(territory), [
            {"competencia": month, "municipio": city, "bairro": neighborhood,
             "classe_consumo": usage_class, "receita_total_reais": amount,
             "consumo_total_kwh": energy, "qtd_ucs_distintas_faturadas_no_mes": count,
             "receita_base_comparavel_reais": amount, "consumo_base_comparavel_kwh": energy}
            for month, city, neighborhood, usage_class, amount, energy, count in facts
        ])

    def analytics_db():
        with Session(engine) as session:
            yield session

    monkeypatch.setitem(app.dependency_overrides, get_analytics_db, analytics_db)
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    try:
        yield
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def session_auth(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")


def _revenue(client: TestClient, params=None):
    return client.get("/api/v1/revenue", params=params)


def test_gold_v2_revenue_map_query_uses_extremes_series_and_class_filter(client, monkeypatch, gold_v2_revenue_db):
    login_as_profile(client, monkeypatch, "commercial")
    response = _revenue(client, {"competencia_inicio": START, "competencia_fim": END})

    assert response.status_code == 200
    data = response.json()["data"]
    assert [point["competencia"] for point in data["series"]] == [START, MIDDLE, END]
    assert [point["billed_amount"] for point in data["series"]] == [350.0, 360.0, 340.0]
    assert [point["measured_energy_kwh"] for point in data["series"]] == [41.0, 42.0, 38.0]
    assert data["comparison"]["initial"]["billed_amount"] == 350.0
    assert data["comparison"]["final"]["billed_amount"] == 340.0
    assert data["comparison"]["billed_amount_change_brl"] == -10.0
    assert data["comparison"]["measured_energy_change_kwh"] == -3.0
    assert data["comparison"]["billed_amount_change_percent"] is None
    assert data["quality"]["percent_change_eligible"] is False

    filtered = _revenue(client, {
        "competencia_inicio": START, "competencia_fim": END, "classe": "Residencial",
    })
    assert filtered.status_code == 200
    filtered_data = filtered.json()["data"]
    assert [point["billed_amount"] for point in filtered_data["series"]] == [100.0, 100.0, 100.0]
    assert filtered_data["comparison"]["billed_amount_change_brl"] == 0.0


def test_gold_v2_revenue_map_neighborhood_detail_distinguishes_zero_and_absence(client, monkeypatch, gold_v2_revenue_db):
    login_as_profile(client, monkeypatch, "commercial")
    response = _revenue(client, {
        "competencia_inicio": START, "competencia_fim": END,
        "municipio": "Recife", "group_by": "bairro",
    })

    assert response.status_code == 200
    items = {item["filters"]["bairro"]: item for item in response.json()["data"]["breakdown"]["items"]}
    assert items["Centro"]["comparison"]["billed_amount_change_brl"] == -20.0
    assert items["Centro"]["comparison"]["measured_energy_change_kwh"] == -3.0
    assert items["Jardins"]["comparison"]["initial"]["billed_amount"] == 0.0
    assert items["Jardins"]["comparison"]["final"]["billed_amount"] == 20.0
    assert items["Jardins"]["comparison"]["billed_amount_change_percent"] is None
    assert items["Várzea"]["comparison"]["final"]["billed_amount"] is None
    assert items["Várzea"]["comparison"]["billed_amount_change_brl"] is None


@pytest.mark.parametrize("params", [
    {"competencia_inicio": "2025-13", "competencia_fim": END},
    [("competencia_inicio", START), ("competencia_inicio", MIDDLE), ("competencia_fim", END)],
])
def test_gold_v2_revenue_map_rejects_invalid_period_and_repeated_scalar(client, monkeypatch, gold_v2_revenue_db, params):
    login_as_profile(client, monkeypatch, "commercial")
    response = _revenue(client, params)
    assert response.status_code == 422


@pytest.mark.parametrize(("profile", "expected"), [("commercial", 200), ("admin", 200), ("operations", 403)])
def test_gold_v2_revenue_map_authorizes_before_opening_analytics_source(
    client, monkeypatch, gold_v2_revenue_db, profile, expected,
):
    login_as_profile(client, monkeypatch, profile)
    response = _revenue(client, {"competencia_inicio": START, "competencia_fim": END})
    assert response.status_code == expected


def test_gold_v2_revenue_map_requires_session_before_opening_analytics_source(client, monkeypatch, gold_v2_revenue_db):
    opened = []

    def fail_if_opened():
        opened.append(True)
        raise AssertionError("Gold repository dependency should not resolve before authentication")

    monkeypatch.setitem(app.dependency_overrides, get_analytics_db, fail_if_opened)
    response = _revenue(client, {"competencia_inicio": START, "competencia_fim": END})
    assert response.status_code == 401
    assert opened == []


def test_gold_v2_revenue_map_rejects_stale_publication_reference(client, monkeypatch, gold_v2_revenue_db):
    login_as_profile(client, monkeypatch, "commercial")
    response = _revenue(client, {
        "competencia_inicio": START, "competencia_fim": END,
        "expected_lote": "previous-publication",
    })
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stale_batch"


@pytest.mark.parametrize("profile", ["customer_service", "losses", "operations"])
def test_gold_v2_revenue_map_denies_profile_before_opening_analytics_source(
    client, monkeypatch, gold_v2_revenue_db, profile,
):
    login_as_profile(client, monkeypatch, profile)
    opened = []

    def fail_if_opened():
        opened.append(True)
        raise AssertionError("Gold repository dependency should not resolve before authorization")

    monkeypatch.setitem(app.dependency_overrides, get_analytics_db, fail_if_opened)
    response = _revenue(client, {"competencia_inicio": START, "competencia_fim": END})
    assert response.status_code == 403
    assert opened == []
