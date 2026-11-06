"""Captura candidatos Gemini para o benchmark F1 sem executar SQL.

Os contextos devem ter sido exportados pelo avaliador Backend. A captura não grava
perguntas nem conteúdo de contexto; sua saída contém apenas candidatos artificiais
e telemetria sanitizada e deve permanecer em work/.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import math
from pathlib import Path
from time import perf_counter

from dotenv import dotenv_values
from google import genai

from app.providers.protocols import ModelProviderRejected, ModelProviderUnavailable
from app.providers.sql_generator import (
    SQL_GENERATION_PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    GeminiSqlGenerator,
)
from app.schemas.sql_generation import SqlGenerationCandidate

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "ai-agent/tests/fixtures/text_to_sql_f1_benchmark.json"
PRICING_MODEL = "gemini-3.5-flash-lite"
INPUT_USD_PER_MILLION = 0.30
OUTPUT_USD_PER_MILLION = 2.50
INPUT_OVERHEAD_BYTES_PER_REQUEST = 8192
PRICING_SNAPSHOT_DATE = "2026-11-05"
PRICING_SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
MAX_OUTPUT_TOKENS = 4096


def validate_context_bundle(context_bundle, case_ids):
    benchmark_bytes = FIXTURE.read_bytes()
    benchmark = json.loads(benchmark_bytes)
    cases = {case["id"]: case for case in benchmark["cases"]}
    unknown = set(case_ids) - set(cases)
    if unknown:
        raise ValueError("A seleção inclui IDs ausentes do benchmark F1.")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("A seleção de IDs deve ser única.")

    expected_hash = hashlib.sha256(benchmark_bytes).hexdigest()
    if context_bundle.get("benchmark_sha256") != expected_hash:
        raise ValueError("Os contextos pertencem a outra versão do benchmark.")
    contexts = {item["id"]: item for item in context_bundle.get("contexts", [])}
    if set(case_ids) - set(contexts):
        raise ValueError("Há caso selecionado sem contexto exportado.")
    return expected_hash, contexts


def estimate_worst_case_cost_usd(contexts, case_ids, max_output_tokens=MAX_OUTPUT_TOKENS):
    """Paid-tier estimate using UTF-8 bytes as a token upper-bound proxy plus overhead."""
    schema_bytes = len(json.dumps(
        SqlGenerationCandidate.model_json_schema(), separators=(",", ":")
    ).encode("utf-8"))
    instruction_bytes = len(SYSTEM_INSTRUCTION.encode("utf-8"))
    input_bytes = sum(
        len(contexts[case_id]["contents"].encode("utf-8"))
        + schema_bytes
        + instruction_bytes
        + INPUT_OVERHEAD_BYTES_PER_REQUEST
        for case_id in case_ids
    )
    output_tokens = len(case_ids) * max_output_tokens
    return (
        input_bytes * INPUT_USD_PER_MILLION / 1_000_000
        + output_tokens * OUTPUT_USD_PER_MILLION / 1_000_000
    )


def reserve_capture_cost(carry_reserved_usd, prior_reserved_usd, pending_reserved_usd):
    values = (carry_reserved_usd, prior_reserved_usd, pending_reserved_usd)
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
           for value in values):
        raise ValueError("reservas devem ser números não negativos")
    return sum(values)


def prepare_capture(contexts, case_ids, prior_report=None):
    prior_candidates = {}
    prior_observations = []
    prior_uncaptured_attempts = []
    prior_reserved = 0.0
    if prior_report is not None:
        if (
            prior_report.get("benchmark_sha256")
            != hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
            or prior_report.get("prompt_version") != SQL_GENERATION_PROMPT_VERSION
            or prior_report.get("model") != PRICING_MODEL
        ):
            raise ValueError("A captura anterior usa benchmark, prompt ou modelo diferente.")
        prior_candidates = dict(prior_report.get("candidates", {}))
        prior_observations = list(prior_report.get("observations", []))
        prior_uncaptured_attempts = list(prior_report.get("uncaptured_attempts", []))
        if set(prior_candidates) - set(case_ids):
            raise ValueError("A captura anterior contém casos fora da seleção atual.")
        prior_parameters = prior_report.get("generation_parameters", {})
        prior_output_limit = prior_parameters.get("max_output_tokens", MAX_OUTPUT_TOKENS)
        if type(prior_output_limit) is not int or not 1 <= prior_output_limit <= MAX_OUTPUT_TOKENS:
            raise ValueError("A captura anterior tem limite de saída inválido.")
        for row in prior_observations:
            case_id = row.get("id")
            usage = row.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens")
            if (
                case_id in contexts
                and type(prompt_tokens) is int
                and prompt_tokens >= 0
            ):
                # max_output_tokens is the hard combined ceiling for response and thoughts.
                prior_reserved += (
                    prompt_tokens * INPUT_USD_PER_MILLION / 1_000_000
                    + prior_output_limit * OUTPUT_USD_PER_MILLION / 1_000_000
                )
            elif case_id in contexts:
                prior_reserved += estimate_worst_case_cost_usd(contexts, [case_id])
        for unknown_attempt in prior_uncaptured_attempts:
            case_id = unknown_attempt.get("id")
            count = unknown_attempt.get("count", 1)
            if case_id not in contexts or type(count) is not int or count < 1:
                raise ValueError("A captura anterior tem reserva de chamadas sem caso válido.")
            prior_reserved += count * estimate_worst_case_cost_usd(contexts, [case_id])

    observed_case_ids = {row.get("id") for row in prior_observations}
    if (len(observed_case_ids) != len(prior_observations)
            or observed_case_ids - set(case_ids)):
        raise ValueError("A captura anterior contém observações duplicadas ou fora da seleção.")
    uncertain_case_ids = {row["id"] for row in prior_uncaptured_attempts}
    pending = [
        case_id for case_id in case_ids
        if (case_id not in prior_candidates and case_id not in observed_case_ids
            and case_id not in uncertain_case_ids)
    ]
    return (
        prior_candidates, prior_observations, prior_uncaptured_attempts,
        pending, prior_reserved,
    )


def cost_from_usage(usage):
    if usage is None:
        return None, None
    prompt_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("output_tokens")
    thought_tokens = usage.get("thought_tokens")
    valid_input = type(prompt_tokens) is int and prompt_tokens >= 0
    valid_output = type(output_tokens) is int and output_tokens >= 0
    if not (valid_input and valid_output):
        return None, None
    lower_bound = (
        prompt_tokens * INPUT_USD_PER_MILLION
        + output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    if type(thought_tokens) is int and thought_tokens >= 0:
        exact_tier_estimate = lower_bound + thought_tokens * OUTPUT_USD_PER_MILLION / 1_000_000
        return round(exact_tier_estimate, 8), round(lower_bound, 8)
    return None, round(lower_bound, 8)


def build_report(
    *, expected_hash, model, parameters, max_cost_usd, worst_case_cost,
    case_ids, candidates, observations, uncaptured_attempts,
):
    return {
        "version": "text-to-sql-f1-gemini-capture-2",
        "boundary": "synthetic F1 prompts, real Gemini, no SQL execution",
        "benchmark_sha256": expected_hash,
        "model": model,
        "prompt_version": SQL_GENERATION_PROMPT_VERSION,
        "generation_parameters": parameters,
        "retry_attempts": 1,
        "pricing_snapshot": {
            "date": PRICING_SNAPSHOT_DATE,
            "source": PRICING_SOURCE,
            "tier_assumed": "paid; free-tier discount ignored",
            "input_usd_per_million_tokens": INPUT_USD_PER_MILLION,
            "output_usd_per_million_tokens": OUTPUT_USD_PER_MILLION,
            "cost_is_estimate_not_invoice": True,
        },
        "cost_guard": {
            "configured_max_usd": max_cost_usd,
            "reserved_worst_case_usd": round(worst_case_cost, 6),
            "input_upper_bound_method": (
                "UTF-8 bytes + 8 KiB per request for protocol overhead, schema and system"
            ),
            "max_output_tokens_per_request": parameters["max_output_tokens"],
        },
        "requested_denominator": len(case_ids),
        "attempted_denominator_upper_bound": (
            len(observations) + sum(item.get("count", 1) for item in uncaptured_attempts)
        ),
        "observed_attempt_count": len(observations),
        "uncaptured_attempt_count": sum(
            item.get("count", 1) for item in uncaptured_attempts
        ),
        "completed_case_count": len(candidates),
        "paid_tier_cost_estimate_usd": (
            round(sum(
                row["paid_tier_cost_estimate_usd"]
                for row in observations
                if row.get("paid_tier_cost_estimate_usd") is not None
            ), 8)
            if all(
                row.get("paid_tier_cost_estimate_usd") is not None
                for row in observations
            ) and not uncaptured_attempts
            else None
        ),
        "cost_estimates_missing_usage": sum(
            row.get("paid_tier_cost_estimate_usd") is None for row in observations
        ) + sum(item.get("count", 1) for item in uncaptured_attempts),
        "paid_tier_cost_lower_bound_usd": round(sum(
            row.get("paid_tier_cost_lower_bound_usd") or 0
            for row in observations
        ), 8),
        "candidates": candidates,
        "observations": observations,
        "uncaptured_attempts": uncaptured_attempts,
    }


def write_report(output, report):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)


class TelemetryCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.usage = []
        self.failures = []

    def emit(self, record):
        message = record.getMessage()
        if message.startswith("genai_usage "):
            self.usage.append(json.loads(message.removeprefix("genai_usage ")))
        elif message.startswith("genai_provider_failure "):
            self.failures.append(
                json.loads(message.removeprefix("genai_provider_failure "))
            )


async def capture(
    context_bundle, case_ids, output, max_cost_usd, prior_report=None,
    carry_reserved_usd=0.0,
    max_output_tokens=MAX_OUTPUT_TOKENS,
):
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS:
        raise ValueError("Limite de saída fora do teto do runner.")
    if (prior_report and prior_report.get("generation_parameters", {}).get("max_output_tokens")
            != max_output_tokens):
        raise ValueError("Retomada exige o mesmo limite de saída.")
    if output.exists() and prior_report is None:
        raise ValueError("Arquivo de captura já existe; use --resume ou outro --output.")
    expected_hash, contexts = validate_context_bundle(context_bundle, case_ids)
    (
        prior_candidates, prior_observations, prior_uncaptured_attempts,
        pending, prior_reserved,
    ) = prepare_capture(contexts, case_ids, prior_report)
    if (
        type(carry_reserved_usd) not in (int, float)
        or not 0 <= carry_reserved_usd < max_cost_usd
    ):
        raise ValueError("reserva anterior deve ser não negativa e menor que o teto")
    pending_reserved = estimate_worst_case_cost_usd(contexts, pending, max_output_tokens)
    worst_case_cost = reserve_capture_cost(
        carry_reserved_usd, prior_reserved, pending_reserved,
    )
    if worst_case_cost > max_cost_usd:
        raise ValueError(
            "O teto configurado é inferior à reserva conservadora para a seleção."
        )

    settings = dotenv_values(ROOT / ".env")
    api_key = settings.get("GENAI_GEMINI_API_KEY")
    model = settings.get("GENAI_GEMINI_MODEL")
    if not api_key or not model:
        raise ValueError("Configure GENAI_GEMINI_API_KEY e GENAI_GEMINI_MODEL no .env local.")
    if model != PRICING_MODEL:
        raise ValueError("O modelo não corresponde à referência de preço configurada no runner.")

    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": 20000, "retry_options": {"attempts": 1}},
    )
    parameters = {"max_output_tokens": max_output_tokens, "temperature": 0.0}
    generator = GeminiSqlGenerator(
        client=client, model_name=model, **parameters,
    )
    logger = logging.getLogger("uvicorn.error")
    previous_level = logger.level
    telemetry = TelemetryCapture()
    logger.addHandler(telemetry)
    logger.setLevel(logging.INFO)
    candidates = prior_candidates
    observations = prior_observations
    uncaptured_attempts = prior_uncaptured_attempts
    output.parent.mkdir(parents=True, exist_ok=True)
    write_report(output, build_report(
        expected_hash=expected_hash, model=model, parameters=parameters,
        max_cost_usd=max_cost_usd, worst_case_cost=worst_case_cost,
        case_ids=case_ids, candidates=candidates, observations=observations,
        uncaptured_attempts=uncaptured_attempts,
    ))
    try:
        for case_id in pending:
            context = contexts[case_id]
            started = perf_counter()
            usage_count = len(telemetry.usage)
            failure_count = len(telemetry.failures)
            try:
                candidate = await generator.generate(
                    context["contents"],
                    context_version=context["context_version"],
                )
                candidates[case_id] = candidate.model_dump(mode="json")
                outcome = candidate.status
                error_type = None
            except Exception as exc:  # noqa: BLE001 - record a sanitized class only
                outcome = "provider_or_contract_error"
                error_type = type(exc).__name__
            usage = telemetry.usage[-1] if len(telemetry.usage) > usage_count else None
            failure = (
                telemetry.failures[-1]
                if len(telemetry.failures) > failure_count
                else None
            )
            estimated_cost, lower_bound = cost_from_usage(usage)
            observations.append(
                {
                    "id": case_id,
                    "outcome": outcome,
                    "error_type": error_type,
                    "elapsed_ms": round((perf_counter() - started) * 1000, 2),
                    "usage": usage,
                    "paid_tier_cost_estimate_usd": estimated_cost,
                    "paid_tier_cost_lower_bound_usd": lower_bound,
                    "provider_failure": failure,
                }
            )
            write_report(output, build_report(
                expected_hash=expected_hash, model=model, parameters=parameters,
                max_cost_usd=max_cost_usd, worst_case_cost=worst_case_cost,
                case_ids=case_ids, candidates=candidates, observations=observations,
                uncaptured_attempts=uncaptured_attempts,
            ))
            if error_type in {
                ModelProviderUnavailable.__name__, ModelProviderRejected.__name__,
            }:
                break
    finally:
        logger.removeHandler(telemetry)
        logger.setLevel(previous_level)
        await client.aio.aclose()

    report = build_report(
        expected_hash=expected_hash, model=model, parameters=parameters,
        max_cost_usd=max_cost_usd, worst_case_cost=worst_case_cost,
        case_ids=case_ids, candidates=candidates, observations=observations,
        uncaptured_attempts=uncaptured_attempts,
    )
    write_report(output, report)
    print(json.dumps({
        "requested_denominator": report["requested_denominator"],
        "attempted_denominator_upper_bound": report["attempted_denominator_upper_bound"],
        "candidate_count": len(candidates),
        "outcomes": sorted({row["outcome"] for row in observations}),
        "output": str(output),
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contexts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", action="append", required=True)
    parser.add_argument("--max-cost-usd", type=float, required=True)
    parser.add_argument("--max-output-tokens", type=int, default=MAX_OUTPUT_TOKENS)
    parser.add_argument(
        "--carry-reserved-usd", type=float, default=0.0,
        help="Reserva conservadora de chamadas em outra versão de prompt.",
    )
    parser.add_argument("--resume", type=Path)
    parser.add_argument(
        "--max-requests", type=int, default=1,
        help="Teto explícito de chamadas; padrão 1 para controlar custo.",
    )
    args = parser.parse_args()
    if not 1 <= args.max_requests <= 40 or len(args.case_id) > args.max_requests:
        parser.error("a seleção deve respeitar --max-requests entre 1 e 40")
    if args.max_cost_usd <= 0:
        parser.error("--max-cost-usd deve ser maior que zero")
    if not 0 <= args.carry_reserved_usd < args.max_cost_usd:
        parser.error("--carry-reserved-usd deve ser não negativo e menor que o teto")
    bundle = json.loads(args.contexts.read_text(encoding="utf-8"))
    prior_report = (
        json.loads(args.resume.read_text(encoding="utf-8")) if args.resume else None
    )
    asyncio.run(capture(
        bundle, args.case_id, args.output, args.max_cost_usd, prior_report,
        args.carry_reserved_usd,
        args.max_output_tokens,
    ))


if __name__ == "__main__":
    main()
