"""Avalia alertas sobre um resumo Text-to-SQL já agregado e sanitizado."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_POLICY_VERSION = "text-to-sql-alert-policy-v1"


def evaluate_alerts(summary: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if policy.get("version") != _POLICY_VERSION:
        raise ValueError("Versão da política de alertas incompatível.")
    alerts = []
    http = summary.get("http", {})
    status_counts = http.get("status_counts", {})
    requests = summary.get("requests", 0)
    errors = sum(
        count for status, count in status_counts.items()
        if status.isdigit() and (int(status) == 429 or int(status) >= 500)
    )
    if requests >= policy["minimum_http_requests"]:
        ratio = 100 * errors / requests
        if ratio > policy["http_error_ratio_percent"]:
            alerts.append({
                "code": "http_error_ratio", "severity": "warning",
                "observed_percent": round(ratio, 2),
                "threshold_percent": policy["http_error_ratio_percent"],
            })

    request_p95 = http.get("latency", {}).get("p95_ms")
    if type(request_p95) is int and request_p95 >= policy["request_p95_critical_ms"]:
        alerts.append({
            "code": "request_latency_p95", "severity": "critical",
            "observed_ms": request_p95,
            "threshold_ms": policy["request_p95_critical_ms"],
        })
    elif type(request_p95) is int and request_p95 >= policy["request_p95_warning_ms"]:
        alerts.append({
            "code": "request_latency_p95", "severity": "warning",
            "observed_ms": request_p95,
            "threshold_ms": policy["request_p95_warning_ms"],
        })

    sql_p95 = summary.get("stages", {}).get("sql_execution", {}).get("p95_ms")
    if type(sql_p95) is int and sql_p95 >= policy["sql_p95_warning_ms"]:
        alerts.append({
            "code": "sql_latency_p95", "severity": "warning",
            "observed_ms": sql_p95,
            "threshold_ms": policy["sql_p95_warning_ms"],
        })

    provider = summary.get("provider_calls", {})
    provider_calls = provider.get("usage_events", 0) + provider.get("failure_events", 0)
    failures = provider.get("failure_events", 0)
    if provider_calls >= policy["provider_minimum_calls"]:
        ratio = 100 * failures / provider_calls
        if ratio > policy["provider_failure_ratio_percent"]:
            alerts.append({
                "code": "provider_failure_ratio", "severity": "warning",
                "observed_percent": round(ratio, 2),
                "threshold_percent": policy["provider_failure_ratio_percent"],
            })

    database_failures = sum(
        counts.get("database_error", 0)
        for stage in summary.get("stages", {}).values()
        for counts in (stage.get("reasons", {}),)
    )
    threshold = policy["database_failure_critical_count"]
    severity = "critical" if database_failures >= threshold else "warning"
    if database_failures >= policy["database_failure_warning_count"]:
        alerts.append({
            "code": "database_failures", "severity": severity,
            "observed_count": database_failures,
            "threshold_count": threshold if severity == "critical"
            else policy["database_failure_warning_count"],
        })

    return {
        "report_version": "text-to-sql-alerts-v1",
        "policy_version": _POLICY_VERSION,
        "alerts": alerts,
        "critical_count": sum(alert["severity"] == "critical" for alert in alerts),
        "contains_request_ids": False,
        "contains_question_or_sql": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--webhook-url", help="Destino HTTP(S) configurado para receber alertas sanitizados")
    parser.add_argument("--webhook-timeout", type=float, default=3.0)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    report = evaluate_alerts(summary, policy)
    print(json.dumps(report, indent=2))
    if args.webhook_url:
        parsed_url = urlparse(args.webhook_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            parser.error("--webhook-url deve ser uma URL HTTP(S) absoluta.")
        if args.webhook_timeout <= 0:
            parser.error("--webhook-timeout deve ser positivo.")
        request = Request(
            args.webhook_url,
            data=json.dumps(report).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=args.webhook_timeout) as response:
                if not 200 <= response.status < 300:
                    print(f"Coletor de alertas respondeu HTTP {response.status}.", file=sys.stderr)
                    return 2
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            status = getattr(exc, "code", None)
            reason = f"HTTP {status}" if status is not None else type(exc).__name__
            print(f"Falha ao entregar alertas ao coletor ({reason}).", file=sys.stderr)
            return 2
    return 1 if report["critical_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
