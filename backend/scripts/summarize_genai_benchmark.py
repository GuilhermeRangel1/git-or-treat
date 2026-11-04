"""Resume métricas permitidas pelos IDs da carga; nunca copia conteúdo dos logs."""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.benchmark_genai import percentile


def summarize(
    benchmark: dict,
    lines: list[str],
    *,
    provider: str,
    input_rate: float,
    output_rate: float,
) -> dict:
    ids = {
        sample["correlation_id"]
        for sample in benchmark["samples"]
        if isinstance(sample.get("correlation_id"), str)
        and re.fullmatch(r"[a-f0-9]{32}", sample["correlation_id"])
    }
    usage, execution = [], []
    for line in lines:
        for marker, target in (
            ("genai_usage ", usage),
            ("genai_execution ", execution),
        ):
            if marker not in line:
                continue
            try:
                event = json.loads(line.split(marker, 1)[1])
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("correlation_id") in ids:
                target.append(event)
    known_usage = [
        row
        for row in usage
        if row.get("provider") == provider
        and type(row.get("prompt_tokens")) is int
        and type(row.get("total_tokens")) is int
        and row["total_tokens"] >= row["prompt_tokens"] >= 0
    ]
    prompt = sum(row["prompt_tokens"] for row in known_usage)
    generated = sum(row["total_tokens"] - row["prompt_tokens"] for row in known_usage)
    hits = {
        row.get("correlation_id")
        for row in execution
        if row.get("stage") == "cache" and row.get("outcome") == "hit"
    }
    missing = sum(
        sample["status"] == "answered"
        and not any(
            row.get("correlation_id") == sample["correlation_id"] for row in known_usage
        )
        and sample["correlation_id"] not in hits
        for sample in benchmark["samples"]
    )
    stages = {}
    for stage in ("query", "model", "source"):
        rows = [row for row in execution if row.get("stage") == stage]
        stages[stage] = {"samples": len(rows)}
        for key in ("queue_ms", "work_ms", "row_count", "evidence_bytes"):
            values = [
                row[key] for row in rows if type(row.get(key)) is int and row[key] >= 0
            ]
            if values:
                stages[stage][key] = {
                    "p50": percentile(values, 0.5),
                    "p95": percentile(values, 0.95),
                    "max": max(values),
                }
    return {
        "requests": benchmark["requests"],
        "concurrency": benchmark["concurrency"],
        "p50_ms": benchmark["p50_ms"],
        "p95_ms": benchmark["p95_ms"],
        "unexpected": benchmark["unexpected"],
        "usage_samples": len(known_usage),
        "answered_without_usage": missing,
        "prompt_tokens": prompt,
        "cache_hits": len(hits),
        "generated_tokens_including_thinking": generated,
        "observed_standard_cost_upper_bound_usd": round(
            (prompt * input_rate + generated * output_rate) / 1_000_000, 8
        )
        if known_usage
        else None,
        "cost_is_invoice": False,
        "stages": stages,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--logs", required=True, type=Path, nargs="+")
    parser.add_argument("--provider", required=True, choices=["gemini", "groq"])
    parser.add_argument("--input-usd-per-million", required=True, type=float)
    parser.add_argument("--output-usd-per-million", required=True, type=float)
    args = parser.parse_args()
    import math

    if not all(
        math.isfinite(rate) and rate >= 0
        for rate in (args.input_usd_per_million, args.output_usd_per_million)
    ):
        parser.error("Preço deve ser finito e não negativo.")
    result = summarize(
        json.loads(args.benchmark.read_text(encoding="utf-8")),
        [
            line
            for path in args.logs
            for line in path.read_text(encoding="utf-8").splitlines()
        ],
        provider=args.provider,
        input_rate=args.input_usd_per_million,
        output_rate=args.output_usd_per_million,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
