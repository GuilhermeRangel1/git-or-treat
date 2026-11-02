"""Orçamento por solicitação e limites compartilhados de chamadas assíncronas."""

import asyncio
import hashlib
import json
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from app.schemas.access import AccessContext
from app.schemas.read_plan import LogicalReadPlan, cache_plan_digest

T = TypeVar("T")


class ExecutionLimitExceeded(Exception):
    """A solicitação esgotou tempo, chamadas ou capacidade de execução."""


def authorized_cache_scope(context: AccessContext, plan: LogicalReadPlan) -> str:
    """Isola cache por identidade, permissões e plano sem incluir correlação transitória."""

    payload = {
        "access": context.model_dump(mode="json", exclude={"correlation_id"}),
        # Filtros normalizados: ordem diferente não separa o mesmo recorte.
        "plan": cache_plan_digest(plan),
        "catalog_version": plan.catalog_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExecutionLimits:
    request_seconds: float = 30.0
    source_seconds: float = 10.0
    model_seconds: float = 20.0
    max_source_calls: int = 1
    max_model_calls: int = 1
    concurrent_requests: int = 16
    concurrent_sources: int = 8
    concurrent_models: int = 8

    def __post_init__(self) -> None:
        if any(
            value <= 0
            for value in (
                self.request_seconds,
                self.source_seconds,
                self.model_seconds,
                self.max_source_calls,
                self.max_model_calls,
                self.concurrent_requests,
                self.concurrent_sources,
                self.concurrent_models,
            )
        ):
            raise ValueError("limites de execução devem ser positivos")


class ExecutionController:
    """Compartilha semáforos; cada chamada recebe seu próprio orçamento."""

    def __init__(self, limits: ExecutionLimits | None = None) -> None:
        self.limits = limits or ExecutionLimits()
        self._requests = asyncio.Semaphore(self.limits.concurrent_requests)
        self._sources = asyncio.Semaphore(self.limits.concurrent_sources)
        self._models = asyncio.Semaphore(self.limits.concurrent_models)

    def ensure_model_capacity(self, *models: object) -> None:
        """Rejeita cadeias capazes de exceder o orçamento de tentativas por request.

        Com vários modelos chamados em sequência, como na escalada do roteador, soma o pior
        caso de cada um.
        """
        attempts = [getattr(model, "max_attempts", 1) for model in models]
        if (
            not attempts
            or any(type(item) is not int or item < 1 for item in attempts)
            or sum(attempts) > self.limits.max_model_calls
        ):
            raise ValueError("A cadeia de modelos excede o limite de chamadas configurado.")

    async def run(
        self, action: Callable[["RequestBudget"], Awaitable[T]], *,
        timeout_seconds: float | None = None,
    ) -> T:
        seconds = self.limits.request_seconds
        if timeout_seconds is not None:
            if (
                isinstance(timeout_seconds, bool)
                or not math.isfinite(timeout_seconds)
                or timeout_seconds <= 0
            ):
                raise ValueError("prazo recebido deve ser positivo e finito")
            seconds = min(seconds, timeout_seconds)
        try:
            async with asyncio.timeout(seconds) as deadline:
                async with self._requests:
                    result = await action(RequestBudget(self))
                    if deadline.expired() or asyncio.get_running_loop().time() >= deadline.when():
                        raise ExecutionLimitExceeded("prazo da solicitação esgotado")
                    return result
        except TimeoutError:
            if not deadline.expired():
                raise
            raise ExecutionLimitExceeded("prazo da solicitação esgotado") from None


class RequestBudget:
    def __init__(self, controller: ExecutionController) -> None:
        self._controller = controller
        self._source_calls = 0
        self._model_calls = 0

    async def source(self, action: Callable[[], Awaitable[T]]) -> T:
        self._source_calls += 1
        if self._source_calls > self._controller.limits.max_source_calls:
            raise ExecutionLimitExceeded("limite de chamadas à fonte")
        return await self._bounded(
            self._controller._sources, self._controller.limits.source_seconds, action
        )

    async def model(self, action: Callable[[], Awaitable[T]]) -> T:
        self._model_calls += 1
        if self._model_calls > self._controller.limits.max_model_calls:
            raise ExecutionLimitExceeded("limite de chamadas ao modelo")
        return await self._bounded(
            self._controller._models, self._controller.limits.model_seconds, action
        )

    @staticmethod
    async def _bounded(
        semaphore: asyncio.Semaphore,
        seconds: float,
        action: Callable[[], Awaitable[T]],
    ) -> T:
        try:
            async with asyncio.timeout(seconds) as deadline:
                async with semaphore:
                    return await action()
        except TimeoutError:
            if not deadline.expired():
                raise
            raise ExecutionLimitExceeded("prazo da dependência esgotado") from None
