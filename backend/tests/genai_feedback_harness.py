"""Harness da avaliação de recusas/esclarecimentos pelo caminho real do Backend.

Duas fases, executadas com o Python do Backend (`python -m tests.genai_feedback_harness`):

* ``dump``: para cada caso, monta a requisição, executa ``observe_sql_generation`` com um
  cliente que apenas captura o que seria enviado ao modelo. Desfechos que não precisam do
  modelo (regras determinísticas) saem prontos, com zero chamadas.
* ``replay``: devolve candidatos já obtidos (Gemini real ou modelo controlado) ao mesmo
  caminho e converte o resultado no formato do avaliador.

Nenhuma consulta é executada na Gold e nenhum dado Gold é enviado ao modelo: o contexto vem
do catálogo e de cobertura artificial. Isto mede decisão e apresentação, não números.
"""

import asyncio
import json
import sys
from pathlib import Path

from app.schemas.genai_internal import QuestionPlanRequest
from app.schemas.sql_generation import SqlGenerationResponse
from app.services.genai_client import (
    GenAIResponseInvalid,
    GenAIServiceUnavailable,
    GenAITimeout,
)
from app.services.genai_deadline import GenAIRequestDeadline
from app.services.genai_sql_context import SqlContextUnavailable
from app.services.genai_sql_observation import observe_sql_generation

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "ai-agent" / "tests" / "fixtures"
CORRELATION = "b" * 32
BATCH = (
    "gold-csv-v2:GOLD_20000101T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc"
)
MONTHLY = (
    "billing.revenue",
    "energy.consumption",
    "billing.average_ticket",
    "billing.effective_tariff",
    "energy.average_consumption_per_uc",
    "network.equivalent_interruption_duration",
    "network.equivalent_interruption_frequency",
    "service.attendance",
    "service.satisfaction",
)
SNAPSHOT = (
    "service.accumulated_attendance",
    "service.accumulated_satisfaction",
    "energy.gd_units",
    "energy.gd_consumption_drop",
)
COMPETENCIES = [
    f"{year}-{month:02d}"
    for year in range(2022, 2027)
    for month in range(1, 13)
    if "2022-07" <= f"{year}-{month:02d}" <= "2026-06"
]
TECHNICAL_MESSAGE = "A análise dos dados está temporariamente indisponível."


class _Captured(Exception):
    def __init__(self, payload):
        self.payload = payload


class _CapturingClient:
    async def generate_sql_candidate(self, payload, *, correlation_id):
        raise _Captured(payload)


class _ReplayClient:
    def __init__(self, candidate=None, error=None):
        self.candidate = candidate
        self.error = error
        self.calls = 0

    async def generate_sql_candidate(self, payload, *, correlation_id):
        self.calls += 1
        if self.error == "unavailable":
            raise GenAIServiceUnavailable
        if self.error == "timeout":
            raise GenAITimeout
        if self.error is not None:
            raise GenAIResponseInvalid
        return SqlGenerationResponse.model_validate(
            {
                "correlation_id": correlation_id,
                "generation_contract_version": payload.generation_contract_version,
                "candidate": self.candidate,
            }
        )


def build_request(case) -> QuestionPlanRequest:
    return QuestionPlanRequest.model_validate(
        {
            "question": case["question"],
            "context": case["context"],
            "remaining_timeout_ms": 30000,
            "batch_ref": BATCH,
            "access_scope": {
                "caller_ref": "session:" + "a" * 64,
                "profile_id": "v-energy-grid-360-gold",
                "source_id": "gold.local",
                "allowed_operations": ["read"],
                "allowed_metric_ids": [*MONTHLY, *SNAPSHOT],
                "allowed_dimension_ids": [
                    "geography.municipality",
                    "customer.consumption_class",
                    "network.feeder",
                    "generation.distributed",
                ],
            },
            "temporal_coverage": [
                *(
                    {
                        "metric_id": metric,
                        "kind": "monthly",
                        "competencies": COMPETENCIES,
                    }
                    for metric in MONTHLY
                ),
                *({"metric_id": metric, "kind": "none"} for metric in SNAPSHOT),
            ],
            "dimension_value_coverage": [
                {"dimension_id": "generation.distributed", "values": ["Sim", "N\u00e3o"]},
                {
                    "dimension_id": "geography.municipality",
                    "values": ["Recife", "Olinda"],
                },
                {
                    "dimension_id": "customer.consumption_class",
                    "values": ["Residencial", "Comercial", "Industrial"],
                },
            ],
        }
    )


def _outcome(observation) -> dict:
    candidate = observation.candidate
    outcome = {
        "status": candidate.status,
        "reason_code": None,
        "missing_fields": [],
        "message": "",
        "options": [],
        "sql": None,
        "has_quantitative_evidence": False,
        "model_calls": observation.model_calls,
        "source_queries": 0,
    }
    if candidate.status == "needs_clarification":
        clarification = candidate.clarification
        outcome.update(
            reason_code=clarification.reason_code,
            missing_fields=list(clarification.missing_fields),
            message=clarification.question,
            options=[option.model_dump() for option in clarification.options],
        )
    elif candidate.status == "unsupported":
        outcome.update(
            reason_code=candidate.unsupported_reason.reason_code,
            message=candidate.unsupported_reason.message,
        )
    else:
        # Teria consulta na Gold; a avaliação não a executa.
        outcome.update(sql=candidate.sql or "<compiled>", source_queries=1)
    return outcome


def _technical(model_calls: int, note: str) -> dict:
    return {
        "status": "technical_error",
        "reason_code": None,
        "missing_fields": [],
        "message": TECHNICAL_MESSAGE,
        "options": [],
        "sql": None,
        "has_quantitative_evidence": False,
        "model_calls": model_calls,
        "source_queries": 0,
        "note": note,
    }


async def _observe(request, client):
    return await observe_sql_generation(
        request,
        client=client,
        deadline=GenAIRequestDeadline.start(60),
        correlation_id=CORRELATION,
    )


def dump(cases) -> dict:
    result = {}
    for case in cases:
        entry = {"id": case["id"]}
        if case.get("access"):
            entry["skip"] = (
                "perfil restrito é conferido na borda HTTP, fora deste harness"
            )
        elif case.get("mode", {}).get("provider_failure"):
            entry["simulated_failure"] = case["mode"]["provider_failure"]
        else:
            try:
                observation = asyncio.run(
                    _observe(build_request(case), _CapturingClient())
                )
                entry["outcome"] = _outcome(observation)
            except _Captured as captured:
                payload = captured.payload
                entry["model_request"] = {
                    "generation_contract_version": payload.generation_contract_version,
                    "context_version": payload.context_version,
                    "contents": payload.contents,
                }
            except SqlContextUnavailable as exc:
                entry["outcome"] = _technical(0, f"context_unavailable:{exc.reason}")
        result[case["id"]] = entry
    return result


def replay(cases, dumped, candidates) -> dict:
    outcomes = {}
    for case in cases:
        entry = dumped[case["id"]]
        if "skip" in entry:
            outcomes[case["id"]] = {"skipped": entry["skip"]}
            continue
        if "outcome" in entry:
            outcomes[case["id"]] = entry["outcome"]
            continue
        if "simulated_failure" in entry:
            error = (
                "timeout" if entry["simulated_failure"] == "timeout" else "unavailable"
            )
            client = _ReplayClient(error=error)
        else:
            supplied = candidates.get(case["id"]) or {}
            if supplied.get("not_modeled"):
                outcomes[case["id"]] = {
                    "skipped": "sem modelo controlado para consulta"
                }
                continue
            client = _ReplayClient(
                candidate=supplied.get("candidate"), error=supplied.get("error")
            )
        try:
            observation = asyncio.run(_observe(build_request(case), client))
            outcomes[case["id"]] = _outcome(observation)
        except (GenAIResponseInvalid, GenAIServiceUnavailable, GenAITimeout) as exc:
            outcomes[case["id"]] = _technical(client.calls, type(exc).__name__)
        except Exception as exc:  # noqa: BLE001 - registra e não derruba a medição inteira
            outcomes[case["id"]] = _technical(
                client.calls, f"unhandled:{type(exc).__name__}"
            )
    return outcomes


def main(argv) -> int:
    mode, source, *rest = argv
    cases = json.loads(Path(source).read_text(encoding="utf-8"))["cases"]
    if mode == "dump":
        target = Path(rest[0])
        target.write_text(json.dumps(dump(cases), ensure_ascii=False), encoding="utf-8")
        return 0
    dumped = json.loads(Path(rest[0]).read_text(encoding="utf-8"))
    candidates = (
        json.loads(Path(rest[1]).read_text(encoding="utf-8")) if len(rest) > 2 else {}
    )
    target = Path(rest[-1])
    target.write_text(
        json.dumps(replay(cases, dumped, candidates), ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
