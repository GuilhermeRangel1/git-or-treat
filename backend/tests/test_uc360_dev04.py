from copy import deepcopy

from app.core.config import settings
from app.repositories.analytics import (
    AnalyticsSourceUnavailable,
    SyntheticAnalyticsRepository,
    UCCoverage,
    get_analytics_repository,
)


def _use_repository(repository):
    from app.main import app

    app.dependency_overrides[get_analytics_repository] = lambda: repository
    return app


def test_search_and_overview_expose_known_comparison_as_json_numbers(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "synthetic")
    repo = deepcopy(SyntheticAnalyticsRepository())
    app = _use_repository(repo)
    try:
        search = client.get("/api/v1/ucs", params={"q": "  uc-1001  "})
        assert search.status_code == 200
        assert search.json()["data"]["items"][0]["uc_id"] == "UC-1001"

        response = client.get(
            "/api/v1/ucs/UC-1001/overview",
            params={"start": "2025-01", "end": "2025-02"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["contract_version"] == "1.1.0"
        assert body["data"]["profile"]["uc_id"] == "UC-1001"
        assert body["metadata"]["source"]["is_demo"] is True
        assert (
            body["data"]["comparison"]["initial"]["measured_energy_kwh"]["value"] == 100
        )
        assert body["data"]["comparison"]["final"]["measured_energy_kwh"]["value"] == 90
        assert body["data"]["comparison"]["measured_energy_kwh"]["delta"] == -10
        assert (
            body["data"]["comparison"]["measured_energy_kwh"]["percent_change"] == -10
        )
        assert body["data"]["comparison"]["initial"]["billed_amount"]["value"] == 100
        assert body["data"]["comparison"]["final"]["billed_amount"]["value"] == 105
        assert body["data"]["comparison"]["billed_amount"]["delta"] == 5
        assert isinstance(
            body["data"]["comparison"]["billed_amount"]["delta"], (int, float)
        )
        assert body["data"]["comparison"]["initial"]["billed_energy_kwh"]["value"] == 90
        assert body["data"]["comparison"]["final"]["billed_energy_kwh"]["value"] == 95
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_search_and_overview_validate_identifiers_periods_and_source(client):
    repo = deepcopy(SyntheticAnalyticsRepository())
    app = _use_repository(repo)
    try:
        assert client.get("/api/v1/ucs", params={"q": "UC/1001"}).status_code == 422
        assert (
            client.get("/api/v1/ucs", params={"q": "NOT-FOUND"}).json()["data"]["items"]
            == []
        )
        assert client.get("/api/v1/ucs/UC-9999/overview").status_code == 404
        assert (
            client.get(
                "/api/v1/ucs/UC-1001/overview",
                params={"start": "2025-13", "end": "2026-01"},
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/v1/ucs/UC-1001/overview",
                params={"start": "2025-02", "end": "2025-01"},
            ).status_code
            == 422
        )
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)

    from app.main import app

    app.dependency_overrides[get_analytics_repository] = lambda: (_ for _ in ()).throw(
        AnalyticsSourceUnavailable()
    )
    try:
        response = client.get("/api/v1/ucs/UC-1001/overview")
        assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_history_pagination_does_not_change_overview_and_keeps_invoice_grain(client):
    repo = deepcopy(SyntheticAnalyticsRepository())
    repo.invoices.extend(
        [
            {
                "invoice_id": "F-1001-X",
                "uc_id": "UC-1001",
                "competencia": "2025-02",
                "billed_amount": 20.0,
                "paid_amount": 20.0,
                "billed_energy_kwh": 15.0,
                "due_date": "2025-03-20",
                "payment_date": "2025-03-19",
                "payment_status": "paid",
            },
            {
                "invoice_id": "F-1001-Y",
                "uc_id": "UC-1001",
                "competencia": "2025-02",
                "billed_amount": 5.0,
                "paid_amount": 5.0,
                "billed_energy_kwh": 3.0,
                "due_date": "2025-03-22",
                "payment_date": "2025-03-21",
                "payment_status": "paid",
            },
        ]
    )
    app = _use_repository(repo)
    try:
        first = client.get(
            "/api/v1/ucs/UC-1001/history/invoices",
            params={"start": "2025-01", "end": "2025-02", "page_size": 2},
        )
        second = client.get(
            "/api/v1/ucs/UC-1001/history/invoices",
            params={"start": "2025-01", "end": "2025-02", "page_size": 2, "page": 2},
        )
        beyond = client.get(
            "/api/v1/ucs/UC-1001/history/invoices",
            params={"start": "2025-01", "end": "2025-02", "page_size": 2, "page": 3},
        )
        assert [first.status_code, second.status_code, beyond.status_code] == [
            200,
            200,
            200,
        ]
        assert first.json()["pagination"]["total"] == 4
        assert len(first.json()["data"]["items"]) == 2
        assert len(second.json()["data"]["items"]) == 2
        assert beyond.json()["data"]["items"] == []
        all_pages = first.json()["data"]["items"] + second.json()["data"]["items"]
        assert len({row["invoice_id"] for row in all_pages}) == 4

        overview = client.get(
            "/api/v1/ucs/UC-1001/overview",
            params={"start": "2025-01", "end": "2025-02"},
        ).json()["data"]["comparison"]
        assert overview["final"]["billed_amount"]["value"] == 130
        assert overview["final"]["measured_energy_kwh"]["value"] == 90
        same_month = client.get(
            "/api/v1/ucs/UC-1001/overview",
            params={"start": "2025-01", "end": "2025-01"},
        ).json()["data"]["comparison"]
        assert same_month["measured_energy_kwh"]["delta"] == 0
        assert same_month["measured_energy_kwh"]["percent_change"] == 0

        assert (
            client.get("/api/v1/ucs/UC-1001/history/not-a-section").status_code == 422
        )
        assert (
            client.get(
                "/api/v1/ucs/UC-1001/history/invoices", params={"page": 0}
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/v1/ucs/UC-1001/history/invoices", params={"page_size": 101}
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/v1/ucs/UC-1001/history/invoices",
                params={"order_by": "customer_name"},
            ).status_code
            == 422
        )
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_zero_gap_meter_snapshot_and_individual_coverage_are_explicit(client):
    repo = deepcopy(SyntheticAnalyticsRepository())
    app = _use_repository(repo)
    try:
        zero = client.get(
            "/api/v1/ucs/UC-1003/overview",
            params={"start": "2025-01", "end": "2025-02"},
        ).json()["data"]["comparison"]
        assert zero["initial"]["measured_energy_kwh"] == {
            "value": 0,
            "status": "available",
            "limitations": [],
        }
        assert zero["measured_energy_kwh"]["delta"] == 10
        assert zero["measured_energy_kwh"]["percent_change"] is None
        assert any(
            "non_positive_base" in x for x in zero["measured_energy_kwh"]["limitations"]
        )

        gap = client.get(
            "/api/v1/ucs/UC-1004/history/consumption",
            params={"start": "2025-01", "end": "2025-02"},
        ).json()
        assert gap["metadata"]["status"] == "partial"
        february = next(
            row for row in gap["data"]["items"] if row["competencia"] == "2025-02"
        )
        assert february["measured_energy_kwh"] is None
        assert february["status"] == "partial"
        overview = client.get(
            "/api/v1/ucs/UC-1004/overview",
            params={"start": "2025-01", "end": "2025-02"},
        ).json()["data"]
        assert overview["open_invoices"]["count"] == 0
        assert overview["current_meter"]["status"] == "empty"

        repo.uc_monthly_coverage.pop("measured_energy_kwh")
        uncovered = client.get(
            "/api/v1/ucs/UC-1001/overview",
            params={"start": "2025-01", "end": "2025-02"},
        ).json()["data"]
        assert uncovered["profile"]["uc_id"] == "UC-1001"
        assert (
            uncovered["comparison"]["initial"]["measured_energy_kwh"]["status"]
            == "unavailable"
        )
        assert uncovered["section_status"]["consumption"] == "unavailable"
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_internal_source_exception_is_not_converted_to_empty_or_unavailable(client):
    class BrokenRepository(SyntheticAnalyticsRepository):
        @property
        def invoices(self):
            raise RuntimeError("internal failure")

        @invoices.setter
        def invoices(self, value):
            self._invoices = value

    app = _use_repository(BrokenRepository())
    try:
        response = client.get("/api/v1/ucs/UC-1001/overview")
        assert response.status_code == 500
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_partial_coverage_limits_history_rows_and_percent_change(client):
    repo = deepcopy(SyntheticAnalyticsRepository())
    repo.uc_monthly_coverage["billed_amount"] = UCCoverage(
        frozenset({"UC-1001"}), "2025-02", "2025-02"
    )
    repo.invoices.append(
        {
            "invoice_id": "OUT-OF-COVERAGE",
            "uc_id": "UC-1001",
            "competencia": "2025-01",
            "billed_amount": 900.0,
            "paid_amount": 900.0,
            "billed_energy_kwh": 800.0,
            "due_date": "2025-02-10",
            "payment_date": "2025-02-09",
            "payment_status": "paid",
        }
    )
    app = _use_repository(repo)
    try:
        history = client.get(
            "/api/v1/ucs/UC-1001/history/invoices",
            params={"start": "2025-01", "end": "2025-02"},
        ).json()
        assert history["metadata"]["status"] == "partial"
        assert all(row["competencia"] == "2025-02" for row in history["data"]["items"])

        overview = client.get(
            "/api/v1/ucs/UC-1001/overview",
            params={"start": "2025-01", "end": "2025-02"},
        ).json()
        amount_change = overview["data"]["comparison"]["billed_amount"]
        assert amount_change["delta"] is None
        assert amount_change["percent_change"] is None
        assert amount_change["status"] == "partial"
        assert overview["metadata"]["status"] == "partial"
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_snapshot_overlap_and_generation_coverage_are_explicit(client):
    repo = deepcopy(SyntheticAnalyticsRepository())
    repo.meters.append(
        {
            "meter_id": "MED-FUTURE",
            "uc_id": "UC-1001",
            "installed_at": "2027-01-01",
            "removed_at": None,
        }
    )
    app = _use_repository(repo)
    try:
        current = client.get("/api/v1/ucs/UC-1001/overview").json()["data"][
            "current_meter"
        ]
        assert current["item"]["meter_id"] == "MED-01"
        assert current["status"] == "available"
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)

    repo.meters.append(
        {
            "meter_id": "MED-OVERLAP",
            "uc_id": "UC-1001",
            "installed_at": "2025-01-01",
            "removed_at": None,
        }
    )
    app = _use_repository(repo)
    try:
        overlap = client.get("/api/v1/ucs/UC-1001/overview").json()["data"][
            "current_meter"
        ]
        assert overlap["item"] is None
        assert overlap["status"] == "partial"

        generation = client.get("/api/v1/ucs/UC-1002/overview").json()["data"][
            "distributed_generation"
        ]
        assert generation["status"] == "available"
        assert generation["items"][0]["capacity_kw"] == 4.2

        repo.uc_snapshot_coverage.pop("distributed_generation")
        unknown = client.get("/api/v1/ucs/UC-1002/overview").json()["data"][
            "distributed_generation"
        ]
        assert unknown["status"] == "unavailable"
        assert unknown["items"] == []
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_month_grammar_rejects_non_ascii_and_noncanonical_months(client):
    repo = deepcopy(SyntheticAnalyticsRepository())
    app = _use_repository(repo)
    try:
        for value in ("2025-+1", "2025- 1", "2025-０１", "0000-01"):
            response = client.get(
                "/api/v1/ucs/UC-1001/overview",
                params={"start": value, "end": "2025-02"},
            )
            assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_all_history_sections_preserve_grain_and_later_payment_date(client):
    repo = deepcopy(SyntheticAnalyticsRepository())
    app = _use_repository(repo)
    try:
        for uc_id, section in (
            ("UC-1001", "consumption"),
            ("UC-1001", "invoices"),
            ("UC-1001", "meters"),
            ("UC-1002", "distributed_generation"),
            ("UC-1001", "interruptions"),
            ("UC-1001", "calls"),
        ):
            response = client.get(f"/api/v1/ucs/{uc_id}/history/{section}")
            assert response.status_code == 200
            assert response.json()["metadata"]["contract_version"] == "1.1.0"
            assert response.json()["data"]["items"]

        invoices = client.get("/api/v1/ucs/UC-1002/history/invoices").json()["data"][
            "items"
        ]
        february = next(row for row in invoices if row["competencia"] == "2025-02")
        assert february["billed_amount"] == 82
        assert february["paid_amount"] == 70
        assert february["payment_date"] == "2025-03-05"
        assert february["payment_status"] == "partial"
        overview = client.get("/api/v1/ucs/UC-1002/overview").json()["data"]
        assert overview["open_invoices"]["count"] == 1
        assert overview["distributed_generation"]["items"][0]["capacity_kw"] == 4.2
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_multiple_readings_do_not_silently_choose_one(client):
    repo = deepcopy(SyntheticAnalyticsRepository())
    repo.readings.append(
        {
            "uc_id": "UC-1001",
            "competencia": "2025-02",
            "measured_energy_kwh": 999.0,
            "status": "available",
        }
    )
    app = _use_repository(repo)
    try:
        overview = client.get("/api/v1/ucs/UC-1001/overview").json()["data"][
            "comparison"
        ]
        assert overview["final"]["measured_energy_kwh"]["value"] is None
        assert overview["final"]["measured_energy_kwh"]["status"] == "unavailable"
        history = client.get("/api/v1/ucs/UC-1001/history/consumption").json()
        february = next(
            row for row in history["data"]["items"] if row["competencia"] == "2025-02"
        )
        assert february["measured_energy_kwh"] is None
        assert february["status"] == "unavailable"
        assert history["metadata"]["status"] == "partial"
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_financial_measure_gap_makes_invoice_section_partial(client):
    repo = deepcopy(SyntheticAnalyticsRepository())
    repo.invoices[0]["paid_amount"] = None
    app = _use_repository(repo)
    try:
        response = client.get(
            "/api/v1/ucs/UC-1001/overview",
            params={"start": "2025-01", "end": "2025-02"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["comparison"]["initial"]["paid_amount"]["status"] == "partial"
        assert data["comparison"]["paid_amount"]["percent_change"] is None
        assert data["section_status"]["invoices"] == "partial"
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)


def test_search_result_with_profile_but_no_analytic_coverage_still_opens(client):
    repo = deepcopy(SyntheticAnalyticsRepository())
    app = _use_repository(repo)
    try:
        search = client.get("/api/v1/ucs", params={"q": "UC-1005"})
        assert search.status_code == 200
        assert [item["uc_id"] for item in search.json()["data"]["items"]] == ["UC-1005"]

        response = client.get("/api/v1/ucs/UC-1005/overview")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["profile"]["uc_id"] == "UC-1005"
        assert data["comparison"]["initial"]["measured_energy_kwh"] == {
            "value": None,
            "status": "unavailable",
            "limitations": [
                "Cobertura de measured_energy_kwh desconhecida para 2025-01."
            ],
        }
        assert data["open_invoices"]["count"] is None
        assert data["current_meter"]["status"] == "unavailable"
        assert data["distributed_generation"] == {
            "items": [],
            "status": "unavailable",
            "limitations": [
                "Cobertura do cadastro de geração distribuída desconhecida."
            ],
        }
        assert set(data["section_status"].values()) == {"unavailable"}
    finally:
        app.dependency_overrides.pop(get_analytics_repository, None)
