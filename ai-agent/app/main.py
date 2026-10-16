"""Fábrica da aplicação FastAPI do serviço GenAI."""

from fastapi import FastAPI

from app.agent.orchestrator import QuestionOrchestrator
from app.api.routes import router
from app.config import Settings, get_settings
from app.providers.unavailable import UnavailableModelAdapter
from app.tools.evidence import NoEvidenceTool


def create_app(
    settings: Settings | None = None,
    question_orchestrator: QuestionOrchestrator | None = None,
) -> FastAPI:
    """Cria a API isolada; adaptadores reais podem ser injetados quando estiverem disponíveis."""

    active_settings = settings or get_settings()
    application = FastAPI(
        title=active_settings.service_name,
        version="0.1.0",
        description="API independente do agente GenAI do V-Energy Grid 360.",
    )
    application.state.question_orchestrator = question_orchestrator or QuestionOrchestrator(
        evidence_tool=NoEvidenceTool(),
        model_adapter=UnavailableModelAdapter(),
    )
    application.include_router(router)
    return application


app = create_app()
