import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.operational import InspectionOrder
from app.models.operational import OrderStatus
from app.schemas.inspections import OrderCreateRequest, OrderUpdateRequest
from app.services import inspections as inspection_service
from tests.conftest import TestingSessionLocal, test_engine


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
        json={"status": "EM_ANDAMENTO"},
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
        json={"status": "EM_ANDAMENTO", "result": "Medidor em análise"},
    )

    assert updated.status_code == 200
    assert updated.json()["status"] == "EM_ANDAMENTO"
    assert updated.json()["notes"] == "Observação inicial"
    assert updated.json()["result"] == "Medidor em análise"


def test_updating_missing_order_keeps_http_404_contract(client):
    response = client.patch(
        "/api/v1/inspections/orders/987654",
        json={"status": "EM_ANDAMENTO"},
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
        json={"status": "STATUS_DESCONHECIDO"},
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
            json={"status": "EM_ANDAMENTO"},
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
                OrderUpdateRequest(status=OrderStatus.IN_PROGRESS),
            )

        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER fail_order_update"))

        persisted = db.query(InspectionOrder).filter_by(id=created.id).one()
        assert persisted.status == OrderStatus.PENDING
        updated = inspection_service.update_order(
            db,
            created.id,
            OrderUpdateRequest(status=OrderStatus.IN_PROGRESS),
        )
        assert updated.status == OrderStatus.IN_PROGRESS
    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_mandatory_fields_and_priority_validation(client):
    res1 = client.post("/api/v1/inspections/orders", json={"uc_id": "   ", "reason": "Motivo"})
    assert res1.status_code == 422

    res2 = client.post("/api/v1/inspections/orders", json={"uc_id": "UC-VAL-1", "reason": "   "})
    assert res2.status_code == 422

    res3 = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-VAL-1", "reason": "Motivo", "priority": "URGENTISSIMA"},
    )
    assert res3.status_code == 422

    res4 = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-VAL-1", "reason": "Motivo", "priority": "ALTA"},
    )
    assert res4.status_code == 201
    assert res4.json()["priority"] == "ALTA"


def test_allowed_state_transitions_full_cycle(client):
    created = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-CYCLE-1", "reason": "Checar suspeita de fraude"},
    ).json()
    order_id = created["id"]
    assert created["status"] == "PENDENTE"
    assert created["version"] == 1

    to_in_progress = client.patch(
        f"/api/v1/inspections/orders/{order_id}",
        json={"status": "EM_ANDAMENTO", "notes": "Técnico a caminho"},
    )
    assert to_in_progress.status_code == 200
    assert to_in_progress.json()["status"] == "EM_ANDAMENTO"
    assert to_in_progress.json()["version"] == 2

    to_completed = client.post(
        f"/api/v1/inspections/orders/{order_id}/result",
        json={
            "result": "Fraude confirmada: medidor adulterado no borne",
            "notes": "Auto de infração lavrado",
        },
    )
    assert to_completed.status_code == 200
    assert to_completed.json()["status"] == "CONCLUIDA"
    assert to_completed.json()["result"] == "Fraude confirmada: medidor adulterado no borne"
    assert to_completed.json()["version"] == 3


def test_server_rejects_invalid_state_transitions(client):
    created = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-INVALID-TRANS", "reason": "Teste de transição inválida"},
    ).json()
    order_id = created["id"]

    invalid_comp = client.patch(
        f"/api/v1/inspections/orders/{order_id}",
        json={"status": "CONCLUIDA"},
    )
    assert invalid_comp.status_code == 400
    assert "resultado de campo é obrigatório" in invalid_comp.json()["detail"].lower()


def test_field_result_registration_and_validation(client):
    created = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-RESULT-TEST", "reason": "Inspeção para resultado"},
    ).json()
    order_id = created["id"]

    empty_res = client.post(
        f"/api/v1/inspections/orders/{order_id}/result",
        json={"result": "   "},
    )
    assert empty_res.status_code == 422

    success_res = client.post(
        f"/api/v1/inspections/orders/{order_id}/result",
        json={
            "result": "Medidor operando normalmente sem divergências",
            "notes": "Verificado em 20/10",
        },
    )
    assert success_res.status_code == 200
    assert success_res.json()["status"] == "CONCLUIDA"
    assert success_res.json()["result"] == "Medidor operando normalmente sem divergências"

    dup_res = client.post(
        f"/api/v1/inspections/orders/{order_id}/result",
        json={"result": "Outro resultado"},
    )
    assert dup_res.status_code == 409


def test_order_cancellation_confirmation_and_identification(client):
    created = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-CANCEL-TEST", "reason": "Ordem a ser cancelada"},
    ).json()
    order_id = created["id"]

    cancelled = client.post(
        f"/api/v1/inspections/orders/{order_id}/cancel",
        json={"reason": "UC regularizada pelo cliente via agência"},
    )
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["id"] == order_id
    assert body["uc_id"] == "UC-CANCEL-TEST"
    assert body["status"] == "CANCELADA"
    assert body["cancellation_reason"] == "UC regularizada pelo cliente via agência"

    re_cancel = client.post(
        f"/api/v1/inspections/orders/{order_id}/cancel",
        json={"reason": "Tentando cancelar de novo"},
    )
    assert re_cancel.status_code == 409
    assert "já se encontra cancelada" in re_cancel.json()["detail"].lower()


def test_cannot_cancel_completed_order(client):
    created = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-CANCEL-COMPL", "reason": "Ordem a concluir"},
    ).json()
    order_id = created["id"]

    client.post(
        f"/api/v1/inspections/orders/{order_id}/result",
        json={"result": "Inspeção finalizada com sucesso"},
    )

    cancelled = client.post(
        f"/api/v1/inspections/orders/{order_id}/cancel",
        json={"reason": "Tentar cancelar ordem já concluída"},
    )
    assert cancelled.status_code == 409
    assert "já foi concluída" in cancelled.json()["detail"].lower()


def test_order_history_tracking_lifecycle(client):
    created = client.post(
        "/api/v1/inspections/orders",
        json={
            "uc_id": "UC-HIST-TEST",
            "reason": "Acompanhamento de histórico",
            "notes": "Nota inicial",
        },
    ).json()
    order_id = created["id"]

    client.patch(
        f"/api/v1/inspections/orders/{order_id}",
        json={"status": "EM_ANDAMENTO", "notes": "Em campo"},
    )

    client.post(
        f"/api/v1/inspections/orders/{order_id}/result",
        json={"result": "Irregularidade sanada", "notes": "Lacres trocados"},
    )

    history_resp = client.get(f"/api/v1/inspections/orders/{order_id}/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == 3

    assert history[0]["action"] == "CRIACAO"
    assert history[0]["previous_status"] is None
    assert history[0]["new_status"] == "PENDENTE"

    assert history[1]["action"] == "ATUALIZACAO_STATUS"
    assert history[1]["previous_status"] == "PENDENTE"
    assert history[1]["new_status"] == "EM_ANDAMENTO"

    assert history[2]["action"] == "REGISTRO_RESULTADO"
    assert history[2]["previous_status"] == "EM_ANDAMENTO"
    assert history[2]["new_status"] == "CONCLUIDA"


def test_idempotency_key_and_double_click_prevention(client):
    order1 = client.post(
        "/api/v1/inspections/orders",
        json={
            "uc_id": "UC-IDEMP-01",
            "reason": "Suspeita de derivação",
            "idempotency_key": "IDEMP-KEY-12345",
        },
    )
    assert order1.status_code == 201

    order2 = client.post(
        "/api/v1/inspections/orders",
        json={
            "uc_id": "UC-IDEMP-01",
            "reason": "Suspeita de derivação",
            "idempotency_key": "IDEMP-KEY-12345",
        },
    )
    assert order2.status_code == 201
    assert order2.json()["id"] == order1.json()["id"]

    order3 = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-IDEMP-02", "reason": "Outro motivo"},
        headers={"X-Idempotency-Key": "HEADER-KEY-999"},
    )
    assert order3.status_code == 201

    order4 = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-IDEMP-02", "reason": "Outro motivo"},
        headers={"X-Idempotency-Key": "HEADER-KEY-999"},
    )
    assert order4.status_code == 201
    assert order4.json()["id"] == order3.json()["id"]


def test_prevent_duplicate_active_orders_for_same_uc(client):
    client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-ACTIVE-DUP", "reason": "Primeira ordem"},
    )

    second = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-ACTIVE-DUP", "reason": "Segunda ordem indevida"},
    )
    assert second.status_code == 409
    assert "já existe uma ordem ativa" in second.json()["detail"].lower()


def test_can_reopen_inspection_for_uc_after_previous_order_cancelled_or_completed(client):
    first = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-REOPEN-CYCLE", "reason": "Primeira inspeção"},
    ).json()
    client.post(f"/api/v1/inspections/orders/{first['id']}/cancel")

    second = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-REOPEN-CYCLE", "reason": "Nova inspeção meses depois"},
    )
    assert second.status_code == 201
    assert second.json()["id"] != first["id"]


def test_optimistic_concurrency_control_with_versioning(client):
    created = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-CONCURRENCY", "reason": "Teste de concorrência"},
    ).json()
    order_id = created["id"]
    assert created["version"] == 1

    update_a = client.patch(
        f"/api/v1/inspections/orders/{order_id}",
        json={"status": "EM_ANDAMENTO", "version": 1},
    )
    assert update_a.status_code == 200
    assert update_a.json()["version"] == 2

    update_b = client.patch(
        f"/api/v1/inspections/orders/{order_id}",
        json={"notes": "Tentativa concorrente de alteração", "version": 1},
    )
    assert update_b.status_code == 409
    assert "conflito de concorrência" in update_b.json()["detail"].lower()


def test_prototype_regression_cancelled_order_cannot_be_reactivated(client):
    """
    Verificação da regressão observada no protótipo Figma (docs/design/grid360-prototype.md):
    Depois de cancelar a ordem OS-DEMO-001, reabrir ações não pode reativar indevidamente a ordem cancelada.
    """
    created = client.post(
        "/api/v1/inspections/orders",
        json={"uc_id": "UC-REGRESSION-CHECK", "reason": "Ordem para testar regressão"},
    ).json()
    order_id = created["id"]

    cancel_resp = client.post(f"/api/v1/inspections/orders/{order_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELADA"

    reactivate_patch = client.patch(
        f"/api/v1/inspections/orders/{order_id}",
        json={"status": "EM_ANDAMENTO"},
    )
    assert reactivate_patch.status_code == 409
    assert "já está cancelada" in reactivate_patch.json()["detail"].lower()

    reopen_patch = client.patch(
        f"/api/v1/inspections/orders/{order_id}",
        json={"status": "PENDENTE"},
    )
    assert reopen_patch.status_code == 409

    result_attempt = client.post(
        f"/api/v1/inspections/orders/{order_id}/result",
        json={"result": "Resultado em ordem cancelada"},
    )
    assert result_attempt.status_code == 409
    assert "já se encontra cancelada" in result_attempt.json()["detail"].lower()

    persisted = client.get(f"/api/v1/inspections/orders/{order_id}").json()
    assert persisted["status"] == "CANCELADA"
