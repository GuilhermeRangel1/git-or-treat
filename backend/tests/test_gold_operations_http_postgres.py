"""Gold operation endpoints against a disposable PostgreSQL database and artificial rows."""
import os
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.main import app
import app.repositories.gold_context as gold_context_module
from app.models.gold_load import BATCH, SCHEMA_VERSION, TABLES


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_GOLD_ANALYTICS_POSTGRES_URL"),
    reason="Set TEST_GOLD_ANALYTICS_POSTGRES_URL to a disposable Gold analytics PostgreSQL database.",
)


@pytest.fixture(scope="module")
def gold_engine() -> Engine:
    url = os.environ["TEST_GOLD_ANALYTICS_POSTGRES_URL"]
    parsed = make_url(url)
    assert parsed.get_backend_name() == "postgresql" and parsed.database.endswith("_test")
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    with engine.connect() as connection:
        assert not inspect(connection).get_table_names(), "O banco descartável de analytics deve estar vazio."
        assert connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")) is False
    try:
        with engine.begin() as connection:
            BATCH.create(connection)
            TABLES["indicadores_dec_fec"].create(connection)
        yield engine
    finally:
        with engine.begin() as connection:
            TABLES["indicadores_dec_fec"].drop(connection, checkfirst=True)
            BATCH.drop(connection, checkfirst=True)
        engine.dispose()


@pytest.fixture
def artificial_operations_gold(gold_engine):
    table = TABLES["indicadores_dec_fec"]
    fingerprint = "c" * 64
    with gold_engine.begin() as connection:
        connection.execute(table.delete())
        connection.execute(BATCH.delete())
        connection.execute(BATCH.insert().values(
            id=1, lote="operations-test", schema_version=SCHEMA_VERSION,
            fingerprint=fingerprint,
            importado_em=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
            manifesto={},
        ))
        rows = []
        for feeder, town, months in (
            ("AL-STABLE", "Cidade A", [
                ("2025-01", 10, 4.0, 2), ("2025-02", 10, 6.0, 1),
            ]),
            ("AL-VARIABLE", "Cidade A", [
                ("2025-01", 10, 1.0, 1), ("2025-02", 20, 1.0, 1),
            ]),
            ("AL-GAP", "Cidade A", [("2025-01", 10, 2.0, 1)]),
            ("AL-NULL-NUMERATOR", "Cidade A", [
                ("2025-01", 10, 2.0, 1), ("2025-02", 10, None, None),
            ]),
            ("AL-NULL-DENOMINATOR", "Cidade B", [
                ("2025-01", None, 2.0, 1), ("2025-02", None, 3.0, 1),
            ]),
            ("AL-NULL-DURATION", "Cidade A", [
                ("2025-01", 10, 1.0, 1), ("2025-02", 10, None, 2),
            ]),
            ("AL-NULL-FREQUENCY", "Cidade A", [
                ("2025-01", 10, 1.0, 1), ("2025-02", 10, 2.0, None),
            ]),
            ("AL-NULL-BOTH", "Cidade A", [
                ("2025-01", 10, 1.0, 1), ("2025-02", 10, None, None),
            ]),
            ("AL-ZERO-BASE", "Cidade A", [
                ("2025-01", 0, 1.0, 1), ("2025-02", 0, 2.0, 1),
            ]),
        ):
            for month, denominator, duration, count in months:
                rows.append({
                    "id_alimentador": feeder, "municipio": town, "competencia": month,
                    "total_ucs_alimentador": denominator,
                    "ucs_interrompidas": 1 if count is not None else None,
                    "frequencia_total_interrupcoes": count,
                    "duracao_total_interrupcoes_horas": duration,
                    "DEC": Decimal("0.1") if duration is not None else None,
                    "FEC": Decimal("0.1") if count is not None else None,
                })
        connection.execute(table.insert(), rows)
    return fingerprint


def test_gold_operation_discovery_preserves_feeder_without_municipality(gold_engine, artificial_operations_gold, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "service")
    token = "artificial-read-" + "x" * 32
    monkeypatch.setattr(settings, "ORDERS_READ_TOKEN", SecretStr(token))
    monkeypatch.setattr(gold_context_module, "engine", gold_engine)
    table = TABLES["indicadores_dec_fec"]
    with gold_engine.begin() as connection:
        connection.execute(table.update().where(table.c.id_alimentador == "AL-STABLE").values(municipio=None))
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        options = client.get("/api/v1/operations/options", headers=headers)
        assert options.status_code == 200
        assert None not in options.json()["data"]["municipios"]
        assert {"id": "AL-STABLE", "municipio": None} in options.json()["data"]["alimentadores"]
        detail = client.get("/api/v1/operations/feeders/AL-STABLE?competencia_inicio=2025-01&competencia_fim=2025-02", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["data"]["summary"]["municipality"] is None
        assert detail.json()["data"]["summary"]["dec_hours_per_uc"] == 1.0


def test_gold_operations_http_reconciles_windows_filters_and_missing_evidence(
    gold_engine, artificial_operations_gold, monkeypatch,
):
    fingerprint = artificial_operations_gold
    token = "gold-operations-read-" + "r" * 32
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "service")
    monkeypatch.setattr(settings, "ORDERS_READ_TOKEN", SecretStr(token))
    monkeypatch.setattr(settings, "ORDERS_WRITE_TOKEN", None)
    monkeypatch.setattr(gold_context_module, "engine", gold_engine)
    headers = {"Authorization": f"Bearer {token}"}
    suffix = f"expected_lote=operations-test&expected_fingerprint={fingerprint}"
    window = "competencia_inicio=2025-01&competencia_fim=2025-02"
    with TestClient(app) as client:
        assert client.get("/api/v1/operations/options").status_code == 401
        options = client.get(f"/api/v1/operations/options?{suffix}", headers=headers)
        assert options.status_code == 200
        assert options.headers["cache-control"] == "no-store"
        assert options.json()["data"]["competencias"] == ["2025-01", "2025-02"]
        assert {row["id"] for row in options.json()["data"]["alimentadores"]} >= {"AL-STABLE", "AL-VARIABLE"}
        assert options.json()["metadata"]["fingerprint"] == fingerprint
        assert options.json()["metadata"]["period"] is None
        assert client.get("/api/v1/operations/options?expected_lote=obsolete", headers=headers).status_code == 409
        continuity_response = client.get(f"/api/v1/operations/continuity?{window}&{suffix}", headers=headers)
        assert continuity_response.status_code == 200, continuity_response.text
        continuity = {row["feeder_id"]: row for row in continuity_response.json()["data"]}
        stable = continuity["AL-STABLE"]
        assert stable["duration_hours_sum"] == 10.0
        assert stable["interruption_count"] == 3
        assert stable["denominator_uc_count"] == 10
        assert stable["dec_hours_per_uc"] == 1.0
        assert stable["fec_interruptions_per_uc"] == 0.3
        assert stable["observed_competencies"] == ["2025-01", "2025-02"]
        assert stable["status"] == "partial"
        assert continuity["AL-VARIABLE"]["dec_hours_per_uc"] is None
        assert continuity["AL-VARIABLE"]["denominator_uc_count"] == 10
        assert continuity["AL-VARIABLE"]["status"] == "unavailable"
        assert continuity["AL-VARIABLE"]["dec_status"] == "unavailable"
        assert continuity["AL-VARIABLE"]["fec_status"] == "unavailable"
        assert continuity["AL-GAP"]["missing_competencies"] == ["2025-02"]
        assert continuity["AL-GAP"]["dec_hours_per_uc"] is None
        assert continuity["AL-GAP"]["dec_status"] == "unavailable"
        assert continuity["AL-GAP"]["fec_status"] == "unavailable"
        assert continuity["AL-NULL-NUMERATOR"]["duration_hours_sum"] is None
        assert continuity["AL-NULL-NUMERATOR"]["fec_interruptions_per_uc"] is None
        assert continuity["AL-NULL-DENOMINATOR"]["dec_hours_per_uc"] is None

        null_duration = continuity["AL-NULL-DURATION"]
        assert null_duration["duration_hours_sum"] is None
        assert null_duration["interruption_count"] == 3
        assert null_duration["dec_hours_per_uc"] is None
        assert null_duration["fec_interruptions_per_uc"] == 0.3
        assert null_duration["dec_status"] == "unavailable"
        assert null_duration["fec_status"] == "partial"
        assert "Duração ausente" in " ".join(null_duration["limitations"])
        null_frequency = continuity["AL-NULL-FREQUENCY"]
        assert null_frequency["duration_hours_sum"] == 3.0
        assert null_frequency["interruption_count"] is None
        assert null_frequency["dec_hours_per_uc"] == 0.3
        assert null_frequency["fec_interruptions_per_uc"] is None
        assert null_frequency["dec_status"] == "partial"
        assert null_frequency["fec_status"] == "unavailable"
        assert continuity["AL-NULL-BOTH"]["dec_hours_per_uc"] is None
        assert continuity["AL-NULL-BOTH"]["fec_interruptions_per_uc"] is None
        assert continuity["AL-ZERO-BASE"]["dec_hours_per_uc"] is None
        assert continuity["AL-ZERO-BASE"]["fec_interruptions_per_uc"] is None
        assert continuity["AL-ZERO-BASE"]["dec_status"] == "unavailable"
        assert continuity["AL-ZERO-BASE"]["fec_status"] == "unavailable"

        series_response = client.get(
            f"/api/v1/operations/series?periodo=2025-01&municipio=Cidade%20A&{suffix}",
            headers=headers,
        )
        assert series_response.status_code == 200, series_response.text
        stable_january = next(row for row in series_response.json()["data"]["items"] if row["feeder_id"] == "AL-STABLE")
        assert stable_january["dec_hours_per_uc"] == 0.4
        assert stable_january["fec_interruptions_per_uc"] == 0.2
        assert "AL-NULL-DENOMINATOR" not in {row["feeder_id"] for row in series_response.json()["data"]["items"]}

        summary_response = client.get(f"/api/v1/operations/summary?{window}&{suffix}", headers=headers)
        assert summary_response.status_code == 200, summary_response.text
        summary = summary_response.json()["data"]
        assert summary["dec_included_feeder_ids"] == ["AL-NULL-FREQUENCY", "AL-STABLE"]
        assert summary["fec_included_feeder_ids"] == ["AL-NULL-DURATION", "AL-STABLE"]
        assert set(summary["dec_excluded_feeder_ids"]) == {
            "AL-NULL-BOTH", "AL-NULL-DENOMINATOR", "AL-NULL-DURATION", "AL-NULL-NUMERATOR", "AL-VARIABLE", "AL-GAP", "AL-ZERO-BASE",
        }
        assert set(summary["fec_excluded_feeder_ids"]) == {
            "AL-NULL-BOTH", "AL-NULL-DENOMINATOR", "AL-NULL-FREQUENCY", "AL-NULL-NUMERATOR", "AL-VARIABLE", "AL-GAP", "AL-ZERO-BASE",
        }
        assert summary["dec_denominator_uc_count"] == 20
        assert summary["fec_denominator_uc_count"] == 20
        assert summary["dec_status"] == summary["fec_status"] == "partial"
        assert summary["denominator_uc_count"] is None
        assert summary["included_feeder_ids"] is None
        assert summary["excluded_feeder_ids"] is None
        assert any("populações" in limitation for limitation in summary["limitations"])
        assert summary["duration_hours_sum"] == 13.0
        assert summary["interruption_count"] == 6
        assert summary["dec_hours_per_uc"] == 0.65
        assert summary["fec_interruptions_per_uc"] == 0.3

        stable_summary_response = client.get(
            f"/api/v1/operations/summary?{window}&alimentador=AL-STABLE&{suffix}", headers=headers,
        )
        assert stable_summary_response.status_code == 200, stable_summary_response.text
        stable_summary = stable_summary_response.json()["data"]
        assert stable_summary["denominator_uc_count"] == 10
        assert stable_summary["included_feeder_ids"] == ["AL-STABLE"]
        assert stable_summary["excluded_feeder_ids"] == []
        assert stable_summary["dec_denominator_uc_count"] == stable_summary["fec_denominator_uc_count"] == 10
        assert stable_summary["dec_included_feeder_ids"] == stable_summary["fec_included_feeder_ids"] == ["AL-STABLE"]

        ranking_response = client.get(f"/api/v1/operations/ranking?{window}&metric=fec&{suffix}", headers=headers)
        assert ranking_response.status_code == 200, ranking_response.text
        ranking = ranking_response.json()["data"]
        assert [item["feeder_id"] for item in ranking["items"]] == ["AL-NULL-DURATION", "AL-STABLE"]
        assert ranking["items"][0]["rank"] == 1
        assert ranking["metric"] == "fec"

        dec_ranking_response = client.get(f"/api/v1/operations/ranking?{window}&metric=dec&{suffix}", headers=headers)
        assert dec_ranking_response.status_code == 200, dec_ranking_response.text
        assert [item["feeder_id"] for item in dec_ranking_response.json()["data"]["items"]] == [
            "AL-STABLE", "AL-NULL-FREQUENCY",
        ]

        fec_unavailable_response = client.get(
            f"/api/v1/operations/ranking?{window}&metric=fec&alimentador=AL-NULL-FREQUENCY&{suffix}",
            headers=headers,
        )
        assert fec_unavailable_response.status_code == 200, fec_unavailable_response.text
        fec_unavailable = fec_unavailable_response.json()
        assert fec_unavailable["data"]["items"] == []
        assert fec_unavailable["metadata"]["status"] == "unavailable"
        assert fec_unavailable["data"]["excluded"][0]["dec_status"] == "partial"

        dec_unavailable_response = client.get(
            f"/api/v1/operations/ranking?{window}&metric=dec&alimentador=AL-NULL-DURATION&{suffix}",
            headers=headers,
        )
        assert dec_unavailable_response.status_code == 200, dec_unavailable_response.text
        dec_unavailable = dec_unavailable_response.json()
        assert dec_unavailable["data"]["items"] == []
        assert dec_unavailable["metadata"]["status"] == "unavailable"
        assert dec_unavailable["data"]["excluded"][0]["fec_status"] == "partial"

        detail_response = client.get(f"/api/v1/operations/feeders/AL-STABLE?{window}&{suffix}", headers=headers)
        assert detail_response.status_code == 200, detail_response.text
        detail = detail_response.json()["data"]
        assert detail["occurrences"] is None
        assert detail["occurrences_status"] == "unavailable"
        assert len(detail["series"]) == 2
        assert client.get(f"/api/v1/operations/feeders/AL-UNKNOWN?{window}&{suffix}", headers=headers).status_code == 404
        assert client.get(f"/api/v1/operations/feeders/AL-STABLE?{window}&page=1&{suffix}", headers=headers).status_code == 422

        assert client.get(f"/api/v1/operations/summary?{window}&classe=Residencial&{suffix}", headers=headers).status_code == 422
        assert client.get(f"/api/v1/operations/summary?{window}&municipio=Desconhecida&{suffix}", headers=headers).status_code == 422
        assert client.get(f"/api/v1/operations/summary?{window}&municipio=Cidade%20A&alimentador=AL-NULL-DENOMINATOR&{suffix}", headers=headers).status_code == 422
        assert client.get(f"/api/v1/operations/summary?{window}&expected_lote=stale&expected_fingerprint={fingerprint}", headers=headers).status_code == 409
        assert client.get(f"/api/v1/operations/summary?{window}&expected_lote=operations-test&expected_fingerprint={'d' * 64}", headers=headers).status_code == 409
        assert client.get("/api/v1/operations/summary?" + window).status_code == 401
