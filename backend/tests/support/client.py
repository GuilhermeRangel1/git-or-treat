"""HTTP test client lifecycle helpers."""

from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient


@contextmanager
def client_with_overrides(application: FastAPI, overrides: dict):
    """Apply fixture overrides and restore the exact prior snapshot on every exit."""
    previous_overrides = application.dependency_overrides.copy()
    application.dependency_overrides.update(overrides)
    try:
        with TestClient(application, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()
        application.dependency_overrides.update(previous_overrides)
