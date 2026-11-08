import json
import logging

import pytest
from app.core.config import settings
from app.services.genai_sql_telemetry import record_sql_stage, sql_stage
from sqlalchemy.exc import SQLAlchemyError

from tests.support.platform_auth import login_as_profile


def _events(caplog):
    return [
        json.loads(record.getMessage().removeprefix("genai_execution "))
        for record in caplog.records
        if record.getMessage().startswith("genai_execution {")
    ]


def test_sql_stage_records_correlated_duration_without_request_material(caplog):
    correlation_id = "a" * 32
    private_question = "pergunta privada Recife"

    with caplog.at_level(logging.INFO, logger="uvicorn.error"), sql_stage(
        correlation_id, "generation", context_version="b" * 64,
    ):
        pass

    [event] = _events(caplog)
    assert event["service"] == "backend"
    assert event["strategy"] == "text_to_sql_f1"
    assert event["contract_version"] == "text-to-sql-f1-v1"
    assert event["correlation_id"] == correlation_id
    assert event["stage"] == "generation"
    assert event["outcome"] == "success"
    assert event["elapsed_ms"] >= 0
    assert event["context_version"] == "b" * 64
    assert private_question not in caplog.text
    assert not {"question", "sql", "parameters", "filters", "exception"} & event.keys()


def test_sql_stage_logs_allowlisted_reason_without_exception_message(caplog):
    provider_error = type("ModelProviderUnavailable", (RuntimeError,), {})
    private_detail = "private endpoint token=do-not-log"

    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
        pytest.raises(provider_error),
        sql_stage("c" * 32, "generation"),
    ):
        raise provider_error(private_detail)

    [event] = _events(caplog)
    assert event["outcome"] == "error"
    assert event["reason"] == "provider_unavailable"
    assert private_detail not in caplog.text
    assert "token=do-not-log" not in caplog.text


def test_sql_stage_classifies_database_error_without_driver_details(caplog):
    private_database_detail = "relation gold.secret_table missing at db.internal"

    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
        pytest.raises(SQLAlchemyError),
        sql_stage("e" * 32, "sql_execution"),
    ):
        raise SQLAlchemyError(private_database_detail)

    [event] = _events(caplog)
    assert event["outcome"] == "error"
    assert event["reason"] == "database_error"
    assert private_database_detail not in caplog.text
    assert "db.internal" not in caplog.text


def test_sql_stage_sanitizes_invalid_correlation_duration_and_reason(caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        record_sql_stage(
            correlation_id="not-a-correlation",
            stage="http",
            elapsed_ms=-10,
            outcome="error",
            reason="secret detail",
            http_status=503,
        )

    [event] = _events(caplog)
    assert event["correlation_id"] == "invalid"
    assert event["elapsed_ms"] == 0
    assert event["reason"] is None
    assert event["http_status"] == 503


def test_f1_http_failure_is_correlated_without_question_or_path_details(
    client, monkeypatch, caplog,
):
    login_as_profile(client, monkeypatch, "commercial", username="sql-telemetry")
    monkeypatch.setattr(settings, "GENAI_SQL_EXECUTION_ENABLED", False)

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = client.post(
            "/api/v1/ai/sql-analyses", json={"question": "pergunta confidencial Recife"},
        )

    assert response.status_code == 503
    events = _events(caplog)
    http_event = next(event for event in events if event["stage"] == "http")
    assert http_event["strategy"] == "text_to_sql_f1"
    assert http_event["http_status"] == 503
    assert http_event["outcome"] == "error"
    assert "pergunta confidencial" not in caplog.text
    assert "/api/v1/ai/sql-analyses" not in caplog.text
