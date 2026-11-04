import pytest

from tests.support.platform_auth import login_as_profile

from app.main import app
from app.repositories.analytics import SyntheticAnalyticsRepository, get_analytics_repository


@pytest.fixture(autouse=True)
def synthetic_source(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")


@pytest.fixture(autouse=True)
def authenticated_commercial_session(client, monkeypatch):
    login_as_profile(client, monkeypatch, "commercial")


def test_kpis_publish_versioned_envelope_and_reconciled_synthetic_total(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/kpis")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["metrics"][0] == {
        "id": "billed_amount",
        "label": "Valor faturado",
        "value": 1727.0,
        "unit": "BRL",
        "status": "available",
        "limitations": [],
    }
    assert body["metadata"] == {
        "contract_version": "1.0.0",
        "status": "partial",
        "period": {"start": "2025-01", "end": "2025-02", "granularity": "month"},
        "filters": {"municipio": None, "bairro": None, "classe": None, "alimentador": None},
        "source": {
            "kind": "synthetic",
            "version": "dev03-v1",
            "is_demo": True,
            "updated_at": "2026-10-21T00:00:00Z",
        },
        "limitations": [
            "Dados sintéticos; não constituem diagnóstico da V-Energy.",
            "Há leituras ausentes no recorte; o total soma apenas valores observados.",
        ],
    }


def test_analytics_rejects_invalid_competence_range(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get(
        "/api/v1/kpis?competencia_inicio=2025-13&competencia_fim=2025-02"
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"


def test_analytics_source_defaults_to_unavailable(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "unavailable", raising=False)

    response = client.get("/api/v1/kpis")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "source_unavailable"


def test_zero_measurement_and_billed_amount_remain_available(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/kpis?municipio=Olinda&classe=Residencial")

    assert response.status_code == 200
    metrics = {item["id"]: item for item in response.json()["data"]["metrics"]}
    assert metrics["billed_amount"]["value"] == 80.0
    assert metrics["billed_amount"]["status"] == "available"
    assert metrics["measured_energy_kwh"]["value"] == 10.0
    assert metrics["measured_energy_kwh"]["status"] == "available"


def test_known_municipality_without_records_returns_empty_null_metrics(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/kpis?municipio=Paulista")

    assert response.status_code == 200
    metrics = {item["id"]: item for item in response.json()["data"]["metrics"]}
    assert metrics["billed_amount"]["value"] is None
    assert metrics["billed_amount"]["status"] == "empty"
    assert response.json()["metadata"]["status"] == "empty"


def test_contradictory_geography_filters_are_rejected(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/kpis?municipio=Recife&bairro=Casa%20Caiada")

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "bairro"


def test_revenue_keeps_billed_and_measured_energy_distinct(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/revenue")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_billed_amount"] == 1727.0
    assert data["total_paid_amount"] == 1710.0
    assert data["total_billed_energy_kwh"] == 1585.0
    assert data["total_measured_energy_kwh"] == 407.0
    assert data["observed_price_brl_per_kwh"] == 1.0896
    assert data["price_volume"]["interaction_effect_brl"] is not None
    assert round(
        data["price_volume"]["price_effect_brl"]
        + data["price_volume"]["volume_effect_brl"]
        + data["price_volume"]["interaction_effect_brl"],
        2,
    ) == 127.0


def test_synthetic_analytics_route_does_not_open_a_database_after_identity_resolution(
    client, monkeypatch
):
    from app.core.database import get_db
    from app.core.platform_access import PlatformProfile, permissions_for_profile
    from app.core.platform_identity import PlatformIdentity, get_platform_identity

    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    def fail_if_database_is_requested():
        raise AssertionError("Synthetic analytics must not request a database session")

    # Keep this provider-boundary test independent of the session resolver's DB read.
    client.app.dependency_overrides[get_platform_identity] = lambda: PlatformIdentity(
        actor="fixture:commercial",
        profile=PlatformProfile.COMMERCIAL,
        permissions=permissions_for_profile("commercial"),
        auth_mode="session",
    )
    client.app.dependency_overrides[get_db] = fail_if_database_is_requested
    response = client.get("/api/v1/kpis")

    assert response.status_code == 200


def test_legacy_single_competence_query_parameter_remains_supported(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/kpis?competencia=2025-01")

    assert response.status_code == 200
    assert response.json()["metadata"]["period"] == {
        "start": "2025-01", "end": "2025-01", "granularity": "month"
    }


def test_missing_reading_is_not_reported_as_an_empty_record_set(client):
    response = client.get(
        "/api/v1/kpis?alimentador=AL-03&competencia=2025-02"
    )

    assert response.status_code == 200
    body = response.json()
    energy = next(
        item for item in body["data"]["metrics"]
        if item["id"] == "measured_energy_kwh"
    )
    assert energy["value"] is None
    assert energy["status"] == "unavailable"
    assert energy["limitations"]
    assert body["metadata"]["status"] == "partial"


def test_blank_competence_is_rejected_instead_of_using_default(client):
    response = client.get("/api/v1/kpis?competencia_inicio=")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"


def test_revenue_does_not_replace_a_missing_comparison_endpoint(client):
    response = client.get(
        "/api/v1/revenue?competencia_inicio=2024-12&competencia_fim=2025-02"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["period"]["start"] == "2024-12"
    assert body["data"]["comparison"]["billed_amount_change_brl"] is None
    assert body["data"]["price_volume"]["status"] == "unavailable"
    assert body["data"]["price_volume"]["price_effect_brl"] is None
    assert any(
        "competências solicitadas" in message
        for message in body["data"]["price_volume"]["limitations"]
    )


def test_repository_override_can_report_non_demo_provenance(client):
    # Contract test double only: this does not implement or connect to Gold.
    repository = SyntheticAnalyticsRepository()
    repository.source_kind = "contract-test"
    repository.source_version = "test-adapter-v1"
    repository.source_is_demo = False
    app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        response = client.get("/api/v1/kpis")
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)

    assert response.status_code == 200
    source = response.json()["metadata"]["source"]
    assert source["kind"] == "contract-test"
    assert source["version"] == "test-adapter-v1"
    assert source["is_demo"] is False
