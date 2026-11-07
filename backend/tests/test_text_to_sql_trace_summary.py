import json
from pathlib import Path

import pytest
from scripts.summarize_text_to_sql_trace import summarize_trace


def _line(marker, event):
    return f"INFO {marker} {json.dumps(event)}"


def test_summary_aggregates_only_f1_and_never_returns_correlation_or_content():
    correlation = "a" * 32
    lines = [
        _line("genai_execution", {
            "service": "backend", "strategy": "text_to_sql_f1",
            "correlation_id": correlation, "stage": "http", "elapsed_ms": 90,
            "outcome": "success", "http_status": 200,
            "contract_version": "text-to-sql-f1-v1", "context_version": "b" * 64,
        }),
        _line("genai_execution", {
            "service": "backend", "strategy": "text_to_sql_f1",
            "correlation_id": correlation, "stage": "sql_execution", "elapsed_ms": 30,
            "outcome": "success", "question": "private question", "sql": "SELECT secret",
        }),
        _line("genai_execution", {
            "correlation_id": correlation, "stage": "model", "queue_ms": 5,
            "work_ms": 40, "outcome": "success",
        }),
        _line("genai_usage", {
            "correlation_id": correlation, "provider": "gemini", "model": "model-a",
            "prompt_version": "f1-16", "attempts": 1, "prompt_tokens": 100,
            "output_tokens": 20, "thought_tokens": None, "cached_tokens": 0,
            "total_tokens": 120,
            "dependencies": {"google-genai": "2.30.0", "sqlglot": "30.24.0", "psycopg": None},
        }),
        _line("genai_execution", {
            "service": "backend", "strategy": "text_to_sql_f1",
            "correlation_id": correlation, "stage": "runtime", "elapsed_ms": 0,
            "outcome": "success",
            "dependencies": {"sqlglot": "30.24.0", "sqlalchemy": "2.0.44", "psycopg": None},
        }),
        _line("genai_execution", {
            "service": "backend", "strategy": "text_to_sql_f1",
            "correlation_id": correlation, "stage": "context", "elapsed_ms": 2,
            "outcome": "success", "mapping_version": "mapping-v2",
            "dictionary_version": "dictionary-v3",
        }),
        _line("genai_execution", {
            "service": "backend", "strategy": "legacy", "correlation_id": "c" * 32,
            "stage": "http", "elapsed_ms": 999,
        }),
    ]
    report = summarize_trace(lines)

    assert report["requests"] == 1
    assert report["http"]["latency"] == {"samples": 1, "p50_ms": 90, "p95_ms": 90, "max_ms": 90}
    assert report["stages"]["sql_execution"]["p50_ms"] == 30
    assert report["model_queue"]["queue"]["p95_ms"] == 5
    assert report["model_queue"]["work"]["p95_ms"] == 40
    assert report["provider_calls"]["attempts"]["total"] == 1
    assert report["provider_calls"]["tokens"]["thought"]["total"] is None
    assert report["versions"]["models"] == ["model-a"]
    assert report["versions"]["mapping_versions"] == ["mapping-v2"]
    assert report["versions"]["dictionary_versions"] == ["dictionary-v3"]
    assert report["versions"]["backend_dependencies"] == {
        "sqlalchemy": ["2.0.44"], "sqlglot": ["30.24.0"],
    }
    assert report["versions"]["backend_dependencies_missing"] == ["psycopg"]
    assert report["versions"]["agent_dependencies"]["google-genai"] == ["2.30.0"]
    serialized = json.dumps(report)
    assert correlation not in serialized
    assert "private question" not in serialized
    assert "SELECT secret" not in serialized
    assert report["contains_request_ids"] is False
    assert report["contains_question_or_sql"] is False


def test_cost_pairs_usage_and_contract_failure_by_correlation():
    correlation = "d" * 32
    lines = [
        _line("genai_execution", {
            "service": "backend", "strategy": "text_to_sql_f1",
            "correlation_id": correlation, "stage": "http", "elapsed_ms": 1,
            "outcome": "error", "http_status": 503,
        }),
        _line("genai_usage", {
            "correlation_id": correlation, "provider": "gemini", "model": "model-a",
            "attempts": 1, "prompt_tokens": 100, "total_tokens": 150,
        }),
        _line("genai_provider_failure", {
            "correlation_id": correlation, "provider": "gemini", "model": "model-a",
            "attempts": 1, "kind": "invalid_response", "reason": "contract_validation",
        }),
    ]
    prices = {
        "version": "text-to-sql-price-book-v1", "source": "approved internal price sheet",
        "prices": [{
            "provider": "gemini", "model": "model-a", "effective_from": "2026-01-01",
            "input_usd_per_million": 1, "output_usd_per_million": 2,
        }],
    }

    report = summarize_trace(lines, price_data=prices, as_of="2026-11-07")

    assert report["cost"]["state"] == "estimated_upper_bound"
    assert report["cost"]["priced_calls"] == 1
    assert report["cost"]["unpriced_calls"] == 0
    assert report["cost"]["calls_without_usage"] == 0
    assert report["cost"]["amount_usd"] == pytest.approx(0.0002)
    assert report["provider_calls"]["failure_events"] == 1
    assert report["provider_calls"]["attempts"]["total"] == 1


def test_provider_failure_without_usage_is_counted_once_as_unpriced():
    correlation = "f" * 32
    lines = [
        _line("genai_execution", {
            "service": "backend", "strategy": "text_to_sql_f1",
            "correlation_id": correlation, "stage": "http", "elapsed_ms": 1,
            "outcome": "error", "http_status": 503,
        }),
        _line("genai_provider_failure", {
            "correlation_id": correlation, "provider": "gemini", "model": "model-a",
            "attempts": 1, "kind": "quota", "status": 429,
        }),
    ]
    prices = {
        "version": "text-to-sql-price-book-v1", "source": "approved internal price sheet",
        "prices": [{
            "provider": "gemini", "model": "model-a", "effective_from": "2026-01-01",
            "input_usd_per_million": 1, "output_usd_per_million": 2,
        }],
    }

    report = summarize_trace(lines, price_data=prices, as_of="2026-11-07")

    assert report["cost"]["state"] == "unknown"
    assert report["cost"]["amount_usd"] is None
    assert report["cost"]["priced_calls"] == 0
    assert report["cost"]["unpriced_calls"] == 1
    assert report["cost"]["calls_without_usage"] == 1
    assert report["provider_calls"]["attempts"]["total"] == 1
    assert report["provider_calls"]["attempts"]["known_events"] == 1


def test_invalid_or_unversioned_price_book_is_rejected():
    with pytest.raises(ValueError, match="Versão"):
        summarize_trace([], price_data={"prices": []}, as_of="2026-11-07")

    valid = {
        "version": "text-to-sql-price-book-v1", "source": "source",
        "prices": [{
            "provider": "gemini", "model": "model-a", "effective_from": "2026-01-01",
            "input_usd_per_million": 1, "output_usd_per_million": 2,
        }],
    }
    with pytest.raises(ValueError, match="--as-of"):
        summarize_trace([], price_data=valid)


def test_repository_price_book_estimates_only_the_explicit_default_model():
    root = Path(__file__).resolve().parents[1]
    prices = json.loads(
        (root / "config/text_to_sql_price_book_2026-11-07.json").read_text(encoding="utf-8")
    )
    correlation = "e" * 32
    lines = [
        _line("genai_execution", {
            "service": "backend", "strategy": "text_to_sql_f1",
            "correlation_id": correlation, "stage": "http", "elapsed_ms": 1,
            "outcome": "success", "http_status": 200,
        }),
        _line("genai_usage", {
            "correlation_id": correlation, "provider": "gemini",
            "model": "gemini-3.5-flash-lite", "prompt_tokens": 1000,
            "total_tokens": 1200,
        }),
    ]

    report = summarize_trace(lines, price_data=prices, as_of="2026-11-07")

    assert report["cost"]["state"] == "estimated_upper_bound"
    assert report["cost"]["amount_usd"] == pytest.approx(0.0008)
    assert report["cost"]["source"].startswith("https://ai.google.dev/")
