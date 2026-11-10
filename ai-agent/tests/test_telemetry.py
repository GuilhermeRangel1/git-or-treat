import json

from app.telemetry import record_provider_failure, record_usage


def event(caplog, event_name):
    record = next(
        record for record in caplog.records if record.getMessage().startswith(event_name + " ")
    )
    return json.loads(record.getMessage().removeprefix(event_name + " "))


def test_usage_event_records_generation_metadata_and_available_token_counts(caplog):
    with caplog.at_level("INFO", logger="uvicorn.error"):
        record_usage(
            "gemini",
            model="gemini-test",
            prompt_version="text-to-sql-f1-9",
            elapsed_ms=15.126,
            context_bytes=900,
            max_output_tokens=4096,
            temperature=0.0,
            attempts=1,
            prompt=12,
            output=8,
            total=20,
        )

    observed = event(caplog, "genai_usage")
    assert observed["model"] == "gemini-test"
    assert observed["prompt_version"] == "text-to-sql-f1-9"
    assert observed["elapsed_ms"] == 15.13
    assert observed["context_bytes"] == 900
    assert observed["max_output_tokens"] == 4096
    assert observed["temperature"] == 0.0
    assert observed["attempts"] == 1
    assert (
        observed["prompt_tokens"], observed["output_tokens"], observed["total_tokens"]
    ) == (12, 8, 20)


def test_usage_event_keeps_missing_or_invalid_metrics_null(caplog):
    with caplog.at_level("INFO", logger="uvicorn.error"):
        record_usage(
            "gemini", prompt=-1, output=True, total=None, elapsed_ms=float("nan"),
            context_bytes=-2, max_output_tokens=True, temperature=True,
            attempts=True,
        )

    observed = event(caplog, "genai_usage")
    assert observed["prompt_tokens"] is None
    assert observed["output_tokens"] is None
    assert observed["total_tokens"] is None
    assert observed["elapsed_ms"] is None
    assert observed["context_bytes"] is None
    assert observed["max_output_tokens"] is None
    assert observed["temperature"] is None
    assert observed["attempts"] is None


def test_failure_event_records_only_classified_provider_metadata(caplog):
    with caplog.at_level("WARNING", logger="uvicorn.error"):
        record_provider_failure(
            "gemini", "gemini-test", "invalid_response", 503,
            prompt_version="text-to-sql-f1-9", elapsed_ms=42.0,
            context_bytes=100, max_output_tokens=4096, temperature=0.0,
            attempts=1, reason="contract_validation",
        )

    observed = event(caplog, "genai_provider_failure")
    assert observed["model"] == "gemini-test"
    assert observed["kind"] == "invalid_response"
    assert observed["reason"] == "contract_validation"
    assert observed["status"] == 503
    assert observed["attempts"] == 1
    assert observed["prompt_version"] == "text-to-sql-f1-9"
    assert "prompt" not in observed
    assert "contents" not in observed
