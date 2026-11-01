import pytest

from tests.support.platform_auth import login_as_profile

from app.main import app
from app.repositories.analytics import SyntheticAnalyticsRepository, get_analytics_repository_provider


@pytest.fixture(autouse=True)
def synthetic_source(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")


@pytest.fixture(autouse=True)
def authenticated_operations_session(client, monkeypatch):
    login_as_profile(client, monkeypatch, "operations")


def test_summary_consolidates_original_numerators_and_discloses_excluded_feeder(client):
    response = client.get("/api/v1/operations/summary")

    assert response.status_code == 200
    body = response.json()
    summary = body["data"]["summary"]
    assert summary["period"] == {
        "start": "2025-01", "end": "2025-02", "granularity": "month",
    }
    assert summary["observed_period"] == summary["period"]
    assert summary["dec_hours_per_uc"] == 1.5
    assert summary["fec_interruptions_per_uc"] == 0.75
    assert summary["duration_hours_sum"] == 6
    assert summary["interruption_count"] == 3
    assert summary["denominator_uc_count"] == 4
    assert summary["included_uc_count"] == 4
    assert summary["served_uc_count"] == 10
    assert summary["included_feeder_ids"] == ["AL-01", "AL-02"]
    assert summary["excluded_feeder_ids"] == ["AL-03"]
    assert summary["status"] == body["metadata"]["status"] == "partial"
    assert body["metadata"]["contract_version"] == "1.2.0"
    assert client.get("/api/v1/operations/series").json()["metadata"]["contract_version"] == "1.1.0"
    assert client.get("/api/v1/operations/continuity").json()["metadata"]["contract_version"] == "1.0.0"
    assert body["data"]["definition"]["dec_formula"] == (
        "Soma das durações originais em horas dos registros UC-interrupção "
        "/ soma dos denominadores dos alimentadores incluídos."
    )
    assert "available" in body["data"]["definition"]["inclusion_rule"]
    assert "AL-03" in " ".join(summary["limitations"])


@pytest.mark.parametrize(
    "feeder,dec,fec,denominator",
    [("AL-01", 1.5, 1, 2), ("AL-02", 1.5, 0.5, 2)],
)
def test_summary_filter_includes_only_requested_feeder(client, feeder, dec, fec, denominator):
    body = client.get(
        "/api/v1/operations/summary", params={"alimentador": feeder},
    ).json()
    summary = body["data"]["summary"]
    assert summary["dec_hours_per_uc"] == dec
    assert summary["fec_interruptions_per_uc"] == fec
    assert summary["denominator_uc_count"] == denominator
    assert summary["included_feeder_ids"] == [feeder]
    assert summary["excluded_feeder_ids"] == []
    assert summary["status"] == "available"


def test_summary_is_unavailable_when_selected_feeder_has_no_valid_denominator(client):
    body = client.get(
        "/api/v1/operations/summary?alimentador=AL-03",
    ).json()
    summary = body["data"]["summary"]
    assert summary["status"] == body["metadata"]["status"] == "unavailable"
    assert summary["dec_hours_per_uc"] is None
    assert summary["fec_interruptions_per_uc"] is None
    assert summary["duration_hours_sum"] is None
    assert summary["interruption_count"] is None
    assert summary["denominator_uc_count"] is None
    assert summary["served_uc_count"] == 6
    assert summary["included_uc_count"] == 0
    assert summary["included_feeder_ids"] == []
    assert summary["excluded_feeder_ids"] == ["AL-03"]


def test_summary_uses_summed_denominators_for_distinct_weights(client, monkeypatch):
    repository = SyntheticAnalyticsRepository()
    repository.feeders[0]["denominator_uc_count"] = 2
    repository.feeders[1]["denominator_uc_count"] = 3
    repository.feeders[2]["denominator_uc_count"] = None
    repository.units.append({
        **repository.units[2], "uc_id": "UC-WEIGHT-AL02", "alimentador": "AL-02",
    })
    repository.interruptions = [
        {"event_id": "EV-X1", "uc_id": "UC-X1", "feeder_id": "AL-01",
         "competencia": "2025-01", "duration_hours": 3},
        {"event_id": "EV-X2", "uc_id": "UC-X2", "feeder_id": "AL-01",
         "competencia": "2025-02", "duration_hours": 3},
        {"event_id": "EV-X3", "uc_id": "UC-X3", "feeder_id": "AL-02",
         "competencia": "2025-02", "duration_hours": 0},
    ]
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)

    summary = client.get("/api/v1/operations/summary").json()["data"]["summary"]
    assert summary["duration_hours_sum"] == 6
    assert summary["interruption_count"] == 3
    assert summary["denominator_uc_count"] == 5
    assert summary["dec_hours_per_uc"] == 1.2
    assert summary["fec_interruptions_per_uc"] == 0.6
    assert summary["included_feeder_ids"] == ["AL-01", "AL-02"]
    assert summary["excluded_feeder_ids"] == ["AL-03"]


def test_summary_rounds_only_after_aggregating_unrounded_feeder_numerators(client, monkeypatch):
    repository = SyntheticAnalyticsRepository()
    repository.feeders[0]["denominator_uc_count"] = 7
    repository.feeders[1]["denominator_uc_count"] = 3
    repository.units.extend(
        {**repository.units[0], "uc_id": f"UC-ROUND-AL01-{index}"}
        for index in range(5)
    )
    repository.units.append({
        **repository.units[2], "uc_id": "UC-ROUND-AL02", "alimentador": "AL-02",
    })
    repository.interruptions = [
        {"event_id": "EV-R1", "uc_id": "UC-R1", "feeder_id": "AL-01",
         "competencia": "2025-01", "duration_hours": 0.00357},
        {"event_id": "EV-R2", "uc_id": "UC-R2", "feeder_id": "AL-02",
         "competencia": "2025-01", "duration_hours": 0.0012},
    ]
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)

    body = client.get("/api/v1/operations/summary").json()
    summary = body["data"]["summary"]
    assert summary["duration_hours_sum"] == pytest.approx(0.00477)
    assert summary["denominator_uc_count"] == 10
    assert summary["dec_hours_per_uc"] == 0
    # Averaging individually rounded feeder DEC values would yield 0.001.
    assert round((round(0.00357 / 7, 3) * 7 + round(0.0012 / 3, 3) * 3) / 10, 3) == 0.001


@pytest.mark.parametrize(
    "start,end,coverage,observed",
    [
        ("2024-12", "2025-01", "known", {"start": "2025-01", "end": "2025-01", "granularity": "month"}),
        ("2026-01", "2026-02", "known", None),
        ("2025-01", "2025-02", "unknown", None),
    ],
)
def test_summary_does_not_claim_coverage_for_partial_external_or_unknown_windows(
    client, monkeypatch, start, end, coverage, observed,
):
    repository = SyntheticAnalyticsRepository()
    if coverage == "unknown":
        repository.continuity_coverage = None
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)
    response = client.get(
        "/api/v1/operations/summary",
        params={"competencia_inicio": start, "competencia_fim": end},
    )
    assert response.status_code == 200
    summary = response.json()["data"]["summary"]
    assert summary["observed_period"] == observed
    assert summary["status"] == "unavailable"
    assert summary["dec_hours_per_uc"] is None
    assert summary["fec_interruptions_per_uc"] is None
    assert summary["denominator_uc_count"] is None
    assert summary["included_feeder_ids"] == []
    assert summary["excluded_feeder_ids"] == ["AL-01", "AL-02", "AL-03"]


def test_summary_preserves_known_zero_when_coverage_and_denominator_are_known(client):
    body = client.get(
        "/api/v1/operations/summary?alimentador=AL-02&periodo=2025-01",
    ).json()
    summary = body["data"]["summary"]
    assert summary["status"] == "available"
    assert summary["dec_hours_per_uc"] == 0
    assert summary["fec_interruptions_per_uc"] == 0
    assert summary["duration_hours_sum"] == 0
    assert summary["interruption_count"] == 0
    assert summary["denominator_uc_count"] == 2
    assert summary["observed_period"] == summary["period"]


@pytest.mark.parametrize("denominator", [None, 0, -1, 2.5, "2", True])
def test_summary_excludes_invalid_denominators_without_fabricating_numerators(
    client, monkeypatch, denominator,
):
    repository = SyntheticAnalyticsRepository()
    repository.feeders[0]["denominator_uc_count"] = denominator
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)
    summary = client.get(
        "/api/v1/operations/summary?alimentador=AL-01",
    ).json()["data"]["summary"]
    assert summary["status"] == "unavailable"
    assert summary["dec_hours_per_uc"] is None
    assert summary["fec_interruptions_per_uc"] is None
    assert summary["duration_hours_sum"] is None
    assert summary["interruption_count"] is None
    assert summary["denominator_uc_count"] is None
    assert summary["excluded_feeder_ids"] == ["AL-01"]


def test_summary_empty_source_differs_from_source_without_eligible_feeders(client, monkeypatch):
    repository = SyntheticAnalyticsRepository()
    repository.feeders = []
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)

    body = client.get("/api/v1/operations/summary").json()
    summary = body["data"]["summary"]
    assert summary["status"] == body["metadata"]["status"] == "empty"
    assert summary["served_uc_count"] == 0
    assert summary["included_uc_count"] == 0
    assert summary["included_feeder_ids"] == summary["excluded_feeder_ids"] == []
    assert summary["dec_hours_per_uc"] is None
    assert summary["denominator_uc_count"] is None


@pytest.mark.parametrize(
    "path,status",
    [
        ("?alimentador=UNKNOWN", 422),
        ("?periodo=2025-01&periodo=2025-02", 422),
        ("?municipio=Recife", 422),
        ("?competencia_inicio=2020-01&competencia_fim=2030-01", 422),
    ],
)
def test_summary_validates_filters_and_window(client, path, status):
    response = client.get(f"/api/v1/operations/summary{path}")
    assert response.status_code == status
    assert response.json()["error"]["code"] == "invalid_query"
    assert response.headers["Cache-Control"] == "no-store"


def test_summary_source_unavailable_fails_closed_and_is_documented(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "unavailable")
    response = client.get("/api/v1/operations/summary")
    assert response.status_code == 503
    assert "data" not in response.json()
    assert response.headers["Cache-Control"] == "no-store"
    operation = client.get("/openapi.json").json()["paths"]["/api/v1/operations/summary"]["get"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    refs = {schema.get("$ref", "")} | {variant.get("$ref", "") for variant in schema.get("anyOf", [])}
    assert any(reference.endswith(("OperationSummaryResponse", "GoldOperationSummaryResponse")) for reference in refs)
    assert operation["responses"]["422"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/AnalyticsErrorResponse"
    assert operation["responses"]["503"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/AnalyticsErrorResponse"
