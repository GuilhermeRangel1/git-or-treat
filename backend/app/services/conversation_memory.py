"""Recuperação limitada de intenções; mensagens antigas nunca são evidência."""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.ai import AIQuestionResponse, AIQuestionText
from app.schemas.gold_publication import PublicationReference
from app.services.genai_documentation import document_response_is_current

MEMORY_VERSION = 1
MAX_MEMORY_BYTES = 4096  # limite de texto; sem chamada de sumarização


class MemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    position: Annotated[int, Field(strict=True, ge=1, le=200)] | Literal[-1, -2]
    follow_up: str = Field(default="", max_length=1000)


class ConversationMemory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = MEMORY_VERSION
    source_request_id: UUID
    source_sequence: int = Field(strict=True, ge=1)
    author: Literal["user"] = "user"
    kind: Literal["gold", "documentation"] = "gold"
    question: AIQuestionText
    batch: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_reference_for_kind(self):
        if self.kind == "documentation":
            if self.batch is not None:
                raise ValueError("Memória documental não é uma medição do lote.")
            return self
        if self.batch is None or PublicationReference.parse(self.batch).schema_version != "gold-csv-v2":
            raise ValueError("Memória exige publicação Gold v2 válida.")
        return self


class MemoryUnavailable(ValueError):
    """Não é seguro escolher outra consulta para substituir a referência pedida."""


def memory_request(question: str) -> MemoryRequest | None:
    """Só recupera por referência explícita; uma pergunta comum usa o contexto atual."""
    indexed = [(part, index) for index, char in enumerate(question)
               for part in unicodedata.normalize("NFD", char.lower())
               if unicodedata.category(part) != "Mn"]
    normalized = "".join(part for part, _ in indexed)
    match = re.fullmatch(
        r"\s*(?:por favor[, ]+)?(?:retom[ae]|retomar|volt[ae]|voltar|continue)\s+"
        r"(?:(?:a|para a|com a)\s+)?"
        r"(?:(?P<ordinal>primeira|segunda|terceira|ultima|penultima|anterior)\s+"
        r"(?:consulta|pergunta|analise)|(?:consulta|pergunta|analise)\s+"
        r"(?:(?:numero\s+)?(?P<number>[1-9][0-9]{0,2})|"
        r"(?P<after>primeira|segunda|terceira|ultima|penultima|anterior)))"
        r"(?:(?:\s*[,;:]\s*|\s+(?=(?:mas|agora|e|so|corrigindo)\b))"
        r"(?P<suffix>.+?))?\s*[.!?]?\s*",
        normalized,
    )
    if match is None:
        return None
    positions = {"primeira": 1, "segunda": 2, "terceira": 3, "ultima": -1,
                 "penultima": -2, "anterior": -2}
    ordinal = match["ordinal"] or match["after"]
    position = positions[ordinal] if ordinal else int(match["number"])
    if position > 200:
        raise MemoryUnavailable
    # Usar o texto original do complemento preserva nomes, pontuação e negações.
    suffix = (question[indexed[match.start("suffix")][1]:indexed[match.end("suffix") - 1][1] + 1]
              if match["suffix"] else "")
    return MemoryRequest(position=position, follow_up=suffix)


def select_memory(
    rows: Sequence[Mapping[str, Any]], reference: MemoryRequest, scope: str,
) -> ConversationMemory:
    """Linhas vêm do histórico autorizado, em ordem decrescente de autoria."""
    eligible = []
    for row in reversed(rows):
        try:
            response = AIQuestionResponse.model_validate(row["response"])
        except (ValueError, TypeError):
            raise MemoryUnavailable from None
        if response.status in {"answered", "no_evidence"}:
            eligible.append(row)
    index = reference.position - 1 if reference.position > 0 else reference.position
    try:
        source = eligible[index]
        if source["scope_digest"] != scope or source["format_version"] != 1:
            raise MemoryUnavailable
        response = AIQuestionResponse.model_validate(source["response"])
        if any(item.source == "documentation.indicators" for item in response.evidence):
            if not document_response_is_current(response) or reference.follow_up:
                raise MemoryUnavailable
            question = source["anchor"] if source["anchor"] is not None else source["question"]
            if not isinstance(question, str) or memory_request(question) is not None:
                raise MemoryUnavailable
            return ConversationMemory(
                source_request_id=source["request_id"], source_sequence=source["sequence"],
                question=question, kind="documentation",
            )
        if (not isinstance(source["anchor"], str)
                or len(source["anchor"].encode("utf-8")) > MAX_MEMORY_BYTES):
            raise MemoryUnavailable
        return ConversationMemory(
            source_request_id=source["request_id"], source_sequence=source["sequence"],
            question=source["anchor"], batch=source["batch"],
        )
    except (IndexError, ValueError, TypeError):
        raise MemoryUnavailable from None
