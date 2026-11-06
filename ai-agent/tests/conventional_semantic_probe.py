"""Sonda manual e limitada do Gemini para a linguagem do case; não é aceite de qualidade."""

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

_CASES = (
    {
        "id": "CONV-API-01",
        "question": "Quanto foi o faturamento total em janeiro de 2024?",
        "expected": {
            "status": "ready",
            "metric_id": "billing.revenue",
            "period_month": "2024-01",
            "groups": [],
        },
    },
    {
        "id": "CONV-API-02",
        "question": "Qual foi o faturamento em janeiro de 2024, dividido por setores?",
        "expected": {
            "status": "ready",
            "metric_id": "billing.revenue",
            "period_month": "2024-01",
            "groups": ["customer.consumption_class"],
        },
    },
    {
        "id": "CONV-API-03",
        "question": "Qual bairro mais perdeu volume residencial no último ano?",
        "expected": {
            "status": "needs_clarification",
            "clarification_fragments": ["energia faturada", "consumo medido"],
        },
    },
)


class _UsageCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.rows = []

    def emit(self, record):
        message = record.getMessage()
        if message.startswith("genai_usage "):
            self.rows.append(json.loads(message.removeprefix("genai_usage ")))


def _make_request(question: str) -> QuestionPlanRequest:
    _, request = _setup(question)
    payload = request.model_dump(mode="json")
    payload["temporal_coverage"] = [
        {
            **coverage,
            "competencies": [
                f"{year:04d}-{month:02d}"
                for year, months in ((2024, range(1, 13)), (2025, range(1, 13)),
                                     (2026, range(1, 7)))
                for month in months
            ],
        }
        if coverage["kind"] == "monthly" else coverage
        for coverage in payload["temporal_coverage"]
    ]
    return QuestionPlanRequest.model_validate(payload)


def _actual(proposal):
    intent = proposal.intent
    return {
        "status": proposal.status.value,
        "metric_id": intent.metric_id if intent is not None else None,
        "period_phrase": intent.period_phrase if intent is not None else None,
        "group_by_dimension_ids": intent.group_by_dimension_ids if intent is not None else [],
        "clarification_question": proposal.clarification_question,
    }


def _matches(actual: dict, expected: dict) -> bool:
    if actual["status"] != expected["status"]:
        return False
    if expected["status"] == "needs_clarification":
        message = (actual["clarification_question"] or "").casefold()
        return all(fragment.casefold() in message
                   for fragment in expected["clarification_fragments"])
    period = (actual["period_phrase"] or "").casefold()
    normalized_period = period.replace("ç", "c")
    period_match = expected["period_month"] in normalized_period or (
        expected["period_month"] == "2024-01"
        and "janeiro" in normalized_period and "2024" in normalized_period
    )
    return (
        actual["metric_id"] == expected["metric_id"]
        and period_match
        and actual["group_by_dimension_ids"] == expected["groups"]
    )


async def main():
    config = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    api_key = config.get("GENAI_GEMINI_API_KEY")
    model = config.get("GENAI_GEMINI_MODEL")
    if not api_key or not model:
        raise RuntimeError("Configure GENAI_GEMINI_API_KEY e GENAI_GEMINI_MODEL no .env")

    client = genai.Client(api_key=api_key, http_options={
        "timeout": 20000,
        "retry_options": {"attempts": 1},
    })
    logger = logging.getLogger("uvicorn.error")
    old_level = logger.level
    capture = _UsageCapture()
    logger.addHandler(capture)
    logger.setLevel(logging.INFO)
    rows = []
    try:
        for case in _CASES:
            capture.rows.clear()
            started = perf_counter()
            row = {"id": case["id"], "question": case["question"],
                   "expected": case["expected"]}
            try:
                request = _make_request(case["question"])
                async with asyncio.timeout(25):
                    proposal = await GeminiIntentProposer(
                        client=client,
                        model=model,
                        profile=GRID360_GOLD_PROFILE,
                        request=request,
                        access_authorizer=ReadAccessPolicy(GRID360_GOLD_PROFILE, "gold.local"),
                        max_output_tokens=512,
                    ).propose()
                row["actual"] = _actual(proposal)
                row["matches_expected"] = _matches(row["actual"], case["expected"])
            except Exception as exc:
                row["error_type"] = type(exc).__name__
                row["provider_status"] = getattr(exc, "code", None)
                row["matches_expected"] = False
            row["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
            row["usage"] = list(capture.rows)
            rows.append(row)
            print(json.dumps({
                "id": row["id"],
                "matches_expected": row["matches_expected"],
                "actual": row.get("actual"),
                "error_type": row.get("error_type"),
                "elapsed_ms": row["elapsed_ms"],
                "usage": row["usage"],
            }, ensure_ascii=False), flush=True)
    finally:
        logger.removeHandler(capture)
        logger.setLevel(old_level)
        await client.aio.aclose()

    report = {
        "scope": "sonda observacional do interpretador Gemini; 3 perguntas; sem execução SQL/dados",
        "model": model,
        "requests": len(rows),
        "retry_attempts": 1,
        "max_output_tokens_per_request": 512,
        "cases": rows,
    }
    target = Path(__file__).resolve().parents[1] / "reports/genai-conventional-language-probe.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": target.name,
        "passed": sum(row["matches_expected"] for row in rows),
        "total": len(rows),
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
