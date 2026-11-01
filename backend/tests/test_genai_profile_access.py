import asyncio
from unittest.mock import AsyncMock

from sqlalchemy import create_engine

from app.core.genai_gold_access import build_profile_access_scope
from app.core.platform_access import PlatformProfile
from app.core.platform_identity import PlatformIdentity
from app.schemas.ai import AIQuestionRequest
from app.services.genai_planning import plan_gold_question


def identity(profile: PlatformProfile | None) -> PlatformIdentity:
    return PlatformIdentity("user:test", profile, frozenset({"ai:ask"}), "session")


def test_scope_matrix_separates_commercial_and_operations_and_keeps_admin_union():
    commercial = build_profile_access_scope(identity(PlatformProfile.COMMERCIAL))
    operations = build_profile_access_scope(identity(PlatformProfile.OPERATIONS))
    admin = build_profile_access_scope(identity(PlatformProfile.ADMIN))

    assert "billing.revenue" in commercial.allowed_metric_ids
    assert "network.equivalent_interruption_duration" not in commercial.allowed_metric_ids
    assert "network.equivalent_interruption_duration" in operations.allowed_metric_ids
    assert "billing.revenue" not in operations.allowed_metric_ids
    assert admin.allowed_metric_ids == commercial.allowed_metric_ids | operations.allowed_metric_ids
    assert admin.allowed_dimension_ids == commercial.allowed_dimension_ids | operations.allowed_dimension_ids
    assert (admin.profile_id, admin.source_id) == ("v-energy-grid-360-gold", "gold.local")


def test_customer_service_and_losses_have_explicit_empty_gold_scope():
    for profile in (PlatformProfile.CUSTOMER_SERVICE, PlatformProfile.LOSSES):
        scope = build_profile_access_scope(identity(profile))
        assert scope.allowed_operations == frozenset({"read"})
        assert scope.allowed_metric_ids == frozenset()
        assert scope.allowed_dimension_ids == frozenset()


def test_scope_cannot_be_built_without_ai_permission_or_individual_session():
    for candidate in (
        PlatformIdentity("user:test", PlatformProfile.ADMIN, frozenset(), "session"),
        PlatformIdentity("service:test", PlatformProfile.ADMIN, frozenset({"ai:ask"}), "service"),
        PlatformIdentity("demo", None, frozenset({"ai:ask"}), "demo"),
    ):
        try:
            build_profile_access_scope(candidate)
        except ValueError:
            pass
        else:
            raise AssertionError("identity must not produce a Gold access scope")


def test_empty_scope_returns_limitation_before_publication_or_model():
    client = AsyncMock()
    resolve_scope = lambda: build_profile_access_scope(identity(PlatformProfile.LOSSES))

    result = asyncio.run(plan_gold_question(
        create_engine("sqlite://"), client, AIQuestionRequest(question="Atendimentos"),
        resolve_scope=resolve_scope, correlation_id="a" * 32,
    ))

    assert result.response.status.value == "needs_clarification"
    assert result.response.response.limitations
    assert result.publication is None
    client.plan.assert_not_called()
