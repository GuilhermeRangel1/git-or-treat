"""HTTP → operational database; synthetic queue is the real DEV-05 adapter."""
import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.repositories.analytics import get_analytics_repository
from app.repositories.analytics import SyntheticAnalyticsRepository
from tests.test_migrations import alembic_config
from alembic import command

ROOT = "/api/v1/inspections"


@pytest.fixture
def orders(client, monkeypatch):
    token = "dev06-test-" + "t" * 32
    monkeypatch.setattr("app.core.config.settings.ORDERS_WRITE_TOKEN", SecretStr(token))
    client.headers["Authorization"] = "Bearer " + token
    app.dependency_overrides[get_analytics_repository] = SyntheticAnalyticsRepository
    yield client


def request(client, uc="UC-1004"):
    detail = client.get(f"{ROOT}/queue/{uc}").json()
    return {"source_version": detail["metadata"]["source"]["version"],
            "rule_version": detail["data"]["rule_version"]}


def create(client, payload=None, key="dev06-intention-0001", uc="UC-1004"):
    return client.post(f"{ROOT}/queue/{uc}/orders", json=payload or request(client, uc),
                       headers={"Idempotency-Key": key})


def test_queue_creation_replay_conflicts_and_new_intention_after_closure(orders):
    payload = request(orders)
    first = create(orders, payload)
    assert first.status_code == 201
    body = first.json()
    assert body["uc_id"] == "UC-1004"
    assert body["suspicion_snapshot"]["data"]["priority"] == .92
    assert body["suspicion_snapshot"]["data"]["potential_recoverable_energy_kwh"] == 45
    assert body["reason"] == body["suspicion_snapshot"]["data"]["reason"]
    assert create(orders, payload).status_code == 200
    assert create(orders, payload).json()["id"] == body["id"]
    assert create(orders, {**payload, "notes": "Outro conteúdo"}).status_code == 409
    assert create(orders, payload, key="dev06-intention-0002").status_code == 409
    oid = body["id"]
    assert orders.patch(f"{ROOT}/orders/{oid}", json={"status": "CANCELADA"}).status_code == 200
    assert create(orders, payload).json()["status"] == "CANCELADA"
    assert create(orders, payload, key="dev06-intention-0002").status_code == 201
    assert orders.get(f"{ROOT}/orders/{oid}").json()["suspicion_snapshot"] == body["suspicion_snapshot"]


def test_server_rejects_forgery_stale_source_and_invalid_requests(orders):
    payload = request(orders)
    for change, code in [({"source_version": "stale"}, 409), ({"rule_version": "stale"}, 409),
                         ({"reason": "invented"}, 422), ({"uc_id": "another"}, 422),
                         ({"priority": "INVALID"}, 422), ({"notes": "x" * 4001}, 422)]:
        assert create(orders, {**payload, **change}).status_code == code
    assert orders.post(f"{ROOT}/queue/UC-1004/orders", json=payload).status_code == 422
    assert create(orders, payload, uc="UNKNOWN").status_code == 404
    assert create(orders, payload).status_code == 201


def test_paginated_listing_filters_totals_and_access(orders):
    first = create(orders).json()
    create(orders, key="dev06-intention-0002", uc="UC-1002")
    page = orders.get(f"{ROOT}/orders/search?page_size=1").json()
    assert page["pagination"] == {"page": 1, "page_size": 1, "total": 2, "total_pages": 2}
    assert page["items"][0]["uc_id"] == "UC-1002"
    assert orders.get(f"{ROOT}/orders/search?page=2&page_size=1").json()["items"][0]["id"] == first["id"]
    assert orders.get(f"{ROOT}/orders/search?uc_id=UC-1004&priority=MEDIA&status=PENDENTE").json()["pagination"]["total"] == 1
    assert orders.get(f"{ROOT}/orders/search?page=99").json()["items"] == []
    for query in ("page=0", "page_size=101", "status=invalid", "priority=invalid", "uc_id="):
        assert orders.get(f"{ROOT}/orders/search?{query}").status_code == 422
    orders.headers.pop("Authorization")
    assert orders.get(f"{ROOT}/orders/{first['id']}").status_code == 401
    assert orders.get(f"{ROOT}/orders/search").status_code == 401


def test_record_and_idempotency_survive_engine_and_http_client_restart(orders, tmp_path):
    url = f"sqlite:///{(tmp_path / 'restart.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    with engine.connect() as connection:
        command.upgrade(alembic_config(connection), "head")
        connection.commit()

    def database():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = database
    payload = request(orders)
    first = create(orders, payload).json()
    engine.dispose()
    engine = create_engine(url, connect_args={"check_same_thread": False})
    try:
        with TestClient(app) as restarted:
            restarted.headers.update(orders.headers)
            assert restarted.get(f"{ROOT}/orders/{first['id']}").json() == first
            assert create(restarted, payload).status_code == 200
            assert restarted.get(f"{ROOT}/orders/search").json()["pagination"]["total"] == 1
    finally:
        engine.dispose()


def test_real_api_process_restart_preserves_created_order(tmp_path):
    import os
    import socket
    import subprocess
    import sys
    import time
    from contextlib import contextmanager
    from pathlib import Path
    import httpx

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{(tmp_path / 'process.db').as_posix()}",
           "ANALYTICS_SOURCE": "synthetic", "ORDERS_WRITE_TOKEN": "restart-local-" + "r" * 32}
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]

    @contextmanager
    def running_api():
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=Path(__file__).resolve().parents[1], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", headers={"Authorization": "Bearer " + env["ORDERS_WRITE_TOKEN"]}) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        pytest.fail("API encerrou antes de iniciar o teste de reinício.")
                    try:
                        if client.get("/").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.1)
                else:
                    pytest.fail("API não iniciou para o teste de reinício.")
                yield client
        finally:
            process.terminate()
            process.wait(timeout=10)

    with running_api() as client:
        payload = request(client)
        created = create(client, payload)
        assert created.status_code == 201
        body = created.json()
    with running_api() as client:
        assert client.get(f"{ROOT}/orders/{body['id']}").json() == body
        assert create(client, payload).status_code == 200
        assert client.get(f"{ROOT}/orders/search").json()["pagination"]["total"] == 1


def test_concurrent_creation_and_persistence_on_disposable_postgres(monkeypatch):
    import os
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from app.models.operational import InspectionOrder
    from app.schemas.inspections import QueueOrderCreateRequest
    from app.services.inspections import create_from_queue, OrderConflictError
    from tests.test_migrations import migrated_database

    raw = os.getenv("TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("Defina TEST_POSTGRES_URL para PostgreSQL descartável *_test.")
    url = make_url(raw)
    assert url.get_backend_name() == "postgresql" and url.database.endswith("_test")
    engine = create_engine(url)
    repository = SyntheticAnalyticsRepository()
    payload = QueueOrderCreateRequest(source_version=repository.source_version, rule_version="dev05-v1")
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")) is False
            connection.rollback()
            with migrated_database(connection):
                for same_key in (True, False):
                    barrier = Barrier(2)

                    def attempt(worker):
                        with Session(engine) as db:
                            barrier.wait(timeout=10)
                            try:
                                row, created = create_from_queue(db, repository, "UC-1004", payload,
                                    f"concurrent-{same_key}-" + ("same" if same_key else str(worker)))
                                return row.id, created
                            except OrderConflictError:
                                return None, False

                    with ThreadPoolExecutor(max_workers=2) as pool:
                        results = list(pool.map(attempt, (0, 1)))
                    assert sum(created for _, created in results) == 1
                    with Session(engine) as db:
                        row = db.query(InspectionOrder).one()
                        if same_key:
                            assert results[0][0] == results[1][0] == row.id
                        else:
                            assert sum(oid is None for oid, _ in results) == 1
                        assert row.suspicion_snapshot["data"]["priority"] == .92
                        db.delete(row)
                        db.commit()
    finally:
        engine.dispose()
