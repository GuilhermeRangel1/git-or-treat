import pytest

from app.core.platform_access import default_route_for_profile, permissions_for_profile


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("commercial", {"panorama:read", "revenue:read", "ai:ask"}),
        ("customer_service", {"ucs:read", "ai:ask"}),
        ("losses", {"inspections:read", "orders:read", "orders:write", "ai:ask"}),
        ("operations", {"operations:read", "ai:ask"}),
        (
            "admin",
            {
                "panorama:read",
                "revenue:read",
                "ucs:read",
                "inspections:read",
                "orders:read",
                "orders:write",
                "operations:read",
                "ai:ask",
            },
        ),
        (None, set()),
        ("unknown", set()),
    ],
)
def test_permissions_are_explicitly_derived_from_platform_profile(profile, expected):
    assert permissions_for_profile(profile) == frozenset(expected)


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("commercial", "/panorama"),
        ("customer_service", "/uc-360"),
        ("losses", "/inspecoes"),
        ("operations", "/operacao"),
        ("admin", "/panorama"),
        (None, None),
        ("unknown", None),
    ],
)
def test_default_route_is_defined_only_for_known_profiles(profile, expected):
    assert default_route_for_profile(profile) == expected


def test_business_profiles_do_not_receive_unrelated_permissions():
    assert "orders:read" not in permissions_for_profile("commercial")
    assert "revenue:read" not in permissions_for_profile("operations")
    assert {"orders:read", "orders:write"} <= permissions_for_profile("losses")
