def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["online", "degraded"]
    assert data["database"] in ["connected", "disconnected"]


def test_kpis_endpoint_envelope(client):
    response = client.get("/api/v1/kpis")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "metadata" in data
