import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.operational import InspectionOrder
from app.models.operational import OrderStatus
from app.schemas.inspections import OrderCreateRequest, OrderUpdateRequest
from app.services import inspections as inspection_service
from tests.conftest import TestingSessionLocal, test_engine


@pytest.fixture(autouse=True)
def order_writer(client, monkeypatch):
    token = "isolated-writer-" + "x" * 32
    monkeypatch.setattr("app.core.config.settings.ORDERS_WRITE_TOKEN", SecretStr(token))
    monkeypatch.setattr("app.core.config.settings.ORDERS_READ_TOKEN", None)
    client.headers["Authorization"] = "Bearer " + token


def test_order_creation_persists_and_keeps_existing_response_contract(client):
    created = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-TEST-001", "reason": "Inspeção solicitada"},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["uc_id"] == "UC-TEST-001"
    assert body["reason"] == "Inspeção solicitada"
    assert body["priority"] == "MEDIA"
    assert body["status"] == "PENDENTE"
    assert body["notes"] is None
    assert body["result"] is None
    assert body["id"] > 0
    assert body["created_at"]
    assert body["updated_at"]

    listed = client.get("/api/v1/inspections/orders")
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)
    assert [order["id"] for order in listed.json()] == [body["id"]]


def test_orders_can_be_filtered_by_existing_status_enum(client):
    pending = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-PENDING", "reason": "Pendente"},
    ).json()
    in_progress = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-IN-PROGRESS", "reason": "Em andamento"},
    ).json()
    client.patch(
        f"/api/v1/inspections/orders/{in_progress['id']}",
        json={"version": 1, "status": "EM_ANDAMENTO"},
    )

    response = client.get("/api/v1/inspections/orders?status=PENDENTE")

    assert response.status_code == 200
    assert [order["id"] for order in response.json()] == [pending["id"]]


def test_order_update_changes_only_supplied_fields(client):
    created = client.post(
        "/api/v1/inspections/orders",
        json={
            "uc_id": "UC-UPDATE",
            "reason": "Checar medidor",
            "notes": "Observação inicial",
        },
    ).json()

    updated = client.patch(
        f"/api/v1/inspections/orders/{created['id']}",
        json={"version": 1, "status": "EM_ANDAMENTO", "result": "Medidor em análise"},
    )

    assert updated.status_code == 200
    assert updated.json()["status"] == "EM_ANDAMENTO"
    assert updated.json()["notes"] == "Observação inicial"
    assert updated.json()["result"] == "Medidor em análise"


def test_updating_missing_order_keeps_http_404_contract(client):
    response = client.patch(
        "/api/v1/inspections/orders/987654",
        json={"version": 1, "status": "EM_ANDAMENTO"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Ordem de inspeção não encontrada."


def test_invalid_request_field_types_are_rejected_by_http_contract(client):
    invalid_create = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": 123, "reason": "Inspeção", "priority": []},
    )
    created = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-INVALID-UPDATE", "reason": "Inspeção"},
    ).json()
    invalid_update = client.patch(
        f"/api/v1/inspections/orders/{created['id']}",
        json={"version": 1, "status": "STATUS_DESCONHECIDO"},
    )

    assert invalid_create.status_code == 422
    assert invalid_update.status_code == 422
    assert client.get("/api/v1/inspections/orders").json() == [created]


def test_database_errors_roll_back_order_writes(client):
    with test_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TRIGGER fail_order_insert BEFORE INSERT "
                "ON operational_inspection_orders BEGIN "
                "SELECT RAISE(ABORT, 'forced insert failure'); END"
            )
        )

    try:
        failed_create = client.post(
            "/api/v1/inspections/orders",
            json={"uc_id": "UC-ROLLBACK-CREATE", "reason": "Falha simulada"},
        )
    finally:
        with test_engine.begin() as connection:
            connection.execute(text("DROP TRIGGER fail_order_insert"))

    assert failed_create.status_code == 500
    assert client.get("/api/v1/inspections/orders").json() == []

    created = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-ROLLBACK-UPDATE", "reason": "Atualizar"},
    ).json()
    with test_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TRIGGER fail_order_update BEFORE UPDATE "
                "ON operational_inspection_orders BEGIN "
                "SELECT RAISE(ABORT, 'forced update failure'); END"
            )
        )

    try:
        failed_update = client.patch(
            f"/api/v1/inspections/orders/{created['id']}",
            json={"version": 1, "status": "EM_ANDAMENTO"},
        )
    finally:
        with test_engine.begin() as connection:
            connection.execute(text("DROP TRIGGER fail_order_update"))

    assert failed_update.status_code == 500
    db = TestingSessionLocal()
    try:
        persisted = db.query(InspectionOrder).filter_by(id=created["id"]).one()
        assert persisted.status.value == "PENDENTE"
    finally:
        db.close()


def test_service_rollback_keeps_same_session_usable_after_insert_and_update_errors(
    tmp_path,
):
    database_path = (tmp_path / "same_session_rollback.sqlite").as_posix()
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    create_payload = OrderCreateRequest(
        uc_id="UC-SAME-SESSION", reason="Teste de rollback"
    )

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TRIGGER fail_order_insert BEFORE INSERT "
                    "ON operational_inspection_orders BEGIN "
                    "SELECT RAISE(ABORT, 'forced insert failure'); END"
                )
            )

        with pytest.raises(IntegrityError):
            inspection_service.create_order(db, create_payload)

        # Use a separate connection to remove the fault while keeping `db` alive.
        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER fail_order_insert"))

        assert db.query(InspectionOrder).count() == 0
        created = inspection_service.create_order(db, create_payload)
        assert created.status == OrderStatus.PENDING

        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TRIGGER fail_order_update BEFORE UPDATE "
                    "ON operational_inspection_orders BEGIN "
                    "SELECT RAISE(ABORT, 'forced update failure'); END"
                )
            )

        with pytest.raises(IntegrityError):
            inspection_service.update_order(
                db,
                created.id,
                OrderUpdateRequest(version=1, status=OrderStatus.IN_PROGRESS),
            )

        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER fail_order_update"))

        persisted = db.query(InspectionOrder).filter_by(id=created.id).one()
        assert persisted.status == OrderStatus.PENDING
        updated = inspection_service.update_order(
            db,
            created.id,
            OrderUpdateRequest(version=1, status=OrderStatus.IN_PROGRESS),
        )
        assert updated.status == OrderStatus.IN_PROGRESS
    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
