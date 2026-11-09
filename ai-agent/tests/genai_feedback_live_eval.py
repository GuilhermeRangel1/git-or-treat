"""Avaliação das decisões de recusa/esclarecimento: modelo controlado (offline) ou Gemini real.

Uso, a partir de ``ai-agent`` e com o Python do ai-agent::

    python -m tests.genai_feedback_live_eval --offline
    python -m tests.genai_feedback_live_eval --live [--cases genai_feedback_cases.json]

Fluxo: o Backend monta o contexto real e aplica as regras determinísticas (``dump``); os
casos que precisam do modelo recebem um candidato (scriptado no modo offline, Gemini real no
modo live, uma tentativa por caso, sem retry); o Backend reaplica a decisão (``replay``) e o
avaliador compara com o oráculo. Nenhuma consulta Gold é executada e nenhum dado Gold é
enviado ao modelo. O modo offline prova a fiação, não a qualidade do modelo.

A chave do Gemini é lida do ``.env`` da raiz dentro deste processo e nunca é impressa.
"""

import argparse
import asyncio
import json
import logging
import statistics
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from app.providers.sql_generator import SQL_GENERATION_PROMPT_VERSION, GeminiSqlGenerator

from .genai_feedback_evaluation import FIXTURES, evaluate_outcome, load_cases

ROOT = Path(__file__).resolve().parents[2]
BACKEND_PYTHON = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
REPORTS = ROOT / "ai-agent" / "reports"
CASES_FILE = FIXTURES / "genai_feedback_cases.json"


def _backend(mode: str, *arguments: Path) -> None:
    subprocess.run(
        [
            str(BACKEND_PYTHON),
            "-X",
            "utf8",
            "-m",
            "tests.genai_feedback_harness",
            mode,
            str(CASES_FILE),
            *map(str, arguments),
        ],
        cwd=ROOT / "backend",
        check=True,
        timeout=300,
    )


def _git_state() -> dict:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False
        ).stdout.strip()

    return {
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(run("status", "--porcelain", "--", "ai-agent/app", "backend/app")),
    }


def controlled_candidate(case: dict, model_request: dict) -> dict | None:
    """Modelo controlado: devolve a primeira decisão permitida, quando ela é recusa/pergunta."""
    allowed = case["allowed_outcomes"][0]
    base = {
        "generation_contract_version": model_request["generation_contract_version"],
        "context_version": model_request["context_version"],
        "semantic_intent": None,
    }
    if allowed["status"] == "unsupported":
        reason = allowed.get("reason_code") or case["expected_reason"]
        return {
            **base,
            "status": "unsupported",
            "scope_assessment": {
                "status": "out_of_domain" if reason == "out_of_domain" else "in_domain"
            },
            "unsupported_reason": {
                "code": "metric_outside_f1",
                "message": "Posso ajudar com os indicadores de energia da V-Energy.",
                "reason_code": reason,
            },
        }
    if allowed["status"] == "needs_clarification":
        reason = allowed.get("reason_code") or "missing_context"
        return {
            **base,
            "status": "needs_clarification",
            "scope_assessment": {
                "status": "uncertain" if reason == "ambiguous_subject" else "in_domain"
            },
            "clarification": {
                "question": "Pode confirmar essa informação para eu continuar?",
                "missing_fields": case["pending_fields"][:1] or ["context"],
                "reason_code": reason,
            },
        }
    return None


class _Usage(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[dict] = []
        self.failures: list[dict] = []

    def emit(self, record):
        message = record.getMessage()
        if message.startswith("genai_usage "):
            self.records.append(json.loads(message.removeprefix("genai_usage ")))
        elif message.startswith("genai_provider_failure "):
            # Só motivo e campos do contrato; nunca o texto devolvido pelo provedor.
            self.failures.append(json.loads(message.removeprefix("genai_provider_failure ")))


async def _live_candidates(cases, dumped, model_name, api_key, pause_seconds, only=None):
    from google import genai

    client = genai.Client(
        api_key=api_key, http_options={"timeout": 20000, "retry_options": {"attempts": 1}}
    )
    generator = GeminiSqlGenerator(client=client, model_name=model_name)
    logger = logging.getLogger("uvicorn.error")
    usage = _Usage()
    previous = logger.level
    logger.addHandler(usage)
    logger.setLevel(logging.INFO)
    results = {}
    try:
        for case in cases:
            request = dumped[case["id"]].get("model_request")
            if request is None or (only and case["id"] not in only):
                continue
            before = len(usage.records)
            failures_before = len(usage.failures)
            started = perf_counter()
            entry = {"input_bytes": len(request["contents"].encode("utf-8")), "attempts": 1}
            try:
                candidate = await generator.generate(
                    request["contents"], context_version=request["context_version"]
                )
                entry["candidate"] = candidate.model_dump(mode="json")
            except Exception as exc:
                name = type(exc).__name__
                entry["error"] = "unavailable" if "Unavailable" in name else "invalid_response"
                entry["error_type"] = name
            entry["elapsed_ms"] = round((perf_counter() - started) * 1000, 1)
            entry["usage"] = usage.records[before:]
            entry["provider_failures"] = usage.failures[failures_before:]
            results[case["id"]] = entry
            await asyncio.sleep(pause_seconds)
    finally:
        logger.removeHandler(usage)
        logger.setLevel(previous)
        await client.aio.aclose()
    return results


def _classify(case: dict, outcome: dict, violations: list[str]) -> list[str]:
    tags = []
    group, status = case["group"], outcome["status"]
    if group == "external_mixed" and status == "sql_candidate":
        tags.append("external_accepted_as_sql")
    if group == "legitimate_near_external" and status in {"unsupported", "access_denied"}:
        tags.append("legitimate_refused")
    allows_clarification = any(
        a["status"] == "needs_clarification" for a in case["allowed_outcomes"]
    )
    if status == "needs_clarification" and not allows_clarification:
        tags.append("unnecessary_clarification")
    if status == "needs_clarification" and allows_clarification and not violations:
        tags.append("correct_clarification")
    if group == "ambiguity_continuation" and status == "sql_candidate" and not violations:
        tags.append("continuation_resolved")
    if status == "technical_error" and not any(
        a["status"] == "technical_error" for a in case["allowed_outcomes"]
    ):
        tags.append("operational_failure")
    return tags


def build_report(cases, outcomes, candidates, *, mode, model_name):
    rows, evaluated, counts, latencies, tokens = [], 0, {}, [], 0
    model_calls = 0
    for case in cases:
        outcome = outcomes[case["id"]]
        if "skipped" in outcome:
            rows.append({"id": case["id"], "result": "not_evaluated", "reason": outcome["skipped"]})
            continue
        entry = candidates.get(case["id"], {})
        evaluated += 1
        violations = evaluate_outcome(case, outcome)
        tags = _classify(case, outcome, violations)
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
        model_calls += outcome.get("model_calls", 0)
        if "elapsed_ms" in entry:
            latencies.append(entry["elapsed_ms"])
        for item in entry.get("usage", []):
            tokens += int(item.get("total_tokens") or 0)
        rows.append(
            {
                "id": case["id"],
                "result": "pass" if not violations else "fail",
                "first_divergence": violations[0] if violations else None,
                "violations": violations,
                "status": outcome["status"],
                "reason_code": outcome.get("reason_code"),
                "tags": tags,
                "model_calls": outcome.get("model_calls", 0),
                "note": outcome.get("note"),
            }
        )
    passed = sum(row["result"] == "pass" for row in rows)
    latencies.sort()
    summary = {
        "mode": mode,
        "model": model_name,
        "evaluated": evaluated,
        "passed": passed,
        "failed": evaluated - passed,
        "not_evaluated": sum(row["result"] == "not_evaluated" for row in rows),
        "model_calls": model_calls,
        "total_tokens": tokens,
        "tag_counts": counts,
        "latency_ms": {
            "count": len(latencies),
            "p50": statistics.median(latencies) if latencies else None,
            "p95": latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))]
            if latencies
            else None,
        },
    }
    return {"summary": summary, "cases": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--pause", type=float, default=1.0)
    parser.add_argument("--only", help="IDs separados por vírgula (apenas live)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.offline == args.live:
        parser.error("escolha exatamente um entre --offline e --live")

    cases = load_cases(CASES_FILE)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dumped_path = tmp_path / "dump.json"
        _backend("dump", dumped_path)
        dumped = json.loads(dumped_path.read_text(encoding="utf-8"))
        if args.live and args.only:
            selected = set(args.only.split(","))
            for case in cases:
                if case["id"] not in selected:
                    dumped[case["id"]] = {"skip": "fora da sele\u00e7\u00e3o"}
            dumped_path.write_text(json.dumps(dumped, ensure_ascii=False), encoding="utf-8")

        model_name = "controlled-model"
        if args.offline:
            candidates = {}
            for case in cases:
                request = dumped[case["id"]].get("model_request")
                if request is None:
                    continue
                candidate = controlled_candidate(case, request)
                candidates[case["id"]] = (
                    {"candidate": candidate} if candidate else {"not_modeled": True}
                )
        else:
            from dotenv import dotenv_values

            config = dotenv_values(ROOT / ".env")
            model_name = config["GENAI_GEMINI_MODEL"]
            candidates = asyncio.run(
                _live_candidates(
                    cases,
                    dumped,
                    model_name,
                    config["GENAI_GEMINI_API_KEY"],
                    args.pause,
                    set(args.only.split(",")) if args.only else None,
                )
            )
        candidates_path, outcomes_path = tmp_path / "cand.json", tmp_path / "out.json"
        candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
        if args.live:
            # As chamadas reais já foram consumidas: preserve os candidatos antes do replay.
            REPORTS.mkdir(exist_ok=True)
            (REPORTS / "genai-feedback-live-candidates.json").write_text(
                json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        _backend("replay", dumped_path, candidates_path, outcomes_path)
        outcomes = json.loads(outcomes_path.read_text(encoding="utf-8"))

    report = build_report(
        cases,
        outcomes,
        candidates,
        mode="offline" if args.offline else "live",
        model_name=model_name,
    )
    report["summary"].update(
        prompt_version=SQL_GENERATION_PROMPT_VERSION,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        git=_git_state(),
        cases_file=CASES_FILE.name,
        scope=(
            "decision and presentation only; no Gold query executed; "
            "no Gold data sent to the model"
        ),
    )
    if not args.offline:
        report["raw_candidates"] = {
            key: {k: v for k, v in value.items() if k != "usage"}
            for key, value in candidates.items()
        }
    target = args.out or REPORTS / f"genai-feedback-{report['summary']['mode']}.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    for row in report["cases"]:
        if row["result"] == "fail":
            print(row["id"], "->", row["first_divergence"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
