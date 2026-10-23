import os

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models.operational import InspectionOrder, OrderStatus
from app.schemas.inspections import OrderCreateRequest, OrderUpdateRequest
from app.services.inspections import OrderConflictError, create_order, update_order
from tests.test_migrations import migrated_database


def test_order_security_on_disposable_postgres(monkeypatch):
    raw_url = os.environ.get("TEST_POSTGRES_URL")
    if not raw_url:
        pytest.skip("Defina TEST_POSTGRES_URL para um PostgreSQL descartável *_test.")
    url = make_url(raw_url)
    assert url.get_backend_name() == "postgresql" and url.database.endswith("_test")
    engine = create_engine(url)
    token = "postgres-isolated-writer-" + "w" * 32
    monkeypatch.setattr("app.core.config.settings.ORDERS_WRITE_TOKEN", SecretStr(token))
    monkeypatch.setattr("app.core.config.settings.ORDERS_READ_TOKEN", None)
    previous_overrides = app.dependency_overrides.copy()

    def database():
        with Session(engine) as session:
            yield session

    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")) is False
            connection.rollback()
            with migrated_database(connection):
                app.dependency_overrides[get_db] = database
                with TestClient(app) as client:
                    endpoint = "/api/v1/inspections/orders"
                    headers = {"Authorization": "Bearer " + token}
                    assert client.get(endpoint).status_code == 401
                    created = client.post(endpoint, headers=headers, json={"uc_id": "U" * 50, "reason": "R" * 255, "notes": "N" * 4000})
                    assert created.status_code == 201
                    oid = created.json()["id"]
                    assert client.patch(endpoint + "/9223372036854775808", headers=headers, json={"status": "EM_ANDAMENTO"}).status_code == 422
                    assert client.post(endpoint, headers=headers, json={"uc_id": "U" * 51, "reason": "Motivo"}).status_code == 422
                with Session(engine) as stale, Session(engine) as writer:
                    original = stale.get(InspectionOrder, oid)
                    assert original.status == OrderStatus.PENDING
                    update_order(writer, oid, OrderUpdateRequest(status=OrderStatus.CANCELLED))
                    with pytest.raises(OrderConflictError):
                        update_order(stale, oid, OrderUpdateRequest(status=OrderStatus.IN_PROGRESS))
                    stale.rollback()
                    assert stale.get(InspectionOrder, oid).status == OrderStatus.CANCELLED
                with Session(engine) as fresh:
                    persisted = fresh.get(InspectionOrder, oid)
                    assert persisted.status == OrderStatus.CANCELLED
                    assert len(persisted.uc_id) == 50 and len(persisted.notes) == 4000
                    normal = create_order(fresh, OrderCreateRequest(uc_id="SECOND-TEST", reason="Inspeção"))
                    update_order(fresh, normal.id, OrderUpdateRequest(status=OrderStatus.IN_PROGRESS))
                    update_order(fresh, normal.id, OrderUpdateRequest(status=OrderStatus.COMPLETED, result="Conferido"))
                    assert normal.status == OrderStatus.COMPLETED
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        engine.dispose()
