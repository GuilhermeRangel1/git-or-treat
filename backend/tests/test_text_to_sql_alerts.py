import json
import sys

from scripts.evaluate_text_to_sql_alerts import evaluate_alerts

from scripts import evaluate_text_to_sql_alerts

POLICY = {
    "version": "text-to-sql-alert-policy-v1",
    "minimum_http_requests": 20,
    "http_error_ratio_percent": 5,
    "provider_minimum_calls": 10,
    "provider_failure_ratio_percent": 5,
    "request_p95_warning_ms": 45000,
    "request_p95_critical_ms": 54000,
    "sql_p95_warning_ms": 4000,
    "database_failure_warning_count": 1,
    "database_failure_critical_count": 3,
}


def test_alerts_respect_sample_size_and_remain_sanitized():
    report = evaluate_alerts(
        {
            "requests": 2,
            "http": {"status_counts": {"503": 2}, "latency": {"p95_ms": 100}},
            "provider_calls": {"usage_events": 1, "failure_events": 1},
            "stages": {},
            "question": "do not leak",
        },
        POLICY,
    )

    assert report["alerts"] == []
    assert report["critical_count"] == 0
    assert report["contains_request_ids"] is False
    assert report["contains_question_or_sql"] is False
    assert "question" not in report


def test_alerts_emit_codes_for_http_provider_latency_and_database_failures():
    report = evaluate_alerts(
        {
            "requests": 20,
            "http": {"status_counts": {"200": 18, "503": 2}, "latency": {"p95_ms": 54000}},
            "provider_calls": {"usage_events": 9, "failure_events": 1},
            "stages": {
                "publication": {"reasons": {"database_error": 3}},
                "sql_execution": {"p95_ms": 4000, "reasons": {}},
            },
            "sql": "SELECT secret",
        },
        POLICY,
    )

    assert {(alert["code"], alert["severity"]) for alert in report["alerts"]} == {
        ("http_error_ratio", "warning"),
        ("request_latency_p95", "critical"),
        ("sql_latency_p95", "warning"),
        ("provider_failure_ratio", "warning"),
        ("database_failures", "critical"),
    }
    assert report["critical_count"] == 2
    assert "SELECT secret" not in str(report)


def test_database_warning_and_request_latency_warning_are_distinct():
    report = evaluate_alerts(
        {
            "requests": 0,
            "http": {"status_counts": {}, "latency": {"p95_ms": 45000}},
            "provider_calls": {"usage_events": 0, "failure_events": 0},
            "stages": {"context": {"reasons": {"database_error": 1}}},
        },
        POLICY,
    )

    assert {(alert["code"], alert["severity"]) for alert in report["alerts"]} == {
        ("request_latency_p95", "warning"),
        ("database_failures", "warning"),
    }
    assert report["critical_count"] == 0


def test_cli_delivers_only_sanitized_alert_report_to_configured_webhook(monkeypatch, tmp_path):
    received = {}

    class Response:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        received["url"] = request.full_url
        received["body"] = json.loads(request.data)
        received["content_type"] = request.headers["Content-type"]
        received["timeout"] = timeout
        return Response()

    summary_path = tmp_path / "summary.json"
    policy_path = tmp_path / "policy.json"
    summary_path.write_text(json.dumps({
        "requests": 20,
        "http": {"status_counts": {"200": 18, "503": 2}, "latency": {"p95_ms": 100}},
        "provider_calls": {"usage_events": 0, "failure_events": 0},
        "stages": {},
        "question": "must not reach collector",
    }), encoding="utf-8")
    policy_path.write_text(json.dumps(POLICY), encoding="utf-8")
    monkeypatch.setattr(evaluate_text_to_sql_alerts, "urlopen", fake_urlopen)
    monkeypatch.setattr(sys, "argv", [
        "evaluate_text_to_sql_alerts.py", "--summary", str(summary_path),
        "--policy", str(policy_path), "--webhook-url", "http://local-collector:8080/alerts",
    ])

    assert evaluate_text_to_sql_alerts.main() == 0
    assert received["url"] == "http://local-collector:8080/alerts"
    assert received["content_type"] == "application/json"
    assert received["body"]["alerts"][0]["code"] == "http_error_ratio"
    assert "question" not in received["body"]
    assert received["body"]["contains_question_or_sql"] is False
