"""Porta assíncrona para fontes autorizadas de evidências analíticas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.schemas.evidence import EvidenceLookupResult

if TYPE_CHECKING:
    from app.schemas.analysis import AnalysisIntent


class EvidenceToolUnavailable(Exception):
    """Fonte indisponível ou resposta que viola o contrato de evidências."""


class EvidenceAccessDenied(Exception):
    """A política da fonte não autoriza a consulta solicitada."""


class EvidenceSource(Protocol):
    """Fonte async: use I/O assíncrono ou delegue operações bloqueantes."""

    async def retrieve(self, intent: AnalysisIntent) -> EvidenceLookupResult: ...
