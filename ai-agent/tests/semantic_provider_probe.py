"""Avalia perguntas autorais no Gemini e registra intenção/uso, sem segredos."""

import asyncio
import json
import logging
from pathlib import Path
from time import perf_counter

from dotenv import dotenv_values
from google import genai

from app.agent.access import ReadAccessPolicy
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.providers.intent_proposer import GeminiIntentProposer
from app.schemas.internal import QuestionPlanRequest

from .test_gold_question_filters import _setup


async def main():
    config = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    client = genai.Client(api_key=config["GENAI_GEMINI_API_KEY"], http_options={
        "timeout": 20000, "retry_options": {"attempts": 1},
    })
    dataset = json.loads(
        (Path(__file__).parent / "fixtures/gold_p0_user_reported.json").read_text(encoding="utf-8")
    )
    usage_rows = []

    class UsageCapture(logging.Handler):
        def emit(self, record):
            message = record.getMessage()
            if message.startswith("genai_usage "):
                usage_rows.append(json.loads(message.removeprefix("genai_usage ")))

    usage_logger = logging.getLogger("uvicorn.error")
    previous_level = usage_logger.level
    capture = UsageCapture()
    usage_logger.addHandler(capture)
    usage_logger.setLevel(logging.INFO)
    results = []
    try:
        for case in dataset["cases"]:
            _, request = _setup(case["question"])
            payload = request.model_dump(mode="json")
            payload["context"] = case.get("context", [])
            for coverage in payload["temporal_coverage"]:
                coverage["competencies"] = case["competencies"]
            request = QuestionPlanRequest.model_validate(payload)
            started = perf_counter()
            usage_rows.clear()
            try:
                async with asyncio.timeout(30):
                    proposal = await GeminiIntentProposer(
                        client=client,
                        model=config["GENAI_GEMINI_MODEL"],
                        profile=GRID360_GOLD_PROFILE,
                        request=request,
                        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
                    ).propose()
                row = {
                    "id": case["id"],
                    "status": proposal.status,
                    "intent": proposal.intent.model_dump(mode="json") if proposal.intent else None,
                }
            except Exception as exc:
                row = {
                    "id": case["id"],
                    "error_type": type(exc).__name__,
                    "status": getattr(exc, "code", None),
                }
            row["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
            row["usage"] = list(usage_rows)
            row["cost"] = None
            row["cost_unavailable_reason"] = "pricing_not_configured"
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        target = Path(__file__).resolve().parents[1] / "reports/genai-semantic-probe.json"
        target.write_text(
            json.dumps(
                {
                    "scope": "development probe, not quality acceptance",
                    "model": config["GENAI_GEMINI_MODEL"],
                    "application_requests": len(results),
                    "retry_attempts": 1,
                    "cases": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        usage_logger.removeHandler(capture)
        usage_logger.setLevel(previous_level)
        await client.aio.aclose()


if __name__ == "__main__":
    asyncio.run(main())
