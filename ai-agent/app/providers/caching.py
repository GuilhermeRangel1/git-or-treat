"""Cache em memória de respostas do modelo, com TTL, limite LRU e chamada única por chave."""

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable

from app.providers.protocols import GeneratedAnswer, ModelAdapter
from app.schemas.questions import ConversationTurn
from app.tools.evidence import EvidenceResult

CACHE_KEY_VERSION = 1


def cache_key(
    question: str,
    context: list[ConversationTurn],
    evidence: EvidenceResult,
) -> str:
    """Hash estável das entradas; qualquer mudança na evidência gera outra chave."""

    payload = json.dumps(
        {
            "v": CACHE_KEY_VERSION,
            "question": question,
            "context": [turn.model_dump(mode="json") for turn in context],
            "evidence": evidence.model_dump(mode="json"),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CachingModelAdapter:
    """Reaproveita respostas bem-sucedidas; falhas nunca são guardadas.

    Chamadas iguais e simultâneas compartilham uma única chamada ao modelo. A checagem de
    números continua nos orquestradores, que também recebem as respostas vindas do cache.
    """

    def __init__(
        self,
        inner: ModelAdapter,
        *,
        ttl_seconds: float,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or max_entries < 1:
            raise ValueError("TTL e tamanho máximo do cache devem ser positivos.")
        self._inner = inner
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, GeneratedAnswer]] = OrderedDict()
        self._in_flight: dict[str, asyncio.Task[GeneratedAnswer]] = {}

    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        key = cache_key(question, context, evidence)
        cached = self._lookup(key)
        if cached is not None:
            return cached.model_copy()

        task = self._in_flight.get(key)
        if task is None or task.done():
            task = asyncio.ensure_future(self._fill(key, question, context, evidence))
            self._in_flight[key] = task
            task.add_done_callback(lambda done: self._forget(key, done))
        # shield: cancelar quem espera não cancela a chamada compartilhada com os demais.
        answer = await asyncio.shield(task)
        return answer.model_copy()

    async def _fill(
        self,
        key: str,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        answer = await self._inner.generate(question, context, evidence)
        self._store(key, answer)
        return answer

    def _lookup(self, key: str) -> GeneratedAnswer | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, answer = entry
        if expires_at <= self._clock():
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return answer

    def _store(self, key: str, answer: GeneratedAnswer) -> None:
        self._entries[key] = (self._clock() + self._ttl_seconds, answer.model_copy())
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def _forget(self, key: str, done: asyncio.Task[GeneratedAnswer]) -> None:
        if self._in_flight.get(key) is done:
            del self._in_flight[key]
        if not done.cancelled():
            # Marca a exceção como lida mesmo se todos os chamadores tiverem sido cancelados.
            done.exception()
