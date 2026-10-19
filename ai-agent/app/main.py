"""Fábrica da aplicação FastAPI do serviço GenAI."""

from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.agent.access import ReadAccessPolicy
from app.agent.composition import compose_core
from app.agent.execution import ExecutionController, ExecutionLimits
from app.agent.insights import ScreenInsightOrchestrator
from app.agent.orchestrator import QuestionOrchestrator
from app.api.access import SYNTHETIC_SOURCE_ID
from app.api.errors import invalid_request_response, unexpected_error_response
from app.api.routes import router
from app.config import Settings, get_settings
from app.ports.events import EventSink
from app.ports.evidence import EvidenceSource
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.factory import build_model_adapter
from app.providers.protocols import ModelAdapter
from app.scenarios import SYNTHETIC_SCENARIOS
from app.schemas.domain_profile import DomainProfile
from app.tools.synthetic_analytics import SyntheticScenarioTool


def create_app(
    settings: Settings | None = None,
    question_orchestrator: QuestionOrchestrator | None = None,
    insight_orchestrator: ScreenInsightOrchestrator | None = None,
    domain_profile: DomainProfile | None = None,
    evidence_source: EvidenceSource | None = None,
    model_adapter: ModelAdapter | None = None,
    access_policy: ReadAccessPolicy | None = None,
    event_sink: EventSink | None = None,
    source_id: str = SYNTHETIC_SOURCE_ID,
) -> FastAPI:
    """Cria a API isolada; adaptadores reais podem ser injetados quando estiverem disponíveis."""

    active_settings = settings or get_settings()
    active_domain_profile = domain_profile or GRID360_DEMO_PROFILE
    application = FastAPI(
        title=active_settings.service_name,
        version="0.1.0",
        description="API independente do agente GenAI do V-Energy Grid 360.",
    )

    @application.middleware("http")
    async def add_correlation_id(request, call_next):
        correlation_id = uuid4().hex
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    application.add_exception_handler(RequestValidationError, invalid_request_response)
    application.add_exception_handler(Exception, unexpected_error_response)
    application.state.environment = active_settings.environment
    application.state.domain_profile = active_domain_profile
    application.state.source_id = source_id

    execution_controller = ExecutionController(
        ExecutionLimits(
            request_seconds=active_settings.request_timeout_ms / 1000,
            source_seconds=active_settings.source_timeout_ms / 1000,
            model_seconds=active_settings.model_timeout_ms / 1000,
            max_source_calls=active_settings.source_max_calls,
            max_model_calls=active_settings.model_max_calls,
            concurrent_requests=active_settings.concurrent_requests,
            concurrent_sources=active_settings.concurrent_sources,
            concurrent_models=active_settings.concurrent_models,
        )
    )

    core = None
    if question_orchestrator is None or insight_orchestrator is None:
        core = compose_core(
            profile=active_domain_profile,
            source_id=source_id,
            evidence_source=(
                evidence_source
                if evidence_source is not None
                else SyntheticScenarioTool(SYNTHETIC_SCENARIOS)
            ),
            model_adapter=(
                model_adapter if model_adapter is not None else build_model_adapter(active_settings)
            ),
            execution_controller=execution_controller,
            access_policy=access_policy,
            event_sink=event_sink,
            max_rows=active_settings.evidence_max_rows,
            max_evidence_bytes=active_settings.evidence_max_bytes,
        )
    application.state.question_orchestrator = (
        question_orchestrator or core.question
    )
    application.state.insight_orchestrator = (
        insight_orchestrator or core.insight
    )
    application.include_router(router)
    return application


app = create_app()
