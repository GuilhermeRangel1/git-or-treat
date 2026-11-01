"""Catálogo de perfis e permissões globais do Grid 360."""

from enum import StrEnum


class PlatformProfile(StrEnum):
    COMMERCIAL = "commercial"
    CUSTOMER_SERVICE = "customer_service"
    LOSSES = "losses"
    OPERATIONS = "operations"
    ADMIN = "admin"


ALL_PERMISSIONS = frozenset({
    "panorama:read",
    "revenue:read",
    "ucs:read",
    "inspections:read",
    "orders:read",
    "orders:write",
    "operations:read",
    "ai:ask",
})

_PROFILE_PERMISSIONS = {
    PlatformProfile.COMMERCIAL: frozenset({"panorama:read", "revenue:read", "ai:ask"}),
    PlatformProfile.CUSTOMER_SERVICE: frozenset({"ucs:read", "ai:ask"}),
    PlatformProfile.LOSSES: frozenset({"inspections:read", "orders:read", "orders:write", "ai:ask"}),
    PlatformProfile.OPERATIONS: frozenset({"operations:read", "ai:ask"}),
    PlatformProfile.ADMIN: ALL_PERMISSIONS,
}

_PROFILE_DEFAULT_ROUTES = {
    PlatformProfile.COMMERCIAL: "/panorama",
    PlatformProfile.CUSTOMER_SERVICE: "/uc-360",
    PlatformProfile.LOSSES: "/inspecoes",
    PlatformProfile.OPERATIONS: "/operacao",
    PlatformProfile.ADMIN: "/panorama",
}


def _known_profile(profile: str | None) -> PlatformProfile | None:
    if profile is None:
        return None
    try:
        return PlatformProfile(profile)
    except ValueError:
        return None


def permissions_for_profile(profile: str | None) -> frozenset[str]:
    """Retorna somente concessões do catálogo; ausente/desconhecido fecha acesso."""
    known = _known_profile(profile)
    return _PROFILE_PERMISSIONS.get(known, frozenset())


def default_route_for_profile(profile: str | None) -> str | None:
    """Rota inicial do portal; perfis legados não recebem rota privilegiada."""
    known = _known_profile(profile)
    return _PROFILE_DEFAULT_ROUTES.get(known)
