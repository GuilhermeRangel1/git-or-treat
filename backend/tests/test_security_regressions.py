import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.middleware.request_limits import MAX_BODY_BYTES

ORDER_URL = "/api/v1/inspections/orders"


@pytest.fixture
def tokens(monkeypatch):
    read = "isolated-reader-" + "r" * 32
    write = "isolated-writer-" + "w" * 32
    monkeypatch.setattr("app.core.config.settings.ORDERS_READ_TOKEN", SecretStr(read))
    monkeypatch.setattr("app.core.config.settings.ORDERS_WRITE_TOKEN", SecretStr(write))
    return {"read": {"Authorization": "Bearer " + read}, "write": {"Authorization": "Bearer " + write}}


def create(client, tokens):
    response = client.post(ORDER_URL, headers=tokens["write"], json={"uc_id": "SECURITY-TEST", "reason": "Inspeção sintética"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize("method,path,payload", [
    ("GET", ORDER_URL, None),
    ("POST", ORDER_URL, {"uc_id": "TEST", "reason": "Inspeção"}),
    ("PATCH", ORDER_URL + "/1", {"status": "EM_ANDAMENTO"}),
])
def test_orders_deny_anonymous_requests(client, method, path, payload):
    response = client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_read_only_credential_cannot_write(client, tokens):
    assert client.get(ORDER_URL, headers=tokens["read"]).status_code == 200
    assert client.post(ORDER_URL, headers=tokens["read"], json={"uc_id": "TEST", "reason": "Inspeção"}).status_code == 403
    assert client.patch(ORDER_URL + "/1", headers=tokens["read"], json={"notes": "Não permitido"}).status_code == 403
    assert client.get(ORDER_URL, headers=tokens["write"]).json() == []


def test_unknown_credential_is_rejected_without_leaking_value(client, tokens):
    response = client.get(ORDER_URL, headers={"Authorization": "Bearer invalid-test-credential"})
    assert response.status_code == 401
    assert "invalid-test-credential" not in response.text


def test_orders_fail_closed_when_no_credentials_are_configured(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ORDERS_READ_TOKEN", None)
    monkeypatch.setattr("app.core.config.settings.ORDERS_WRITE_TOKEN", None)
    assert client.get(ORDER_URL, headers={"Authorization": "Bearer invalid"}).status_code == 503


@pytest.mark.parametrize("order_id", ["0", "-1", "9223372036854775808", "9" * 100])
def test_order_identifier_bounds_are_validated_before_database(client, tokens, order_id):
    response = client.patch(ORDER_URL + "/" + order_id, headers=tokens["write"], json={"status": "EM_ANDAMENTO"})
    assert response.status_code == 422
    assert client.get(ORDER_URL, headers=tokens["read"]).json() == []


@pytest.mark.parametrize("field,value", [
    ("uc_id", ""), ("uc_id", "   "), ("uc_id", "U" * 51),
    ("reason", ""), ("reason", "   "), ("reason", "R" * 256),
    ("priority", "INVALID"), ("priority", "P" * 21), ("notes", "N" * 4001),
    ("status", "CONCLUIDA"),
])
def test_order_input_cannot_persist_invalid_fields(client, tokens, field, value):
    payload = {"uc_id": "TEST", "reason": "Inspeção", field: value}
    assert client.post(ORDER_URL, headers=tokens["write"], json=payload).status_code == 422
    assert client.get(ORDER_URL, headers=tokens["read"]).json() == []


def test_order_strings_trim_spaces_and_accept_column_boundaries(client, tokens):
    response = client.post(ORDER_URL, headers=tokens["write"], json={"uc_id": " " + "U" * 50 + " ", "reason": "R" * 255, "notes": "N" * 4000, "priority": "ALTA"})
    assert response.status_code == 201
    assert response.json()["uc_id"] == "U" * 50


@pytest.mark.parametrize("payload", [{}, {"status": None}, {"notes": "x" * 4001}, {"result": "x" * 4001}, {"uc_id": "OTHER"}])
def test_invalid_updates_are_rejected(client, tokens, payload):
    oid = create(client, tokens)
    assert client.patch(f"{ORDER_URL}/{oid}", headers=tokens["write"], json=payload).status_code == 422


def test_cancelled_orders_cannot_be_reopened_or_changed(client, tokens):
    oid = create(client, tokens)
    url = f"{ORDER_URL}/{oid}"
    assert client.patch(url, headers=tokens["write"], json={"status": "CANCELADA"}).status_code == 200
    assert client.patch(url, headers=tokens["write"], json={"status": "PENDENTE"}).status_code == 409
    assert client.patch(url, headers=tokens["write"], json={"notes": "Alteração indevida"}).status_code == 409
    assert client.patch(url, headers=tokens["write"], json={"status": "CANCELADA"}).status_code == 200
    assert client.get(ORDER_URL, headers=tokens["read"]).json()[0]["status"] == "CANCELADA"


def test_valid_completion_requires_started_order_and_result(client, tokens):
    oid = create(client, tokens)
    url = f"{ORDER_URL}/{oid}"
    assert client.patch(url, headers=tokens["write"], json={"status": "CONCLUIDA", "result": "Conferido"}).status_code == 409
    assert client.patch(url, headers=tokens["write"], json={"status": "EM_ANDAMENTO"}).status_code == 200
    assert client.patch(url, headers=tokens["write"], json={"status": "CONCLUIDA", "result": "  "}).status_code == 422
    assert client.patch(url, headers=tokens["write"], json={"status": "CONCLUIDA", "result": "Conferido"}).status_code == 200
    assert client.patch(url, headers=tokens["write"], json={"status": "EM_ANDAMENTO"}).status_code == 409
    assert client.get(ORDER_URL, headers=tokens["read"]).json()[0]["result"] == "Conferido"


@pytest.mark.parametrize("content_type", ["application/json", "application/problem+json", ""])
def test_deep_json_is_rejected_before_parser_without_crashing(client, content_type):
    response = client.post("/api/v1/ai/query", content="[" * 1500 + "0" + "]" * 1500, headers={"Content-Type": content_type})
    assert response.status_code == 413
    assert "Traceback" not in response.text
    assert client.get("/api/v1/health").status_code == 200


def test_large_body_rejected_even_without_content_length(client):
    def chunks():
        yield b"x" * (MAX_BODY_BYTES // 2)
        yield b"x" * (MAX_BODY_BYTES // 2 + 1)
    assert client.post("/api/v1/ai/query", content=chunks()).status_code == 413


def test_json_structure_characters_inside_strings_do_not_count_as_depth(client):
    payload = {"intent": "[" * 200 + '\\"' + "}" * 200, "target_table": "gold_indicadores"}
    response = client.post("/api/v1/ai/query", json=payload)
    assert response.status_code == 200


def test_adversarial_content_length_does_not_overflow_integer_parser(client):
    assert client.post("/api/v1/ai/query", content=b"{}", headers={"Content-Length": "9" * 5000}).status_code == 413


def test_foreign_host_is_rejected_and_security_headers_are_present(client):
    assert client.get("/", headers={"Host": "attacker.invalid"}).status_code == 400
    response = client.get("/api/v1/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/docs").status_code == 200


@pytest.mark.parametrize("options", [
    {"ORDERS_WRITE_TOKEN": "short"},
    {"ORDERS_READ_TOKEN": "same-test-" * 5, "ORDERS_WRITE_TOKEN": "same-test-" * 5},
])
def test_weak_or_identical_service_credentials_rejected(options):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **options)

@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_non_utf8_json_cannot_bypass_depth_limit(client, encoding):
    malicious = '{"x":"\\\"","y":' + '[' * 1500 + '0' + ']' * 1500 + '}'
    response = client.post('/api/v1/ai/query', content=malicious.encode(encoding), headers={"Content-Type": "application/json"})
    assert response.status_code == 400

def test_openapi_declares_orders_service_authentication(client):
    document = client.get('/openapi.json').json()
    for path, method in [(ORDER_URL, 'get'), (ORDER_URL, 'post'), (ORDER_URL + '/{order_id}', 'patch')]:
        assert document['paths'][path][method]['security'] == [{'OrdersServiceToken': []}]

def test_transition_event_does_not_log_credentials_or_payload(client, tokens, caplog):
    import logging
    oid = create(client, tokens)
    with caplog.at_level(logging.INFO, logger='app.services.inspections'):
        response = client.patch(f'{ORDER_URL}/{oid}', headers=tokens['write'], json={'status': 'EM_ANDAMENTO', 'notes': 'Private audit sample'})
    assert response.status_code == 200
    event = next(record for record in caplog.records if record.message == 'inspection_order_status_changed')
    assert event.order_id == oid
    assert event.previous_status == 'PENDENTE' and event.new_status == 'EM_ANDAMENTO'
    assert event.actor == 'orders-writer'
    assert 'Private audit sample' not in caplog.text
    assert tokens['write']['Authorization'] not in caplog.text

@pytest.mark.parametrize('content', [
    '{"intent":NaN,"target_table":"gold_indicadores"}',
    '{"intent":Infinity,"target_table":"gold_indicadores"}',
    '{"intent":1e999,"target_table":"gold_indicadores"}',
    '9' * 5000,
])
def test_nonfinite_or_extreme_json_numbers_never_cause_internal_error(client, content):
    response = client.post('/api/v1/ai/query', content=content, headers={'Content-Type': 'application/json'})
    assert response.status_code in {400, 422}
    assert client.get('/api/v1/health').status_code == 200

@pytest.mark.parametrize('content_type', ['text/plain', 'application/octet-stream'])
def test_unexpected_body_formats_cannot_trigger_error_serialization_failure(client, content_type):
    response = client.post('/api/v1/ai/query', content=b'\xff', headers={'Content-Type': content_type})
    assert response.status_code == 415

@pytest.mark.parametrize('encoded', [r'\ud800', r'\udfff', r'\u0000'])
def test_invalid_unicode_and_nul_in_json_are_rejected_before_storage(client, encoded):
    content = '{"intent":"' + encoded + '","target_table":"gold_indicadores"}'
    response = client.post('/api/v1/ai/query', content=content, headers={'Content-Type': 'application/json'})
    assert response.status_code == 400


def test_valid_unicode_surrogate_pair_remains_supported(client):
    response = client.post('/api/v1/ai/query', content=r'{"intent":"\ud83d\ude00","target_table":"gold_indicadores"}', headers={'Content-Type': 'application/json'})
    assert response.status_code == 200
