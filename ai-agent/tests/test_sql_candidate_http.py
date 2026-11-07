import asyncio
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import Settings
from app.gold_runtime import create_gold_app
from app.providers.factory import ModelConfigurationError, build_sql_generator
from app.providers.protocols import ModelProviderUnavailable
from app.schemas.sql_generation import SqlGenerationCandidate, SqlGenerationResponse

from .conftest import FakeModelAdapter, InProcessClient

FIXTURE = (
    Path(__file__).resolve().parents[2] / "docs/contracts/examples/text-to-sql-f1-http-v1.json"
)
PATH = "/api/v1/internal/sql-candidates"
TOKEN = "test-gold-sql-generation-token-0000000000"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "X-Correlation-ID": "b" * 32}


def data():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def application(monkeypatch, *, enabled=True, mode="valid"):
    from app import main
    from app.audit import BackendEventSink

    calls = []
    events = []

    class Generator:
        async def generate(self, contents, *, context_version, timeout_seconds):
            calls.append(timeout_seconds)
            if mode == "unavailable":
                raise ModelProviderUnavailable("private-provider-detail")
            if mode == "wait":
                await asyncio.Event().wait()
            row = copy.deepcopy(data()["response"]["candidate"])
            if mode == "wrong_context":
                row["context_version"] = "c" * 64
            return SqlGenerationCandidate.model_validate(row)

    def record(self, event):
        if mode == "audit_failed":
            raise OSError("private-audit-detail")
        events.append(event)

    monkeypatch.setattr(main, "build_model_adapter", lambda settings: FakeModelAdapter())
    monkeypatch.setattr(main, "build_sql_generator", lambda settings: Generator())
    monkeypatch.setattr(BackendEventSink, "record", record)
    app = create_gold_app(
        Settings(
            _env_file=None,
            sql_generation_enabled=enabled,
            service_api_token=TOKEN,
            documentation_search_enabled=False,
            audit_url="http://backend/api/v1/internal/genai-audit-events",
            audit_write_token="test-gold-sql-audit-token-0000000000000",
        )
    )
    return app, calls, events


def test_official_gold_factory_generates_only_audited_candidate(monkeypatch):
    app, calls, events = application(monkeypatch)
    with InProcessClient(app) as client:
        response = client.post(PATH, json=data()["request"], headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json() == SqlGenerationResponse.model_validate(data()["response"]).model_dump(
        mode="json"
    )
    assert response.headers["x-correlation-id"] == "b" * 32
    assert calls == [20]
    assert events and all(event.source_calls == 0 for event in events)
    assert all(event.correlation_id == "b" * 32 for event in events)


def test_repeated_candidate_generation_is_not_cached(monkeypatch):
    app, calls, _ = application(monkeypatch)
    with InProcessClient(app) as client:
        first = client.post(PATH, json=data()["request"], headers=HEADERS)
        second = client.post(PATH, json=data()["request"], headers=HEADERS)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert calls == [20, 20]


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}])
def test_missing_or_wrong_auth_never_reaches_generator(monkeypatch, headers):
    app, calls, _ = application(monkeypatch)
    with InProcessClient(app) as client:
        response = client.post(PATH, json=data()["request"], headers=headers)
    assert response.status_code == 401
    assert calls == []


def test_generation_is_disabled_by_default_and_does_not_call_provider(monkeypatch):
    assert Settings(_env_file=None).sql_generation_enabled is False
    app, calls, _ = application(monkeypatch, enabled=False)
    with InProcessClient(app) as client:
        response = client.post(PATH, json=data()["request"], headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["error"]["retryable"] is False
    assert calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        {"remaining_timeout_ms": 0},
        {"remaining_timeout_ms": True},
        {"contents": "private-invalid-context"},
        {"context_version": "d" * 64},
        {"validated": True},
    ],
)
def test_bad_contract_is_rejected_without_echoing_context(monkeypatch, mutation):
    app, calls, _ = application(monkeypatch)
    payload = {**data()["request"], **mutation}
    with InProcessClient(app) as client:
        response = client.post(PATH, json=payload, headers=HEADERS)
    assert response.status_code == 422
    assert calls == []
    assert "private-invalid-context" not in response.text


@pytest.mark.parametrize(
    "mode,status,retryable",
    [
        ("unavailable", 503, True),
        ("wrong_context", 502, False),
        ("audit_failed", 503, False),
        ("wait", 503, True),
    ],
)
def test_failures_preserve_error_semantics_and_deadline(monkeypatch, mode, status, retryable):
    app, calls, _ = application(monkeypatch, mode=mode)
    payload = data()["request"]
    if mode == "wait":
        payload["remaining_timeout_ms"] = 30
    with InProcessClient(app) as client:
        response = client.post(PATH, json=payload, headers=HEADERS)
    assert response.status_code == status
    assert response.json()["error"]["retryable"] is retryable
    assert "private-" not in response.text
    if mode == "audit_failed":
        assert calls == []


def test_sql_factory_requires_supported_provider_and_key():
    assert build_sql_generator(Settings(_env_file=None)) is None
    with pytest.raises(ModelConfigurationError):
        build_sql_generator(Settings(_env_file=None, sql_generation_enabled=True))
    with pytest.raises(ModelConfigurationError):
        build_sql_generator(
            Settings(_env_file=None, sql_generation_enabled=True, model_provider="gemini")
        )
    marker = object()
    built = build_sql_generator(
        Settings(
            _env_file=None,
            sql_generation_enabled=True,
            model_provider="gemini",
            gemini_api_key="test-key-not-real",
        ),
        client=marker,
    )
    assert built.client is marker


def test_gold_flag_does_not_break_import_or_enable_compatibility_demo():
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            "from app.main import app; "
            "assert app.state.sql_candidate_service is None; "
            "assert app.state.runtime_settings.sql_generation_enabled is False",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        env={
            **os.environ,
            "GENAI_SQL_GENERATION_ENABLED": "true",
            "GENAI_MODEL_PROVIDER": "unavailable",
        },
        timeout=30,
        check=False,
    )
    assert result.returncode == 0
