"""Recuperação textual não concede acesso à Gold nem produz valores de negócio."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.schemas.access import AccessContext


class DocumentSelectionUnavailable(Exception):
    """Falha sanitizada na seleção de uma referência documental."""


@dataclass(frozen=True)
class DocumentSelection:
    id: str | None
    sufficient: bool


@dataclass(frozen=True)
class DocumentChunk:
    id: str

    title: str

    section: str

    version: str

    owner: str

    text: str

    metric_ids: frozenset[str]

    keywords: tuple[str, ...]


class DocumentationSource(Protocol):
    def authorized_chunks(
        self,
        access: AccessContext,
        today: date,
    ) -> tuple[DocumentChunk, ...]: ...


class DocumentSelector(Protocol):
    async def select(
        self,
        question: str,
        chunks: tuple[DocumentChunk, ...],
    ) -> DocumentSelection: ...
