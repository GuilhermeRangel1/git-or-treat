"""Métricas operacionais sem conteúdo de pergunta, evidência ou resposta."""

import json
import logging
from contextvars import ContextVar

correlation = ContextVar("model_correlation", default=None)
logger = logging.getLogger("uvicorn.error")


def record_execution(stage: str, queue_ms: int, work_ms: int, outcome: str) -> None:
    logger.info(
        "genai_execution %s",
        json.dumps(
            {
                "correlation_id": correlation.get(),
                "stage": stage,
                "queue_ms": queue_ms,
                "work_ms": work_ms,
                "outcome": outcome,
            },
            separators=(",", ":"),
        ),
    )


def record_usage(
    provider: str,
    *,
    prompt=None,
    output=None,
    thoughts=None,
    cached=None,
    total=None,
):
    """Ausência de metadado continua nula; nunca presume consumo igual a zero."""

    def count(value):
        return value if type(value) is int and 0 <= value <= 2_147_483_647 else None

    logger.info(
        "genai_usage %s",
        json.dumps(
            {
                "correlation_id": correlation.get(),
                "provider": provider,
                "prompt_tokens": count(prompt),
                "output_tokens": count(output),
                "thought_tokens": count(thoughts),
                "cached_tokens": count(cached),
                "total_tokens": count(total),
            },
            separators=(",", ":"),
        ),
    )
