"""Prazo B6 compartilhado pelo futuro coordenador; sem defaults de produto."""

import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import TypeVar

from app.services.genai_client import GenAITimeout

T = TypeVar("T")


def _positive_seconds(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Prazo deve ser numérico.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Prazo deve ser positivo e finito.")


@dataclass(frozen=True)
class GenAIRequestDeadline:
    """Instância por requisição; etapas consomem o mesmo relógio monotônico."""

    expires_at: float
    clock: Callable[[], float]

    @classmethod
    def start(
        cls, total_seconds: float, *, clock: Callable[[], float] = monotonic
    ) -> "GenAIRequestDeadline":
        _positive_seconds(total_seconds)
        expires_at = clock() + total_seconds
        if not math.isfinite(expires_at):
            raise ValueError("Prazo absoluto inválido.")
        return cls(expires_at, clock)

    def remaining_seconds(self, stage_limit_seconds: float) -> float:
        _positive_seconds(stage_limit_seconds)
        remaining = self.expires_at - self.clock()
        if remaining <= 0:
            raise GenAITimeout
        return min(remaining, stage_limit_seconds)

    def sql_timeout_ms(self, stage_limit_seconds: float) -> int:
        # Zero significa timeout desativado no PostgreSQL; nunca o devolvemos.
        milliseconds = int(self.remaining_seconds(stage_limit_seconds) * 1000)
        if milliseconds < 1:
            raise GenAITimeout
        return milliseconds

    async def run(self, stage_limit_seconds: float, operation: Callable[[], Awaitable[T]]) -> T:
        """Não cria a operação se o prazo acabou; não repete ou oculta falhas.

        Cancelamento assíncrono não comprova cancelamento de SQL ou trabalho em
        thread. O executor deverá aplicar timeout/cancelamento no próprio banco.
        """
        seconds = self.remaining_seconds(stage_limit_seconds)
        deadline = asyncio.timeout(seconds)
        try:
            async with deadline:
                result = await operation()
        except TimeoutError:
            if not deadline.expired():
                raise
            raise GenAITimeout from None
        if deadline.expired():
            raise GenAITimeout
        # Também impede publicar resultado concluído após o prazo global.
        self.remaining_seconds(stage_limit_seconds)
        return result
