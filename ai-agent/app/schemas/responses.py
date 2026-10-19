"""Metadados públicos e tradução de falhas internas para respostas seguras."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PUBLIC_RESPONSE_VERSION = "v1"
CorrelationId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-f0-9]{32}$", min_length=32, max_length=32),
]


class PublicErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    OUT_OF_SCOPE = "out_of_scope"
    POLICY_REFUSAL = "policy_refusal"
    SECURITY_VIOLATION = "security_violation"
    ACCESS_DENIED = "access_denied"
    SERVICE_UNAVAILABLE = "service_unavailable"
    LIMIT_EXCEEDED = "limit_exceeded"
    INVALID_UPSTREAM_RESPONSE = "invalid_upstream_response"
    UNGROUNDED_RESPONSE = "ungrounded_response"
    INVALID_CONTEXT = "invalid_context"
    INTERNAL_ERROR = "internal_error"


class FailureCode(StrEnum):
    """Categorias internas; detalhes de execução não fazem parte da API pública."""

    INVALID_REQUEST = "invalid_request"
    OUT_OF_SCOPE = "out_of_scope"
    POLICY_REFUSAL = "policy_refusal"
    INSIGHT_REFUSAL = "insight_refusal"
    SECURITY_VIOLATION = "security_violation"
    INTERPRETATION_FAILURE = "interpretation_failure"
    ACCESS_DENIED = "access_denied"
    SOURCE_UNAVAILABLE = "source_unavailable"
    INVALID_SOURCE_RESPONSE = "invalid_source_response"
    EXECUTION_LIMIT = "execution_limit"
    MODEL_UNAVAILABLE = "model_unavailable"
    MODEL_REJECTED = "model_rejected"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    UNGROUNDED_OUTPUT = "ungrounded_output"
    UNGROUNDED_INSIGHT = "ungrounded_insight"
    SESSION_INVALID = "session_invalid"
    UNEXPECTED = "unexpected"


class PublicError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: PublicErrorCode = Field(description="Código público estável, sem detalhe interno.")
    retryable: bool = Field(
        description=(
            "Indica se repetir a mesma solicitação pode ser útil; "
            "não dispara retry automático."
        )
    )


class PublicResponseMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["v1"] = Field(
        default=PUBLIC_RESPONSE_VERSION,
        description="Versão do envelope público da resposta.",
    )
    correlation_id: CorrelationId | None = Field(
        default=None,
        description="Identificador gerado pelo serviço e também enviado em X-Correlation-ID.",
    )
    # This remains null until a durable audit event exists; correlation alone is not an audit log.
    audit_reference: str | None = Field(
        default=None,
        description="Referência de auditoria persistida; nula enquanto não houver trilha durável.",
    )
    error: PublicError | None = None


class PublicErrorResponse(PublicResponseMetadata):
    """Envelope para erro de protocolo HTTP, como uma entrada inválida."""

    status: Literal["error"] = "error"
    message: str = Field(min_length=1, max_length=300)
    error: PublicError
    correlation_id: CorrelationId


@dataclass(frozen=True)
class MappedFailure:
    error: PublicError
    message: str


_FAILURE_MAP: dict[FailureCode, MappedFailure] = {
    FailureCode.INVALID_REQUEST: MappedFailure(
        error=PublicError(code=PublicErrorCode.INVALID_REQUEST, retryable=False),
        message="A solicitação não segue o contrato esperado.",
    ),
    FailureCode.OUT_OF_SCOPE: MappedFailure(
        error=PublicError(code=PublicErrorCode.OUT_OF_SCOPE, retryable=False),
        message="Esse tema está fora do escopo deste agente.",
    ),
    FailureCode.POLICY_REFUSAL: MappedFailure(
        error=PublicError(code=PublicErrorCode.POLICY_REFUSAL, retryable=False),
        message="Não posso atender a essa solicitação.",
    ),
    FailureCode.INSIGHT_REFUSAL: MappedFailure(
        error=PublicError(code=PublicErrorCode.POLICY_REFUSAL, retryable=False),
        message="Não posso atribuir uma causa com a evidência disponível.",
    ),
    FailureCode.SECURITY_VIOLATION: MappedFailure(
        error=PublicError(code=PublicErrorCode.SECURITY_VIOLATION, retryable=False),
        message="Não posso executar alterações nem expor dados pessoais ou instruções internas.",
    ),
    FailureCode.INTERPRETATION_FAILURE: MappedFailure(
        error=PublicError(code=PublicErrorCode.INTERNAL_ERROR, retryable=False),
        message="Não foi possível interpretar a solicitação.",
    ),
    FailureCode.ACCESS_DENIED: MappedFailure(
        error=PublicError(code=PublicErrorCode.ACCESS_DENIED, retryable=False),
        message="Essa consulta não está autorizada para o escopo disponível.",
    ),
    FailureCode.SOURCE_UNAVAILABLE: MappedFailure(
        error=PublicError(code=PublicErrorCode.SERVICE_UNAVAILABLE, retryable=True),
        message="A consulta está temporariamente indisponível. Tente novamente.",
    ),
    FailureCode.INVALID_SOURCE_RESPONSE: MappedFailure(
        error=PublicError(code=PublicErrorCode.INVALID_UPSTREAM_RESPONSE, retryable=False),
        message="A fonte de dados não retornou um resultado válido.",
    ),
    FailureCode.EXECUTION_LIMIT: MappedFailure(
        error=PublicError(code=PublicErrorCode.LIMIT_EXCEEDED, retryable=False),
        message="A solicitação excede os limites permitidos.",
    ),
    FailureCode.MODEL_UNAVAILABLE: MappedFailure(
        error=PublicError(code=PublicErrorCode.SERVICE_UNAVAILABLE, retryable=True),
        message="O serviço de resposta está temporariamente indisponível. Tente novamente.",
    ),
    FailureCode.MODEL_REJECTED: MappedFailure(
        error=PublicError(code=PublicErrorCode.SERVICE_UNAVAILABLE, retryable=False),
        message="O serviço de resposta não aceitou a solicitação.",
    ),
    FailureCode.INVALID_MODEL_OUTPUT: MappedFailure(
        error=PublicError(code=PublicErrorCode.INVALID_UPSTREAM_RESPONSE, retryable=False),
        message="O serviço de resposta não retornou um resultado válido.",
    ),
    FailureCode.UNGROUNDED_OUTPUT: MappedFailure(
        error=PublicError(code=PublicErrorCode.UNGROUNDED_RESPONSE, retryable=False),
        message="Não consigo confirmar essa resposta com a evidência disponível.",
    ),
    FailureCode.UNGROUNDED_INSIGHT: MappedFailure(
        error=PublicError(code=PublicErrorCode.UNGROUNDED_RESPONSE, retryable=False),
        message=(
            "Não consigo apresentar esse insight porque ele contém números ausentes "
            "do contexto recebido."
        ),
    ),
    FailureCode.SESSION_INVALID: MappedFailure(
        error=PublicError(code=PublicErrorCode.INVALID_CONTEXT, retryable=False),
        message="O contexto enviado não pôde ser validado.",
    ),
    FailureCode.UNEXPECTED: MappedFailure(
        error=PublicError(code=PublicErrorCode.INTERNAL_ERROR, retryable=False),
        message="Não foi possível concluir a solicitação.",
    ),
}


def map_failure(code: FailureCode) -> MappedFailure:
    """Traduz uma categoria interna em código, mensagem segura e retry explícito."""

    return _FAILURE_MAP[code]
