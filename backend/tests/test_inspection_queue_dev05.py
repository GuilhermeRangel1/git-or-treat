from copy import deepcopy

import pytest

from app.main import app
from app.repositories.analytics import SyntheticAnalyticsRepository, get_analytics_repository


@pytest.fixture(autouse=True)
def synthetic_source(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")


def test_detail_exposes_reproducible_priority_and_monthly_projection(client):
    response = client.get("/api/v1/inspections/queue/UC-1004")
    assert response.status_code == 200
    body = response.json()
    item = body["data"]
    # Independently worked example: 0.60 + 0.32 = 0.92; (90 - 45) * 1 = 45.
    assert item["priority"] == 0.92
    assert [signal["weight"] for signal in item["signals"]] == [0.6, 0.32]
    assert item["potential_recoverable_energy_kwh"] == 45
    assert item["estimate_evidence"]["baseline_kwh"] == 90
    assert item["estimate_evidence"]["observed_kwh"] == 45
    assert item["estimate_evidence"]["horizon_months"] == 1
    assert item["rule_version"] == "dev05-v1"
    assert body["metadata"]["source"]["is_demo"] is True
    assert any("não confirma" in text for text in item["limitations"])


def test_missing_comparable_baseline_does_not_become_zero(client):
    item = client.get("/api/v1/inspections/queue/UC-1002").json()["data"]
    assert item["priority"] == 0.61
    assert item["potential_recoverable_energy_kwh"] is None
    assert item["estimate_evidence"]["baseline_kwh"] is None
    assert item["estimate_evidence"]["unavailable_reason"]


@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_energy_sort_keeps_unknown_last_in_both_directions(client, direction):
    body = client.get("/api/v1/inspections/queue", params={
        "order_by": "potential_recoverable_energy_kwh", "direction": direction,
    }).json()
    assert [item["uc_id"] for item in body["data"]["items"]] == ["UC-1004", "UC-1002"]


def test_filter_pagination_and_empty_queue_preserve_context(client):
    body = client.get("/api/v1/inspections/queue?page_size=1&page=2").json()
    assert body["pagination"] == {"page": 2, "page_size": 1, "total": 2, "total_pages": 2}
    assert body["data"]["items"][0]["uc_id"] == "UC-1002"
    filtered = client.get("/api/v1/inspections/queue?municipio=Recife&classe=Residencial&alimentador=AL-03").json()
    assert [item["uc_id"] for item in filtered["data"]["items"]] == ["UC-1004"]
    empty = client.get("/api/v1/inspections/queue?municipio=Olinda").json()
    assert empty["data"]["items"] == []
    assert empty["metadata"]["status"] == "empty"
    assert "Recife" in empty["data"]["filter_options"]["municipio"]
    assert empty["metadata"]["filters"]["municipio"] == "Olinda"


@pytest.mark.parametrize("query", ["page=0", "page_size=101", "direction=wrong", "order_by=reason", "municipio=Unknown"])
def test_invalid_queue_query_uses_error_contract(client, query):
    response = client.get(f"/api/v1/inspections/queue?{query}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"


def test_unknown_suspicion_returns_404(client):
    response = client.get("/api/v1/inspections/queue/UC-1001")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_equal_priority_ties_by_energy_then_uc_and_zero_is_known(client):
    repository = SyntheticAnalyticsRepository()
    original = deepcopy(repository.suspicions[0])
    second = deepcopy(original)
    second["uc_id"] = "UC-1001"
    third = deepcopy(original)
    third["uc_id"] = "UC-1003"
    third["estimate_evidence"]["observed_kwh"] = 100
    repository.suspicions = [original, third, second]
    app.dependency_overrides[get_analytics_repository] = lambda: repository
    body = client.get("/api/v1/inspections/queue?page_size=1").json()
    assert body["data"]["items"][0]["uc_id"] == "UC-1001"
    assert client.get("/api/v1/inspections/queue?page_size=1&page=2").json()["data"]["items"][0]["uc_id"] == "UC-1004"
    assert client.get("/api/v1/inspections/queue/UC-1003").json()["data"]["potential_recoverable_energy_kwh"] == 0


def test_unavailable_source_does_not_fallback_to_demo(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "unavailable")
    assert client.get("/api/v1/inspections/queue").status_code == 503
    assert client.get("/api/v1/inspections/queue/UC-1004").status_code == 503


def test_synthetic_rule_is_not_applied_to_real_source(client):
    repository = SyntheticAnalyticsRepository()
    repository.source_is_demo = False
    app.dependency_overrides[get_analytics_repository] = lambda: repository
    response = client.get("/api/v1/inspections/queue")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "rule_unavailable"


def test_queue_summary_covers_entire_filtered_scope_not_only_page(client):
    first = client.get("/api/v1/inspections/queue?page_size=1").json()
    second = client.get("/api/v1/inspections/queue?page_size=1&page=2").json()
    expected = {"total_units": 2, "highest_priority": 0.92, "estimated_units": 1, "unavailable_estimate_units": 1}
    assert first["data"]["summary"] == second["data"]["summary"] == expected
    assert first["data"]["items"][0]["signals"][0]["label"] == "Lacuna de leitura"
    assert first["data"]["items"][0]["signals"][0]["weight"] == 0.6
    empty = client.get("/api/v1/inspections/queue?municipio=Olinda").json()
    assert empty["data"]["summary"] == {"total_units": 0, "highest_priority": None, "estimated_units": 0, "unavailable_estimate_units": 0}
    residential = client.get("/api/v1/inspections/queue?classe=Residencial").json()
    assert residential["data"]["summary"] == {"total_units": 1, "highest_priority": 0.92, "estimated_units": 1, "unavailable_estimate_units": 0}
