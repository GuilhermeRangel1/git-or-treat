"""Tradução de falhas de protocolo para envelopes HTTP públicos e estáveis."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.responses import (
    FailureCode,
    PublicErrorResponse,
    map_failure,
)


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
