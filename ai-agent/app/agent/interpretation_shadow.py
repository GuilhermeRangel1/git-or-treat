"""Observação de intenções propostas, sem acesso ao planner ou ao executor."""

import asyncio
from time import perf_counter
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.schemas.interpretation import IntentInterpretation


class IntentProposer(Protocol):
    async def propose(self) -> IntentInterpretation: ...


class ShadowObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    elapsed_ms: float
    differing_fields: tuple[str, ...] = ()


async def observe_interpretation(
    proposer: IntentProposer,
    reference: IntentInterpretation,
    *,
    timeout_seconds: float = 20,
) -> ShadowObservation:
    """Compara com referência anotada; nunca retorna uma proposta executável.

    O chamador fornece um proposer já vinculado ao contexto permitido. A saída
    contém somente nomes de campos e tempo; perguntas e valores não viram logs.
    Cancelamento do chamador é preservado.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout deve ser positivo")
    started = perf_counter()
    differences: tuple[str, ...] = ()
    try:
        async with asyncio.timeout(timeout_seconds):
            proposal = await proposer.propose()
        if not isinstance(proposal, IntentInterpretation):
            raise ValueError("proposta deve usar o contrato de interpretação")
        expected = reference.model_dump(mode="json")
        actual = proposal.model_dump(mode="json")
        differences = tuple(sorted(key for key in expected if actual[key] != expected[key]))
        if reference.intent is not None and proposal.intent is not None:
            expected_intent = reference.intent.model_dump(mode="json")
            actual_intent = proposal.intent.model_dump(mode="json")
            differences = tuple(
                sorted(
                    [key for key in differences if key != "intent"]
                    + [
                        f"intent.{key}"
                        for key in expected_intent
                        if actual_intent[key] != expected_intent[key]
                    ]
                )
            )
        status = "match" if not differences else "mismatch"
    except TimeoutError:
        status = "timeout"
    except Exception:
        status = "proposal_error"
    return ShadowObservation(
        status=status,
        elapsed_ms=(perf_counter() - started) * 1000,
        differing_fields=differences,
    )
