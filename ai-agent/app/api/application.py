"""Configuração da borda HTTP do serviço GenAI."""

from __future__ import annotations

import re
from typing import Literal, Protocol
from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.access import AccessContextResolver
from app.api.errors import (
    ServiceAuthenticationError,
    invalid_request_response,
    service_auth_error_response,
    unexpected_error_response,
)
from app.api.routes import router
from app.config import Settings
from app.schemas.access import AccessContext
from app.schemas.domain_profile import DomainProfile
from app.schemas.insights import ScreenContext, ScreenInsightResponse
from app.schemas.questions import QuestionRequest, QuestionResponse


SourceMode = Literal["demo", "external"]


class QuestionHandler(Protocol):
    """Caso de uso consumido pela rota de perguntas."""

    async def answer(
        self,
        payload: QuestionRequest,
        access_context: AccessContext | None,
        correlation_id: str,
    ) -> QuestionResponse: ...


class InsightHandler(Protocol):
    """Caso de uso consumido pela rota de insights."""

    async def generate(
        self,
        screen: ScreenContext,
        access_context: AccessContext | None,
        correlation_id: str,
    ) -> ScreenInsightResponse: ...


def create_api_application(
    *,
    settings: Settings,
    question_handler: QuestionHandler,
    insight_handler: InsightHandler,
    domain_profile: DomainProfile,
    source_id: str,
    source_mode: SourceMode,
    access_context_resolver: AccessContextResolver | None,
) -> FastAPI:
    """Configura a aplicação HTTP sem conhecer a composição concreta do serviço."""

    application = FastAPI(
        title=settings.service_name,
        version="0.1.0",
        description="API independente do agente GenAI do V-Energy Grid 360.",
    )

    @application.middleware("http")
    async def add_correlation_id(request, call_next):
        incoming_id = request.headers.get("x-correlation-id", "")
        correlation_id = (
            incoming_id if re.fullmatch(r"[a-f0-9]{32}", incoming_id) else uuid4().hex
        )
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    application.add_exception_handler(RequestValidationError, invalid_request_response)
    application.add_exception_handler(ServiceAuthenticationError, service_auth_error_response)
    application.add_exception_handler(Exception, unexpected_error_response)
    application.state.environment = settings.environment
    application.state.enable_demo_access = settings.enable_demo_access
    application.state.service_api_token = settings.service_api_token
    application.state.domain_profile = domain_profile
    application.state.source_id = source_id
    application.state.source_mode = source_mode
    application.state.access_context_resolver = access_context_resolver
    application.state.question_orchestrator = question_handler
    application.state.insight_orchestrator = insight_handler
    application.include_router(router)
    return application
