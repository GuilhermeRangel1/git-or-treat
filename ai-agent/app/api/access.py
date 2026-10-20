"""A borda gera o escopo demonstrativo; o cliente não fornece identidade."""

from fastapi import Request

from app.schemas.access import AccessContext
from app.schemas.domain_profile import CatalogOperation, CatalogSensitivity, DomainProfile

SYNTHETIC_SOURCE_ID = "synthetic.fixture"


def demo_access_context(
    profile: DomainProfile,
    correlation_id: str,
    source_id: str = SYNTHETIC_SOURCE_ID,
) -> AccessContext:
    """Somente composição local/testes podem criar este principal fictício."""

    safe_dimensions = {
        item.id
        for item in profile.dimensions
        if item.sensitivity is not CatalogSensitivity.PERSONAL
    }
    return AccessContext(
        caller_ref="local.demo",
        profile_id=profile.profile_id,
        source_id=source_id,
        correlation_id=correlation_id,
        allowed_operations=frozenset({CatalogOperation.READ}),
        allowed_metric_ids=frozenset(
            item.id
            for item in profile.metrics
            if item.sensitivity is not CatalogSensitivity.PERSONAL
        ),
        allowed_dimension_ids=frozenset(safe_dimensions),
    )


def resolve_access_context(request: Request) -> AccessContext | None:
    """Sem autenticação verificada no modo real, nega por padrão."""

    if (
        request.app.state.environment != "local"
        or not request.app.state.enable_demo_access
    ):
        return None
    return demo_access_context(
        request.app.state.domain_profile,
        request.state.correlation_id,
        request.app.state.source_id,
    )
