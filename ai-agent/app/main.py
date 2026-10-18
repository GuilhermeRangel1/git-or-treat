"""Fábrica da aplicação FastAPI do serviço GenAI."""

from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.agent.insights import ScreenInsightOrchestrator
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.api.errors import invalid_request_response, unexpected_error_response
from app.api.routes import router
from app.config import Settings, get_settings
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.factory import build_model_adapter
from app.scenarios import SYNTHETIC_SCENARIOS
from app.schemas.domain_profile import DomainProfile
from app.tools.synthetic_analytics import SyntheticScenarioTool


def create_app(
    settings: Settings | None = None,
    question_orchestrator: QuestionOrchestrator | None = None,
    insight_orchestrator: ScreenInsightOrchestrator | None = None,
    domain_profile: DomainProfile | None = None,
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

    model_adapter = (
        build_model_adapter(active_settings)
        if question_orchestrator is None or insight_orchestrator is None
        else None
    )
    application.state.question_orchestrator = question_orchestrator or QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(
            interpreter=QuestionInterpreter(profile=active_domain_profile),
            evidence_source=SyntheticScenarioTool(SYNTHETIC_SCENARIOS),
        ),
        model_adapter=model_adapter,
    )
    application.state.insight_orchestrator = insight_orchestrator or ScreenInsightOrchestrator(
        model_adapter
    )
    application.include_router(router)
    return application


app = create_app()
