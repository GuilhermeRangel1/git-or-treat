"""Porta mínima de eventos do núcleo, sem transporte ou persistência embutidos."""

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoreEvent:
    flow: Literal["question", "insight"]
    outcome: str
    correlation_id: str | None


class EventSink(Protocol):
    def record(self, event: CoreEvent) -> None: ...


class NoopEventSink:
    def record(self, event: CoreEvent) -> None:
        return None


def record_safely(sink: EventSink, event: CoreEvent) -> None:
    """Falha de telemetria opcional não modifica a decisão do caso de uso."""

    try:
        sink.record(event)
    except Exception:
        logger.warning("Falha ao registrar evento operacional do núcleo.")
