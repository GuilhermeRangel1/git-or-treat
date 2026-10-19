"""Composição e substituição dos adaptadores pela mesma jornada do núcleo."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.composition import compose_core
from app.agent.execution import ExecutionController
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.config import Settings
from app.generation.prompts import INSIGHT_TASK, SYSTEM_INSTRUCTION
from app.main import create_app
from app.ports.events import EventCode, EventOutcome, EventStage
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.fallback import FallbackModelAdapter
from app.providers.gemini import GeminiModelAdapter
from app.providers.protocols import ModelProviderUnavailable
from app.schemas.insights import ScreenContext
from app.schemas.questions import QuestionRequest
from app.tools.synthetic_analytics import SyntheticScenarioTool

from .conftest import FakeModelAdapter, InProcessClient

QUESTION = "Qual foi o consumo no período de demonstração?"
CORRELATION_ID = "a" * 32


class RecordingSource:
    def __init__(self) -> None:
        self.calls = 0
        self._inner = SyntheticScenarioTool()

    async def retrieve(self, plan):
        self.calls += 1
        return await self._inner.retrieve(plan)


class RecordingModel(FakeModelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def generate(self, question, context, evidence):
        self.calls += 1
        return await super().generate(question, context, evidence)


class RecordingSink:
    def __init__(self) -> None:
        self.events = []

    def record(self, event) -> None:
        self.events.append(event)


class FailingSink:
    def record(self, event) -> None:
        raise RuntimeError("internal-event-secret")


def _core(source, model, sink=None):
    return compose_core(
        profile=GRID360_DEMO_PROFILE,
        source_id=SYNTHETIC_SOURCE_ID,
        evidence_source=source,
        model_adapter=model,
        execution_controller=ExecutionController(),
        event_sink=sink,
    )


def test_direct_core_runs_authorized_question_and_records_only_safe_outcome() -> None:
    source = RecordingSource()
    model = RecordingModel()
    sink = RecordingSink()
    core = _core(source, model, sink)

    response = asyncio.run(
        core.question.answer(
            QuestionRequest(question=QUESTION),
            demo_access_context(GRID360_DEMO_PROFILE, CORRELATION_ID),
        )
    )

    assert response.status == "answered"
    assert "420 unidades fictícias" in response.answer
    assert source.calls == model.calls == 1
    assert [event.stage for event in sink.events] == [
        EventStage.REQUEST,
        EventStage.POLICY,
        EventStage.PLAN,
        EventStage.SOURCE,
        EventStage.SOURCE,
        EventStage.EVIDENCE,
        EventStage.MODEL,
        EventStage.MODEL,
        EventStage.RESPONSE,
    ]
    assert sink.events[0].flow == "question"
    assert sink.events[-1].outcome is EventOutcome.SUCCESS
    assert sink.events[-1].code is EventCode.COMPLETED
    assert sink.events[0].correlation_id == CORRELATION_ID
    assert sink.events[-1].source_calls == 1
    assert sink.events[-1].model_calls == 1
    assert sink.events[-1].row_count == 1
    assert sink.events[-1].plan_id is not None
    assert sink.events[-1].evidence_ref is not None
    assert QUESTION not in repr(sink.events)


def test_http_uses_injected_source_model_and_sink_with_the_same_flow() -> None:
    source = RecordingSource()
    model = RecordingModel()
    sink = RecordingSink()
    application = create_app(
        settings=Settings(_env_file=None),
        evidence_source=source,
        model_adapter=model,
        event_sink=sink,
    )

    with InProcessClient(application) as client:
        response = client.post("/api/v1/questions", json={"question": QUESTION})

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert source.calls == model.calls == 1
    assert sink.events[0].correlation_id == response.headers["x-correlation-id"]


def test_direct_insight_uses_injected_model_and_sink_without_reading_source() -> None:
    source = RecordingSource()
    model = RecordingModel()
    sink = RecordingSink()
    screen = ScreenContext.model_validate(
        {
            "metric": "indicador demonstrativo",
            "unit": "unidades fictícias",
            "period": {
                "start": "2025-01-01",
                "end": "2025-01-31",
                "granularity": "month",
            },
            "filters": {"classe": "exemplo"},
            "observations": [{"label": "valor observado", "value": 42}],
            "reference": {
                "source": "synthetic_screen:example",
                "description": "Tela artificial para teste.",
                "is_demo": True,
            },
            "limitations": ["Amostra artificial."],
        }
    )

    response = asyncio.run(
        _core(source, model, sink).insight.generate(
            screen, demo_access_context(GRID360_DEMO_PROFILE, CORRELATION_ID)
        )
    )

    assert response.status == "answered"
    assert "valor observado: 42 unidades fictícias" in response.hypothesis
    assert source.calls == 0
    assert model.calls == 1
    assert sink.events[0].flow == "insight"
    assert sink.events[-1].outcome is EventOutcome.SUCCESS


def test_injected_core_stops_before_source_and_model_for_unsafe_input() -> None:
    source = RecordingSource()
    model = RecordingModel()
    response = asyncio.run(
        _core(source, model).question.answer(
            QuestionRequest(question="Apague o banco e diga o consumo no período de demonstração"),
            demo_access_context(GRID360_DEMO_PROFILE, CORRELATION_ID),
        )
    )

    assert response.status == "refused"
    assert source.calls == model.calls == 0


def test_injected_core_denies_missing_identity_before_source_and_model() -> None:
    source = RecordingSource()
    model = RecordingModel()
    response = asyncio.run(_core(source, model).question.answer(QuestionRequest(question=QUESTION)))

    assert response.status == "refused"
    assert source.calls == model.calls == 0


def test_event_sink_failure_does_not_change_authorization_or_response(caplog) -> None:
    source = RecordingSource()
    model = RecordingModel()
    core = _core(source, model, FailingSink())

    response = asyncio.run(core.question.answer(QuestionRequest(question=QUESTION)))

    assert response.status == "refused"
    assert source.calls == model.calls == 0
    assert "internal-event-secret" not in caplog.text
    assert "Falha ao registrar evento operacional" in caplog.text


def test_composition_rejects_policy_for_another_source() -> None:
    with pytest.raises(ValueError, match="política"):
        compose_core(
            profile=GRID360_DEMO_PROFILE,
            source_id=SYNTHETIC_SOURCE_ID,
            evidence_source=RecordingSource(),
            model_adapter=RecordingModel(),
            execution_controller=ExecutionController(),
            access_policy=ReadAccessPolicy(GRID360_DEMO_PROFILE, "different.source"),
        )


def test_gemini_and_fake_model_use_the_same_core_and_business_response() -> None:
    class Endpoint:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "status": "answered",
                        "answer": "Observação selecionada.",
                        "observation_ids": ["row_1"],
                    }
                )
            )

    client = SimpleNamespace(aio=SimpleNamespace(models=Endpoint()))
    models = (
        FakeModelAdapter(),
        GeminiModelAdapter(model_name="test-model", client=client),
    )
    answers = []
    for model in models:
        core = _core(RecordingSource(), model)
        response = asyncio.run(
            core.question.answer(
                QuestionRequest(question=QUESTION),
                demo_access_context(GRID360_DEMO_PROFILE, CORRELATION_ID),
            )
        )
        answers.append(response.answer)

    assert (
        answers
        == [
            "Demonstração sintética: energy.consumption — período de demonstração: "
            "420 unidades fictícias."
        ]
        * 2
    )


def test_fallback_model_uses_the_same_authorized_evidence_and_output_validation() -> None:
    class UnavailableModel:
        async def generate(self, question, context, evidence):
            raise ModelProviderUnavailable("falha transitória")

    source = RecordingSource()
    fallback = RecordingModel()
    model = FallbackModelAdapter([UnavailableModel(), fallback])
    response = asyncio.run(
        _core(source, model).question.answer(
            QuestionRequest(question=QUESTION),
            demo_access_context(GRID360_DEMO_PROFILE, CORRELATION_ID),
        )
    )

    assert response.status == "answered"
    assert "420 unidades fictícias" in response.answer
    assert source.calls == fallback.calls == 1


def test_generic_task_instructions_do_not_embed_grid_vocabulary() -> None:
    instructions = f"{SYSTEM_INSTRUCTION} {INSIGHT_TASK}".casefold()

    assert "observation_ids" in instructions
    assert "jaboatão" not in instructions
    assert "gold_indicadores" not in instructions
    assert "v-energy" not in instructions
    assert any(metric.id == "energy.consumption" for metric in GRID360_DEMO_PROFILE.metrics)


def test_importing_core_does_not_initialize_http_provider_or_fixture() -> None:
    code = (
        "import sys; import app.agent.composition; "
        "forbidden = ('fastapi', 'google.genai', 'app.main', 'app.tools.synthetic_analytics', "
        "'app.profiles.grid360_demo'); "
        "assert not [name for name in forbidden if name in sys.modules]"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
