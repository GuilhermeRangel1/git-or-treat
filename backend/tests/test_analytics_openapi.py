import pytest


@pytest.fixture(autouse=True)
def synthetic_source(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")


@pytest.mark.parametrize("path", [
    "/api/v1/kpis",
    "/api/v1/panorama",
    "/api/v1/revenue",
    "/api/v1/ucs",
    "/api/v1/ucs/{uc_id}",
    "/api/v1/inspections/queue",
    "/api/v1/operations/continuity",
])
def test_openapi_documents_the_actual_analytics_error_envelope(client, path):
    operation = client.get("/openapi.json").json()["paths"][path]["get"]

    for status in ("422", "503"):
        schema = operation["responses"][status]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/AnalyticsErrorResponse"}
