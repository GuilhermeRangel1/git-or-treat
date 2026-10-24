"""A borda gera o escopo demonstrativo; o cliente não fornece identidade."""

from collections.abc import Callable
from secrets import compare_digest

from fastapi import Header, Request

from app.api.errors import ServiceAuthenticationError
from app.schemas.access import AccessContext
from app.schemas.domain_profile import CatalogOperation, CatalogSensitivity, DomainProfile

SYNTHETIC_SOURCE_ID = "synthetic.fixture"
AccessContextResolver = Callable[[Request], AccessContext | None]


def require_service_auth(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Exige token interno quando configurado; produção falha fechada sem ele."""

    configured = request.app.state.service_api_token
    if configured is None:
        if request.app.state.environment == "local":
            return
        raise ServiceAuthenticationError(configured=False)

    scheme, separator, supplied = (authorization or "").partition(" ")
    expected = configured.get_secret_value()
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not compare_digest(supplied, expected)
    ):
        raise ServiceAuthenticationError(configured=True)


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
    """Obtém o escopo de uma borda confiável ou do modo demonstrativo local."""

    resolver: AccessContextResolver | None = getattr(
        request.app.state, "access_context_resolver", None
    )
    if resolver is not None:
        context = resolver(request)
        if (
            context is None
            or context.correlation_id != request.state.correlation_id
            or context.caller_ref == "local.demo"
        ):
            return None
        return context

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
