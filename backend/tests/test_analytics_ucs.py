import pytest

from tests.support.platform_auth import login_as_profile


@pytest.fixture(autouse=True)
def synthetic_source(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")


@pytest.fixture(autouse=True)
def authenticated_customer_service_session(client, monkeypatch):
    login_as_profile(client, monkeypatch, "customer_service")


def test_uc_detail_returns_not_found_for_unknown_identifier(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/ucs/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_uc_detail_exposes_partial_read_and_independent_empty_invoice_section(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/ucs/UC-1004")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["section_status"]["consumption"] == "partial"
    assert body["data"]["section_status"]["invoices"] == "empty"
    assert body["data"]["consumption"][1]["measured_energy_kwh"] is None
    assert body["data"]["meters"][0]["removed_at"] == "2025-01-31"
    assert body["data"]["profile"]["customer_reference"] == "CLI-DEMO-04"
    assert body["data"]["profile"]["customer_name"] == "Pessoa Demonstração 04"


def test_listings_return_empty_out_of_range_page_and_preserve_total(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic", raising=False)

    response = client.get("/api/v1/ucs?page=20&page_size=2&q=UC-10")

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []
    assert response.json()["pagination"] == {"page": 20, "page_size": 2, "total": 10, "total_pages": 5}


def test_partially_paid_invoice_has_a_consistent_payment_status(client):
    response = client.get("/api/v1/ucs/UC-1002")

    assert response.status_code == 200
    invoice = next(
        item for item in response.json()["data"]["invoices"]
        if item["competencia"] == "2025-02"
    )
    assert invoice["billed_amount"] == 82.0
    assert invoice["paid_amount"] == 70.0
    assert invoice["payment_status"] == "partial"
    assert invoice["payment_date"] == "2025-03-05"


def test_uc_search_preserves_case_insensitive_id_filter_order_pagination_and_projection(client):
    response = client.get("/api/v1/ucs?q=uc-10&order_by=municipio&page_size=2")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["items"] == [
        {"uc_id": "UC-1003", "municipio": "Olinda", "bairro": "Casa Caiada", "classe": "Residencial", "alimentador": "AL-02", "status": "active"},
        {"uc_id": "UC-1005", "municipio": "Paulista", "bairro": "Jardim", "classe": "Residencial", "alimentador": "AL-02", "status": "active"},
    ]
    assert body["pagination"] == {"page": 1, "page_size": 2, "total": 10, "total_pages": 5}
    assert body["metadata"]["status"] == "available"


@pytest.mark.parametrize("q", ["Pessoa", "CLI-DEMO"])
def test_uc_search_does_not_search_customer_fields(client, q):
    response = client.get("/api/v1/ucs", params={"q": q})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["items"] == []
    assert body["pagination"]["total"] == 0
    assert body["metadata"]["status"] == "empty"


@pytest.mark.parametrize("query", [{"q": ""}, {"q": "  "}, {"order_by": "customer_name"}])
def test_uc_search_preserves_validation_errors(client, query):
    response = client.get("/api/v1/ucs", params=query)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"
