"""Local synthetic workflow must remain usable before the login feature."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.main import app
from app.repositories.analytics import (
    SyntheticAnalyticsRepository, get_analytics_repository,
    get_analytics_repository_provider,
)

ROOT = "/api/v1/inspections"


@pytest.fixture
def demo(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "demo")
    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "synthetic")
    app.dependency_overrides[get_analytics_repository] = SyntheticAnalyticsRepository
    app.dependency_overrides[get_analytics_repository_provider] = lambda: SyntheticAnalyticsRepository
    return client


def test_create_replay_and_consult_without_login(demo):
    access = demo.get(ROOT + "/access")
    assert access.status_code == 200
    assert access.json()["auth_mode"] == "demo"
    assert access.json()["actor"] == "local-demo"
    suspicion = demo.get(ROOT + "/queue/UC-1004").json()
    payload = {"source_version": suspicion["metadata"]["source"]["version"],
               "rule_version": suspicion["data"]["rule_version"]}
    headers = {"Idempotency-Key": "demo-no-login-intention-001",
               "Origin": "http://localhost:5173"}
    first = demo.post(ROOT + "/queue/UC-1004/orders", json=payload, headers=headers)
    assert first.status_code == 201
    replay = demo.post(ROOT + "/queue/UC-1004/orders", json=payload, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert demo.get(ROOT + "/orders/search").json()["pagination"]["total"] == 1
    assert demo.get(ROOT + f"/orders/{first.json()['id']}").json()["uc_id"] == "UC-1004"


@pytest.mark.parametrize("headers", [
    {"Origin": "https://attacker.invalid"}, {"Sec-Fetch-Site": "cross-site"},
])
def test_demo_rejects_cross_site_browser_requests(demo, headers):
    assert demo.post(ROOT + "/orders", json={"uc_id": "DEMO", "reason": "test"},
                     headers=headers).status_code == 403
    assert demo.get(ROOT + "/orders/search").json()["pagination"]["total"] == 0


@pytest.mark.parametrize("options", [
    {"APP_ENV": "production", "ANALYTICS_SOURCE": "synthetic"},
    {"APP_ENV": "development", "ANALYTICS_SOURCE": "unavailable"},
])
def test_demo_configuration_is_limited_to_synthetic_development(options):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ORDERS_AUTH_MODE="demo", **options)


def test_service_mode_still_requires_credentials(client, monkeypatch):
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "service")
    assert client.get(ROOT + "/orders").status_code == 401
