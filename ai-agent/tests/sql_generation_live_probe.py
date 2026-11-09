"""Uma geração real sobre contexto artificial; nunca executa SQL candidato."""

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from dotenv import dotenv_values
from google import genai

from app.providers.sql_generator import SQL_GENERATION_PROMPT_VERSION, GeminiSqlGenerator

ROOT = Path(__file__).resolve().parents[2]


async def main():
    # Helper de teste explícito: isto não é sessão real nem prontidão Gold.
    built = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            "from tests.test_genai_sql_context import request_payload; "
            "from app.schemas.genai_internal import QuestionPlanRequest; "
            "from app.services.genai_sql_context import build_sql_generation_context; "
            "print(build_sql_generation_context(QuestionPlanRequest.model_validate("
            "request_payload())).contents)",
        ],
        cwd=ROOT / "backend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )
    context = json.loads(built.stdout)
    config = dotenv_values(ROOT / ".env")
    client = genai.Client(
        api_key=config["GENAI_GEMINI_API_KEY"],
        http_options={
            "timeout": 20000,
            "retry_options": {"attempts": 1},
        },
    )
    usage = []
    provider_failures = []

    class Capture(logging.Handler):
        def emit(self, record):
            message = record.getMessage()
            if message.startswith("genai_usage "):
                usage.append(json.loads(message.removeprefix("genai_usage ")))
            elif message.startswith("genai_provider_failure "):
                provider_failures.append(
                    json.loads(message.removeprefix("genai_provider_failure "))
                )

    logger = logging.getLogger("uvicorn.error")
    previous = logger.level
    capture = Capture()
    logger.addHandler(capture)
    logger.setLevel(logging.INFO)
    generation_parameters = {"max_output_tokens": 4096, "temperature": 0.0}
    report = {
        "scope": "artificial F1 context, real Gemini, no SQL execution",
        "model": config["GENAI_GEMINI_MODEL"],
        "prompt_version": SQL_GENERATION_PROMPT_VERSION,
        "context_bytes": len(built.stdout.encode("utf-8")),
        "generation_parameters": generation_parameters,
        "application_requests": 1,
        "retry_attempts": 1,
    }
    started = perf_counter()
    try:
        candidate = await GeminiSqlGenerator(
            client=client,
            model_name=config["GENAI_GEMINI_MODEL"],
            **generation_parameters,
        ).generate(built.stdout, context_version=context["context_version"])
        report["outcome"] = "valid_candidate_contract"
        report["candidate"] = candidate.model_dump(mode="json")
    except Exception as exc:
        report.update(outcome="generation_error", error_type=type(exc).__name__)
    finally:
        report["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
        report["usage"] = usage
        report["provider_failures"] = provider_failures
        report["cost"] = None
        report["cost_unavailable_reason"] = "pricing_not_configured"
        logger.removeHandler(capture)
        logger.setLevel(previous)
        await client.aio.aclose()
    target = ROOT / "work/text-to-sql-f1-live-probe.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "outcome", "elapsed_ms", "usage", "provider_failures",
    )}))
    if report["outcome"] == "generation_error":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
