"""Cache em memória de respostas do modelo, com TTL, limite LRU e chamada única por chave."""

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable

from pydantic import ValidationError

from app.providers.protocols import (
    GeneratedAnswer,
    ModelAdapter,
    ModelProviderInvalidResponse,
)
from app.schemas.evidence import EvidenceResult
from app.schemas.questions import ConversationTurn
from app.schemas.read_plan import normalized_filters
from app.telemetry import record_execution

# v2: filtros normalizados e catálogo físico da proveniência na chave.
CACHE_KEY_VERSION = 2


def cache_key(
    question: str,
    context: list[ConversationTurn],
    evidence: EvidenceResult,
    namespace: str,
) -> str:
    """Hash estável das entradas; qualquer mudança na evidência gera outra chave.

    A proveniência inclui lote, qualidade e catálogo físico; filtros entram na forma
    canônica para que a ordem não separe recortes iguais.
    """

    evidence_payload = evidence.model_dump(mode="json")
    if evidence.provenance is not None:
        evidence_payload["provenance"]["filters"] = normalized_filters(
            evidence.provenance.filters
        )
    payload = json.dumps(
        {
            "v": CACHE_KEY_VERSION,
            "namespace": namespace,
            "scope": evidence.cache_scope,
            "question": question,
            "context": [turn.model_dump(mode="json") for turn in context],
            "evidence": evidence_payload,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CachingModelAdapter:
    """Reaproveita respostas bem-sucedidas; falhas nunca são guardadas.

    Sem escopo autorizado e proveniência, a chamada passa diretamente ao modelo.
    Chamadas compartilhadas são canceladas quando nenhum solicitante permanece.
    """

    def __init__(
        self,
        inner: ModelAdapter,
        *,
        ttl_seconds: float,
        max_entries: int,
        max_bytes: int = 4_194_304,
        namespace: str = "local-model-v1",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or max_entries < 1 or max_bytes < 1:
            raise ValueError("TTL e tamanho máximo do cache devem ser positivos.")
        self._inner = inner
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._bytes = 0
        self._sizes: dict[str, int] = {}
        self._namespace = namespace
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, GeneratedAnswer]] = OrderedDict()
        self._in_flight: dict[str, asyncio.Task[GeneratedAnswer]] = {}
        self._waiters: dict[str, int] = {}

    @property
    def max_attempts(self) -> int:
        """Um cache miss pode executar toda a cadeia encapsulada."""
        return getattr(self._inner, "max_attempts", 1)

    async def generate(
        self,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        if evidence.cache_scope is None or evidence.provenance is None:
            return await self._inner.generate(question, context, evidence)
        key = cache_key(question, context, evidence, self._namespace)
        cached = self._lookup(key)
        if cached is not None:
            record_execution("cache", 0, 0, "hit")
            return cached.model_copy(deep=True)
        record_execution("cache", 0, 0, "miss")

        self._purge_expired()
        task = self._in_flight.get(key)
        if task is None or task.done():
            if len(self._in_flight) >= self._max_entries:
                return await self._inner.generate(question, context, evidence)
            task = asyncio.ensure_future(self._fill(key, question, context, evidence))
            self._in_flight[key] = task
            task.add_done_callback(lambda done: self._forget(key, done))
        self._waiters[key] = self._waiters.get(key, 0) + 1
        try:
            # A primeira desistência não interrompe outra solicitação ainda aguardando.
            answer = await asyncio.shield(task)
            return answer.model_copy(deep=True)
        finally:
            remaining = self._waiters[key] - 1
            if remaining:
                self._waiters[key] = remaining
            else:
                del self._waiters[key]
                if not task.done():
                    if self._in_flight.get(key) is task:
                        del self._in_flight[key]
                    task.cancel()

    async def _fill(
        self,
        key: str,
        question: str,
        context: list[ConversationTurn],
        evidence: EvidenceResult,
    ) -> GeneratedAnswer:
        answer = await self._inner.generate(question, context, evidence)
        try:
            answer = GeneratedAnswer.model_validate(
                answer.model_dump() if isinstance(answer, GeneratedAnswer) else answer
            )
        except (ValidationError, TypeError, ValueError, AttributeError):
            raise ModelProviderInvalidResponse("Saída do modelo inválida.") from None
        observation_ids = answer.observation_ids
        available_ids = {
            record["observation_id"]
            for record in evidence.records
            if isinstance(record, dict) and isinstance(record.get("observation_id"), str)
        }
        if (
            answer.status == "answered"
            and observation_ids
            and len(set(observation_ids)) == len(observation_ids)
            and set(observation_ids) <= available_ids
        ):
            self._store(key, answer)
        return answer

    def _lookup(self, key: str) -> GeneratedAnswer | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, answer = entry
        if expires_at <= self._clock():
            self._remove(key)
            return None
        self._entries.move_to_end(key)
        return answer

    def _remove(self, key: str) -> None:
        self._entries.pop(key, None)
        self._bytes -= self._sizes.pop(key, 0)

    def _purge_expired(self) -> None:
        now = self._clock()
        for key, (expires, _) in list(self._entries.items()):
            if expires <= now:
                self._remove(key)

    def _store(self, key: str, answer: GeneratedAnswer) -> None:
        self._purge_expired()
        size = len(key.encode()) + len(answer.model_dump_json().encode())
        if size > self._max_bytes:
            return
        self._remove(key)
        self._entries[key] = (self._clock() + self._ttl_seconds, answer.model_copy(deep=True))
        self._sizes[key] = size
        self._bytes += size
        while len(self._entries) > self._max_entries or self._bytes > self._max_bytes:
            self._remove(next(iter(self._entries)))

    def _forget(self, key: str, done: asyncio.Task[GeneratedAnswer]) -> None:
        if self._in_flight.get(key) is done:
            del self._in_flight[key]
        if not done.cancelled():
            # Marca a exceção como lida mesmo se todos os chamadores tiverem sido cancelados.
            done.exception()
