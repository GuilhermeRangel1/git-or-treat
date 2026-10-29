import pytest

from app.main import app
from app.repositories.analytics import SyntheticAnalyticsRepository, get_analytics_repository_provider


@pytest.mark.parametrize("alimentador", ["", "   ", "AL-99", " AL-01 "])
def test_continuity_rejects_invalid_feeder_with_analytics_error(client, monkeypatch, alimentador):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")

    response = client.get("/api/v1/operations/continuity", params={"alimentador": alimentador})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_query"
    assert error["details"][0]["field"] == "alimentador"


def test_inspection_queue_orders_by_priority_and_places_pagination_at_root(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/inspections/queue?page=1&page_size=1")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["items"][0]["uc_id"] == "UC-1004"
    assert body["pagination"] == {"page": 1, "page_size": 1, "total": 2, "total_pages": 2}
    assert body["data"]["items"][0]["potential_recoverable_energy_kwh"] == 45.0


def test_continuity_without_denominator_is_unavailable_and_null(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/operations/continuity?alimentador=AL-03")

    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert item["status"] == "unavailable"
    assert item["dec_hours_per_uc"] is None
    assert item["fec_interruptions_per_uc"] is None
    assert item["denominator_uc_count"] is None


def test_continuity_discloses_multimunicipal_feeder_territory(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/operations/continuity?alimentador=AL-02")

    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert item["municipalities"] == ["Olinda", "Paulista"]
    assert item["territory_status"] == "multi_municipal"
    assert item["covered_uc_count"] == item["denominator_uc_count"] == 2


def test_zero_interruptions_with_known_coverage_are_available_zero(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/operations/continuity?periodo=2025-01&alimentador=AL-02")

    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert item["status"] == "available"
    assert item["interruption_count"] == 0
    assert item["dec_hours_per_uc"] == 0.0
    assert item["fec_interruptions_per_uc"] == 0.0


@pytest.mark.parametrize("start,end", [("2024-11", "2024-12"), ("2025-03", "2025-04")])
def test_continuity_outside_source_period_is_unavailable_despite_spatial_coverage(client, monkeypatch, start, end):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")

    response = client.get("/api/v1/operations/continuity", params={
        "alimentador": "AL-01", "competencia_inicio": start, "competencia_fim": end,
    })

    assert response.status_code == 200
    body = response.json()
    item = body["data"]["items"][0]
    assert item["status"] == body["metadata"]["status"] == "unavailable"
    assert item["dec_hours_per_uc"] is None
    assert item["fec_interruptions_per_uc"] is None
    assert item["coverage_status"] == "available"
    assert item["coverage_ratio"] == 1.0
    assert any("2025-01" in text and "2025-02" in text and "temporal" in text.lower() for text in item["limitations"])
    assert all(text in body["metadata"]["limitations"] for text in item["limitations"])


@pytest.mark.parametrize("start,end,dec,fec,count", [
    ("2024-12", "2025-01", 1.0, 0.5, 1),
    ("2025-02", "2025-03", 0.5, 0.5, 1),
    ("2024-12", "2025-03", 1.5, 1.0, 2),
])
def test_continuity_partial_period_reports_only_observed_intersection(client, monkeypatch, start, end, dec, fec, count):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")

    response = client.get("/api/v1/operations/continuity", params={
        "alimentador": "AL-01", "competencia_inicio": start, "competencia_fim": end,
    })

    assert response.status_code == 200
    body = response.json()
    item = body["data"]["items"][0]
    assert item["status"] == body["metadata"]["status"] == "partial"
    assert item["dec_hours_per_uc"] == dec
    assert item["fec_interruptions_per_uc"] == fec
    assert item["interruption_count"] == count
    assert item["coverage_status"] == "available"
    assert body["metadata"]["period"]["start"] == start
    assert body["metadata"]["period"]["end"] == end
    assert any("temporal" in text.lower() and "observad" in text.lower() for text in item["limitations"])


def test_continuity_preserves_available_feeders_when_another_lacks_denominator(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")

    response = client.get("/api/v1/operations/continuity")

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["status"] == "partial"
    first, second, third = body["data"]["items"]
    assert first["status"] == second["status"] == "available"
    assert first["dec_hours_per_uc"] == second["dec_hours_per_uc"] == 1.5
    assert first["fec_interruptions_per_uc"] == 1.0
    assert second["fec_interruptions_per_uc"] == 0.5
    assert third["status"] == "unavailable"
    assert third["dec_hours_per_uc"] is None


@pytest.mark.parametrize("start,end", [("2025-03", "2025-03"), ("2025-02", "2025-03")])
def test_continuity_keeps_missing_denominator_and_temporal_limitations(client, monkeypatch, start, end):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")

    response = client.get("/api/v1/operations/continuity", params={
        "alimentador": "AL-03", "competencia_inicio": start, "competencia_fim": end,
    })

    assert response.status_code == 200
    body = response.json()
    item = body["data"]["items"][0]
    assert item["status"] == body["metadata"]["status"] == "unavailable"
    assert item["dec_hours_per_uc"] is item["fec_interruptions_per_uc"] is None
    assert any("Denominador" in text for text in item["limitations"])
    assert any("temporal" in text.lower() for text in item["limitations"])


def test_continuity_unknown_temporal_coverage_does_not_infer_availability_from_events(client, monkeypatch):
    repository = SyntheticAnalyticsRepository()
    repository.continuity_coverage = None
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)

    response = client.get("/api/v1/operations/continuity?alimentador=AL-01")

    assert response.status_code == 200
    body = response.json()
    item = body["data"]["items"][0]
    assert item["status"] == body["metadata"]["status"] == "unavailable"
    assert item["dec_hours_per_uc"] is item["fec_interruptions_per_uc"] is None
    assert any("temporal" in text.lower() and "desconhecida" in text for text in item["limitations"])
