"""Carga limitada pela API local; arquivo de casos e credenciais ficam fora do Git."""

import argparse
import asyncio
import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

import httpx


def percentile(values: list[float], fraction: float) -> float | None:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None


async def benchmark(
    base: str, cases: list[dict], *, concurrency: int, repeat: int
) -> dict:
    address = urlsplit(base)
    if (
        address.scheme != "http"
        or address.hostname not in {"localhost", "127.0.0.1", "backend"}
        or address.username
        or address.password
        or address.query
        or address.fragment
    ):
        raise ValueError("Somente Backend local sem credenciais na URL.")
    if (
        not isinstance(cases, list)
        or not 1 <= concurrency <= 8
        or not 1 <= len(cases) * repeat <= 100
    ):
        raise ValueError(
            "Carga deve ter até oito chamadas concorrentes e cem solicitações."
        )
    for case in cases:
        if (
            not isinstance(case, dict)
            or set(case) != {"question", "expected_status"}
            or not isinstance(case["question"], str)
            or not 1 <= len(case["question"]) <= 1000
            or case["expected_status"]
            not in {"answered", "needs_clarification", "refused", "no_evidence"}
        ):
            raise ValueError("Caso inválido.")
    rows = []
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(
        base_url=base,
        timeout=70,
        trust_env=False,
        headers={"Origin": "http://localhost:5173"},
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": os.environ["GENAI_BENCHMARK_USERNAME"],
                "password": os.environ["GENAI_BENCHMARK_PASSWORD"],
            },
        )
        if response.status_code != 200:
            raise ValueError("Autenticação indisponível.")

        async def ask(index, case):
            submitted = monotonic()
            async with semaphore:
                started = monotonic()
                status, http, correlation = "transport_error", None, None
                try:
                    result = await client.post(
                        "/api/v1/ai/questions", json={"question": case["question"]}
                    )
                    http = result.status_code
                    body = result.json()
                    if not isinstance(body, dict):
                        raise ValueError("Envelope inválido.")
                    status = body.get("status", "invalid_response")
                    if not isinstance(status, str) or status not in {
                        "answered",
                        "needs_clarification",
                        "refused",
                        "no_evidence",
                        "recoverable_error",
                    }:
                        status = "invalid_response"
                    correlation = body.get("correlation_id")
                    if (
                        not isinstance(correlation, str)
                        or re.fullmatch("[a-f0-9]{32}", correlation) is None
                    ):
                        correlation = None
                except (httpx.HTTPError, ValueError, TypeError):
                    pass
                rows.append(
                    {
                        "case": index,
                        "http": http,
                        "status": status,
                        "expected": case["expected_status"],
                        "correlation_id": correlation,
                        "client_queue_ms": round((started - submitted) * 1000, 2),
                        "latency_ms": round((monotonic() - started) * 1000, 2),
                    }
                )

        started = monotonic()
        try:
            await asyncio.gather(
                *(ask(i, case) for _ in range(repeat) for i, case in enumerate(cases))
            )
        finally:
            await client.post("/api/v1/auth/logout")
    timings = [row["latency_ms"] for row in rows]
    return {
        "concurrency": concurrency,
        "requests": len(rows),
        "elapsed_ms": round((monotonic() - started) * 1000, 2),
        "p50_ms": percentile(timings, 0.5),
        "p95_ms": percentile(timings, 0.95),
        "statuses": dict(Counter(row["status"] for row in rows)),
        "unexpected": sum(
            row["http"] != 200 or row["status"] != row["expected"] for row in rows
        ),
        "samples": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    try:
        result = asyncio.run(
            benchmark(
                os.environ.get("GENAI_BENCHMARK_URL", "http://localhost:8000"),
                json.loads(args.cases.read_text(encoding="utf-8-sig")),
                concurrency=args.concurrency,
                repeat=args.repeat,
            )
        )
    except (ValueError, KeyError, TypeError, OSError, httpx.HTTPError):
        print("Carga não concluída; confira configuração, casos e serviços.")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "samples"}))
    return int(result["unexpected"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
