"""Fábrica da aplicação FastAPI do serviço GenAI."""

from fastapi import FastAPI

from app.agent.insights import ScreenInsightOrchestrator
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.api.routes import router
from app.config import Settings, get_settings
from app.providers.factory import build_model_adapter
from app.scenarios import SYNTHETIC_SCENARIOS
from app.tools.synthetic_analytics import SyntheticScenarioTool


def create_app(
    settings: Settings | None = None,
    question_orchestrator: QuestionOrchestrator | None = None,
    insight_orchestrator: ScreenInsightOrchestrator | None = None,
) -> FastAPI:
    """Cria a API isolada; adaptadores reais podem ser injetados quando estiverem disponíveis."""

    active_settings = settings or get_settings()
    application = FastAPI(
        title=active_settings.service_name,
        version="0.1.0",
        description="API independente do agente GenAI do V-Energy Grid 360.",
    )
    model_adapter = (
        build_model_adapter(active_settings)
        if question_orchestrator is None or insight_orchestrator is None
        else None
    )
    application.state.question_orchestrator = question_orchestrator or QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(
            interpreter=QuestionInterpreter(),
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
