"""Resume traces Text-to-SQL em métricas agregadas; não imprime IDs nem conteúdo."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any

_MARKERS = ("genai_execution", "genai_usage", "genai_provider_failure")
_CORRELATION = re.compile(r"^[a-f0-9]{32}$")
_PRICE_VERSION = "text-to-sql-price-book-v1"


def _percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def _events(lines: list[str]) -> list[tuple[str, dict[str, Any]]]:
    result = []
    for line in lines:
        for marker in _MARKERS:
            offset = line.find(marker)
            if offset < 0:
                continue
            try:
                event = json.loads(line[offset + len(marker):])
            except (TypeError, ValueError):
                break
            if isinstance(event, dict):
                result.append((marker.strip(), event))
            break
    return result


def _validate_price_book(value: object, as_of: date) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("version") != _PRICE_VERSION:
        raise ValueError("Versão da tabela de preços ausente ou incompatível.")
    source = value.get("source")
    rows = value.get("prices")
    if not isinstance(source, str) or not source.strip() or len(source) > 240:
        raise ValueError("A origem da tabela de preços é obrigatória.")
    if not isinstance(rows, list) or not rows:
        raise ValueError("A tabela de preços precisa de ao menos uma linha.")
    clean = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("Linha de preço inválida.")
        provider, model, effective_from = row.get("provider"), row.get("model"), row.get("effective_from")
        if not all(isinstance(item, str) and item.strip() for item in (provider, model, effective_from)):
            raise ValueError("Provedor, modelo e data efetiva são obrigatórios.")
        parsed_date = date.fromisoformat(effective_from)
        if parsed_date.isoformat() != effective_from:
            raise ValueError("effective_from deve usar YYYY-MM-DD.")
        rates = (row.get("input_usd_per_million"), row.get("output_usd_per_million"))
        if any(type(rate) not in (int, float) or not math.isfinite(rate) or rate < 0 for rate in rates):
            raise ValueError("Tarifas devem ser números finitos e não negativos.")
        key = (provider, model, effective_from)
        if key in seen:
            raise ValueError("A tabela repete provedor/modelo/data.")
        seen.add(key)
        clean.append({
            "provider": provider,
            "model": model,
            "effective_from": parsed_date,
            "input_usd_per_million": float(rates[0]),
            "output_usd_per_million": float(rates[1]),
        })
    return {"version": _PRICE_VERSION, "source": source.strip(), "as_of": as_of, "prices": clean}


def _price_for(price_book: dict[str, Any], provider: object, model: object):
    if not isinstance(provider, str) or not isinstance(model, str):
        return None
    candidates = [
        row for row in price_book["prices"]
        if row["provider"] == provider and row["model"] == model
        and row["effective_from"] <= price_book["as_of"]
    ]
    return max(candidates, key=lambda row: row["effective_from"], default=None)


def _stats(rows: list[dict[str, Any]], key: str) -> dict[str, int | None]:
    values = [row[key] for row in rows if type(row.get(key)) is int and row[key] >= 0]
    return {
        "samples": len(values),
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "max_ms": max(values) if values else None,
    }


def _attempts_by_correlation(
    events: tuple[dict[str, Any], ...], call_ids: set[str]
) -> dict[str, int]:
    attempts: dict[str, int] = {}
    for event in events:
        correlation_id = event.get("correlation_id")
        value = event.get("attempts")
        if correlation_id in call_ids and type(value) is int and value >= 0:
            attempts[correlation_id] = max(value, attempts.get(correlation_id, 0))
    return attempts


def _known_attempt_calls(
    events: tuple[dict[str, Any], ...], call_ids: set[str]
) -> int:
    return len(_attempts_by_correlation(events, call_ids))


def _attempt_total(
    events: tuple[dict[str, Any], ...], call_ids: set[str]
) -> int | None:
    attempts = _attempts_by_correlation(events, call_ids)
    if not call_ids or len(attempts) != len(call_ids):
        return None
    return sum(attempts.values())


def summarize_trace(
    lines: list[str], *, price_data: object | None = None, as_of: str | None = None,
) -> dict[str, Any]:
    events = _events(lines)
    backend = [
        event for marker, event in events
        if marker == "genai_execution"
        and event.get("service") == "backend"
        and event.get("strategy") == "text_to_sql_f1"
        and isinstance(event.get("correlation_id"), str)
        and _CORRELATION.fullmatch(event["correlation_id"])
    ]
    correlations = {event["correlation_id"] for event in backend}
    related = [
        (marker, event) for marker, event in events
        if event.get("correlation_id") in correlations
    ]
    usage = [event for marker, event in related if marker == "genai_usage"]
    failures = [event for marker, event in related if marker == "genai_provider_failure"]
    # A successful HTTP response from the provider may emit both usage and a
    # failure event when the returned envelope fails validation. Pair them by
    # request correlation so one provider call is not counted or priced twice.
    usage_by_correlation = {
        event["correlation_id"]: event for event in usage
        if isinstance(event.get("correlation_id"), str)
    }
    failures_by_correlation = {
        event["correlation_id"]: event for event in failures
        if isinstance(event.get("correlation_id"), str)
    }
    provider_call_ids = set(usage_by_correlation) | set(failures_by_correlation)
    calls_without_usage = len(set(failures_by_correlation) - set(usage_by_correlation))
    http = [event for event in backend if event.get("stage") == "http"]
    stage_names = sorted({
        event.get("stage") for event in backend
        if isinstance(event.get("stage"), str)
        and event.get("stage") not in {"http", "runtime"}
    })
    dependency_versions: dict[str, list[str | None]] = {}
    for event in backend:
        if event.get("stage") != "runtime" or not isinstance(event.get("dependencies"), dict):
            continue
        for name, value in event["dependencies"].items():
            if isinstance(name, str) and (value is None or isinstance(value, str)):
                dependency_versions.setdefault(name, []).append(value)
    agent_dependency_versions: dict[str, list[str | None]] = {}
    for event in (*usage, *failures):
        dependencies = event.get("dependencies")
        if not isinstance(dependencies, dict):
            continue
        for name, value in dependencies.items():
            if isinstance(name, str) and (value is None or isinstance(value, str)):
                agent_dependency_versions.setdefault(name, []).append(value)
    stages = {
        stage: {
            **_stats([event for event in backend if event.get("stage") == stage], "elapsed_ms"),
            "outcomes": {
                outcome: sum(event.get("outcome") == outcome for event in backend if event.get("stage") == stage)
                for outcome in ("success", "clarification", "unsupported", "error", "cancelled")
            },
            "reasons": {
                reason: sum(event.get("reason") == reason for event in backend if event.get("stage") == stage)
                for reason in sorted({
                    event.get("reason") for event in backend
                    if event.get("stage") == stage and isinstance(event.get("reason"), str)
                })
            },
        }
        for stage in stage_names
    }
    model_queue = [
        event for marker, event in related
        if marker == "genai_execution" and event.get("stage") == "model"
    ]
    token_fields = {
        "prompt": "prompt_tokens",
        "output": "output_tokens",
        "thought": "thought_tokens",
        "cached": "cached_tokens",
        "total": "total_tokens",
    }
    tokens = {}
    for label, key in token_fields.items():
        known = [event[key] for event in usage if type(event.get(key)) is int and event[key] >= 0]
        tokens[label] = {
            "total": sum(known) if len(known) == len(usage) and usage else None,
            "known_calls": len(known),
            "missing_calls": len(usage) - len(known),
        }

    cost: dict[str, Any] = {
        "state": "not_configured",
        "amount_usd": None,
        "basis": None,
        "price_book_version": None,
        "as_of": None,
        "source": None,
        "priced_calls": 0,
        "unpriced_calls": len(provider_call_ids),
        "calls_without_usage": calls_without_usage,
    }
    price_book = None
    if price_data is not None:
        if as_of is None:
            raise ValueError("--as-of é obrigatório quando uma tabela de preços é informada.")
        parsed_as_of = date.fromisoformat(as_of)
        if parsed_as_of.isoformat() != as_of:
            raise ValueError("--as-of deve usar YYYY-MM-DD.")
        price_book = _validate_price_book(price_data, parsed_as_of)
        cost.update({
            "state": "partial",
            "basis": "standard_input_rate_upper_bound_including_thinking_tokens",
            "price_book_version": price_book["version"],
            "as_of": as_of,
            "source": price_book["source"],
        })
        amounts = []
        unpriced = calls_without_usage
        for event in usage_by_correlation.values():
            price = _price_for(price_book, event.get("provider"), event.get("model"))
            prompt, total = event.get("prompt_tokens"), event.get("total_tokens")
            if (price is None or type(prompt) is not int or type(total) is not int
                    or prompt < 0 or total < prompt):
                unpriced += 1
                continue
            generated_including_thinking = total - prompt
            amounts.append((
                prompt * price["input_usd_per_million"]
                + generated_including_thinking * price["output_usd_per_million"]
            ) / 1_000_000)
        cost["priced_calls"] = len(amounts)
        cost["unpriced_calls"] = unpriced
        cost["amount_usd"] = round(sum(amounts), 10) if amounts else None
        if amounts and unpriced == 0:
            cost["state"] = "estimated_upper_bound"
        elif amounts:
            cost["state"] = "partial"
        else:
            cost["state"] = "unknown"

    return {
        "report_version": "text-to-sql-trace-summary-v1",
        "strategy": "text_to_sql_f1",
        "requests": len({event["correlation_id"] for event in http}),
        "http": {
            "status_counts": {
                str(status): sum(event.get("http_status") == status for event in http)
                for status in sorted({event.get("http_status") for event in http if type(event.get("http_status")) is int})
            },
            "latency": _stats(http, "elapsed_ms"),
        },
        "versions": {
            "contracts": sorted({
                value for event in backend
                if isinstance((value := event.get("contract_version")), str)
            }),
            "contexts_observed": len({
                event.get("context_version") for event in backend
                if isinstance(event.get("context_version"), str)
            }),
            "mapping_versions": sorted({
                event.get("mapping_version") for event in backend
                if isinstance(event.get("mapping_version"), str)
            }),
            "dictionary_versions": sorted({
                event.get("dictionary_version") for event in backend
                if isinstance(event.get("dictionary_version"), str)
            }),
            "providers": sorted({
                event.get("provider") for event in (*usage, *failures)
                if isinstance(event.get("provider"), str)
            }),
            "models": sorted({
                event.get("model") for event in (*usage, *failures)
                if isinstance(event.get("model"), str)
            }),
            "prompts": sorted({
                event.get("prompt_version") for event in (*usage, *failures)
                if isinstance(event.get("prompt_version"), str)
            }),
            "backend_dependencies": {
                name: sorted({value for value in values if value is not None})
                for name, values in sorted(dependency_versions.items())
                if any(value is not None for value in values)
            },
            "backend_dependencies_missing": sorted(
                name for name, values in dependency_versions.items() if None in values
            ),
            "agent_dependencies": {
                name: sorted({value for value in values if value is not None})
                for name, values in sorted(agent_dependency_versions.items())
                if any(value is not None for value in values)
            },
            "agent_dependencies_missing": sorted(
                name for name, values in agent_dependency_versions.items() if None in values
            ),
        },
        "stages": stages,
        "model_queue": {
            "events": len(model_queue),
            "queue": _stats(model_queue, "queue_ms"),
            "work": _stats(model_queue, "work_ms"),
        },
        "provider_calls": {
            "usage_events": len(usage),
            "failure_events": len(failures),
            "attempts": {
                "total": _attempt_total((*usage, *failures), provider_call_ids),
                "known_events": _known_attempt_calls(
                    (*usage, *failures), provider_call_ids
                ),
                "missing_events": len(provider_call_ids) - _known_attempt_calls(
                    (*usage, *failures), provider_call_ids
                ),
            },
            "failure_kinds": {
                kind: sum(event.get("kind") == kind for event in failures)
                for kind in sorted({event.get("kind") for event in failures if isinstance(event.get("kind"), str)})
            },
            "failure_status_counts": {
                str(status): sum(event.get("status") == status for event in failures)
                for status in sorted({
                    event.get("status") for event in failures
                    if type(event.get("status")) is int
                })
            },
            "tokens": tokens,
        },
        "cost": cost,
        "contains_request_ids": False,
        "contains_question_or_sql": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", required=True, type=Path, nargs="+")
    parser.add_argument("--prices", type=Path)
    parser.add_argument("--as-of", help="Data de referência YYYY-MM-DD para a tabela de preços")
    args = parser.parse_args()
    price_data = json.loads(args.prices.read_text(encoding="utf-8")) if args.prices else None
    lines = [line for path in args.logs for line in path.read_text(encoding="utf-8").splitlines()]
    print(json.dumps(summarize_trace(lines, price_data=price_data, as_of=args.as_of), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
