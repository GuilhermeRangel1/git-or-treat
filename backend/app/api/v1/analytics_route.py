from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.datastructures import QueryParams
from sqlalchemy.exc import SQLAlchemyError

from app.services.analytics import AnalyticsAPIError

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
            except SQLAlchemyError:
                return JSONResponse(status_code=503, headers={"Cache-Control": "no-store"}, content={"error": {
                    "code": "source_unavailable", "message": "A fonte analítica está indisponível; confira a carga e as migrações.", "details": [],
                }})
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


def repeated_query_parameters(parameters: QueryParams) -> list[str]:
    """Return repeated scalar parameter names in a deterministic order."""
    return sorted(name for name in parameters if len(parameters.getlist(name)) > 1)


class StrictAnalyticsRoute(AnalyticsRoute):
    """Reject unsupported or repeated scalar filters before source resolution."""

    def get_route_handler(self):
        handler = super().get_route_handler()
        allowed: set[str] = set()

        def collect_query_parameters(dependant) -> None:
            allowed.update(parameter.alias for parameter in dependant.query_params)
            for dependency in dependant.dependencies:
                collect_query_parameters(dependency)

        collect_query_parameters(self.dependant)

        async def strict_handler(request: Request):
            repeated = repeated_query_parameters(request.query_params)
            unknown = set(request.query_params) - allowed
            if repeated or unknown:
                raise AnalyticsAPIError(
                    422,
                    "invalid_query",
                    "Parâmetro de consulta desconhecido ou repetido.",
                    [{
                        "field": "query",
                        "message": "Use somente os parâmetros documentados, uma vez cada.",
                    }],
                )
            return await handler(request)

        return strict_handler
