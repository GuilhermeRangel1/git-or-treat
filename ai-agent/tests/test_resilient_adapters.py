import asyncio
import logging

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.interpreter import QuestionInterpreter
from app.agent.orchestrator import QuestionOrchestrator
from app.agent.planner import QuestionAnalysisPlanner
from app.api.access import SYNTHETIC_SOURCE_ID, demo_access_context
from app.config import Settings
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.providers.caching import CachingModelAdapter
from app.providers.factory import build_model_adapter
from app.providers.fallback import FallbackModelAdapter
from app.providers.gemini import GeminiModelAdapter
from app.providers.protocols import GeneratedAnswer, ModelProviderUnavailable
from app.schemas.evidence import EvidenceResult
from app.schemas.questions import (
    ConversationTurn,
    EvidenceReference,
    QuestionRequest,
    QuestionStatus,
)
from app.tools.synthetic_analytics import SyntheticScenarioTool

QUESTION = "Qual foi o consumo no período de demonstração?"


def _evidence(value: int = 42, source: str = "synthetic_fixture:consumption_demo"):
    return EvidenceResult(
        reference=EvidenceReference(
            source=source,
            description="Resultado artificial para teste, sem dados da V-Energy.",
            is_demo=True,
        ),
        records=[{"metric": "consumption_demo", "value": value, "unit": "unidades fictícias"}],
    )


def _answer(text: str = "O consumo foi 42 unidades fictícias.") -> GeneratedAnswer:
    return GeneratedAnswer(status="answered", answer=text)


class ScriptedAdapter:
    """Devolve cada item do roteiro em ordem; exceções são levantadas."""

    def __init__(self, *script, delay: float = 0.0) -> None:
        self.script = list(script)
        self.delay = delay
        self.calls = 0

    async def generate(self, question, context, evidence) -> GeneratedAnswer:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        outcome = self.script[min(self.calls, len(self.script)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def _unavailable() -> ModelProviderUnavailable:
    return ModelProviderUnavailable("indisponível")


# Fallback


def test_fallback_tries_next_adapter_until_one_answers() -> None:
    first = ScriptedAdapter(_unavailable())
    second = ScriptedAdapter(_unavailable())
    third = ScriptedAdapter(_answer("terceiro"))
    unused = ScriptedAdapter(_answer("não deveria ser chamado"))
    adapter = FallbackModelAdapter([first, second, third, unused])

    result = asyncio.run(adapter.generate(QUESTION, [], _evidence()))

    assert result.answer == "terceiro"
    assert (first.calls, second.calls, third.calls, unused.calls) == (1, 1, 1, 0)


def test_fallback_raises_unavailable_when_every_adapter_fails() -> None:
    adapters = [ScriptedAdapter(_unavailable()) for _ in range(3)]

    with pytest.raises(ModelProviderUnavailable):
        asyncio.run(FallbackModelAdapter(adapters).generate(QUESTION, [], _evidence()))

    assert [item.calls for item in adapters] == [1, 1, 1]


def test_fallback_does_not_hide_unexpected_errors() -> None:
    second = ScriptedAdapter(_answer())
    adapter = FallbackModelAdapter([ScriptedAdapter(RuntimeError("bug")), second])

    with pytest.raises(RuntimeError):
        asyncio.run(adapter.generate(QUESTION, [], _evidence()))

    assert second.calls == 0


def test_fallback_requires_at_least_one_adapter() -> None:
    with pytest.raises(ValueError):
        FallbackModelAdapter([])


def test_fallback_total_timeout_becomes_unavailable() -> None:
    fast_failure = ScriptedAdapter(_unavailable())
    slow = ScriptedAdapter(_answer(), delay=5)
    never_reached = ScriptedAdapter(_answer())
    adapter = FallbackModelAdapter(
        [fast_failure, slow, never_reached],
        total_timeout_seconds=0.05,
    )

    with pytest.raises(ModelProviderUnavailable):
        asyncio.run(adapter.generate(QUESTION, [], _evidence()))

    assert (fast_failure.calls, slow.calls, never_reached.calls) == (1, 1, 0)


def test_fallback_timeout_raised_by_adapter_is_not_mistaken_for_deadline() -> None:
    adapter = FallbackModelAdapter(
        [ScriptedAdapter(TimeoutError())],
        total_timeout_seconds=10,
    )

    with pytest.raises(TimeoutError):
        asyncio.run(adapter.generate(QUESTION, [], _evidence()))


def test_fallback_logs_without_question_content(caplog) -> None:
    secret_question = "pergunta-marcador-confidencial"
    adapter = FallbackModelAdapter([ScriptedAdapter(_unavailable()), ScriptedAdapter(_answer())])

    with caplog.at_level(logging.DEBUG, logger="app.providers.fallback"):
        asyncio.run(adapter.generate(secret_question, [], _evidence()))

    assert caplog.records
    assert secret_question not in caplog.text


# Cache


def _cached(inner, clock=None, ttl=300, max_entries=256) -> CachingModelAdapter:
    return CachingModelAdapter(
        inner,
        ttl_seconds=ttl,
        max_entries=max_entries,
        clock=clock or FakeClock(),
    )


def test_cache_hit_skips_inner_adapter() -> None:
    inner = ScriptedAdapter(_answer())
    adapter = _cached(inner)

    async def run():
        first = await adapter.generate(QUESTION, [], _evidence())
        second = await adapter.generate(QUESTION, [], _evidence())
        return first, second

    first, second = asyncio.run(run())

    assert first == second == _answer()
    assert inner.calls == 1


def test_cache_returns_copies_that_do_not_change_stored_answer() -> None:
    adapter = _cached(ScriptedAdapter(_answer()))

    async def run():
        first = await adapter.generate(QUESTION, [], _evidence())
        first.answer = "alterado"
        return await adapter.generate(QUESTION, [], _evidence())

    assert asyncio.run(run()).answer == _answer().answer


def test_cache_miss_when_question_or_context_differs() -> None:
    inner = ScriptedAdapter(_answer())
    adapter = _cached(inner)
    turn = ConversationTurn(role="user", content="Qual o consumo?")

    async def run():
        await adapter.generate(QUESTION, [], _evidence())
        await adapter.generate("Outra pergunta?", [], _evidence())
        await adapter.generate(QUESTION, [turn], _evidence())

    asyncio.run(run())

    assert inner.calls == 3


def test_cache_key_changes_when_evidence_changes() -> None:
    inner = ScriptedAdapter(_answer())
    adapter = _cached(inner)

    async def run():
        await adapter.generate(QUESTION, [], _evidence(value=42))
        await adapter.generate(QUESTION, [], _evidence(value=43))
        await adapter.generate(QUESTION, [], _evidence(value=42, source="synthetic_fixture:outra"))
        await adapter.generate(QUESTION, [], _evidence(value=42))

    asyncio.run(run())

    assert inner.calls == 3


def test_cache_entry_expires_after_ttl() -> None:
    inner = ScriptedAdapter(_answer())
    clock = FakeClock()
    adapter = _cached(inner, clock=clock, ttl=300)

    async def run():
        await adapter.generate(QUESTION, [], _evidence())
        clock.now += 299
        await adapter.generate(QUESTION, [], _evidence())
        clock.now += 1
        await adapter.generate(QUESTION, [], _evidence())

    asyncio.run(run())

    assert inner.calls == 2


def test_cache_evicts_least_recently_used_entry() -> None:
    inner = ScriptedAdapter(_answer())
    adapter = _cached(inner, max_entries=2)

    async def run():
        await adapter.generate("a?", [], _evidence())
        await adapter.generate("b?", [], _evidence())
        await adapter.generate("a?", [], _evidence())  # "a" passa a ser a mais recente
        await adapter.generate("c?", [], _evidence())  # descarta "b"
        await adapter.generate("a?", [], _evidence())
        await adapter.generate("b?", [], _evidence())

    asyncio.run(run())

    assert inner.calls == 4


def test_cache_does_not_store_failures() -> None:
    inner = ScriptedAdapter(_unavailable(), _answer())
    adapter = _cached(inner)

    async def run():
        with pytest.raises(ModelProviderUnavailable):
            await adapter.generate(QUESTION, [], _evidence())
        return await adapter.generate(QUESTION, [], _evidence())

    assert asyncio.run(run()) == _answer()
    assert inner.calls == 2


def test_concurrent_identical_calls_share_one_model_call() -> None:
    inner = ScriptedAdapter(_answer(), delay=0.05)
    adapter = _cached(inner)

    async def run():
        return await asyncio.gather(
            *(adapter.generate(QUESTION, [], _evidence()) for _ in range(10))
        )

    results = asyncio.run(run())

    assert inner.calls == 1
    assert all(result == _answer() for result in results)


def test_concurrent_identical_calls_share_failure_without_caching_it() -> None:
    inner = ScriptedAdapter(_unavailable(), _answer(), delay=0.05)
    adapter = _cached(inner)

    async def run():
        failures = await asyncio.gather(
            *(adapter.generate(QUESTION, [], _evidence()) for _ in range(5)),
            return_exceptions=True,
        )
        assert adapter._in_flight == {}
        retry = await adapter.generate(QUESTION, [], _evidence())
        return failures, retry

    failures, retry = asyncio.run(run())

    assert all(isinstance(item, ModelProviderUnavailable) for item in failures)
    assert retry == _answer()
    assert inner.calls == 2


def test_cancelled_caller_does_not_cancel_shared_call() -> None:
    inner = ScriptedAdapter(_answer(), delay=0.05)
    adapter = _cached(inner)

    async def run():
        leader = asyncio.ensure_future(adapter.generate(QUESTION, [], _evidence()))
        await asyncio.sleep(0)
        follower = asyncio.ensure_future(adapter.generate(QUESTION, [], _evidence()))
        await asyncio.sleep(0)
        leader.cancel()
        return await follower

    assert asyncio.run(run()) == _answer()
    assert inner.calls == 1


def test_cached_ungrounded_answer_is_still_refused_by_orchestrator() -> None:
    inner = ScriptedAdapter(_answer("O consumo demonstrativo foi 999 unidades fictícias."))
    orchestrator = QuestionOrchestrator(
        analysis_planner=QuestionAnalysisPlanner(
            QuestionInterpreter(GRID360_DEMO_PROFILE),
            SyntheticScenarioTool(),
            ReadAccessPolicy(GRID360_DEMO_PROFILE, SYNTHETIC_SOURCE_ID),
        ),
        model_adapter=_cached(inner),
    )
    request = QuestionRequest(question=QUESTION)

    async def run():
        return [
            await orchestrator.answer(
                request, demo_access_context(GRID360_DEMO_PROFILE, "0" * 32)
            )
            for _ in range(2)
        ]

    responses = asyncio.run(run())

    assert inner.calls == 1
    for response in responses:
        assert response.status is QuestionStatus.REFUSED
        assert "999" not in response.message


# Configuração e factory


def test_settings_default_keeps_current_behaviour() -> None:
    settings = Settings(_env_file=None)

    assert settings.gemini_fallback_models == []
    assert settings.model_cache_ttl_seconds == 0
    assert settings.model_cache_max_entries == 256
    assert settings.model_total_timeout_ms == 30_000


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("gemini-a, gemini-b", ["gemini-a", "gemini-b"]),
        ('["gemini-a", "gemini-b"]', ["gemini-a", "gemini-b"]),
        ("gemini-a", ["gemini-a"]),
        ("", []),
    ],
)
def test_fallback_models_accept_comma_separated_or_json(monkeypatch, raw, expected) -> None:
    monkeypatch.setenv("GENAI_GEMINI_FALLBACK_MODELS", raw)

    assert Settings(_env_file=None).gemini_fallback_models == expected


class RoutingEndpoint:
    """Simula o SDK Gemini: falha para modelos listados em ``failing``."""

    def __init__(self, failing: set[str]) -> None:
        self.failing = failing
        self.models: list[str] = []

    async def generate_content(self, *, model, **kwargs):
        self.models.append(model)
        if model in self.failing:
            raise ConnectionError("fake-key-for-test rede indisponível")
        return type("Response", (), {"text": _answer().model_dump_json()})()


def _client(endpoint: RoutingEndpoint):
    client = type("Client", (), {})()
    client.aio = type("AsyncClient", (), {})()
    client.aio.models = endpoint
    return client


def _gemini_settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        model_provider="gemini",
        gemini_model="gemini-primary",
        gemini_api_key="fake-key-for-test",
        **overrides,
    )


def test_factory_default_returns_plain_gemini_adapter() -> None:
    adapter = build_model_adapter(_gemini_settings(), client=_client(RoutingEndpoint(set())))

    assert isinstance(adapter, GeminiModelAdapter)


def test_factory_unavailable_provider_is_not_wrapped() -> None:
    settings = Settings(
        _env_file=None,
        gemini_fallback_models=["gemini-b"],
        model_cache_ttl_seconds=300,
    )

    assert build_model_adapter(settings).__class__.__name__ == "UnavailableModelAdapter"


def test_factory_wires_fallback_and_cache_in_configured_order(caplog) -> None:
    endpoint = RoutingEndpoint(failing={"gemini-primary", "gemini-b"})
    settings = _gemini_settings(
        gemini_fallback_models=["gemini-b", "gemini-c"],
        model_cache_ttl_seconds=300,
    )
    adapter = build_model_adapter(settings, client=_client(endpoint))

    async def run():
        first = await adapter.generate(QUESTION, [], _evidence())
        second = await adapter.generate(QUESTION, [], _evidence())
        return first, second

    with caplog.at_level(logging.DEBUG):
        first, second = asyncio.run(run())

    assert first == second == _answer()
    assert endpoint.models == ["gemini-primary", "gemini-b", "gemini-c"]
    assert "fake-key-for-test" not in caplog.text
    assert QUESTION not in caplog.text


def test_factory_fallback_without_cache_calls_model_each_time() -> None:
    endpoint = RoutingEndpoint(failing={"gemini-primary"})
    adapter = build_model_adapter(
        _gemini_settings(gemini_fallback_models="gemini-b"),
        client=_client(endpoint),
    )

    async def run():
        await adapter.generate(QUESTION, [], _evidence())
        await adapter.generate(QUESTION, [], _evidence())

    asyncio.run(run())

    assert endpoint.models == ["gemini-primary", "gemini-b"] * 2
