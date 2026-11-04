"""Eventos internos com campos fechados; conteúdo do usuário nunca entra na trilha."""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic
from typing import Protocol

from app.generation.prompts import PROMPT_VERSION

logger = logging.getLogger(__name__)
_HEX32 = re.compile(r"[a-f0-9]{32}\Z")
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")


class EventStage(StrEnum):
    REQUEST = "request"
    POLICY = "policy"
    PLAN = "plan"
    SOURCE = "source"
    EVIDENCE = "evidence"
    MODEL = "model"
    RESPONSE = "response"


class EventCode(StrEnum):
    STARTED = "started"
    ALLOWED = "allowed"
    DENIED = "denied"
    READY = "ready"
    CLARIFICATION = "clarification"
    NO_EVIDENCE = "no_evidence"
    AVAILABLE = "available"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"
    COMPLETED = "completed"
    REFUSED = "refused"
    ESCALATED = "escalated"
    LIMIT = "limit"
    CANCELLED = "cancelled"


class EventOutcome(StrEnum):
    STARTED = "started"
    SUCCESS = "success"
    REFUSED = "refused"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class CoreEvent:
    flow: str
    stage: EventStage
    code: EventCode
    outcome: EventOutcome
    correlation_id: str | None
    duration_ms: int
    source_calls: int = 0
    model_calls: int = 0
    row_count: int = 0
    contract_version: str = "v1"
    catalog_version: str | None = None
    plan_id: str | None = None
    evidence_ref: str | None = None
    prompt_version: str = PROMPT_VERSION

    def __post_init__(self) -> None:
        if self.flow not in {"question", "insight"}:
            raise ValueError("fluxo de evento inválido")
        if self.prompt_version != PROMPT_VERSION:
            raise ValueError("versão de prompt inválida")
        if not isinstance(self.stage, EventStage) or not isinstance(self.code, EventCode):
            raise ValueError("estágio ou código de evento inválido")
        if not isinstance(self.outcome, EventOutcome):
            raise ValueError("resultado de evento inválido")
        if self.correlation_id is not None and not _HEX32.fullmatch(self.correlation_id):
            raise ValueError("correlação de evento inválida")
        if any(
            value < 0
            for value in (self.duration_ms, self.source_calls, self.model_calls, self.row_count)
        ):
            raise ValueError("quantidade de evento inválida")
        if self.contract_version != "v1" or self.catalog_version not in {None, "v1"}:
            raise ValueError("versão de evento inválida")
        if any(
            value is not None and not _HEX64.fullmatch(value)
            for value in (self.plan_id, self.evidence_ref)
        ):
            raise ValueError("identificador de evento inválido")


class EventSink(Protocol):
    def record(self, event: CoreEvent) -> None: ...


class NoopEventSink:
    durable = False

    def record(self, event: CoreEvent) -> None:
        return None


class AuditUnavailable(Exception):
    """A auditoria obrigatória impediu o fluxo antes da próxima ação."""


def safe_reference_id(source: str) -> str:
    """Fingerprint da referência, sem serializar o valor do adaptador."""

    return hashlib.sha256(source.encode("utf-8")).hexdigest()


class EventTrace:
    """Trilha por solicitação, sem estado global nem campos livres."""

    def __init__(
        self,
        sink: EventSink,
        flow: str,
        correlation_id: str | None,
        *,
        require_durable: bool = False,
    ) -> None:
        self._sink = sink
        self._flow = flow
        self._correlation_id = correlation_id
        self._require_durable = require_durable
        self._started = monotonic()
        self.source_calls = 0
        self.model_calls = 0
        self.plan_id: str | None = None
        self.catalog_version: str | None = None
        self.evidence_ref: str | None = None
        self.row_count = 0

    async def emit_async(self, stage: EventStage, code: EventCode, outcome: EventOutcome) -> None:
        """Aguarda a confirmação do sink síncrono sem bloquear o loop do consumidor.

        O próximo estágio só começa após record retornar. Cancelar a espera não
        interrompe uma operação já iniciada na thread; o adaptador deve limitar I/O.
        """
        await asyncio.to_thread(self.emit, stage, code, outcome)

    def emit(self, stage: EventStage, code: EventCode, outcome: EventOutcome) -> None:
        if self._require_durable and getattr(self._sink, "durable", False) is not True:
            raise AuditUnavailable("destino durável não configurado")
        event = CoreEvent(
            flow=self._flow,
            stage=stage,
            code=code,
            outcome=outcome,
            correlation_id=self._correlation_id,
            duration_ms=max(0, int((monotonic() - self._started) * 1000)),
            source_calls=self.source_calls,
            model_calls=self.model_calls,
            row_count=self.row_count,
            catalog_version=self.catalog_version,
            plan_id=self.plan_id,
            evidence_ref=self.evidence_ref,
        )
        try:
            self._sink.record(event)
        except Exception as exc:
            logger.warning("Falha ao registrar evento operacional do núcleo.")
            if self._require_durable:
                raise AuditUnavailable("destino durável indisponível") from exc
