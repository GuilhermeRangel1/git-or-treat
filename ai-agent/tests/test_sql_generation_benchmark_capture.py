import hashlib

import pytest

from tests.sql_generation_benchmark_capture import (
    FIXTURE,
    PRICING_MODEL,
    SQL_GENERATION_PROMPT_VERSION,
    cost_from_usage,
    estimate_worst_case_cost_usd,
    prepare_capture,
    reserve_capture_cost,
    validate_context_bundle,
)


def bundle(case_ids):
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    return {
        "benchmark_sha256": digest,
        "contexts": [
            {"id": case_id, "context_version": "a" * 64, "contents": "synthetic"}
            for case_id in case_ids
        ],
    }


def test_capture_accepts_only_selected_cases_from_the_frozen_benchmark():
    expected_hash, contexts = validate_context_bundle(bundle(["F1-01-V0"]), ["F1-01-V0"])

    assert expected_hash == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert contexts["F1-01-V0"]["contents"] == "synthetic"


@pytest.mark.parametrize(
    "context_bundle,case_ids",
    [
        ({"benchmark_sha256": "stale", "contexts": []}, ["F1-01-V0"]),
        (bundle(["F1-01-V0"]), ["F1-01-V0", "F1-01-V0"]),
        (bundle([]), ["F1-01-V0"]),
        (bundle(["not-a-case"]), ["not-a-case"]),
    ],
)
def test_capture_rejects_stale_duplicate_or_missing_cases(context_bundle, case_ids):
    with pytest.raises(ValueError):
        validate_context_bundle(context_bundle, case_ids)


def test_cost_guard_reserves_input_overhead_and_maximum_output_for_every_call():
    contexts = {
        "F1-01-V0": {"contents": "synthetic question"},
        "F1-01-V1": {"contents": "another synthetic question"},
    }

    one_call = estimate_worst_case_cost_usd(contexts, ["F1-01-V0"])
    two_calls = estimate_worst_case_cost_usd(contexts, list(contexts))

    assert one_call > 0
    assert two_calls > one_call
    assert two_calls < 1.0


def test_resume_never_retries_an_observed_case_and_reserves_prior_attempts():
    contexts = {
        "F1-01-V0": {"contents": "one"},
        "F1-01-V1": {"contents": "two"},
        "F1-01-V2": {"contents": "three"},
    }
    prior = {
        "benchmark_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "model": PRICING_MODEL,
        "prompt_version": SQL_GENERATION_PROMPT_VERSION,
        "candidates": {"F1-01-V0": {"status": "sql_candidate"}},
        "observations": [
            {"id": "F1-01-V0"},
            {"id": "F1-01-V1"},
        ],
    }

    candidates, observations, unknown_attempts, pending, prior_reserved = prepare_capture(
        contexts, list(contexts), prior
    )

    assert set(candidates) == {"F1-01-V0"}
    assert len(observations) == 2
    assert unknown_attempts == []
    assert pending == ["F1-01-V2"]
    assert prior_reserved > 0


def test_resume_accounts_for_prior_calls_whose_output_was_not_persisted():
    contexts = {
        "F1-01-V0": {"contents": "one"},
        "F1-01-V1": {"contents": "two"},
    }
    prior = {
        "benchmark_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "model": PRICING_MODEL,
        "prompt_version": SQL_GENERATION_PROMPT_VERSION,
        "candidates": {},
        "observations": [],
        "uncaptured_attempts": [{"id": "F1-01-V0", "count": 1}],
    }

    _, _, unknown_attempts, pending, prior_reserved = prepare_capture(
        contexts, list(contexts), prior
    )

    assert unknown_attempts == [{"id": "F1-01-V0", "count": 1}]
    assert pending == ["F1-01-V1"]
    assert prior_reserved == estimate_worst_case_cost_usd(contexts, ["F1-01-V0"])


def test_new_prompt_iteration_carries_prior_reserved_cost():
    contexts = {"F1-01-V0": {"contents": "synthetic"}}
    prior = 0.50
    pending = estimate_worst_case_cost_usd(contexts, ["F1-01-V0"])

    assert reserve_capture_cost(prior, 0, pending) == prior + pending
    with pytest.raises(ValueError):
        reserve_capture_cost(-0.01, 0, pending)


def test_cost_estimate_does_not_assume_missing_thought_tokens_are_zero():
    exact, lower_bound = cost_from_usage({
        "prompt_tokens": 100,
        "output_tokens": 20,
        "thought_tokens": None,
    })

    assert exact is None
    assert lower_bound is not None and lower_bound > 0


def test_lower_output_limit_reduces_only_output_reservation():
    contexts = {"F1-01-V0": {"contents": "synthetic"}}
    full = estimate_worst_case_cost_usd(contexts, list(contexts))
    bounded = estimate_worst_case_cost_usd(contexts, list(contexts), 1536)
    assert full - bounded == pytest.approx((4096 - 1536) * 2.5 / 1_000_000)


def test_resume_rejects_changed_output_limit_before_provider(tmp_path):
    import asyncio

    from tests.sql_generation_benchmark_capture import capture

    with pytest.raises(ValueError, match="mesmo limite"):
        asyncio.run(capture({}, [], tmp_path / "capture.json", 2.0,
                            {"generation_parameters": {"max_output_tokens": 4096}},
                            max_output_tokens=1536))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_cost_guard_rejects_nonfinite_reservations(value):
    with pytest.raises(ValueError):
        reserve_capture_cost(value, 0, 0)


def test_existing_capture_is_not_overwritten_without_resume(tmp_path):
    import asyncio

    from tests.sql_generation_benchmark_capture import capture

    output = tmp_path / "capture.json"
    original = '{"evidence": "preserved"}'
    output.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match="já existe"):
        asyncio.run(capture({}, [], output, 1.0))
    assert output.read_text(encoding="utf-8") == original
