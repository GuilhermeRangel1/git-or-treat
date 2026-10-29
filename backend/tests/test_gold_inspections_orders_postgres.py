"""Opt-in end-to-end Gold queue/order preservation on a disposable PostgreSQL database."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, inspect, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.main import app
from app.models.gold_load import BATCH
from app.repositories import gold_context
from app.services.gold_import import GoldImportError, import_gold


@pytest.fixture
def gold_postgres(tmp_path, monkeypatch):
    url = os.environ.get("TEST_GOLD_ORDERS_POSTGRES_URL")
    if not url:
        pytest.skip("Defina TEST_GOLD_ORDERS_POSTGRES_URL para PostgreSQL descartável exclusivo de ordens.")
    parsed = make_url(url)
    assert parsed.get_backend_name() == "postgresql" and parsed.database.endswith("_test")
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True)
    with engine.connect() as connection:
        assert not inspect(connection).get_table_names(), "O banco PostgreSQL de ordens deve estar vazio."
        assert connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")) is False
    Base.metadata.create_all(engine)

    monkeypatch.setattr(settings, "ANALYTICS_SOURCE", "gold")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "service")
    write_token = "gold-orders-write-" + "w" * 40
    read_token = "gold-orders-read-" + "r" * 40
    monkeypatch.setattr(settings, "ORDERS_WRITE_TOKEN", SecretStr(write_token))
    monkeypatch.setattr(settings, "ORDERS_READ_TOKEN", SecretStr(read_token))
    monkeypatch.setattr(gold_context, "engine", engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def write_batch(folder: Path, *, include_uc: bool):
        from tests.test_gold_import import SAMPLES

        for name, (header, rows) in SAMPLES.items():
            if not include_uc:
                replacement_rows = {
                    "fila_inspecao": "FAKE-B;Cidade fictícia;Bairro fictício;PE;Residencial;B1;FAKE-AL;2020-01-01;ATIVA;Não;0;0;;BAIXA",
                    "variacao_consumo_uc": "FAKE-B;Cidade fictícia;Bairro fictício;Não;;0;;0;;;false",
                    "visao_360_uc": "FAKE-B;Cidade fictícia;Bairro fictício;PE;Residencial;B1;FAKE-AL;2020-01-01;ATIVA;Não;0;;1;1;10",
                }
                if name in replacement_rows:
                    rows = [replacement_rows[name]]
            table_folder = folder / name
            table_folder.mkdir(parents=True)
            (table_folder / "part-1.csv").write_text(
                header + "\n" + "\n".join(rows) + "\n", encoding="utf-8",
            )

    folder = tmp_path / "first"
    folder.mkdir()
    write_batch(folder, include_uc=True)
    import_gold(engine, folder, "fake-gold-1")
    try:
        yield engine, folder, write_batch, write_token, read_token, override_db
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_gold_queue_order_replay_reload_failure_and_removed_uc_preserve_snapshot(gold_postgres):
    engine, first_batch, write_batch, write_token, read_token, override_db = gold_postgres
    from app.core.database import get_db

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            client.headers["Authorization"] = f"Bearer {read_token}"
            queue = client.get("/api/v1/inspections/queue")
            assert queue.status_code == 200
            body = queue.json()
            assert body["metadata"]["period"] is None
            assert body["metadata"]["temporal_scope"] == "snapshot"
            assert body["metadata"]["source"]["version"] == "fake-gold-1"
            assert body["data"]["items"][0]["category"] == "REVISAR"
            assert body["data"]["items"][0]["potential_recoverable_energy_kwh"] is None
            assert body["data"]["items"][0]["variation"]["p1_start"] == "2022-07"
            assert body["data"]["items"][0]["variation"]["p2_end"] == "2026-06"
            client.headers.pop("Authorization")
            assert client.get("/api/v1/inspections/queue").status_code == 401
            client.headers["Authorization"] = f"Bearer {read_token}"
            assert client.get("/api/v1/inspections/queue?order_by=priority").status_code == 422
            assert client.get("/api/v1/inspections/queue?order_by=category").json()["data"]["items"][0]["uc_id"] == "FAKE-A"
            assert client.get("/api/v1/inspections/queue?expected_lote=old-lote").status_code == 409
            fingerprint = body["metadata"]["fingerprint"]
            assert client.get(
                "/api/v1/inspections/queue?expected_fingerprint=" + "0" * 64
            ).status_code == 409

            detail = client.get(
                f"/api/v1/inspections/queue/FAKE-A?expected_lote=fake-gold-1&expected_fingerprint={fingerprint}"
            ).json()
            assert client.get("/api/v1/inspections/queue/FAKE-A?expected_lote=old-lote").status_code == 409
            payload = {
                "source_version": "fake-gold-1",
                "source_fingerprint": fingerprint,
                "rule_version": detail["data"]["rule_version"],
                "priority": "MEDIA",
            }
            client.headers["Authorization"] = f"Bearer {write_token}"
            headers = {"Idempotency-Key": "gold-postgres-test-0001"}
            created = client.post("/api/v1/inspections/queue/FAKE-A/orders", json=payload, headers=headers)
            assert created.status_code == 201
            snapshot = created.json()["suspicion_snapshot"]
            assert snapshot["snapshot_schema_version"] == "2"
            assert snapshot["data"]["category"] == "REVISAR"
            assert snapshot["data"]["evidence"]["inspections_performed"] == 0
            assert snapshot["data"]["variation"]["p1_months_observed"] == 0
            assert created.json()["priority"] == "MEDIA"

            repeated = client.post("/api/v1/inspections/queue/FAKE-A/orders", json=payload, headers=headers)
            assert repeated.status_code == 200
            assert repeated.json()["suspicion_snapshot"] == snapshot
            order_id = created.json()["id"]
            assert client.patch(f"/api/v1/inspections/orders/{order_id}", json={"version": 1, "status": "EM_ANDAMENTO"}).status_code == 200
            completed = client.post(
                f"/api/v1/inspections/orders/{order_id}/result",
                json={"version": 2, "result": "Sem irregularidade"},
            )
            assert completed.status_code == 200
            history = client.get(f"/api/v1/inspections/orders/{order_id}/history").json()
            assert [event["order_version"] for event in history] == [1, 2, 3]

            published_before = client.get("/api/v1/inspections/queue").json()["metadata"]["source"]["version"]
            queue_before_failure = client.get("/api/v1/inspections/queue").json()
            history_before_failure = client.get(f"/api/v1/inspections/orders/{order_id}/history").json()
            assert import_gold(engine, first_batch, "fake-gold-1")["status"] == "unchanged"
            assert client.get("/api/v1/inspections/queue").json()["metadata"]["source"]["version"] == published_before

            bad_reload = first_batch / "visao_360_uc" / "part-1.csv"
            prior_bytes = bad_reload.read_bytes()
            bad_reload.write_text("wrong_header\nbroken\n", encoding="utf-8")
            with pytest.raises(GoldImportError):
                import_gold(engine, first_batch, "failed-reload")
            bad_reload.write_bytes(prior_bytes)
            assert client.get("/api/v1/inspections/queue").json() == queue_before_failure
            assert client.get(f"/api/v1/inspections/orders/{order_id}").json()["suspicion_snapshot"] == snapshot
            assert client.get(f"/api/v1/inspections/orders/{order_id}/history").json() == history_before_failure
            assert client.get("/api/v1/inspections/queue").json()["metadata"]["source"]["version"] == published_before

            replacement = first_batch.parent / "replacement"
            replacement.mkdir()
            write_batch(replacement, include_uc=False)
            import_gold(engine, replacement, "fake-gold-2")
            assert client.get("/api/v1/inspections/queue/FAKE-A").status_code == 404
            historical = client.get(f"/api/v1/inspections/orders/{order_id}").json()
            assert historical["suspicion_snapshot"] == snapshot
            assert client.post("/api/v1/inspections/queue/FAKE-A/orders", json=payload, headers=headers).status_code == 200
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def test_publication_lock_serializes_concurrent_queue_order_creation(gold_postgres):
    from app.models.operational import InspectionOrder, OperationalOrderHistory
    from app.repositories.gold_context import load_gold_context
    from app.repositories.gold_inspections import GoldInspectionRepository
    from app.schemas.inspections import QueueOrderCreateRequest
    from app.services.inspection_analytics import build_gold_suspicion_response
    from app.services.inspections import OrderConflictError, create_from_queue

    engine, _, _, _, _, _ = gold_postgres
    attempted_shared_lock = Event()
    executor = ThreadPoolExecutor(max_workers=1)
    lock_connection = engine.connect()
    lock_transaction = None
    pending_request = None
    listener_registered = False

    def mark_lock_attempt(connection, cursor, statement, parameters, context, executemany):
        if "pg_advisory_xact_lock_shared(73460127)" in statement:
            attempted_shared_lock.set()

    def create_in_worker(payload, key):
        with Session(engine) as db:
            return create_from_queue(
                db, lambda: None, "FAKE-A", payload, key, actor="orders-writer-test",
            )

    try:
        with engine.connect() as read_connection, read_connection.begin():
            context = load_gold_context(read_connection)
            detail = build_gold_suspicion_response(GoldInspectionRepository(context), "FAKE-A")
        payload = QueueOrderCreateRequest(
            source_version=context.lote,
            source_fingerprint=context.fingerprint,
            rule_version=detail.data.rule_version,
            priority="MEDIA",
        )

        lock_transaction = lock_connection.begin()
        lock_connection.execute(text("SELECT pg_advisory_xact_lock(73460127)"))
        event.listen(engine, "before_cursor_execute", mark_lock_attempt)
        listener_registered = True
        pending_request = executor.submit(
            create_in_worker, payload, "gold-concurrent-publication-0001",
        )
        assert attempted_shared_lock.wait(timeout=5), "A criação não chegou ao lock compartilhado."

        deadline = time.monotonic() + 5
        blocked_waiters = 0
        while time.monotonic() < deadline:
            blocked_waiters = lock_connection.execute(text(
                "SELECT count(*) FROM pg_locks "
                "WHERE locktype = 'advisory' AND NOT granted "
                "AND classid = 0 AND objid = 73460127 AND objsubid = 1"
            )).scalar_one()
            if blocked_waiters:
                break
            time.sleep(0.01)
        assert blocked_waiters > 0, "A criação não aguardou a trava exclusiva observada em pg_locks."

        lock_connection.execute(update(BATCH).where(BATCH.c.id == 1).values(
            lote="fake-gold-2", fingerprint="b" * 64,
        ))
        lock_transaction.commit()
        lock_transaction = None

        with pytest.raises(OrderConflictError) as stale:
            pending_request.result(timeout=10)
        assert stale.value.code == "stale_suspicion"
    finally:
        if lock_transaction is not None and lock_transaction.is_active:
            lock_transaction.rollback()
        if listener_registered:
            event.remove(engine, "before_cursor_execute", mark_lock_attempt)
        lock_connection.close()
        if pending_request is not None:
            try:
                pending_request.result(timeout=10)
            except Exception:
                pass
        executor.shutdown(wait=True, cancel_futures=True)

    with Session(engine) as session:
        assert session.query(InspectionOrder).count() == 0
        assert session.query(OperationalOrderHistory).count() == 0
