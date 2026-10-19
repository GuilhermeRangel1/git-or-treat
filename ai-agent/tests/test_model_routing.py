import asyncio

import pytest
from pydantic import ValidationError

from app.providers.fallback import FallbackModelAdapter
from app.providers.protocols import GeneratedAnswer
from app.providers.routing import (
    ModelRouter,
    ModelTier,
    ModelTierNotConfigured,
    RoutingPolicy,
    escalate,
    select_tier,
)

POLICY = RoutingPolicy(
    light_intents={"lookup"},
    strong_intents={"diagnosis"},
    max_light_evidence_records=10,
    max_light_evidence_chars=1_000,
)


class NamedAdapter:
    def __init__(self, name: str) -> None:
        self.name = name

    async def generate(self, question, context, evidence) -> GeneratedAnswer:
        return GeneratedAnswer(status="answered", answer=self.name)


def _select(intent: str | None = "lookup", records: int = 1, chars: int = 100) -> ModelTier:
    return select_tier(
        intent=intent, evidence_records=records, evidence_chars=chars, policy=POLICY
    )


def test_light_intent_with_small_evidence_uses_light():
    assert _select() is ModelTier.LIGHT


def test_strong_intent_uses_strong_even_with_small_evidence():
    assert _select("diagnosis") is ModelTier.STRONG


@pytest.mark.parametrize("intent", [None, "unknown", "", "LOOKUP"])
def test_missing_or_unknown_intent_uses_strong(intent):
    assert _select(intent) is ModelTier.STRONG


@pytest.mark.parametrize(("records", "expected"), [(10, ModelTier.LIGHT), (11, ModelTier.STRONG)])
def test_record_limit_is_inclusive(records, expected):
    assert _select(records=records) is expected


@pytest.mark.parametrize(
    ("chars", "expected"), [(1_000, ModelTier.LIGHT), (1_001, ModelTier.STRONG)]
)
def test_char_limit_is_inclusive(chars, expected):
    assert _select(chars=chars) is expected


def test_empty_evidence_uses_light():
    assert _select(records=0, chars=0) is ModelTier.LIGHT


def test_any_exceeded_limit_is_enough_for_strong():
    assert _select(records=11, chars=0) is ModelTier.STRONG
    assert _select(records=0, chars=1_001) is ModelTier.STRONG


@pytest.mark.parametrize(("records", "chars"), [(-1, 0), (0, -1)])
def test_negative_evidence_size_is_rejected(records, chars):
    with pytest.raises(ValueError, match="negativo"):
        _select(records=records, chars=chars)


def test_default_policy_sends_every_intent_to_strong():
    policy = RoutingPolicy()

    assert policy.max_light_evidence_records == 50
    assert policy.max_light_evidence_chars == 8_000
    tier = select_tier(intent="lookup", evidence_records=0, evidence_chars=0, policy=policy)
    assert tier is ModelTier.STRONG


def test_policy_is_immutable_and_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        POLICY.max_light_evidence_records = 99
    with pytest.raises(ValidationError):
        RoutingPolicy(max_tokens=10)


def test_policy_rejects_negative_limits():
    with pytest.raises(ValidationError):
        RoutingPolicy(max_light_evidence_records=-1)
    with pytest.raises(ValidationError):
        RoutingPolicy(max_light_evidence_chars=-1)


def test_policy_rejects_intent_in_both_sets():
    with pytest.raises(ValidationError, match="lookup"):
        RoutingPolicy(light_intents={"lookup"}, strong_intents={"lookup"})


def test_escalate_goes_from_light_to_strong_and_stops():
    assert escalate(ModelTier.LIGHT) is ModelTier.STRONG
    assert escalate(ModelTier.STRONG) is None


def test_router_returns_adapter_of_selected_tier():
    light, strong = NamedAdapter("light"), NamedAdapter("strong")
    router = ModelRouter({ModelTier.LIGHT: light, ModelTier.STRONG: strong}, POLICY)

    assert router.route(intent="lookup", evidence_records=1, evidence_chars=10) == (
        ModelTier.LIGHT,
        light,
    )
    assert router.route(intent="diagnosis", evidence_records=1, evidence_chars=10) == (
        ModelTier.STRONG,
        strong,
    )
    assert router.route(intent="lookup", evidence_records=11, evidence_chars=10) == (
        ModelTier.STRONG,
        strong,
    )


def test_router_adapter_for_supports_escalation():
    light, strong = NamedAdapter("light"), NamedAdapter("strong")
    router = ModelRouter({ModelTier.LIGHT: light, ModelTier.STRONG: strong}, POLICY)

    tier, _ = router.route(intent="lookup", evidence_records=1, evidence_chars=10)
    assert router.adapter_for(escalate(tier)) is strong


def test_router_accepts_fallback_chain_as_tier_adapter():
    chain = FallbackModelAdapter([NamedAdapter("strong-a"), NamedAdapter("strong-b")])
    router = ModelRouter({ModelTier.LIGHT: NamedAdapter("light"), ModelTier.STRONG: chain}, POLICY)

    tier, adapter = router.route(intent=None, evidence_records=0, evidence_chars=0)

    assert tier is ModelTier.STRONG
    answer = asyncio.run(adapter.generate("pergunta", [], None))
    assert answer.answer == "strong-a"


def test_router_raises_clear_error_for_missing_tier():
    router = ModelRouter({ModelTier.STRONG: NamedAdapter("strong")}, POLICY)

    with pytest.raises(ModelTierNotConfigured, match="'light'.*strong"):
        router.adapter_for(ModelTier.LIGHT)


@pytest.mark.parametrize("configured", list(ModelTier))
def test_router_with_single_tier_always_uses_it(configured):
    only = NamedAdapter("only")
    router = ModelRouter({configured: only}, POLICY)

    for intent, records in [("lookup", 1), ("diagnosis", 1), (None, 1), ("lookup", 999)]:
        assert router.route(intent=intent, evidence_records=records, evidence_chars=10) == (
            configured,
            only,
        )


def test_router_requires_at_least_one_tier():
    with pytest.raises(ValueError, match="ao menos um"):
        ModelRouter({}, POLICY)


def test_router_exposes_configured_tiers():
    router = ModelRouter({ModelTier.LIGHT: NamedAdapter("light")}, POLICY)

    assert router.tiers == frozenset({ModelTier.LIGHT})
