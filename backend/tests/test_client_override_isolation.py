from contextlib import asynccontextmanager

import pytest

from app.main import app
from app.core.database import get_db
from tests.support.client import client_with_overrides
from tests.support.database import override_get_db


def test_client_restores_existing_overrides_and_discards_changes():
    existing_dependency = object()
    changed_dependency = object()

    def existing_override():
        return "before"

    original = app.dependency_overrides.copy()
    expected = {existing_dependency: existing_override}
    try:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(expected)

        with client_with_overrides(app, {get_db: override_get_db}) as client:
            assert client.get("/openapi.json").status_code == 200
            app.dependency_overrides[changed_dependency] = lambda: "temporary"

        assert app.dependency_overrides == expected
        assert app.dependency_overrides[existing_dependency] is existing_override
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


def test_client_restores_overrides_when_test_body_raises():
    existing_dependency = object()
    changed_dependency = object()
    expected_override = lambda: "existing"
    original = app.dependency_overrides.copy()

    try:
        app.dependency_overrides.clear()
        app.dependency_overrides[existing_dependency] = expected_override

        with pytest.raises(RuntimeError, match="simulated test failure"):
            with client_with_overrides(app, {get_db: override_get_db}) as client:
                assert client.get("/openapi.json").status_code == 200
                app.dependency_overrides[changed_dependency] = lambda: "temporary"
                raise RuntimeError("simulated test failure")

        assert app.dependency_overrides == {existing_dependency: expected_override}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


def test_client_restores_overrides_when_real_testclient_startup_fails(monkeypatch):
    existing_dependency = object()
    expected_override = lambda: "existing"
    original = app.dependency_overrides.copy()

    @asynccontextmanager
    async def fail_startup(application):
        raise RuntimeError("simulated startup failure")
        yield

    try:
        app.dependency_overrides.clear()
        app.dependency_overrides[existing_dependency] = expected_override
        monkeypatch.setattr(app.router, "lifespan_context", fail_startup)

        with pytest.raises(RuntimeError, match="simulated startup failure"):
            with client_with_overrides(app, {get_db: override_get_db}):
                pytest.fail("a client with failed startup cannot be yielded")

        assert app.dependency_overrides == {existing_dependency: expected_override}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


def test_client_restores_overrides_when_real_testclient_shutdown_fails(monkeypatch):
    existing_dependency = object()
    changed_dependency = object()
    expected_override = lambda: "existing"
    original = app.dependency_overrides.copy()
    real_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def fail_shutdown(application):
        async with real_lifespan(application):
            yield
        raise RuntimeError("simulated shutdown failure")

    try:
        app.dependency_overrides.clear()
        app.dependency_overrides[existing_dependency] = expected_override
        monkeypatch.setattr(app.router, "lifespan_context", fail_shutdown)

        with pytest.raises(RuntimeError, match="simulated shutdown failure"):
            with client_with_overrides(app, {get_db: override_get_db}) as client:
                assert client.get("/openapi.json").status_code == 200
                app.dependency_overrides[changed_dependency] = lambda: "temporary"

        assert app.dependency_overrides == {existing_dependency: expected_override}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)
