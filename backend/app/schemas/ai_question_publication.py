"""Publicação exibida pelo portal, informada opcionalmente junto da pergunta.

Fica fora dos envelopes internos: o valor só restringe a requisição (provoca recusa);
a referência executada continua sendo a capturada pelo Backend.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.ai import AIQuestionRequest


class AIExpectedPublication(BaseModel):
    """Mesmo par `lote`/`fingerprint` usado pelas leituras analíticas do portal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lote: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class AIQuestionPublicRequest(AIQuestionRequest):
    """Pergunta pública v1 com publicação esperada opcional e retrocompatível."""

    expected_publication: AIExpectedPublication | None = None

    def without_publication(self) -> AIQuestionRequest:
        """Envelope encaminhado ao núcleo, idêntico ao contrato anterior."""
        return AIQuestionRequest.model_validate(
            self.model_dump(exclude={"expected_publication"})
        )
