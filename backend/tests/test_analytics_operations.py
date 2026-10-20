

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
