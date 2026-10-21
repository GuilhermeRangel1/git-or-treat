from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.schemas.analytics import AnalyticsErrorResponse


class AnalyticsRoute(APIRoute):
    """Keep the analytics error contract local to analytic HTTP routes."""

    def __init__(self, *args, **kwargs):
        kwargs["responses"] = {
            422: {"model": AnalyticsErrorResponse, "description": "Entrada analítica inválida"},
            503: {"model": AnalyticsErrorResponse, "description": "Fonte analítica indisponível"},
            **(kwargs.get("responses") or {}),
        }
        super().__init__(*args, **kwargs)

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def analytics_handler(request: Request):
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                details = [
                    {"field": ".".join(str(part) for part in error.get("loc", ()) if part != "query"), "message": "Valor inválido ou ausente."}
                    for error in exc.errors()
                ]
                return JSONResponse(
                    status_code=422,
                    content={"error": {"code": "invalid_query", "message": "Parâmetros da requisição inválidos.", "details": details}},
                )

        return analytics_handler
