import pytest

from app.main import app
from app.repositories.analytics import SyntheticAnalyticsRepository, get_analytics_repository_provider


@pytest.fixture(autouse=True)
def synthetic_source(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "synthetic")


def test_options_explicitly_identify_unsupported_synthetic_source(client):
    response = client.get("/api/v1/operations/options")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_source"
    assert response.headers["cache-control"] == "no-store"


# Independent manual control: AL-01 has two UCs and events lasting 2h in Jan,
# 1h in Feb. AL-02 has two UCs, no Jan event, one 3h Feb event.
# Thus totals are (DEC 1.5, FEC 1) and (DEC 1.5, FEC .5), respectively.
@pytest.mark.parametrize("feeder,expected", [
    ("AL-01", [(1.0, .5, 2.0, 1), (.5, .5, 1.0, 1)]),
    ("AL-02", [(0.0, 0.0, 0.0, 0), (1.5, .5, 3.0, 1)]),
])
def test_series_ranking_and_detail_agree_with_manual_sample(client, feeder, expected):
    params = {"alimentador": feeder}
    series = client.get("/api/v1/operations/series", params=params).json()
    detail_response = client.get(f"/api/v1/operations/feeders/{feeder}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    ranking = client.get("/api/v1/operations/ranking", params=params).json()
    assert series["data"]["items"] == detail["data"]["series"]
    for point, values, month in zip(series["data"]["items"], expected, ["2025-01", "2025-02"], strict=True):
        assert (point["dec_hours_per_uc"], point["fec_interruptions_per_uc"],
                point["duration_hours_sum"], point["interruption_count"]) == values
        assert point["period"] == point["observed_period"] == {"start": month, "end": month, "granularity": "month"}
        assert point["denominator_uc_count"] == point["served_uc_count"] == 2
        assert point["status"] == "available"
        assert feeder in point["text_alternative"]
        assert "demonstração" in point["text_alternative"]
    summary = detail["data"]["summary"]
    assert summary["dec_hours_per_uc"] == 1.5
    assert summary["fec_interruptions_per_uc"] == (1 if feeder == "AL-01" else .5)
    ranked = ranking["data"]["items"][0]
    assert {key: value for key, value in ranked.items() if key != "rank"} == summary
    assert summary["interruption_count"] == detail["pagination"]["total"]
    assert detail["metadata"]["source"]["is_demo"] is True
    assert detail["metadata"]["contract_version"] == "1.1.0"
    assert detail["data"]["definition"]["dec_unit"] == "h/UC"
    assert detail["data"]["definition"]["fec_unit"] == "interrupções/UC"
    assert detail["data"]["definition"]["reference"].endswith("#definicao-demonstrativa")


@pytest.mark.parametrize("metric,period,ids", [
    ("dec", None, ["AL-01", "AL-02"]),
    ("fec", None, ["AL-01", "AL-02"]),
    ("dec", "2025-02", ["AL-02", "AL-01"]),
    ("fec", "2025-02", ["AL-01", "AL-02"]),
])
def test_ranking_metric_order_ties_and_missing_denominator(client, metric, period, ids):
    params = {"metric": metric}
    if period:
        params["periodo"] = period
    response = client.get("/api/v1/operations/ranking", params=params)
    assert response.status_code == 200
    data = response.json()["data"]
    assert [row["feeder_id"] for row in data["items"]] == ids
    assert [row["rank"] for row in data["items"]] == [1, 2]
    assert [row["feeder_id"] for row in data["excluded"]] == ["AL-03"]
    assert data["excluded"][0]["dec_hours_per_uc"] is None


@pytest.mark.parametrize("denominator", [None, 0, -1])
def test_denominator_does_not_hide_occurrences_or_create_zero(client, monkeypatch, denominator):
    repository = SyntheticAnalyticsRepository()
    repository.feeders[0]["denominator_uc_count"] = denominator
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)
    detail = client.get("/api/v1/operations/feeders/AL-01").json()
    summary = detail["data"]["summary"]
    assert summary["status"] == "unavailable"
    assert summary["denominator_uc_count"] == denominator
    assert summary["dec_hours_per_uc"] is summary["fec_interruptions_per_uc"] is None
    assert summary["interruption_count"] == detail["pagination"]["total"] == 2
    assert summary["duration_hours_sum"] == 3
    assert all(point["status"] == "unavailable" for point in detail["data"]["series"])
    ranked = client.get("/api/v1/operations/ranking?alimentador=AL-01").json()["data"]
    assert ranked["items"] == []
    assert ranked["excluded"][0]["feeder_id"] == "AL-01"


@pytest.mark.parametrize("denominator", [2.5, "invalid", "2", True])
def test_invalid_typed_denominator_is_unavailable_without_hiding_valid_feeders(client, monkeypatch, denominator):
    repository = SyntheticAnalyticsRepository()
    repository.feeders[0]["denominator_uc_count"] = denominator
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)

    series_response = client.get("/api/v1/operations/series")
    ranking_response = client.get("/api/v1/operations/ranking")
    detail_response = client.get("/api/v1/operations/feeders/AL-01")
    continuity_response = client.get("/api/v1/operations/continuity")

    assert [series_response.status_code, ranking_response.status_code,
            detail_response.status_code, continuity_response.status_code] == [200, 200, 200, 200]

    series = series_response.json()["data"]["items"]
    assert {point["feeder_id"] for point in series} == {"AL-01", "AL-02", "AL-03"}
    assert all(point["denominator_uc_count"] is None for point in series if point["feeder_id"] == "AL-01")
    assert all(point["status"] == "unavailable" for point in series if point["feeder_id"] == "AL-01")
    assert all(point["denominator_uc_count"] == 2 for point in series if point["feeder_id"] == "AL-02")

    ranking = ranking_response.json()["data"]
    assert [point["feeder_id"] for point in ranking["items"]] == ["AL-02"]
    assert {point["feeder_id"] for point in ranking["excluded"]} == {"AL-01", "AL-03"}
    assert next(point for point in ranking["excluded"] if point["feeder_id"] == "AL-01")["denominator_uc_count"] is None

    detail = detail_response.json()
    summary = detail["data"]["summary"]
    assert summary["denominator_uc_count"] is None
    assert summary["status"] == "unavailable"
    assert summary["dec_hours_per_uc"] is summary["fec_interruptions_per_uc"] is None
    assert any("Denominador demonstrativo ausente, zero ou inválido" in limitation
               for limitation in summary["limitations"])
    assert detail["pagination"]["total"] == 2
    assert len(detail["data"]["occurrences"]) == 2

    continuity = continuity_response.json()["data"]["items"]
    assert {item["feeder_id"] for item in continuity} == {"AL-01", "AL-02", "AL-03"}
    invalid_item = next(item for item in continuity if item["feeder_id"] == "AL-01")
    assert invalid_item["denominator_uc_count"] is None
    assert invalid_item["status"] == "unavailable"
    assert invalid_item["interruption_count"] == 2


@pytest.mark.parametrize("coverage,start,end,status,observed", [
    (True, "2024-12", "2025-01", "partial", {"start": "2025-01", "end": "2025-01", "granularity": "month"}),
    (True, "2026-01", "2026-02", "unavailable", None),
    (False, "2025-01", "2025-02", "unavailable", None),
])
def test_unknown_or_partial_windows_cannot_compete_in_ranking(client, monkeypatch, coverage, start, end, status, observed):
    repository = SyntheticAnalyticsRepository()
    if not coverage:
        repository.continuity_coverage = None
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)
    params = {"competencia_inicio": start, "competencia_fim": end, "alimentador": "AL-01"}
    response = client.get("/api/v1/operations/ranking", params=params)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["items"] == []
    point = body["data"]["excluded"][0]
    assert point["status"] == body["metadata"]["status"] == status
    assert point["observed_period"] == observed
    detail = client.get("/api/v1/operations/feeders/AL-01", params={key: value for key, value in params.items() if key != "alimentador"}).json()
    assert detail["data"]["summary"] == point
    if observed is None:
        assert detail["data"]["occurrences"] == []
        assert all(row["dec_hours_per_uc"] is None for row in detail["data"]["series"])
    else:
        assert [row["status"] for row in detail["data"]["series"]] == ["unavailable", "available"]
        assert [row["event_id"] for row in detail["data"]["occurrences"]] == ["EV-01"]


def test_occurrences_filter_sort_pagination_and_public_fields(client):
    first = client.get("/api/v1/operations/feeders/AL-01?page_size=1").json()
    second = client.get("/api/v1/operations/feeders/AL-01?page_size=1&page=2").json()
    assert first["pagination"] == {"page": 1, "page_size": 1, "total": 2, "total_pages": 2}
    assert [first["data"]["occurrences"][0]["event_id"], second["data"]["occurrences"][0]["event_id"]] == ["EV-01", "EV-02"]
    assert first["data"]["summary"] == second["data"]["summary"]
    filtered = client.get("/api/v1/operations/feeders/AL-01?periodo=2025-02").json()
    assert [row["event_id"] for row in filtered["data"]["occurrences"]] == ["EV-02"]
    assert client.get("/api/v1/operations/feeders/AL-01?page=10").json()["data"]["occurrences"] == []
    assert set(first["data"]["occurrences"][0]) == {"event_id", "uc_id", "feeder_id", "competencia", "duration_hours"}


def test_repeated_uc_interruptions_count_separately_and_order_is_stable(client, monkeypatch):
    repository = SyntheticAnalyticsRepository()
    repository.interruptions = [
        {"event_id": "EV-B", "uc_id": "UC-1001", "feeder_id": "AL-01", "competencia": "2025-01", "duration_hours": 2.0},
        {"event_id": "EV-A", "uc_id": "UC-1001", "feeder_id": "AL-01", "competencia": "2025-01", "duration_hours": 1.0},
    ]
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)
    body = client.get("/api/v1/operations/feeders/AL-01?periodo=2025-01").json()
    assert body["data"]["summary"]["fec_interruptions_per_uc"] == 1.0
    assert body["data"]["summary"]["dec_hours_per_uc"] == 1.5
    assert [row["event_id"] for row in body["data"]["occurrences"]] == ["EV-A", "EV-B"]


@pytest.mark.parametrize("path", ["series", "ranking", "feeders/AL-01"])
@pytest.mark.parametrize("query", [
    "periodo=2025-01&competencia_inicio=2025-01", "periodo=2025-13",
    "competencia_inicio=2025-02&competencia_fim=2025-01",
    "competencia_inicio=2000-01&competencia_fim=2025-01",
])
def test_invalid_window_returns_analytics_error(client, path, query):
    response = client.get(f"/api/v1/operations/{path}?{query}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"


@pytest.mark.parametrize("path", ["series?alimentador=", "series?alimentador=AL-99", "ranking?metric=invalid",
                                      "feeders/AL-01?page=0", "feeders/AL-01?page_size=101"])
def test_invalid_query_parameters(client, path):
    response = client.get(f"/api/v1/operations/{path}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"


def test_unknown_detail_returns_404(client):
    response = client.get("/api/v1/operations/feeders/AL-99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("path", ["series", "ranking", "feeders/AL-01"])
def test_source_unavailable_fails_closed(client, monkeypatch, path):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "unavailable")
    response = client.get(f"/api/v1/operations/{path}")
    assert response.status_code == 503
    assert "data" not in response.json()


@pytest.mark.parametrize("path", ["continuity", "series", "ranking", "feeders/AL-01"])
def test_invalid_period_is_validated_before_unavailable_source(client, monkeypatch, path):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "unavailable")
    response = client.get(f"/api/v1/operations/{path}?periodo=2025-13")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"


@pytest.mark.parametrize("path", ["series", "ranking", "feeders/{feeder_id}"])
def test_openapi_documents_models_and_errors(client, path):
    operation = client.get("/openapi.json").json()["paths"][f"/api/v1/operations/{path}"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    response_refs = {response_schema.get("$ref", "")} | {
        variant.get("$ref", "") for variant in response_schema.get("anyOf", [])
    }
    assert any(reference.endswith(("OperationSeriesResponse", "GoldOperationSeriesResponse",
                                   "OperationRankingResponse", "GoldOperationRankingResponse",
                                   "OperationDetailResponse", "GoldOperationDetailResponse"))
               for reference in response_refs)
    for status in ("422", "503"):
        assert operation["responses"][status]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/AnalyticsErrorResponse"}


@pytest.mark.parametrize("path", [
    "series?alimentador=AL-01&alimentador=AL-02",
    "ranking?metric=dec&metric=fec",
    "series?periodo=2025-01&periodo=2025-01",
    "series?municipio=Recife",
    "feeders/AL-01?alimentador=AL-02",
    "feeders/AL-01?page=1&page=2",
    "continuity?alimentador=AL-01&alimentador=AL-02",
])
def test_ambiguous_and_unknown_filters_are_rejected_before_source_access(client, monkeypatch, path):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "unavailable")
    response = client.get(f"/api/v1/operations/{path}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query"
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("path,status", [
    ("series", 200), ("ranking", 200), ("feeders/AL-01", 200),
    ("feeders/AL-99", 404), ("series?periodo=2025-13", 422),
])
def test_operation_responses_and_errors_are_not_cached(client, path, status):
    response = client.get(f"/api/v1/operations/{path}")
    assert response.status_code == status
    assert response.headers["Cache-Control"] == "no-store"


def test_unavailable_source_is_not_cached(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ANALYTICS_SOURCE", "unavailable")
    response = client.get("/api/v1/operations/series")
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"


def test_rounded_coverage_cannot_hide_population_mismatch(client, monkeypatch):
    repository = SyntheticAnalyticsRepository()
    repository.feeders[0]["denominator_uc_count"] = 2001
    template = next(unit for unit in repository.units if unit["alimentador"] == "AL-01")
    repository.units.extend(dict(template, uc_id=f"UC-TEST-{index}") for index in range(1998))
    monkeypatch.setitem(app.dependency_overrides, get_analytics_repository_provider, lambda: lambda: repository)
    response = client.get("/api/v1/operations/ranking?alimentador=AL-01")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["items"] == []
    point = body["data"]["excluded"][0]
    assert point["coverage_ratio"] == 1.0  # rounded for display, not for eligibility
    assert point["covered_uc_count"] == 2000
    assert point["denominator_uc_count"] == 2001
    assert point["status"] == point["coverage_status"] == "partial"
    legacy = client.get("/api/v1/operations/continuity?alimentador=AL-01").json()
    assert legacy["data"]["items"][0]["status"] == "partial"
