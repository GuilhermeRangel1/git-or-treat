"""Smoke test opt-in contra a API real do Groq, com pergunta e evidência sintéticas.

Só roda com GENAI_RUN_LIVE_SMOKE=1 e GENAI_GROQ_API_KEY no ambiente; fora disso é pulado,
então o pytest padrão e o CI não fazem chamadas de rede nem precisam de chave.
"""

import asyncio
import os

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.execution import ExecutionController, ExecutionLimits
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.config import Settings
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.groq import GroqModelAdapter
from app.providers.protocols import GeneratedAnswer
from app.schemas.evidence import EvidenceResult
from app.schemas.questions import QuestionRequest, QuestionStatus
from app.tools.synthetic_analytics import SyntheticScenarioTool

QUESTION = "Qual foi o consumo no período de demonstração?"

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("GENAI_RUN_LIVE_SMOKE") != "1"
        or not os.environ.get("GENAI_GROQ_API_KEY", "").strip(),
        reason="Smoke test real desligado: defina GENAI_RUN_LIVE_SMOKE=1 e GENAI_GROQ_API_KEY.",
    ),
]


class RecordingAdapter:
    """Guarda a evidência enviada e a saída do Groq sem registrar a chave."""

    def __init__(self, inner: GroqModelAdapter) -> None:
        self._inner = inner
        self.evidence: list[EvidenceResult] = []
        self.answers: list[GeneratedAnswer] = []
        self.errors: list[str] = []

    async def generate(self, question, context, evidence) -> GeneratedAnswer:
        self.evidence.append(evidence)
        try:
            answer = await self._inner.generate(question, context, evidence)
        except Exception as exc:
            # Só o tipo: a mensagem nunca deve chegar ao relatório do pytest.
            self.errors.append(type(exc).__name__)
            raise
        self.answers.append(answer)
        return answer


def test_groq_answers_synthetic_question_within_contract() -> None:
    # _env_file=None: lê só o ambiente, nunca o .env local.
    settings = Settings(_env_file=None)
    recorder = RecordingAdapter(
        GroqModelAdapter(
            model_name=settings.groq_model,
            api_key=settings.groq_api_key,
            timeout_ms=settings.model_timeout_ms,
        )
    )
    orchestrator = QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(
            QuestionInterpreter(GRID360_DEMO_PROFILE),
            SyntheticScenarioTool(),
            ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID),
        ),
        model_adapter=recorder,
        execution_controller=ExecutionController(
            ExecutionLimits(model_seconds=settings.model_timeout_ms / 1000)
        ),
    )

    response = asyncio.run(
        orchestrator.answer(
            QuestionRequest(question=QUESTION),
            demo_access_context(GRID360_DEMO_PROFILE, "0" * 32),
        )
    )

    assert recorder.errors == [], "O provedor Groq falhou na chamada real."
    assert len(recorder.evidence) == 1, "A evidência sintética não chegou ao modelo."
    assert len(recorder.answers) == 1
    answer = recorder.answers[0]
    GeneratedAnswer.model_validate(answer.model_dump())
    sent_ids = {
        record["observation_id"]
        for record in recorder.evidence[0].records
        if isinstance(record.get("observation_id"), str)
    }
    assert set(answer.observation_ids) <= sent_ids, "observation_ids fora da evidência enviada."
    assert response.status is not QuestionStatus.RECOVERABLE_ERROR
