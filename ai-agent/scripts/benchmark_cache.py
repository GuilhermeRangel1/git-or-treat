"""Microbenchmark reproduzível do adaptador real com provedor artificial; sem rede."""

import asyncio
import json
import math
import tracemalloc
from time import perf_counter

from app.providers.caching import CachingModelAdapter
from app.providers.protocols import GeneratedAnswer
from app.schemas.evidence import EvidenceProvenance, EvidenceResult
from app.schemas.questions import EvidenceReference
from app.schemas.read_plan import ReadWindow, WindowKind


class MeasuredProvider:
    def __init__(self):
        self.calls = 0

    async def generate(self, question, context, evidence):
        self.calls += 1
        await asyncio.sleep(0.02)
        return GeneratedAnswer(status="answered", answer="Resultado artificial.",
                               observation_ids=("row_1",))


def evidence():
    return EvidenceResult(
        reference=EvidenceReference(source="synthetic_fixture:cache",
                                    description="Benchmark artificial", is_demo=True),
        records=[{"observation_id": "row_1", "value": 1}],
        provenance=EvidenceProvenance(source_id="synthetic_fixture",
            reference_source="synthetic_fixture:cache", plan_fingerprint="0" * 64,
            catalog_version="v1", metric_id="cache", unit="unidades",
            window=ReadWindow(kind=WindowKind.CATALOG_PHRASE, phrase="teste")),
        cache_scope="a" * 64,
    )


def summary(samples):
    ordered = sorted(samples)
    return {"p50_ms": round(ordered[math.ceil(len(ordered) * .5) - 1], 3),
            "p95_ms": round(ordered[math.ceil(len(ordered) * .95) - 1], 3)}


async def measure():
    report = {"scope": "artificial_provider_real_cache", "requests_per_case": 20,
              "provider_delay_ms": 20, "network": False, "cases": {}}
    for mode in ("disabled", "cold", "warm", "concurrent"):
        tracemalloc.start()
        provider = MeasuredProvider()
        adapter = provider if mode == "disabled" else CachingModelAdapter(
            provider, ttl_seconds=60, max_entries=64, max_bytes=1048576)
        value = evidence()
        if mode == "warm":
            await adapter.generate("teste", [], value)
        before = provider.calls
        async def once(index, adapter=adapter, mode=mode, value=value):
            started = perf_counter()
            result = await adapter.generate(str(index) if mode == "cold" else "teste", [], value)
            assert result.observation_ids == ("row_1",)
            return (perf_counter() - started) * 1000
        if mode == "concurrent":
            samples = await asyncio.gather(*(once(i) for i in range(20)))
        else:
            samples = [await once(i) for i in range(20)]
        calls = provider.calls - before
        expected = {"disabled": 20, "cold": 20, "warm": 0, "concurrent": 1}[mode]
        if calls != expected:
            raise RuntimeError("Regressão no reaproveitamento do cache.")
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        report["cases"][mode] = {**summary(samples), "provider_calls": calls,
                                "retained_payload_bytes": getattr(adapter, "_bytes", 0),
                                "python_peak_allocated_bytes": peak}
    return report


if __name__ == "__main__":
    print(json.dumps(asyncio.run(measure()), indent=2))
