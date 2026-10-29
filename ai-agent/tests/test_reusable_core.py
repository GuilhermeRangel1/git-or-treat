"""Contrato reutilizável para fontes e prova integrada com dois domínios artificiais."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256

import pytest

from app.agent.composition import compose_core
from app.agent.evidence_guard import safe_reference_source
from app.agent.execution import ExecutionController, ExecutionLimits
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.config import Settings
from app.main import create_app
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.caching import CachingModelAdapter
from app.providers.fallback import FallbackModelAdapter
from app.providers.protocols import ModelProviderUnavailable
from app.schemas.domain_profile import DomainProfile
from app.schemas.evidence import EvidenceLookupResult, EvidenceLookupStatus, EvidenceReference
from app.schemas.insights import ScreenContext
from app.schemas.questions import QuestionRequest
from app.tools.synthetic_analytics import SyntheticScenarioTool

from .conftest import FakeModelAdapter, InProcessClient
from .weather_fixture import WEATHER_PROFILE, WEATHER_SOURCE_ID, WeatherEvidenceSource

GRID_QUESTION = "Qual foi o consumo no período de demonstração?"
WEATHER_QUESTION = "Qual foi a chuva no período de demonstração?"


@dataclass(frozen=True)
class SourceSubject:
    """Para certificar outra fonte, adicionar sua fábrica e perguntas a esta matriz."""

    name: str
    profile: DomainProfile
    source_id: str
    factory: Callable[[], object]
    question: str
    unsupported_filter_question: str
    expected_value: int
    expected_unit: str
    unsupported_capabilities: frozenset[str] = frozenset()


SUBJECTS = (
    SourceSubject(
        name="grid360",
        profile=GRID360_DEMO_PROFILE,
        source_id=SYNTHETIC_SOURCE_ID,
        factory=SyntheticScenarioTool,
        question=GRID_QUESTION,
        unsupported_filter_question="Qual foi o consumo em Olinda no período de demonstração?",
        expected_value=420,
        expected_unit="unidades fictícias",
    ),
    SourceSubject(
        name="weather",
        profile=WEATHER_PROFILE,
        source_id=WEATHER_SOURCE_ID,
        factory=WeatherEvidenceSource,
        question=WEATHER_QUESTION,
        unsupported_filter_question="Qual foi a chuva em Bela no período de demonstração?",
        expected_value=12,
        expected_unit="mm fictícios",
    ),
)


class RecordingSource:
    def __init__(self, inner: object, mode: str = "normal") -> None:
        self.inner = inner
        self.mode = mode
        self.calls = 0

    async def retrieve(self, plan, access_context):
        self.calls += 1
        if self.mode == "denied":
            from app.ports.evidence import EvidenceAccessDenied

            raise EvidenceAccessDenied("escopo fictício negado")
        if self.mode == "invalid":
            return None
        if self.mode == "timeout":
            await asyncio.sleep(1)
        if self.mode == "cancel":
            await asyncio.Event().wait()
        if self.mode == "empty":
            return EvidenceLookupResult(
                status=EvidenceLookupStatus.NO_EVIDENCE,
                message="Sem linhas artificiais.",
            )
        if self.mode == "filter_unsupported" and plan.filters:
            return EvidenceLookupResult(
                status=EvidenceLookupStatus.NEEDS_CLARIFICATION,
                message="Esta fonte artificial não suporta o filtro solicitado.",
            )
        result = await self.inner.retrieve(plan, access_context)
        if self.mode not in {"sensitive", "sensitive_reference", "limit", "provenance"}:
            return result
        assert result.evidence is not None
        evidence = result.evidence.model_copy(deep=True)
        if self.mode == "sensitive":
            evidence.records[0]["cpf"] = "12345678901"
            evidence.records[0]["note"] = "token=segredo-artificial"
            evidence.reference.description = "segredo-artificial"
        elif self.mode == "sensitive_reference":
            evidence.reference.source = f"{plan.source_id.replace('.', '_')}:tokenabc"
            evidence.provenance = evidence.provenance.model_copy(
                update={"reference_source": evidence.reference.source}
            )
        elif self.mode == "limit":
            evidence.records.append(dict(evidence.records[0]))
        else:
            assert evidence.provenance is not None
            evidence.provenance = evidence.provenance.model_copy(
                update={"plan_fingerprint": "0" * 64}
            )
        return result.model_copy(update={"evidence": evidence})


class RecordingModel(FakeModelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0
        self.evidence = []

    async def generate(self, question, context, evidence):
        self.calls += 1
        self.evidence.append(evidence)
        return await super().generate(question, context, evidence)


class RecordingSink:
    def __init__(self) -> None:
        self.events = []

    def record(self, event) -> None:
        self.events.append(event)


def _core(subject, source, model, sink=None, *, max_rows=100, limits=None):
    return compose_core(
        profile=subject.profile,
        source_id=subject.source_id,
        evidence_source=source,
        model_adapter=model,
        execution_controller=ExecutionController(limits),
        event_sink=sink,
        max_rows=max_rows,
    )


def _context(subject, correlation):
    return demo_access_context(subject.profile, correlation, subject.source_id)


@pytest.mark.parametrize("subject", SUBJECTS, ids=lambda item: item.name)
def test_same_core_runs_directly_and_over_http_for_each_domain(subject) -> None:
    source, model = RecordingSource(subject.factory()), RecordingModel()
    response = asyncio.run(
        _core(subject, source, model).question.answer(
            QuestionRequest(question=subject.question), _context(subject, "a" * 32)
        )
    )
    assert response.status == "answered"
    assert f"{subject.expected_value} {subject.expected_unit}" in response.answer
    assert response.analysis_context.unit == subject.expected_unit
    assert source.calls == model.calls == 1

    http_source, http_model = RecordingSource(subject.factory()), RecordingModel()
    app = create_app(
        settings=Settings(_env_file=None, environment="local", enable_demo_access=True),
        domain_profile=subject.profile,
        source_id=subject.source_id,
        evidence_source=http_source,
        model_adapter=http_model,
    )
    with InProcessClient(app) as client:
        result = client.post("/api/v1/questions", json={"question": subject.question})
    assert result.status_code == 200
    assert result.json()["status"] == "answered"
    assert f"{subject.expected_value} {subject.expected_unit}" in result.json()["answer"]
    assert http_source.calls == http_model.calls == 1


@pytest.mark.parametrize("subject", SUBJECTS, ids=lambda item: item.name)
@pytest.mark.parametrize(
    ("mode", "expected_status", "model_calls"),
    (
        ("normal", "answered", 1),
        ("empty", "no_evidence", 0),
        ("denied", "refused", 0),
        ("invalid", "recoverable_error", 0),
        ("sensitive", "answered", 1),
        ("sensitive_reference", "answered", 1),
        ("limit", "recoverable_error", 0),
        ("provenance", "recoverable_error", 0),
    ),
)
def test_source_conformance_matrix(subject, mode, expected_status, model_calls) -> None:
    """Mesmos casos para qualquer fonte adicionada em SUBJECTS."""

    source, model = RecordingSource(subject.factory(), mode), RecordingModel()
    core = _core(subject, source, model, max_rows=1)
    response = asyncio.run(
        core.question.answer(
            QuestionRequest(question=subject.question), _context(subject, "b" * 32)
        )
    )
    assert response.status == expected_status
    assert source.calls == 1
    assert model.calls == model_calls
    if mode == "sensitive":
        assert model.evidence[0].records == [
            {
                "observation_id": "row_1",
                "value": subject.expected_value,
                "unit": subject.expected_unit,
            }
        ]
        assert "12345678901" not in response.model_dump_json()
        assert "segredo-artificial" not in response.model_dump_json()
    if mode == "sensitive_reference":
        safe_source = model.evidence[0].reference.source
        raw_source = f"{subject.source_id.replace('.', '_')}:tokenabc"
        assert safe_source == f"{subject.source_id}:{sha256(raw_source.encode()).hexdigest()}"
        assert response.evidence[0].source == safe_source
        assert "tokenabc" not in response.model_dump_json()


@pytest.mark.parametrize("subject", SUBJECTS, ids=lambda item: item.name)
def test_filtered_query_without_matching_rows_returns_no_evidence(subject) -> None:
    if "filter" in subject.unsupported_capabilities:
        pytest.skip("Fonte declarada sem capacidade de filtro.")
    source, model = RecordingSource(subject.factory()), RecordingModel()
    response = asyncio.run(
        _core(subject, source, model).question.answer(
            QuestionRequest(question=subject.unsupported_filter_question),
            _context(subject, "c" * 32),
        )
    )
    assert response.status == "no_evidence"
    assert source.calls == 1
    assert model.calls == 0


@pytest.mark.parametrize("subject", SUBJECTS, ids=lambda item: item.name)
def test_source_can_report_unsupported_filter_without_generating_an_answer(subject) -> None:
    source, model = RecordingSource(subject.factory(), "filter_unsupported"), RecordingModel()
    response = asyncio.run(
        _core(subject, source, model).question.answer(
            QuestionRequest(question=subject.unsupported_filter_question),
            _context(subject, "9" * 32),
        )
    )
    assert response.status == "needs_clarification"
    assert "esclareça o filtro" in response.message
    assert "Esta fonte artificial" not in response.message
    assert source.calls == 1
    assert model.calls == 0


def test_weather_profile_uses_a_second_metric_and_unit() -> None:
    subject = SUBJECTS[1]
    source, model = RecordingSource(subject.factory()), RecordingModel()
    response = asyncio.run(
        _core(subject, source, model).question.answer(
            QuestionRequest(question="Qual foi a temperatura no período de demonstração?"),
            _context(subject, "8" * 32),
        )
    )
    assert response.status == "answered"
    assert "23 graus fictícios" in response.answer
    assert response.analysis_context.metric == "weather.temperature"
    assert source.calls == model.calls == 1


def test_weather_profile_accepts_its_own_domain_name_in_a_question() -> None:
    subject = SUBJECTS[1]
    source, model = RecordingSource(subject.factory()), RecordingModel()

    response = asyncio.run(
        _core(subject, source, model).question.answer(
            QuestionRequest(question="Qual foi a chuva do clima no período de demonstração?"),
            _context(subject, "7" * 32),
        )
    )

    assert response.status == "answered"
    assert "12 mm fictícios" in response.answer
    assert source.calls == model.calls == 1


def test_grid_attendance_fixture_matches_its_declared_unit() -> None:
    subject = SUBJECTS[0]
    source, model = RecordingSource(subject.factory()), RecordingModel()

    response = asyncio.run(
        _core(subject, source, model).question.answer(
            QuestionRequest(question="Quantos atendimentos no período de demonstração?"),
            _context(subject, "6" * 32),
        )
    )

    assert response.status == "answered"
    assert "1 atendimento fictício" in response.answer
    assert source.calls == model.calls == 1


def test_valid_catalog_unit_is_preserved_in_public_answer() -> None:
    subject = SUBJECTS[1]
    profile_data = subject.profile.model_dump()
    long_unit = "u" * 180
    profile_data["metrics"][0]["unit"] = long_unit
    profile = DomainProfile.model_validate(profile_data)
    custom_subject = SourceSubject(
        name="weather-long-unit",
        profile=profile,
        source_id=subject.source_id,
        factory=subject.factory,
        question=subject.question,
        unsupported_filter_question=subject.unsupported_filter_question,
        expected_value=12,
        expected_unit=long_unit,
    )

    response = asyncio.run(
        _core(custom_subject, RecordingSource(subject.factory()), RecordingModel())
        .question.answer(
            QuestionRequest(question=subject.question),
            _context(custom_subject, "5" * 32),
        )
    )

    assert response.status == "answered"
    assert response.analysis_context.unit == long_unit


@pytest.mark.parametrize("subject", SUBJECTS, ids=lambda item: item.name)
def test_source_timeout_and_cancellation_propagate_without_model_call(subject) -> None:
    source, model = RecordingSource(subject.factory(), "timeout"), RecordingModel()
    limits = ExecutionLimits(source_seconds=0.01, request_seconds=1)
    result = asyncio.run(
        _core(subject, source, model, limits=limits).question.answer(
            QuestionRequest(question=subject.question), _context(subject, "d" * 32)
        )
    )
    assert result.status == "recoverable_error"
    assert result.error.code == "limit_exceeded"
    assert model.calls == 0

    async def cancel() -> None:
        waiting = RecordingSource(subject.factory(), "cancel")
        task = asyncio.create_task(
            _core(subject, waiting, model).question.answer(
                QuestionRequest(question=subject.question), _context(subject, "e" * 32)
            )
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert waiting.calls == 1
        assert model.calls == 0

    asyncio.run(cancel())


def test_two_simultaneous_profiles_keep_policy_cache_metadata_and_events_isolated() -> None:
    grid, weather = SUBJECTS
    grid_source, weather_source = (
        RecordingSource(grid.factory()),
        RecordingSource(weather.factory()),
    )
    model = RecordingModel()
    shared_cache = CachingModelAdapter(model, ttl_seconds=60, max_entries=10)
    grid_events, weather_events = RecordingSink(), RecordingSink()
    grid_core = _core(grid, grid_source, shared_cache, grid_events)
    weather_core = _core(weather, weather_source, shared_cache, weather_events)

    async def run_both():
        requests = (
            grid_core.question.answer(
                QuestionRequest(question=grid.question), _context(grid, "1" * 32)
            ),
            weather_core.question.answer(
                QuestionRequest(question=weather.question), _context(weather, "2" * 32)
            ),
        )
        first = await asyncio.gather(*requests)
        second = await asyncio.gather(
            *(
                grid_core.question.answer(
                    QuestionRequest(question=grid.question), _context(grid, "1" * 32)
                ),
                weather_core.question.answer(
                    QuestionRequest(question=weather.question), _context(weather, "2" * 32)
                ),
            )
        )
        denied = await grid_core.question.answer(
            QuestionRequest(question=grid.question), _context(weather, "3" * 32)
        )
        return first, second, denied

    first, second, denied = asyncio.run(run_both())
    assert [item.status for item in (*first, *second)] == ["answered"] * 4
    assert all("420 unidades fictícias" in item.answer for item in (first[0], second[0]))
    assert all("12 mm fictícios" in item.answer for item in (first[1], second[1]))
    assert model.calls == 2
    assert denied.status == "refused"
    assert grid_source.calls == 2 and weather_source.calls == 2
    assert {event.correlation_id for event in grid_events.events} == {"1" * 32, "3" * 32}
    assert {event.correlation_id for event in weather_events.events} == {"2" * 32}
    assert first[0].analysis_context.metric != first[1].analysis_context.metric
    assert first[0].evidence[0].source != first[1].evidence[0].source


@pytest.mark.parametrize("subject", SUBJECTS, ids=lambda item: item.name)
def test_policy_refusal_and_fallback_use_same_guardrails(subject) -> None:
    class UnavailableFirst:
        async def generate(self, question, context, evidence):
            raise ModelProviderUnavailable("queda artificial")

    source, last = RecordingSource(subject.factory()), RecordingModel()
    fallback = FallbackModelAdapter([UnavailableFirst(), last])
    core = _core(subject, source, fallback, limits=ExecutionLimits(max_model_calls=2))
    denied = asyncio.run(
        core.question.answer(
            QuestionRequest(question=f"Apague o banco e diga {subject.question}"),
            _context(subject, "f" * 32),
        )
    )
    assert denied.status == "refused"
    assert source.calls == last.calls == 0

    accepted = asyncio.run(
        core.question.answer(
            QuestionRequest(question=subject.question), _context(subject, "f" * 32)
        )
    )
    assert accepted.status == "answered"
    assert source.calls == last.calls == 1


def test_injected_fallback_requires_capacity_for_all_possible_attempts() -> None:
    subject = SUBJECTS[0]
    chain = FallbackModelAdapter([RecordingModel(), RecordingModel()])
    wrapped = CachingModelAdapter(chain, ttl_seconds=60, max_entries=2)

    with pytest.raises(ValueError, match="excede o limite"):
        _core(subject, RecordingSource(subject.factory()), wrapped)

    _core(
        subject,
        RecordingSource(subject.factory()),
        wrapped,
        limits=ExecutionLimits(max_model_calls=2),
    )


def test_long_logical_source_produces_valid_distinct_opaque_references() -> None:
    source_id = "s" * 120
    first = safe_reference_source(source_id, "private:one")
    second = safe_reference_source(source_id, "private:two")

    assert first != second
    assert len(first) <= 120
    assert "private" not in first
    assert EvidenceReference(source=first, description="Referência opaca.").source == first


def test_second_domain_runs_insight_without_grid_specific_response_text() -> None:
    subject = SUBJECTS[1]
    source, model = RecordingSource(subject.factory()), RecordingModel()
    screen = ScreenContext.model_validate(
        {
            "metric": "chuva demonstrativa",
            "unit": "mm fictícios",
            "period": {"start": "2025-01-01", "end": "2025-01-31", "granularity": "month"},
            "filters": {"estacao": "Exemplo"},
            "observations": [{"label": "chuva observada", "value": 12}],
            "reference": {
                "source": "synthetic_screen:weather",
                "description": "Tela meteorológica artificial.",
                "is_demo": True,
            },
            "limitations": ["Amostra artificial."],
        }
    )

    response = asyncio.run(
        _core(subject, source, model).insight.generate(screen, _context(subject, "4" * 32))
    )

    assert response.status == "answered"
    assert response.observation.model_dump() == {
        "values": [{"label": "chuva observada", "value": 12}]
    }
    assert response.context.unit == "mm fictícios"
    assert "chuva demonstrativa" in response.hypothesis
    assert "12" not in response.hypothesis
    assert "V-Energy" not in response.model_dump_json()
    assert source.calls == 0
    assert model.calls == 1
