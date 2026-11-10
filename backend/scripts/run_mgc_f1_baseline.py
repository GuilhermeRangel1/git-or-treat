"""Capture a one-shot diagnostic MGC baseline through the authenticated F1 route.

This records route outputs for later semantic and numeric review. It does not
claim an automatic correctness score and never stores continuation tokens or
generated SQL. The holdout split is excluded by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASE_SET = ROOT / "docs/plans/CASOS_MELHORIA_GERAL_CHATBOT.json"
DEFAULT_ORACLES = ROOT / "docs/plans/GABARITOS_GOLD_MELHORIA_GERAL_CHATBOT.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_base_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme != "http"
        or parts.hostname not in {"localhost", "127.0.0.1", "backend"}
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError("A avaliação aceita somente uma URL HTTP local do Backend.")
    return value.rstrip("/")


def select_cases(
    case_set: dict,
    *,
    case_ids: set[str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    # Keep the holdout out of baseline runs; there is deliberately no CLI switch.
    cases = [case for case in case_set["cases"] if case["split"] == "diagnostic"]
    if case_ids is not None:
        unknown = case_ids - {case["id"] for case in cases}
        if unknown:
            raise ValueError(
                "IDs aus outro split ou inexistentes: " + ", ".join(sorted(unknown))
            )
        cases = [case for case in cases if case["id"] in case_ids]
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit deve ser positivo.")
        cases = cases[:limit]
    if not cases:
        raise ValueError("A seleção não contém casos.")
    return cases


def expected_turn_status(case: dict, turn_index: int) -> str:
    expected_turns = case.get("expected_turns", [])
    if turn_index < len(expected_turns):
        return expected_turns[turn_index]["status"]
    return case["expected"]["status"]


def assess_route_status(expected: str, actual: str) -> str:
    if expected.startswith(("conditional_", "blocked_")):
        return "conditional_requires_readiness_review"
    if expected.startswith("answered") or expected == "compare_and_disclose_unavailable_decomposition":
        accepted = {"answered"}
    elif expected.startswith("needs_clarification"):
        accepted = {"needs_clarification"}
    elif expected.startswith(("unsupported", "denied_")):
        accepted = {"unsupported"}
    else:
        return "human_review_required"
    return "expected_state" if actual in accepted else "unexpected_state"


def response_content(body: dict) -> dict:
    """Keep the public evidence and presentation, but discard signed tokens."""
    return {key: value for key, value in body.items() if key != "continuation_token"}


def extract_provider_usage(log_text: str, correlation_ids: set[str]) -> list[dict]:
    allowed_fields = {
        "correlation_id",
        "provider",
        "model",
        "prompt_version",
        "elapsed_ms",
        "prompt_tokens",
        "output_tokens",
        "thought_tokens",
        "cached_tokens",
        "total_tokens",
        "attempts",
    }
    records = []
    for line in log_text.splitlines():
        marker = "genai_usage "
        if marker not in line:
            continue
        payload = line.split(marker, 1)[1]
        try:
            event = json.loads(payload)
        except ValueError:
            continue
        if not isinstance(event, dict) or event.get("correlation_id") not in correlation_ids:
            continue
        records.append({key: value for key, value in event.items() if key in allowed_fields})
    return records


def collect_provider_usage(report: dict, *, since: str) -> None:
    correlation_ids = {
        turn["correlation_id"]
        for case in report["cases"]
        for turn in case["turns"]
        if isinstance(turn.get("correlation_id"), str)
    }
    if not correlation_ids:
        report["provider_usage"] = {"status": "no_correlation_ids", "events": []}
        return
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "logs",
                "--no-color",
                "--timestamps",
                "--since",
                since,
                "ai-agent",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        report["provider_usage"] = {"status": "docker_logs_unavailable", "events": []}
        return
    events = extract_provider_usage(result.stdout, correlation_ids)
    report["provider_usage"] = {
        "status": "captured" if result.returncode == 0 else "docker_logs_unavailable",
        "events": events,
        "cost_usd": None,
        "cost_note": "Token usage is captured when available; cost requires the applicable model price and is not inferred.",
    }
    models = sorted({event["model"] for event in events if event.get("model")})
    prompts = sorted(
        {event["prompt_version"] for event in events if event.get("prompt_version")}
    )
    if models:
        report["model_versions"] = models
    if prompts:
        report["prompt_versions"] = prompts


def run_baseline(
    *,
    base_url: str,
    username: str,
    password: str,
    cases: list[dict],
    oracle_report: dict,
    timeout_seconds: float = 90,
) -> dict:
    url = local_base_url(base_url)
    started_at = datetime.now(UTC)
    oracles = {item["case_id"]: item for item in oracle_report["cases"]}
    rows: list[dict] = []

    with httpx.Client(
        base_url=url,
        timeout=httpx.Timeout(timeout_seconds),
        trust_env=False,
        headers={"Origin": "http://localhost:5173"},
    ) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        if login.status_code != 200:
            raise RuntimeError(f"Login recusado: HTTP {login.status_code}.")

        try:
            for case in cases:
                turns = case.get("turns") or [case["question"]]
                conversation_id = str(uuid4())
                continuation_token = None
                turn_rows = []

                for index, question in enumerate(turns):
                    payload = {
                        "contract_version": "v1",
                        "question": question,
                        "conversation_id": conversation_id,
                    }
                    if continuation_token:
                        payload["continuation_token"] = continuation_token

                    started = monotonic()
                    try:
                        response = client.post(
                            "/api/v1/ai/sql-analyses", json=payload
                        )
                        try:
                            body = response.json()
                        except ValueError:
                            body = {"invalid_body": True}
                        if not isinstance(body, dict):
                            body = {"invalid_body": True}
                        route_status = body.get("status", "invalid_response")
                        expected_status = expected_turn_status(case, index)
                        turn_rows.append(
                            {
                                "turn": index + 1,
                                "question": question,
                                "expected_status": expected_status,
                                "http_status": response.status_code,
                                "route_status": route_status,
                                "status_assessment": assess_route_status(
                                    expected_status, route_status
                                ),
                                "latency_ms": round((monotonic() - started) * 1000, 2),
                                "execution_pipeline": (
                                    "returned_gold_evidence"
                                    if route_status == "answered"
                                    and response.status_code == 200
                                    else "not_proven"
                                ),
                                "correlation_id": body.get("correlation_id"),
                                "response": response_content(body),
                            }
                        )
                        continuation_token = body.get("continuation_token")
                        if index + 1 < len(turns) and not continuation_token:
                            turn_rows.append(
                                {
                                    "turn": index + 2,
                                    "question": turns[index + 1],
                                    "expected_status": expected_turn_status(
                                        case, index + 1
                                    ),
                                    "route_status": "not_run_missing_continuation",
                                }
                            )
                            break
                    except httpx.HTTPError as exc:
                        turn_rows.append(
                            {
                                "turn": index + 1,
                                "question": question,
                                "expected_status": expected_turn_status(case, index),
                                "route_status": "transport_error",
                                "latency_ms": round((monotonic() - started) * 1000, 2),
                                "error_type": type(exc).__name__,
                            }
                        )
                        break

                rows.append(
                    {
                        "case_id": case["id"],
                        "category": case["category"],
                        "family_id": case["family_id"],
                        "split": case["split"],
                        "expected": case["expected"],
                        "oracle": oracles.get(case["id"]),
                        "review_status": "pending_human_review",
                        "turns": turn_rows,
                    }
                )
        finally:
            client.post("/api/v1/auth/logout")

    counts: dict[str, int] = {}
    for case in rows:
        for turn in case["turns"]:
            status = turn["route_status"]
            counts[status] = counts.get(status, 0) + 1

    return {
        "format_version": "mgc-f1-baseline-capture-v1",
        "started_at_utc": started_at.isoformat(),
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "base_url": url,
        "route": "/api/v1/ai/sql-analyses",
        "split": "diagnostic",
        "case_count": len(cases),
        "scheduled_turn_count": sum(len(case["turns"]) for case in rows),
        "attempted_turn_count": sum(
            1 for case in rows for turn in case["turns"] if "http_status" in turn
        ),
        "route_status_counts": counts,
        "model_version": os.getenv("MGC_BASELINE_MODEL_VERSION"),
        "prompt_version": os.getenv("MGC_BASELINE_PROMPT_VERSION"),
        "sql_capture": "not exposed or persisted by this runner; answered responses contain validated Gold evidence",
        "provider_cost_usd": None,
        "automatic_correctness_score": None,
        "human_review_required": True,
        "fixture_sha256": None,
        "oracle_sha256": None,
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("MGC_BASELINE_URL", "http://localhost:8000"))
    parser.add_argument("--case-set", type=Path, default=DEFAULT_CASE_SET)
    parser.add_argument("--oracles", type=Path, default=DEFAULT_ORACLES)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-ids", help="Lista separada por vírgulas; deve pertencer ao split escolhido.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip-provider-telemetry", action="store_true")
    args = parser.parse_args()

    username = os.getenv("MGC_BASELINE_USERNAME")
    password = os.getenv("MGC_BASELINE_PASSWORD")
    if not username or not password:
        parser.error("Configure MGC_BASELINE_USERNAME e MGC_BASELINE_PASSWORD sem passá-los na linha de comando.")

    try:
        case_set = json.loads(args.case_set.read_text(encoding="utf-8"))
        oracle_report = json.loads(args.oracles.read_text(encoding="utf-8"))
        selected = select_cases(
            case_set,
            case_ids=(
                {item.strip() for item in args.case_ids.split(",") if item.strip()}
                if args.case_ids
                else None
            ),
            limit=args.limit,
        )
        report = run_baseline(
            base_url=args.base_url,
            username=username,
            password=password,
            cases=selected,
            oracle_report=oracle_report,
        )
        if not args.skip_provider_telemetry:
            collect_provider_usage(report, since=report["started_at_utc"])
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Baseline não concluída: {exc}", file=sys.stderr)
        return 1

    report["fixture_sha256"] = sha256(args.case_set)
    report["oracle_sha256"] = sha256(args.oracles)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
