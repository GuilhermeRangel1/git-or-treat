import json

import pytest

from scripts import run_mgc_f1_baseline as baseline


def _fixture_case(split="diagnostic", turns=None):
    return {
        "id": "MGC-TEST",
        "category": "individual",
        "question": "Pergunta de teste?",
        "turns": turns or ["Pergunta de teste?"],
        "expected": {"status": "answered_when_ready"},
        "expected_turns": [],
        "family_id": "MGC-FAM-TEST",
        "split": split,
    }


def test_local_base_url_rejects_remote_hosts_and_embedded_credentials():
    assert baseline.local_base_url("http://localhost:8000/") == "http://localhost:8000"
    with pytest.raises(ValueError):
        baseline.local_base_url("https://localhost:8000")
    with pytest.raises(ValueError):
        baseline.local_base_url("http://user:pass@localhost:8000")
    with pytest.raises(ValueError):
        baseline.local_base_url("https://example.com")


def test_select_cases_never_includes_the_holdout():
    case_set = {"cases": [_fixture_case(), _fixture_case(split="holdout")]}
    selected = baseline.select_cases(case_set)
    assert [case["id"] for case in selected] == ["MGC-TEST"]
    with pytest.raises(ValueError, match="outro split"):
        baseline.select_cases(
            case_set, case_ids={"MGC-TEST", "MGC-HOLDOUT"}
        )


def test_response_content_never_keeps_signed_continuation_tokens():
    response = {"status": "answered", "continuation_token": "secret-token"}
    assert baseline.response_content(response) == {"status": "answered"}


def test_extract_provider_usage_keeps_only_correlated_aggregate_metadata():
    correlation_id = "b" * 32
    logs = """2026-11-09T12:00:00Z ai-agent-1 | genai_usage {"correlation_id":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","provider":"gemini","model":"test-model","prompt_version":"f1-test","prompt_tokens":100,"output_tokens":20,"question":"private"}
2026-11-09T12:00:01Z ai-agent-1 | genai_usage {"correlation_id":"cccccccccccccccccccccccccccccccc","provider":"gemini","model":"other"}
"""
    assert baseline.extract_provider_usage(logs, {correlation_id}) == [{
        "correlation_id": correlation_id,
        "provider": "gemini",
        "model": "test-model",
        "prompt_version": "f1-test",
        "prompt_tokens": 100,
        "output_tokens": 20,
    }]


@pytest.mark.parametrize(
    ("expected", "actual", "assessment"),
    [
        ("answered_when_ready", "answered", "expected_state"),
        ("unsupported_join_without_SQL", "unsupported", "expected_state"),
        ("needs_clarification_without_SQL", "answered", "unexpected_state"),
        (
            "conditional_on_readiness_no_certified_result",
            "unsupported",
            "conditional_requires_readiness_review",
        ),
    ],
)
def test_assesses_route_status_without_claiming_full_case_correctness(
    expected, actual, assessment
):
    assert baseline.assess_route_status(expected, actual) == assessment


def test_run_baseline_sends_turns_sequentially_and_does_not_record_tokens(monkeypatch):
    calls = []

    class FakeResponse:
        status_code = 200

        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, path, json=None):
            calls.append((path, json))
            if path.endswith("/login"):
                return FakeResponse({"status": "ok"})
            if path.endswith("/logout"):
                return FakeResponse({"status": "ok"})
            return FakeResponse({
                "status": "answered",
                "correlation_id": "a" * 32,
                "answer": "resposta",
                "continuation_token": "signed-token",
            })

    monkeypatch.setattr(baseline.httpx, "Client", FakeClient)
    case = _fixture_case(turns=["Primeira?", "E depois?"])
    case["expected_turns"] = [
        {"status": "answered_when_ready"},
        {"status": "answered_when_ready"},
    ]
    oracle = {"cases": [{"case_id": "MGC-TEST", "metric_references": []}]}
    result = baseline.run_baseline(
        base_url="http://localhost:8000",
        username="admin",
        password="senha123",
        cases=[case],
        oracle_report=oracle,
    )

    question_calls = [call for call in calls if call[0].endswith("/sql-analyses")]
    assert len(question_calls) == 2
    assert question_calls[0][1]["conversation_id"] == question_calls[1][1]["conversation_id"]
    assert "continuation_token" not in question_calls[0][1]
    assert question_calls[1][1]["continuation_token"] == "signed-token"
    assert result["case_count"] == 1
    assert result["scheduled_turn_count"] == 2
    assert result["attempted_turn_count"] == 2
    assert all("continuation_token" not in turn["response"] for turn in result["cases"][0]["turns"])


def test_runner_selects_only_diagnostic_cases_by_default():
    case_set = json.loads(baseline.DEFAULT_CASE_SET.read_text(encoding="utf-8"))
    selected = baseline.select_cases(case_set)
    assert len(selected) == 186
    assert {case["split"] for case in selected} == {"diagnostic"}
