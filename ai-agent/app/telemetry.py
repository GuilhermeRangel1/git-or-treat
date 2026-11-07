"""Métricas operacionais sem conteúdo de pergunta, evidência ou resposta."""

import json
import logging
from contextvars import ContextVar
from importlib.metadata import PackageNotFoundError, distribution

correlation = ContextVar("model_correlation", default=None)
logger = logging.getLogger("uvicorn.error")


def _runtime_dependencies() -> dict[str, str | None]:
    dependencies = {}
    for package_name in ("google-genai", "sqlglot", "psycopg"):
        try:
            found = distribution(package_name)
            value = found.metadata.get("Version")
            dependencies[package_name] = value if isinstance(value, str) else None
        except PackageNotFoundError:
            dependencies[package_name] = None
    return dependencies


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
                "dependencies": _runtime_dependencies(),
            },
            separators=(",", ":"),
        ),
    )


def record_provider_failure(
    provider: str, model: str, kind: str, status: int | None = None,
    *, prompt_version: str | None = None, elapsed_ms: float | None = None,
    context_bytes: int | None = None, max_output_tokens: int | None = None,
    temperature: float | None = None, attempts: int | None = None,
    reason: str | None = None,
    validation_fields: tuple[str, ...] = (),
) -> None:
    """Só a causa classificada; nunca texto da exceção, pergunta, evidência ou chave."""
    logger.warning(
        "genai_provider_failure %s",
        json.dumps(
            {
                "correlation_id": correlation.get(),
                "provider": provider,
                "model": model,
                "kind": kind,
                "reason": reason if reason in {
                    "invalid_json", "contract_validation", "incomplete_generation",
                    "context_version_mismatch", "invalid_response_shape",
                } else None,
                "validation_fields": sorted(set(validation_fields) & {
                    "envelope", "generation_contract_version", "status", "context_version",
                    "sql", "parameters", "interpretation", "result_columns",
                    "clarification", "unsupported_reason", "other",
                }),
                "status": status if type(status) is int else None,
                "prompt_version": prompt_version,
                "elapsed_ms": _duration(elapsed_ms),
                "context_bytes": _count(context_bytes),
                "max_output_tokens": _count(max_output_tokens),
                "temperature": _temperature(temperature),
                "attempts": _count(attempts),
                "dependencies": _runtime_dependencies(),
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
    model=None,
    prompt_version=None,
    elapsed_ms=None,
    context_bytes=None,
    max_output_tokens=None,
    temperature=None,
    attempts=None,
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
                "model": model if isinstance(model, str) else None,
                "prompt_version": prompt_version if isinstance(prompt_version, str) else None,
                "elapsed_ms": _duration(elapsed_ms),
                "context_bytes": count(context_bytes),
                "max_output_tokens": count(max_output_tokens),
                "temperature": _temperature(temperature),
                "attempts": count(attempts),
                "dependencies": _runtime_dependencies(),
                "prompt_tokens": count(prompt),
                "output_tokens": count(output),
                "thought_tokens": count(thoughts),
                "cached_tokens": count(cached),
                "total_tokens": count(total),
            },
            separators=(",", ":"),
        ),
    )


def _count(value):
    return value if type(value) is int and 0 <= value <= 2_147_483_647 else None


def _duration(value):
    return round(value, 2) if type(value) in (int, float) and 0 <= value <= 86_400_000 else None


def _temperature(value):
    return value if type(value) in (int, float) and 0 <= value <= 1 else None
