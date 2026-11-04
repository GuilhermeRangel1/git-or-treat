"""Tradução de falhas de protocolo para envelopes HTTP públicos e estáveis."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.responses import (
    FailureCode,
    PublicError,
    PublicErrorCode,
    PublicErrorResponse,
    map_failure,
)


class ServiceAuthenticationError(Exception):
    """Credencial interna ausente, inválida ou não configurada."""

    def __init__(self, *, configured: bool) -> None:
        self.configured = configured


async def invalid_request_response(
    request: Request,
    _exception: RequestValidationError,
) -> JSONResponse:
    failure = map_failure(FailureCode.INVALID_REQUEST)
    body = PublicErrorResponse(
        correlation_id=request.state.correlation_id,
        error=failure.error,
        message=failure.message,
    )
    return JSONResponse(
        status_code=422,
        content=body.model_dump(mode="json"),
        headers={"X-Correlation-ID": request.state.correlation_id},
    )


async def unexpected_error_response(request: Request, _exception: Exception) -> JSONResponse:
    failure = map_failure(FailureCode.UNEXPECTED)
    body = PublicErrorResponse(
        correlation_id=request.state.correlation_id,
        error=failure.error,
        message=failure.message,
    )
    return JSONResponse(
        status_code=500,
        content=body.model_dump(mode="json"),
        headers={"X-Correlation-ID": request.state.correlation_id},
    )


async def service_auth_error_response(
    request: Request,
    exception: ServiceAuthenticationError,
) -> JSONResponse:
    if exception.configured:
        status_code = 401
        error = PublicError(code=PublicErrorCode.ACCESS_DENIED, retryable=False)
        message = "Chamador não autorizado."
    else:
        status_code = 503
        error = PublicError(code=PublicErrorCode.SERVICE_UNAVAILABLE, retryable=False)
        message = "A autenticação interna do serviço não está configurada."
    body = PublicErrorResponse(
        correlation_id=request.state.correlation_id,
        error=error,
        message=message,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={"X-Correlation-ID": request.state.correlation_id},
    )
