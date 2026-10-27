"""Mandatory concurrency token and a single confirmed cancellation boundary."""
import pytest
from pydantic import SecretStr

from app.models.operational import OrderStatus
from app.schemas.inspections import OrderUpdateRequest
from app.services import inspections as service
from tests.conftest import TestingSessionLocal

ROOT = "/api/v1/inspections/orders"


@pytest.fixture
def writer(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ORDERS_WRITE_TOKEN", SecretStr("contract-writer-" + "x" * 32))
    client.headers["Authorization"] = "Bearer " + "contract-writer-" + "x" * 32
    return client


def create(writer):
    response = writer.post(ROOT, json={"uc_id": "CONTRACT-UC", "reason": "Inspeção sintética"})
    assert response.status_code == 201
    return response.json()["id"]


def mutate(writer, oid, operation, version):
    if operation == "patch":
        return writer.patch(f"{ROOT}/{oid}", json={"notes": "Atualizada", **version})
    payload = {"result": "Conferido"} if operation == "result" else {"confirmed_order_id": oid}
    return writer.post(f"{ROOT}/{oid}/{operation}", json={**payload, **version})


@pytest.mark.parametrize("operation", ["patch", "result", "cancel"])
@pytest.mark.parametrize("version", [{}, {"version": None}, {"version": 0}, {"version": -1}, {"version": True}, {"version": "1"}, {"version": 1.5}])
def test_missing_or_invalid_version_never_mutates(writer, operation, version):
    oid = create(writer)
    assert mutate(writer, oid, operation, version).status_code == 422
    assert writer.get(f"{ROOT}/{oid}").json()["version"] == 1
    assert len(writer.get(f"{ROOT}/{oid}/history").json()) == 1


@pytest.mark.parametrize("operation", ["patch", "result", "cancel"])
def test_old_screen_conflicts_after_other_request_has_already_committed(writer, operation):
    oid = create(writer)
    assert writer.patch(f"{ROOT}/{oid}", json={"version": 1, "status": "EM_ANDAMENTO"}).status_code == 200
    stale = writer.get(f"{ROOT}/{oid}").json()
    assert writer.patch(f"{ROOT}/{oid}", json={"version": stale["version"], "notes": "Vencedora"}).status_code == 200
    response = mutate(writer, oid, operation, {"version": stale["version"]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_conflict"
    current = writer.get(f"{ROOT}/{oid}").json()
    assert current["status"] == "EM_ANDAMENTO" and current["notes"] == "Vencedora" and current["version"] == 3
    assert len(writer.get(f"{ROOT}/{oid}/history").json()) == 3


def test_patch_cannot_bypass_confirmation_even_for_service_callers(writer):
    oid = create(writer)
    response = writer.patch(f"{ROOT}/{oid}", json={"version": 1, "status": "CANCELADA"})
    assert response.status_code == 422
    with TestingSessionLocal() as db:
        forged = OrderUpdateRequest.model_construct(version=1, status=OrderStatus.CANCELLED)
        with pytest.raises(service.OrderConflictError, match="confirme o ID"):
            service.update_order(db, oid, forged)
    assert writer.get(f"{ROOT}/{oid}").json()["status"] == "PENDENTE"
    assert len(writer.get(f"{ROOT}/{oid}/history").json()) == 1
    wrong = writer.post(f"{ROOT}/{oid}/cancel", json={"version": 1, "confirmed_order_id": oid + 1})
    assert wrong.status_code == 409 and wrong.json()["error"]["code"] == "confirmation_mismatch"
    assert writer.post(f"{ROOT}/{oid}/cancel", json={"version": 1, "confirmed_order_id": oid}).status_code == 200
    # Old request cannot repeat effects; the client reconciles a lost response by GET.
    assert writer.post(f"{ROOT}/{oid}/cancel", json={"version": 1, "confirmed_order_id": oid}).status_code == 409
    assert writer.post(f"{ROOT}/{oid}/cancel", json={"version": 2, "confirmed_order_id": oid}).status_code == 200
    assert len(writer.get(f"{ROOT}/{oid}/history").json()) == 2


def test_swagger_publishes_required_versions_examples_and_allowed_states(writer):
    schemas = writer.get("/openapi.json").json()["components"]["schemas"]
    for name in ("OrderUpdateRequest", "OrderResultRequest", "OrderCancelRequest"):
        schema = schemas[name]
        assert "version" in schema["required"]
        assert schema["properties"]["version"]["type"] == "integer"
        assert schema["properties"]["version"]["minimum"] == 1
        assert all(example["version"] >= 1 for example in schema["examples"])
    statuses = schemas["OrderUpdateRequest"]["properties"]["status"]["anyOf"][0]["enum"]
    assert "CANCELADA" not in statuses
    assert "confirmed_order_id" in schemas["OrderCancelRequest"]["required"]
