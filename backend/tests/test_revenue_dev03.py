import pytest

from app.repositories.analytics import RevenueCoverage, SyntheticAnalyticsRepository, get_analytics_repository
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def synthetic_source(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")


def _controlled_revenue_repository():
    repository = SyntheticAnalyticsRepository()
    repository.units = [
        {"uc_id": f"UC-{index}", "municipio": "Recife", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-01", "status": "active"}
        for index in range(1, 6)
    ]
    initial_amounts = [20_000, 16_000, 15_000, 14_000, 15_000]
    initial_energy = [10_000, 20_000, 20_000, 25_000, 25_000]
    final_amounts = [18_000, 17_000, 16_000, 15_000, 10_500]
    final_energy = [18_000, 18_000, 18_000, 18_000, 18_000]
    repository.invoices = [
        {
            "invoice_id": f"{competencia}-{index}",
            "uc_id": f"UC-{index}",
            "competencia": competencia,
            "billed_amount": amount,
            "paid_amount": amount - 100,
            "billed_energy_kwh": energy,
        }
        for competencia, amounts, energies in (
            ("2025-01", initial_amounts, initial_energy),
            ("2025-02", final_amounts, final_energy),
        )
        for index, (amount, energy) in enumerate(zip(amounts, energies, strict=True), start=1)
    ]
    repository.readings = [
        {"uc_id": f"UC-{index}", "competencia": competencia, "measured_energy_kwh": value}
        for competencia, values in (("2025-01", [10, 20, 30, 40, 50]), ("2025-02", [11, 22, 33, 44, 55]))
        for index, value in enumerate(values, start=1)
    ]
    repository.revenue_coverage = RevenueCoverage(
        billed_amount=frozenset({"2025-01", "2025-02"}),
        billed_energy_kwh=frozenset({"2025-01", "2025-02"}),
        paid_amount=frozenset({"2025-01", "2025-02"}),
        measured_energy_kwh=frozenset({"2025-01", "2025-02"}),
    )
    repository.source_kind = "contract-test"
    repository.source_version = "dev03-http-control-v1"
    repository.source_is_demo = True
    return repository


def _revenue_edge_repository(invoice_rows, covered_months=("2025-01", "2025-02"), unit_count=5):
    repository = SyntheticAnalyticsRepository()
    repository.units = [
        {"uc_id": f"EDGE-{index}", "municipio": "Recife", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-01", "status": "active"}
        for index in range(1, unit_count + 1)
    ]
    repository.invoices = list(invoice_rows)
    repository.readings = []
    covered = frozenset(covered_months)
    repository.revenue_coverage = RevenueCoverage(
        billed_amount=covered,
        billed_energy_kwh=covered,
        paid_amount=covered,
        measured_energy_kwh=covered,
    )
    repository.source_kind = "contract-test"
    repository.source_version = "dev03-p3-edge-v1"
    repository.source_is_demo = True
    return repository


def _edge_invoices(count, initial_amount=100, initial_energy=100, final_amount=110, final_energy=100):
    return [
        {
            "invoice_id": f"{month}-{index}",
            "uc_id": f"EDGE-{index}",
            "competencia": month,
            "billed_amount": amount,
            "paid_amount": amount,
            "billed_energy_kwh": energy,
        }
        for month, amount, energy in (
            ("2025-01", initial_amount, initial_energy),
            ("2025-02", final_amount, final_energy),
        )
        for index in range(1, count + 1)
    ]


def _get_revenue_with_repository(client, repository, query=""):
    previous = client.app.dependency_overrides.get(get_analytics_repository)
    client.app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        return client.get(f"/api/v1/revenue{query}")
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_analytics_repository, None)
        else:
            client.app.dependency_overrides[get_analytics_repository] = previous


def test_revenue_http_publishes_1_1_extremes_and_independent_decimal_control(client):
    repository = _controlled_revenue_repository()
    previous = client.app.dependency_overrides.get(get_analytics_repository)
    client.app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        with TestClient(client.app, raise_server_exceptions=True) as test_client:
            response = test_client.get(
                "/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-02"
            )
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_analytics_repository, None)
        else:
            client.app.dependency_overrides[get_analytics_repository] = previous

    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert body["metadata"]["contract_version"] == "1.1.0"
    assert data["total_billed_amount"] == 156_500.0
    assert data["total_billed_energy_kwh"] == 190_000.0
    assert data["total_measured_energy_kwh"] == 315.0
    assert [point["competencia"] for point in data["series"]] == ["2025-01", "2025-02"]
    assert data["comparison"]["initial"] == {
        "competencia": "2025-01",
        "billed_amount": 80_000.0,
        "billed_energy_kwh": 100_000.0,
        "observed_price_brl_per_kwh": 0.8,
        "billed_uc_count": 5,
        "status": "available",
        "limitations": [],
    }
    assert data["comparison"]["final"] == {
        "competencia": "2025-02",
        "billed_amount": 76_500.0,
        "billed_energy_kwh": 90_000.0,
        "observed_price_brl_per_kwh": 0.85,
        "billed_uc_count": 5,
        "status": "available",
        "limitations": [],
    }
    assert data["comparison"]["billed_amount_change_brl"] == -3_500.0
    assert data["comparison"]["billed_energy_change_kwh"] == -10_000.0
    assert data["comparison"]["measured_energy_change_kwh"] == 15.0
    assert data["comparison"]["billed_amount_change_percent"] == -4.38
    assert data["price_volume"]["volume_effect_brl"] == -8_000.0
    assert data["price_volume"]["price_effect_brl"] == 5_000.0
    assert data["price_volume"]["interaction_effect_brl"] == -500.0
    assert data["price_volume"]["rounding_adjustment_brl"] == 0.0


def test_synthetic_revenue_has_two_covered_municipalities_and_a_valid_main_comparison(client):
    response = client.get("/api/v1/revenue")

    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["comparison"]["initial"]["billed_amount"] == 800.0
    assert data["comparison"]["initial"]["billed_uc_count"] == 8
    assert data["comparison"]["final"]["billed_amount"] == 927.0
    assert data["comparison"]["final"]["billed_uc_count"] == 8
    assert data["comparison"]["billed_amount_change_brl"] == 127.0
    assert data["comparison"]["billed_energy_change_kwh"] == 125.0
    assert data["quality"]["percent_change_eligible"] is True
    assert data["price_volume"]["status"] == "available"
    assert data["filter_options"]["municipios"] == ["Olinda", "Paulista", "Recife"]
    assert data["filter_options"]["classes"] == ["Comercial", "Residencial"]
    assert body["metadata"]["status"] == "partial"
    assert data["coverage"]["measured_energy_kwh"]["status"] == "partial"

    for query, expected_count in (
        ("municipio=Olinda", 1),
        ("municipio=Recife", 7),
        ("bairro=Casa%20Forte", 2),
        ("classe=Comercial", 2),
        ("classe=Residencial", 6),
        ("municipio=Recife&classe=Residencial", 5),
    ):
        filtered = client.get(f"/api/v1/revenue?{query}")
        assert filtered.status_code == 200
        comparison = filtered.json()["data"]["comparison"]
        assert comparison["initial"]["billed_uc_count"] == expected_count
        assert comparison["final"]["billed_uc_count"] == expected_count


def test_revenue_series_includes_uncovered_month_without_fabricating_zero(client):
    response = client.get(
        "/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-03"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert [point["competencia"] for point in data["series"]] == [
        "2025-01", "2025-02", "2025-03"
    ]
    assert data["series"][2]["billed_amount"] is None
    assert data["series"][2]["billed_energy_kwh"] is None
    assert data["coverage"]["billed_amount"]["covered_months"] == ["2025-01", "2025-02"]
    assert data["coverage"]["billed_amount"]["missing_months"] == ["2025-03"]
    assert data["comparison"]["billed_amount_change_brl"] is None
    assert data["price_volume"]["status"] == "unavailable"


def test_revenue_same_competence_keeps_series_and_has_no_comparison(client):
    response = client.get(
        "/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-01"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["series"]) == 1
    assert data["series"][0]["billed_amount"] == 800.0
    assert data["total_billed_amount"] == 800.0
    assert data["comparison"]["billed_amount_change_brl"] is None
    assert data["comparison"]["billed_amount_change_percent"] is None
    assert data["comparison"]["measured_energy_change_kwh"] is None
    assert data["price_volume"]["status"] == "unavailable"
    assert data["price_volume"]["price_effect_brl"] is None


def test_same_competence_with_complete_coverage_does_not_mark_envelope_partial(client):
    repository = _controlled_revenue_repository()
    previous = client.app.dependency_overrides.get(get_analytics_repository)
    client.app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        with TestClient(client.app, raise_server_exceptions=True) as test_client:
            response = test_client.get(
                "/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-01"
            )
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_analytics_repository, None)
        else:
            client.app.dependency_overrides[get_analytics_repository] = previous

    assert response.status_code == 200
    assert response.json()["metadata"]["status"] == "available"
    assert response.json()["data"]["comparison"]["measured_energy_change_kwh"] is None


def test_covered_empty_municipality_is_zero_but_uncovered_month_is_null(client):
    covered = client.get(
        "/api/v1/revenue?municipio=Paulista&competencia_inicio=2025-01&competencia_fim=2025-02"
    )
    uncovered = client.get(
        "/api/v1/revenue?municipio=Paulista&competencia_inicio=2024-12&competencia_fim=2024-12"
    )

    assert covered.status_code == 200
    covered_data = covered.json()["data"]
    assert covered_data["series"][0]["billed_amount"] == 0.0
    assert covered_data["comparison"]["initial"]["billed_uc_count"] == 0
    assert covered_data["comparison"]["billed_amount_change_brl"] == 0.0
    assert covered_data["comparison"]["billed_amount_change_percent"] is None

    assert uncovered.status_code == 200
    uncovered_data = uncovered.json()["data"]
    assert uncovered_data["series"][0]["billed_amount"] is None
    assert uncovered_data["comparison"]["initial"]["billed_amount"] is None
    assert uncovered_data["comparison"]["initial"]["billed_uc_count"] is None


def test_revenue_rejects_repeated_scalar_and_invalid_group_by(client):
    repeated = client.get(
        "/api/v1/revenue?competencia_inicio=2025-01&competencia_inicio=2025-02"
    )
    invalid_group = client.get("/api/v1/revenue?group_by=feeder")

    assert repeated.status_code == 422
    assert repeated.json()["error"]["details"][0]["field"] == "competencia_inicio"
    assert invalid_group.status_code == 422
    assert invalid_group.json()["error"]["code"] == "invalid_query"


def test_revenue_does_not_turn_unknown_payments_into_zero(client):
    repository = _controlled_revenue_repository()
    for invoice in repository.invoices:
        invoice["paid_amount"] = None
    previous = client.app.dependency_overrides.get(get_analytics_repository)
    client.app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        response = client.get(
            "/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-02"
        )
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_analytics_repository, None)
        else:
            client.app.dependency_overrides[get_analytics_repository] = previous

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_paid_amount"] is None
    assert all(point["paid_amount"] is None for point in data["series"])
    assert data["coverage"]["paid_amount"]["status"] == "partial"
    assert data["price_volume"]["status"] == "available"
    assert response.json()["metadata"]["status"] == "partial"


def test_revenue_null_financial_fact_keeps_observed_subtotal_and_blocks_comparison(client):
    repository = _controlled_revenue_repository()
    repository.invoices[0]["billed_amount"] = None
    previous = client.app.dependency_overrides.get(get_analytics_repository)
    client.app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        with TestClient(client.app, raise_server_exceptions=True) as test_client:
            response = test_client.get(
                "/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-02"
            )
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_analytics_repository, None)
        else:
            client.app.dependency_overrides[get_analytics_repository] = previous

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["series"][0]["billed_amount"] == 60_000.0
    assert data["total_billed_amount"] == 136_500.0
    assert data["coverage"]["billed_amount"]["status"] == "partial"
    assert data["comparison"]["initial"]["status"] == "partial"
    assert data["comparison"]["billed_amount_change_brl"] is None
    assert data["price_volume"]["status"] == "unavailable"


def test_valid_filters_without_a_matching_universe_stay_empty_not_zero(client):
    response = client.get(
        "/api/v1/revenue?municipio=Olinda&classe=Comercial"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["status"] == "empty"
    assert body["data"]["comparison"]["initial"]["status"] == "empty"
    assert body["data"]["comparison"]["initial"]["billed_amount"] is None
    assert body["data"]["series"][0]["billed_amount"] is None


def test_openapi_exposes_full_revenue_1_1_response_and_group_parameter(client):
    operation = client.get("/openapi.json").json()["paths"]["/api/v1/revenue"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["group_by"]["schema"]["enum"] == ["municipio", "bairro", "classe"]
    revenue_schema = client.get("/openapi.json").json()["components"]["schemas"]["RevenueData"]
    assert {
        "comparison", "coverage", "quality", "breakdown", "filter_options"
    } <= set(revenue_schema["properties"])


def test_revenue_municipality_breakdown_reconciles_to_independent_http_totals(client):
    repository = _controlled_revenue_repository()
    repository.units.extend([
        {"uc_id": "UC-6", "municipio": "Olinda", "bairro": "Centro", "classe": "Comercial", "alimentador": "AL-02", "status": "active"},
    ])
    repository.invoices.extend([
        {"invoice_id": "2025-01-6", "uc_id": "UC-6", "competencia": "2025-01", "billed_amount": 1_000, "paid_amount": 900, "billed_energy_kwh": 1_000},
        {"invoice_id": "2025-02-6", "uc_id": "UC-6", "competencia": "2025-02", "billed_amount": 1_500, "paid_amount": 1_400, "billed_energy_kwh": 1_500},
    ])
    previous = client.app.dependency_overrides.get(get_analytics_repository)
    client.app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        with TestClient(client.app, raise_server_exceptions=True) as test_client:
            response = test_client.get(
                "/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-02&group_by=municipio"
            )
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_analytics_repository, None)
        else:
            client.app.dependency_overrides[get_analytics_repository] = previous

    assert response.status_code == 200
    data = response.json()["data"]
    breakdown = data["breakdown"]
    assert [(item["key"], item["label"]) for item in breakdown["items"]] == [
        ("municipio:Olinda", "Olinda"),
        ("municipio:Recife", "Recife"),
    ]
    olinda, recife = breakdown["items"]
    assert olinda["filters"]["municipio"] == "Olinda"
    assert olinda["comparison"]["initial"]["billed_amount"] == 1_000.0
    assert olinda["comparison"]["final"]["billed_amount"] == 1_500.0
    assert recife["comparison"]["initial"]["billed_amount"] == 80_000.0
    assert recife["comparison"]["final"]["billed_amount"] == 76_500.0
    reconciliation = breakdown["reconciliation"]
    assert reconciliation["initial_known_sum_brl"] == data["comparison"]["initial"]["billed_amount"] == 81_000.0
    assert reconciliation["final_known_sum_brl"] == data["comparison"]["final"]["billed_amount"] == 78_000.0
    assert reconciliation["comparable_change_sum_brl"] == data["comparison"]["billed_amount_change_brl"] == -3_000.0
    assert reconciliation["non_comparable_group_count"] == 0
    assert reconciliation["unattributed_change_brl"] == 0.0
    assert reconciliation["residual_brl"] == 0.0
    assert reconciliation["status"] == "available"


def test_revenue_neighborhood_groups_keep_municipality_in_identity_and_filters(client):
    repository = _controlled_revenue_repository()
    repository.units.append(
        {"uc_id": "UC-6", "municipio": "Olinda", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-02", "status": "active"}
    )
    repository.invoices.extend([
        {"invoice_id": "2025-01-6", "uc_id": "UC-6", "competencia": "2025-01", "billed_amount": 1_000, "paid_amount": 900, "billed_energy_kwh": 1_000},
        {"invoice_id": "2025-02-6", "uc_id": "UC-6", "competencia": "2025-02", "billed_amount": 1_500, "paid_amount": 1_400, "billed_energy_kwh": 1_500},
    ])
    previous = client.app.dependency_overrides.get(get_analytics_repository)
    client.app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        response = client.get(
            "/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-02&group_by=bairro"
        )
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_analytics_repository, None)
        else:
            client.app.dependency_overrides[get_analytics_repository] = previous

    assert response.status_code == 200
    items = response.json()["data"]["breakdown"]["items"]
    centers = [item for item in items if item["label"] == "Centro"]
    assert len(centers) == 2
    assert {item["filters"]["municipio"] for item in centers} == {"Recife", "Olinda"}
    assert {item["filters"]["bairro"] for item in centers} == {"Centro"}
    assert len({item["key"] for item in centers}) == 2


def test_revenue_class_groups_and_missing_dimension_marker_are_filterable(client):
    repository = _controlled_revenue_repository()
    repository.units.append(
        {"uc_id": "UC-6", "municipio": None, "bairro": "  ", "classe": "Comercial", "alimentador": "AL-02", "status": "active"}
    )
    repository.invoices.extend([
        {"invoice_id": "2025-01-6", "uc_id": "UC-6", "competencia": "2025-01", "billed_amount": 100, "paid_amount": 90, "billed_energy_kwh": 100},
        {"invoice_id": "2025-02-6", "uc_id": "UC-6", "competencia": "2025-02", "billed_amount": 150, "paid_amount": 140, "billed_energy_kwh": 150},
    ])
    previous = client.app.dependency_overrides.get(get_analytics_repository)
    client.app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        class_response = client.get("/api/v1/revenue?group_by=classe")
        missing_response = client.get(
            "/api/v1/revenue?municipio=__grid360_missing__&group_by=municipio"
        )
        invalid_response = client.get(
            "/api/v1/revenue?alimentador=__grid360_missing__"
        )
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_analytics_repository, None)
        else:
            client.app.dependency_overrides[get_analytics_repository] = previous

    assert class_response.status_code == 200
    assert [item["key"] for item in class_response.json()["data"]["breakdown"]["items"]] == [
        "classe:Comercial", "classe:Residencial"
    ]
    assert missing_response.status_code == 200
    missing = missing_response.json()["data"]
    assert missing["breakdown"]["items"][0]["label"] == "Não informado"
    assert missing["breakdown"]["items"][0]["filters"]["municipio"] == "__grid360_missing__"
    assert "__grid360_missing__" in missing["filter_options"]["municipios"]
    assert invalid_response.status_code == 422


def test_revenue_rejects_reserved_missing_marker_as_a_literal_source_value(client):
    repository = _controlled_revenue_repository()
    repository.units[0]["municipio"] = "__grid360_missing__"
    previous = client.app.dependency_overrides.get(get_analytics_repository)
    client.app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        response = client.get("/api/v1/revenue")
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_analytics_repository, None)
        else:
            client.app.dependency_overrides[get_analytics_repository] = previous

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "source_unavailable"


def test_revenue_reconciliation_reports_non_comparable_groups_without_fabricating_residual(client):
    repository = _controlled_revenue_repository()
    repository.units.append(
        {"uc_id": "UC-6", "municipio": "Olinda", "bairro": "Bairro Novo", "classe": "Comercial", "alimentador": "AL-02", "status": "active"}
    )
    repository.invoices.extend([
        {"invoice_id": "2025-01-6", "uc_id": "UC-6", "competencia": "2025-01", "billed_amount": None, "paid_amount": 90, "billed_energy_kwh": 100},
        {"invoice_id": "2025-02-6", "uc_id": "UC-6", "competencia": "2025-02", "billed_amount": 150, "paid_amount": 140, "billed_energy_kwh": 150},
    ])
    previous = client.app.dependency_overrides.get(get_analytics_repository)
    client.app.dependency_overrides[get_analytics_repository] = lambda: repository
    try:
        response = client.get(
            "/api/v1/revenue?competencia_inicio=2025-01&competencia_fim=2025-02&group_by=municipio"
        )
    finally:
        if previous is None:
            client.app.dependency_overrides.pop(get_analytics_repository, None)
        else:
            client.app.dependency_overrides[get_analytics_repository] = previous

    assert response.status_code == 200
    breakdown = response.json()["data"]["breakdown"]
    reconciliation = breakdown["reconciliation"]
    assert reconciliation["non_comparable_group_count"] == 1
    assert reconciliation["initial_known_sum_brl"] == 80_000.0
    assert reconciliation["final_known_sum_brl"] == 76_650.0
    assert reconciliation["comparable_change_sum_brl"] == -3_500.0
    assert reconciliation["unattributed_change_brl"] is None
    assert reconciliation["residual_brl"] is None
    assert reconciliation["status"] == "unavailable"


@pytest.mark.parametrize(("invoice_count", "expected_eligible"), [(0, False), (1, False), (4, False), (5, True)])
def test_revenue_quality_threshold_uses_distinct_billed_units(client, invoice_count, expected_eligible):
    repository = _revenue_edge_repository(_edge_invoices(invoice_count))

    response = _get_revenue_with_repository(client, repository)

    assert response.status_code == 200
    comparison = response.json()["data"]["comparison"]
    quality = response.json()["data"]["quality"]
    assert comparison["initial"]["billed_uc_count"] == invoice_count
    assert comparison["final"]["billed_uc_count"] == invoice_count
    assert quality["small_base"] is (invoice_count < 5)
    assert quality["percent_change_eligible"] is expected_eligible
    assert (comparison["billed_amount_change_percent"] is not None) is expected_eligible


def test_revenue_quality_counts_distinct_units_when_a_unit_has_duplicate_invoices(client):
    invoices = _edge_invoices(5)
    duplicate = dict(invoices[0], invoice_id="2025-01-duplicate", billed_amount=25)
    invoices.append(duplicate)
    repository = _revenue_edge_repository(invoices)

    response = _get_revenue_with_repository(client, repository)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["comparison"]["initial"]["billed_uc_count"] == 5
    assert data["comparison"]["initial"]["billed_amount"] == 525.0
    assert data["quality"]["percent_change_eligible"] is True


@pytest.mark.parametrize(
    ("initial_energy", "final_energy"),
    [(0, 100), (100, 0), (0, 0)],
)
def test_revenue_zero_energy_keeps_known_absolute_change_and_disables_price_volume(
    client, initial_energy, final_energy
):
    repository = _revenue_edge_repository(
        _edge_invoices(5, initial_amount=100, initial_energy=initial_energy, final_amount=120, final_energy=final_energy)
    )

    response = _get_revenue_with_repository(client, repository)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["comparison"]["billed_amount_change_brl"] == 100.0
    assert data["comparison"]["billed_amount_change_percent"] == 20.0
    assert data["price_volume"]["status"] == "unavailable"
    assert data["price_volume"]["price_effect_brl"] is None
    assert data["price_volume"]["volume_effect_brl"] is None


def test_revenue_negative_initial_amount_blocks_percent_but_preserves_absolute_and_method(client):
    repository = _revenue_edge_repository(
        _edge_invoices(5, initial_amount=-100, initial_energy=100, final_amount=-50, final_energy=100)
    )

    response = _get_revenue_with_repository(client, repository)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["comparison"]["initial"]["billed_amount"] == -500.0
    assert data["comparison"]["billed_amount_change_brl"] == 250.0
    assert data["comparison"]["billed_amount_change_percent"] is None
    assert data["quality"]["percent_change_eligible"] is False
    assert data["price_volume"]["status"] == "available"
    assert data["price_volume"]["price_effect_brl"] == 250.0


def test_revenue_missing_intermediate_financial_coverage_blocks_window_comparison(client):
    invoices = [
        {"invoice_id": f"{month}-{index}", "uc_id": f"EDGE-{index}", "competencia": month, "billed_amount": amount, "paid_amount": amount, "billed_energy_kwh": 100}
        for month, amount in (("2025-01", 100), ("2025-03", 130))
        for index in range(1, 6)
    ]
    repository = _revenue_edge_repository(invoices, covered_months=("2025-01", "2025-03"))

    response = _get_revenue_with_repository(
        client,
        repository,
        "?competencia_inicio=2025-01&competencia_fim=2025-03",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert [point["competencia"] for point in data["series"]] == ["2025-01", "2025-02", "2025-03"]
    assert data["series"][1]["billed_amount"] is None
    assert data["coverage"]["billed_amount"]["status"] == "partial"
    assert data["comparison"]["billed_amount_change_brl"] is None
    assert data["price_volume"]["status"] == "unavailable"


def test_revenue_fractional_prices_use_unrounded_decimal_intermediates_and_explicit_adjustment(client):
    repository = _revenue_edge_repository(
        _edge_invoices(5, initial_amount=20, initial_energy=0.6, final_amount=20.2, final_energy=0.602)
    )

    response = _get_revenue_with_repository(client, repository)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["comparison"]["initial"]["billed_amount"] == 100.0
    assert data["comparison"]["final"]["billed_amount"] == 101.0
    assert data["comparison"]["billed_amount_change_brl"] == 1.0
    assert data["comparison"]["initial"]["observed_price_brl_per_kwh"] == 33.3333
    assert data["comparison"]["final"]["observed_price_brl_per_kwh"] == 33.5548
    assert data["price_volume"]["volume_effect_brl"] == 0.33
    assert data["price_volume"]["price_effect_brl"] == 0.66
    assert data["price_volume"]["interaction_effect_brl"] == 0.0
    assert data["price_volume"]["rounding_adjustment_brl"] == 0.01
    assert sum(data["price_volume"][name] for name in (
        "volume_effect_brl", "price_effect_brl", "interaction_effect_brl", "rounding_adjustment_brl"
    )) == data["comparison"]["billed_amount_change_brl"]


def test_revenue_mix_shift_keeps_aggregate_effects_separate_from_group_changes(client):
    units = [
        {"uc_id": f"MIX-A-{index}", "municipio": "Recife", "bairro": "Centro", "classe": "A", "alimentador": "AL-01", "status": "active"}
        for index in range(1, 6)
    ] + [
        {"uc_id": f"MIX-B-{index}", "municipio": "Olinda", "bairro": "Centro", "classe": "B", "alimentador": "AL-02", "status": "active"}
        for index in range(1, 6)
    ]
    invoices = []
    for group, monthly_values in (
        ("A", (("2025-01", 20, 20), ("2025-02", 40, 40))),
        ("B", (("2025-01", 40, 20), ("2025-02", 20, 10))),
    ):
        for month, amount, energy in monthly_values:
            for index in range(1, 6):
                invoices.append({
                    "invoice_id": f"{group}-{month}-{index}",
                    "uc_id": f"MIX-{group}-{index}",
                    "competencia": month,
                    "billed_amount": amount,
                    "paid_amount": amount,
                    "billed_energy_kwh": energy,
                })
    repository = _revenue_edge_repository(invoices)
    repository.units = units

    response = _get_revenue_with_repository(
        client, repository, "?group_by=municipio"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["comparison"]["initial"]["billed_amount"] == 300.0
    assert data["comparison"]["final"]["billed_amount"] == 300.0
    assert data["comparison"]["billed_amount_change_brl"] == 0.0
    assert data["comparison"]["billed_energy_change_kwh"] == 50.0
    assert data["price_volume"]["volume_effect_brl"] == 75.0
    assert data["price_volume"]["price_effect_brl"] == -60.0
    assert data["price_volume"]["interaction_effect_brl"] == -15.0
    assert [item["comparison"]["billed_amount_change_brl"] for item in data["breakdown"]["items"]] == [-100.0, 100.0]
    assert data["breakdown"]["reconciliation"]["comparable_change_sum_brl"] == 0.0
    assert data["breakdown"]["reconciliation"]["residual_brl"] == 0.0


def test_revenue_rounds_negative_half_cents_away_from_zero_and_closes_published_change(client):
    repository = _revenue_edge_repository(
        _edge_invoices(5, initial_amount=-1.005, initial_energy=1, final_amount=1.005, final_energy=1)
    )

    response = _get_revenue_with_repository(client, repository)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["comparison"]["initial"]["billed_amount"] == -5.03
    assert data["comparison"]["final"]["billed_amount"] == 5.03
    assert data["comparison"]["billed_amount_change_brl"] == 10.06
    assert data["price_volume"]["rounding_adjustment_brl"] == 0.01
    assert sum(data["price_volume"][name] for name in (
        "volume_effect_brl", "price_effect_brl", "interaction_effect_brl", "rounding_adjustment_brl"
    )) == data["comparison"]["billed_amount_change_brl"]


def test_revenue_percent_uses_the_published_initial_snapshot(client):
    repository = _revenue_edge_repository(
        _edge_invoices(5, initial_amount=0.005, initial_energy=1, final_amount=0.015, final_energy=1)
    )

    response = _get_revenue_with_repository(client, repository)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["comparison"]["initial"]["billed_amount"] == 0.03
    assert data["comparison"]["final"]["billed_amount"] == 0.08
    assert data["comparison"]["billed_amount_change_brl"] == 0.05
    assert data["comparison"]["billed_amount_change_percent"] == 166.67


def test_revenue_totals_round_after_adding_raw_decimal_facts(client):
    repository = _revenue_edge_repository([
        {"invoice_id": month, "uc_id": "EDGE-1", "competencia": month, "billed_amount": 0.005, "paid_amount": 0.005, "billed_energy_kwh": 0.005}
        for month in ("2025-01", "2025-02")
    ])

    response = _get_revenue_with_repository(client, repository)

    assert response.status_code == 200
    data = response.json()["data"]
    assert [point["billed_amount"] for point in data["series"]] == [0.01, 0.01]
    assert data["total_billed_amount"] == 0.01
    assert data["total_paid_amount"] == 0.01
    assert data["total_billed_energy_kwh"] == 0.01
    assert data["observed_price_brl_per_kwh"] == 1.0


def test_revenue_group_reconciliation_exposes_published_subcent_rounding_mismatch(client):
    repository = _revenue_edge_repository([
        {"invoice_id": "2025-01-a", "uc_id": "EDGE-1", "competencia": "2025-01", "billed_amount": 0.005, "paid_amount": 0.005, "billed_energy_kwh": 1},
        {"invoice_id": "2025-02-a", "uc_id": "EDGE-1", "competencia": "2025-02", "billed_amount": 0.005, "paid_amount": 0.005, "billed_energy_kwh": 1},
        {"invoice_id": "2025-01-b", "uc_id": "EDGE-6", "competencia": "2025-01", "billed_amount": 0.005, "paid_amount": 0.005, "billed_energy_kwh": 1},
        {"invoice_id": "2025-02-b", "uc_id": "EDGE-6", "competencia": "2025-02", "billed_amount": 0.005, "paid_amount": 0.005, "billed_energy_kwh": 1},
    ], unit_count=6)
    repository.units[-1]["municipio"] = "Olinda"

    response = _get_revenue_with_repository(client, repository)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["comparison"]["initial"]["billed_amount"] == 0.01
    items = data["breakdown"]["items"]
    assert [item["comparison"]["initial"]["billed_amount"] for item in items] == [0.01, 0.01]
    reconciliation = data["breakdown"]["reconciliation"]
    assert reconciliation["initial_known_sum_brl"] == 0.02
    assert reconciliation["final_known_sum_brl"] == 0.02
    assert reconciliation["residual_brl"] == 0.0
    assert reconciliation["status"] == "unavailable"
    assert any("arredondamento" in limitation.lower() for limitation in reconciliation["limitations"])
    assert not any("soma das variações" in limitation.lower() for limitation in reconciliation["limitations"])
