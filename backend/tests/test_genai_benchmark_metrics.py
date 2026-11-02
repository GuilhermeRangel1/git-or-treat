"""Preço observado e dados ausentes não se confundem com custo faturado zero."""

import json

from scripts.summarize_genai_benchmark import summarize


def test_summary_filters_other_requests_and_prices_output_including_thinking():
    benchmark = {
        "samples": [{"correlation_id": "a" * 32, "status": "answered"}],
        "requests": 1,
        "concurrency": 1,
        "p50_ms": 120,
        "p95_ms": 120,
        "unexpected": 0,
    }
    events = [
        "INFO genai_usage "
        + json.dumps(
            {
                "correlation_id": "a" * 32,
                "provider": "gemini",
                "prompt_tokens": 100,
                "total_tokens": 120,
            }
        ),
        "INFO genai_usage "
        + json.dumps(
            {
                "correlation_id": "b" * 32,
                "provider": "gemini",
                "prompt_tokens": 999,
                "total_tokens": 1999,
            }
        ),
    ]
    result = summarize(
        benchmark, events, provider="gemini", input_rate=0.30, output_rate=2.50
    )
    assert result["observed_standard_cost_upper_bound_usd"] == 0.00008
    assert result["generated_tokens_including_thinking"] == 20
    assert result["cost_is_invoice"] is False
    assert result["answered_without_usage"] == 0


def test_summary_reports_unknown_usage_instead_of_zero_cost():
    benchmark = {
        "samples": [{"correlation_id": "a" * 32, "status": "answered"}],
        "requests": 1,
        "concurrency": 1,
        "p50_ms": 120,
        "p95_ms": 120,
        "unexpected": 0,
    }
    result = summarize(
        benchmark,
        ["private free text"],
        provider="gemini",
        input_rate=0.30,
        output_rate=2.50,
    )
    assert result["observed_standard_cost_upper_bound_usd"] is None
    assert result["answered_without_usage"] == 1
    assert "private" not in json.dumps(result)


def test_missing_correlation_never_imports_uncorrelated_usage():
    benchmark = {
        "samples": [{"correlation_id": None, "status": "transport_error"}],
        "requests": 1,
        "concurrency": 1,
        "p50_ms": 120,
        "p95_ms": 120,
        "unexpected": 1,
    }
    logs = [
        "genai_usage "
        + json.dumps(
            {
                "correlation_id": None,
                "provider": "gemini",
                "prompt_tokens": 999,
                "total_tokens": 1999,
            }
        )
    ]
    result = summarize(
        benchmark, logs, provider="gemini", input_rate=0.30, output_rate=2.50
    )
    assert result["usage_samples"] == 0
    assert result["observed_standard_cost_upper_bound_usd"] is None
