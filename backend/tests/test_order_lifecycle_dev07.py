"""WEB-05: HTTP, durable audit, independent sessions and legacy migrations."""
import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from alembic import command

from app.models.operational import InspectionOrder, OperationalOrderHistory, OrderStatus
from app.schemas.inspections import OrderUpdateRequest
from app.services import inspections as service
from tests.conftest import TestingSessionLocal, test_engine
from tests.test_migrations import alembic_config

ROOT = "/api/v1/inspections/orders"


@pytest.fixture
def writer(client, monkeypatch):
    token = "dev07-test-" + "w" * 32
    monkeypatch.setattr("app.core.config.settings.ORDERS_WRITE_TOKEN", SecretStr(token))
    client.headers["Authorization"] = "Bearer " + token
    return client


def create(writer):
    response = writer.post(ROOT, json={"uc_id": "UC-DEV07", "reason": "Verificar medidor"})
    assert response.status_code == 201
    return response.json()


def test_full_lifecycle_persists_actor_versions_and_results(writer):
    order = create(writer)
    oid = order["id"]
    started = writer.patch(f"{ROOT}/{oid}", json={"status": "EM_ANDAMENTO", "version": 1})
    assert started.status_code == 200
    done = writer.post(f"{ROOT}/{oid}/result", json={"result": "  Sem irregularidade  ", "version": 2})
    assert done.status_code == 200
    assert done.json()["version"] == 3
    history = writer.get(f"{ROOT}/{oid}/history").json()
    assert [e["action"] for e in history] == ["CRIACAO", "ATUALIZACAO_STATUS", "REGISTRO_RESULTADO"]
    assert [e["order_version"] for e in history] == [1, 2, 3]
    assert all(e["actor"] and e["created_at"].endswith("Z") for e in history)
    assert "Sem irregularidade" in history[-1]["details"]
    with TestingSessionLocal() as db:
        persisted = db.get(InspectionOrder, oid)
        assert persisted.status == OrderStatus.COMPLETED
        assert persisted.result == "Sem irregularidade"
        assert db.query(OperationalOrderHistory).filter_by(order_id=oid).count() == 3
    # Repeat the acknowledged result without duplicating audit/version.
    assert writer.post(f"{ROOT}/{oid}/result", json={"result": "Sem irregularidade"}).json()["version"] == 3
    assert len(writer.get(f"{ROOT}/{oid}/history").json()) == 3
    for payload in ({"notes": "alterar"}, {"result": "outro"}, {"status": "PENDENTE"}):
        assert writer.patch(f"{ROOT}/{oid}", json=payload).status_code == 409


def test_identified_cancellation_reopen_regression_and_retries(writer):
    order = create(writer)
    oid = order["id"]
    assert writer.post(f"{ROOT}/{oid}/cancel", json={}).status_code == 422
    assert writer.post(f"{ROOT}/{oid}/cancel", json={"confirmed_order_id": oid + 1}).status_code == 409
    payload = {"confirmed_order_id": oid, "reason": "Duplicidade verificada"}
    cancelled = writer.post(f"{ROOT}/{oid}/cancel", json=payload)
    assert cancelled.status_code == 200
    assert cancelled.json()["cancellation_reason"] == payload["reason"]
    assert writer.post(f"{ROOT}/{oid}/cancel", json=payload).json()["version"] == 2
    for state in ("PENDENTE", "EM_ANDAMENTO", "CONCLUIDA"):
        assert writer.patch(f"{ROOT}/{oid}", json={"status": state, "result": "tentativa"}).status_code == 409
    assert writer.post(f"{ROOT}/{oid}/result", json={"result": "tentativa"}).status_code == 409
    assert writer.get(f"{ROOT}/{oid}").json()["status"] == "CANCELADA"
    assert len(writer.get(f"{ROOT}/{oid}/history").json()) == 2
    assert writer.post(ROOT, json={"uc_id": "UC-DEV07", "reason": "Novo ciclo"}).status_code == 201


@pytest.mark.parametrize("payload", [{}, {"version": 1}, {"version": 0, "notes": "n"}, {"version": True, "notes": "n"}, {"result": "   "}, {"status": "INVENTADO"}])
def test_invalid_changes_do_not_write(writer, payload):
    order = create(writer)
    assert writer.patch(f"{ROOT}/{order['id']}", json=payload).status_code == 422
    assert len(writer.get(f"{ROOT}/{order['id']}/history").json()) == 1


def test_required_result_stale_version_and_invalid_transition(writer):
    oid = create(writer)["id"]
    assert writer.patch(f"{ROOT}/{oid}", json={"status": "CONCLUIDA"}).status_code == 409
    assert writer.post(f"{ROOT}/{oid}/result", json={"result": "  "}).status_code == 422
    assert writer.patch(f"{ROOT}/{oid}", json={"notes": "primeiro", "version": 1}).status_code == 200
    conflict = writer.patch(f"{ROOT}/{oid}", json={"notes": "obsoleto", "version": 1})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "version_conflict"
    writer.patch(f"{ROOT}/{oid}", json={"status": "EM_ANDAMENTO"})
    assert writer.patch(f"{ROOT}/{oid}", json={"status": "PENDENTE"}).status_code == 409


def test_independent_sessions_cannot_overwrite_same_status_updates(writer):
    oid = create(writer)["id"]
    with TestingSessionLocal() as first, TestingSessionLocal() as second:
        stale = second.get(InspectionOrder, oid)
        service.update_order(first, oid, OrderUpdateRequest(notes="Primeira alteração"))
        assert stale.version == 1
        with pytest.raises(service.OrderConflictError):
            service.update_order(second, oid, OrderUpdateRequest(notes="Sobrescrita concorrente"))
    assert writer.get(f"{ROOT}/{oid}").json()["notes"] == "Primeira alteração"
    assert len(writer.get(f"{ROOT}/{oid}/history").json()) == 2


def test_history_failure_rolls_back_order_and_version(writer):
    oid = create(writer)["id"]
    with test_engine.begin() as conn:
        conn.execute(text("CREATE TRIGGER fail_history BEFORE INSERT ON operational_order_history BEGIN SELECT RAISE(ABORT, 'audit failure'); END"))
    try:
        assert writer.patch(f"{ROOT}/{oid}", json={"status": "EM_ANDAMENTO"}).status_code == 500
        assert writer.post(ROOT, json={"uc_id": "UC-ROLLBACK", "reason": "teste"}).status_code == 500
    finally:
        with test_engine.begin() as conn:
            conn.execute(text("DROP TRIGGER fail_history"))
    order = writer.get(f"{ROOT}/{oid}").json()
    assert order["status"] == "PENDENTE" and order["version"] == 1
    assert len(writer.get(f"{ROOT}/{oid}/history").json()) == 1
    assert len(writer.get(ROOT).json()) == 1


def test_new_routes_require_access_and_report_missing_order(writer):
    for route, payload in (("history", None), ("result", {"result": "r"}), ("cancel", {"confirmed_order_id": 999})):
        response = writer.get(f"{ROOT}/999/{route}") if payload is None else writer.post(f"{ROOT}/999/{route}", json=payload)
        assert response.status_code == 404
    oid = create(writer)["id"]
    writer.headers.pop("Authorization")
    assert writer.get(f"{ROOT}/{oid}/history").status_code == 401
    assert writer.post(f"{ROOT}/{oid}/result", json={"result": "r"}).status_code == 401
    assert writer.post(f"{ROOT}/{oid}/cancel", json={"confirmed_order_id": oid}).status_code == 401


@pytest.mark.parametrize("revision", ["c4b1a239d8e7", "a6d060000002"])
def test_migrate_both_branches_preserves_existing_order(tmp_path, revision):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy_test.db'}")
    with engine.connect() as conn:
        config = alembic_config(conn)
        command.upgrade(config, revision)
        conn.execute(text("INSERT INTO operational_inspection_orders (uc_id, reason, priority, status, created_at, updated_at, idempotency_key) VALUES ('LEGACY', 'preservar', 'MEDIA', 'CANCELLED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'legacy-idempotency-0001')"))
        if revision == "c4b1a239d8e7":
            conn.execute(text("INSERT INTO operational_order_history (order_id, previous_status, new_status, action, details, created_at) SELECT id, 'PENDING', 'CANCELLED', 'CANCELLED', 'motivo legado', CURRENT_TIMESTAMP FROM operational_inspection_orders WHERE uc_id = 'LEGACY'"))
        conn.commit()
        command.upgrade(config, "head")
        conn.commit()
    with Session(engine) as db:
        order = db.query(InspectionOrder).filter_by(uc_id="LEGACY").one()
        assert order.status == OrderStatus.CANCELLED and order.version == 1
        assert order.idempotency_key == "legacy-idempotency-0001"
        if revision == "c4b1a239d8e7":
            event = db.query(OperationalOrderHistory).one()
            assert event.details == "motivo legado" and event.actor is None
        with pytest.raises(service.OrderConflictError):
            service.update_order(db, order.id, OrderUpdateRequest(status=OrderStatus.PENDING))
    with engine.connect() as conn:
        command.downgrade(alembic_config(conn), "base")
    engine.dispose()


def test_queue_replay_keeps_one_creation_history(writer):
    from app.main import app
    from app.repositories.analytics import SyntheticAnalyticsRepository, get_analytics_repository, get_analytics_repository_provider
    app.dependency_overrides[get_analytics_repository] = SyntheticAnalyticsRepository
    app.dependency_overrides[get_analytics_repository_provider] = lambda: SyntheticAnalyticsRepository
    root = "/api/v1/inspections"
    detail = writer.get(f"{root}/queue/UC-1004").json()
    payload = {"source_version": detail["metadata"]["source"]["version"], "rule_version": detail["data"]["rule_version"]}
    first = writer.post(f"{root}/queue/UC-1004/orders", json=payload, headers={"Idempotency-Key": "dev07-queue-audit-001"})
    assert first.status_code == 201
    replay = writer.post(f"{root}/queue/UC-1004/orders", json=payload, headers={"Idempotency-Key": "dev07-queue-audit-001"})
    assert replay.status_code == 200 and replay.json() == first.json()
    history = writer.get(f"{ROOT}/{first.json()['id']}/history").json()
    assert len(history) == 1 and history[0]["action"] == "CRIACAO"
