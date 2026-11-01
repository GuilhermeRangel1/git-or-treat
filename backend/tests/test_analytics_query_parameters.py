import pytest

from tests.support.platform_auth import login_as_profile


@pytest.fixture(autouse=True)
def authenticated_commercial_session(client, monkeypatch):
    login_as_profile(client, monkeypatch, "commercial")


@pytest.mark.parametrize("parameters,fields", [
    ([("group_by", "municipio"), ("group_by", "classe")], ["group_by"]),
    ([
        ("municipio", "Recife"), ("municipio", "Olinda"),
        ("competencia_inicio", "2025-01"), ("competencia_inicio", "2025-02"),
    ], ["competencia_inicio", "municipio"]),
])
def test_revenue_preserves_duplicate_parameter_error_contract(
    client, monkeypatch, parameters, fields,
):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")
    response = client.get("/api/v1/revenue", params=parameters)
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_query",
            "message": "Parâmetros escalares repetidos.",
            "details": [
                {
                    "field": field,
                    "message": "Informe cada parâmetro escalar uma única vez.",
                }
                for field in fields
            ],
        }
    }
