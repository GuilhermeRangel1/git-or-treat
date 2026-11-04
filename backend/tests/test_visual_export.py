from contextlib import nullcontext
from types import SimpleNamespace
from typing import Annotated

import pytest
from fastapi import Depends, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.v1.endpoints import ai_visualizations as routes
from app.core.database import get_db
from app.core.genai_gold_access import get_genai_gold_access_resolver
from app.models.auth import AuthUser
from app.repositories.gold_publication import GoldPublicationChanged
from tests import test_ai_history_http as history_fixtures
from tests import test_ai_history_store as store_fixtures
from tests.test_chat_visualization import BATCH

client = history_fixtures.client
storage = store_fixtures.storage
BODY = {
    "metric": "billing.revenue",
    "dimension_ids": ["geography.municipality"],
    "batch_reference": BATCH,
}


@pytest.fixture
def export_client(client, monkeypatch):
    web, db, _ = client
    db.execute(update(AuthUser).values(profile="admin"))
    db.commit()
    web.app.include_router(routes.router, prefix="/api/v1/ai")
    reader = SimpleNamespace(connect=lambda: nullcontext(None))

    def resources(request: Request, db: Annotated[Session, Depends(get_db)]):
        return reader, get_genai_gold_access_resolver(request, None, db)

    web.app.dependency_overrides[routes.get_question_gold_resources] = resources

    def publication(connection, expected):
        if expected != BATCH:
            raise GoldPublicationChanged()
        return SimpleNamespace(batch_ref=BATCH)

    monkeypatch.setattr(routes, "current_publication", publication)
    return web, db


def post(web, body):
    return web.post(
        "/api/v1/ai/visualizations/verify", json=body, headers=history_fixtures.ORIGIN
    )


def test_verified_session_and_publication_allow_only_metadata(export_client):
    web, _ = export_client
    response = post(web, BODY)
    assert response.status_code == 200, response.text
    assert response.json() == {"authorized": True}


@pytest.mark.parametrize(
    "patch", [{"metric": "billing.paid"}, {"dimension_ids": ["customer.name"]}]
)
def test_request_does_not_grant_metric_or_dimension(export_client, patch):
    web, _ = export_client
    assert post(web, {**BODY, **patch}).status_code == 403


def test_changed_publication_is_rejected(export_client):
    web, _ = export_client
    response = post(
        web, {**BODY, "batch_reference": BATCH.replace("fd69c375", "aaaaaaaa")}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_context"


def test_no_session_revoked_permission_and_cross_origin_are_rejected(export_client):
    web, db = export_client
    web.cookies.clear()
    assert post(web, BODY).status_code == 401
    web.cookies.set("grid360_session", "one")
    assert (
        web.post(
            "/api/v1/ai/visualizations/verify",
            json=BODY,
            headers={"origin": "https://other.invalid"},
        ).status_code
        == 403
    )
    db.execute(update(AuthUser).where(AuthUser.id == "one").values(profile=None))
    db.commit()
    assert post(web, BODY).status_code == 403


def test_revocation_during_check_is_rejected(export_client, monkeypatch):
    web, db = export_client

    def revoked(*args):
        db.execute(update(AuthUser).where(AuthUser.id == "one").values(profile=None))
        db.commit()
        return SimpleNamespace(batch_ref=BATCH)

    monkeypatch.setattr(routes, "current_publication", revoked)
    assert post(web, BODY).status_code == 403


@pytest.mark.parametrize(
    "patch",
    [
        {"sql": "SELECT 1"},
        {"points": [1]},
        {"expected_publication": {"lote": "Lote", "fingerprint": "a" * 64}},
        {"batch_reference": None},
    ],
)
def test_client_cannot_supply_data_sql_or_ambiguous_origin(export_client, patch):
    web, _ = export_client
    assert post(web, {**BODY, **patch}).status_code == 422


def test_panorama_reference_uses_existing_fingerprint_resolver(
    export_client, monkeypatch
):
    web, _ = export_client
    captured = []

    def resolve(engine, expected):
        captured.append(expected.fingerprint)
        return BATCH

    monkeypatch.setattr(routes, "resolve_expected_batch_ref", resolve)
    assert (
        post(
            web,
            {
                "metric": "billing.revenue",
                "dimension_ids": ["geography.municipality"],
                "expected_publication": {"lote": "Lote", "fingerprint": "a" * 64},
            },
        ).status_code
        == 200
    )
    assert captured == ["a" * 64]
