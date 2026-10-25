"""HTTP → operational database; synthetic queue is the real DEV-05 adapter."""
import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.repositories.analytics import get_analytics_repository, get_analytics_repository_provider
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
    app.dependency_overrides[get_analytics_repository_provider] = lambda: SyntheticAnalyticsRepository
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


def test_pages_beyond_total_never_send_oversized_offsets_to_database(orders):
    create(orders)
    for page in (2, 9223372036854775808, 10 ** 100):
        response = orders.get(f"{ROOT}/orders/search?page={page}&page_size=100")
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["pagination"] == {
            "page": page, "page_size": 100, "total": 1, "total_pages": 1,
        }


def test_search_projects_summary_without_loading_snapshot(orders):
    from sqlalchemy import event
    from tests.conftest import test_engine

    order = create(orders).json()
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(test_engine, "before_cursor_execute", capture)
    try:
        response = orders.get(f"{ROOT}/orders/search")
    finally:
        event.remove(test_engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    summary = response.json()["items"][0]
    assert summary["id"] == order["id"]
    assert summary["suspicion_reference"] == order["suspicion_reference"]
    assert "suspicion_snapshot" not in summary
    assert statements and all("suspicion_snapshot" not in sql for sql in statements)
    assert orders.get(f"{ROOT}/orders/{order['id']}").json()["suspicion_snapshot"]


def test_legacy_snapshot_survives_evolving_live_analytical_contract(orders):
    from pydantic import create_model, ValidationError
    from app.models.operational import InspectionOrder
    from app.schemas.inspection_queue import SuspicionResponse
    from tests.conftest import TestingSessionLocal

    created = create(orders).json()
    assert created["suspicion_snapshot"]["snapshot_schema_version"] == "1"
    legacy = created["suspicion_snapshot"].copy()
    legacy.pop("snapshot_schema_version")
    # Simulate a future required field that old analytical JSON cannot supply.
    future_contract = create_model("FutureSuspicion", __base__=SuspicionResponse, new_field=(str, ...))
    with pytest.raises(ValidationError):
        future_contract.model_validate(legacy)
    with TestingSessionLocal() as db:
        row = db.get(InspectionOrder, created["id"])
        row.suspicion_snapshot = legacy
        db.commit()
    persisted = orders.get(f"{ROOT}/orders/{created['id']}")
    assert persisted.status_code == 200
    assert persisted.json()["suspicion_snapshot"] == created["suspicion_snapshot"]
    assert create(orders).status_code == 200
    assert orders.get(f"{ROOT}/orders").status_code == 200


def test_replay_if_competing_request_commits_between_key_and_active_lookup(orders, monkeypatch):
    from app.services import inspections as service
    from app.schemas.inspections import QueueOrderCreateRequest
    from tests.conftest import TestingSessionLocal

    payload = request(orders)
    original = service.build_suspicion_response
    winner_ids = []

    def commit_competitor(repository, uc_id):
        # Deterministic interleaving: the outer request has already missed its
        # key; another worker commits before the outer active-order lookup.
        monkeypatch.setattr(service, "build_suspicion_response", original)
        with TestingSessionLocal() as writer:
            row, created = service.create_from_queue(
                writer, lambda: repository, uc_id, QueueOrderCreateRequest(**payload),
                "dev06-intention-0001",
            )
            assert created
            winner_ids.append(row.id)
        return original(repository, uc_id)

    monkeypatch.setattr(service, "build_suspicion_response", commit_competitor)
    replay = create(orders, payload)
    assert replay.status_code == 200
    assert replay.json()["id"] == winner_ids[0]
    assert orders.get(f"{ROOT}/orders/search").json()["pagination"]["total"] == 1


def test_replay_never_resolves_unavailable_analytics_and_checks_access(orders, monkeypatch):
    from app.repositories.analytics import AnalyticsSourceUnavailable

    payload = request(orders)
    created = create(orders, payload).json()
    calls = []

    def unavailable():
        calls.append(True)
        raise AnalyticsSourceUnavailable()

    app.dependency_overrides[get_analytics_repository_provider] = lambda: unavailable
    replay = create(orders, payload)
    assert replay.status_code == 200 and replay.json()["id"] == created["id"]
    assert calls == []
    mismatch = create(orders, {**payload, "notes": "different"})
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "idempotency_key_reused"
    assert calls == []
    fresh = create(orders, payload, key="fresh-unavailable-0001")
    assert fresh.status_code == 503 and calls == [True]
    orders.headers.pop("Authorization")
    assert create(orders, payload).status_code == 401


def test_structured_conflicts_keep_legacy_message_and_order_link(orders):
    payload = request(orders)
    stale = create(orders, {**payload, "rule_version": "outdated"})
    assert stale.status_code == 409
    assert stale.json()["error"] == {
        "code": "stale_suspicion", "message": stale.json()["detail"], "order_id": None,
    }
    created = create(orders, payload).json()
    active = create(orders, payload, key="another-intention-0001")
    assert active.status_code == 409
    assert active.json()["error"] == {
        "code": "active_order_exists", "message": active.json()["detail"], "order_id": created["id"],
    }


def test_one_active_uc_across_versions_and_manual_creation(orders):
    repository = SyntheticAnalyticsRepository()
    app.dependency_overrides[get_analytics_repository_provider] = lambda: lambda: repository
    payload = request(orders)
    first = create(orders, payload).json()
    repository.source_version = "new-snapshot"
    newer = create(orders, {**payload, "source_version": "new-snapshot"}, key="another-version-0001")
    assert newer.status_code == 409
    assert newer.json()["error"]["order_id"] == first["id"]
    manual = orders.post(f"{ROOT}/orders", json={"uc_id": "UC-1004", "reason": "manual"})
    assert manual.status_code == 409
    assert manual.json()["error"]["code"] == "active_order_exists"
    orders.patch(f"{ROOT}/orders/{first['id']}", json={"status": "CANCELADA"})
    assert orders.post(f"{ROOT}/orders", json={"uc_id": "UC-1004", "reason": "manual"}).status_code == 201
    assert create(orders, {**payload, "source_version": "new-snapshot"}, key="another-version-0001").status_code == 409


def test_failed_insert_rolls_back_key_and_allows_same_intention_retry(orders):
    from sqlalchemy import text
    from tests.conftest import test_engine, TestingSessionLocal
    from app.models.operational import InspectionOrder

    payload = request(orders)
    with test_engine.begin() as conn:
        conn.execute(text("CREATE TRIGGER dev06_fail BEFORE INSERT ON operational_inspection_orders "
                          "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"))
    try:
        assert create(orders, payload).status_code == 500
    finally:
        with test_engine.begin() as conn:
            conn.execute(text("DROP TRIGGER dev06_fail"))
    with TestingSessionLocal() as db:
        assert db.query(InspectionOrder).count() == 0
    assert create(orders, payload).status_code == 201
    assert create(orders, payload).status_code == 200


def test_post_commit_confirmation_failure_recovers_with_source_down(orders, monkeypatch):
    from app.repositories.analytics import AnalyticsSourceUnavailable
    from tests.conftest import TestingSessionLocal
    from app.models.operational import InspectionOrder

    payload = request(orders)
    original_refresh = Session.refresh

    def lost_confirmation(self, *args, **kwargs):
        raise RuntimeError("injected confirmation failure after commit")

    monkeypatch.setattr(Session, "refresh", lost_confirmation)
    assert create(orders, payload).status_code == 500
    monkeypatch.setattr(Session, "refresh", original_refresh)
    with TestingSessionLocal() as db:
        persisted = db.query(InspectionOrder).one()
        oid = persisted.id

    def unavailable():
        raise AnalyticsSourceUnavailable()

    app.dependency_overrides[get_analytics_repository_provider] = lambda: unavailable
    replay = create(orders, payload)
    assert replay.status_code == 200 and replay.json()["id"] == oid
    assert orders.get(f"{ROOT}/orders/search").json()["pagination"]["total"] == 1


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
    from app.schemas.inspections import QueueOrderCreateRequest, OrderCreateRequest
    from app.services.inspections import create_from_queue, create_order, OrderConflictError
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
                for scenario in ("same_key", "different_keys", "different_versions", "manual_queue"):
                    barrier = Barrier(2)

                    def attempt(worker):
                        with Session(engine) as db:
                            barrier.wait(timeout=10)
                            try:
                                candidate = SyntheticAnalyticsRepository()
                                if scenario == "different_versions":
                                    candidate.source_version = f"version-{worker}"
                                selected = payload.model_copy(update={"source_version": candidate.source_version})
                                if scenario == "manual_queue" and worker == 0:
                                    row = create_order(db, OrderCreateRequest(uc_id="UC-1004", reason="manual"))
                                    created = True
                                else:
                                    row, created = create_from_queue(db, lambda: candidate, "UC-1004", selected,
                                        f"concurrent-{scenario}-" + ("same" if scenario == "same_key" else str(worker)))
                                return row.id, created
                            except OrderConflictError:
                                return None, False

                    with ThreadPoolExecutor(max_workers=2) as pool:
                        results = list(pool.map(attempt, (0, 1)))
                    assert sum(created for _, created in results) == 1
                    with Session(engine) as db:
                        row = db.query(InspectionOrder).one()
                        if scenario == "same_key":
                            assert results[0][0] == results[1][0] == row.id
                        else:
                            assert sum(oid is None for oid, _ in results) == 1
                        if row.suspicion_snapshot is not None:
                            assert row.suspicion_snapshot["data"]["priority"] == .92
                        db.delete(row)
                        db.commit()
    finally:
        engine.dispose()
