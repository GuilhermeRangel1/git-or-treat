import pytest


@pytest.fixture(autouse=True)
def synthetic_source(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")


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
    assert response.json()["pagination"] == {"page": 20, "page_size": 2, "total": 5, "total_pages": 3}


def test_partially_paid_invoice_has_a_consistent_payment_status(client):
    response = client.get("/api/v1/ucs/UC-1002")

    assert response.status_code == 200
    invoice = response.json()["data"]["invoices"][0]
    assert invoice["billed_amount"] == 82.0
    assert invoice["paid_amount"] == 70.0
    assert invoice["payment_status"] == "partial"
    assert invoice["payment_date"] == "2025-03-05"
