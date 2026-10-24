"""Individual identity and permissions at the real HTTP boundary, with RSA signatures."""
import logging
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from app.core.config import Settings, settings

ROOT = "/api/v1/inspections"
ISSUER = "https://identity.example.test/tenant"
AUDIENCE = "grid360-api"


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def oidc(client, monkeypatch, key):
    for name, value in {
        "APP_ENV": "production", "ORDERS_AUTH_MODE": "oidc", "ORDERS_READ_TOKEN": None,
        "ORDERS_WRITE_TOKEN": None, "OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE,
        "OIDC_JWKS_URL": ISSUER + "/jwks",
    }.items():
        monkeypatch.setattr(settings, name, value)
    jwk = jwt.PyJWK.from_dict({
        **jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True),
        "kid": "key-1", "alg": "RS256", "use": "sig",
    })

    class Keys:
        def get_signing_keys(self, refresh=False):
            assert refresh is False
            return [jwk]

    def configured_keys(url):
        assert url == ISSUER + "/jwks"
        return Keys()

    monkeypatch.setattr("app.core.order_access._jwks_client", configured_keys)
    return client


def token(key, *, scope="orders:write", sub="operator-a", changes=None, omit=(), headers=None):
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": sub, "iat": now, "exp": now + 300, "scope": scope}
    claims.update(changes or {})
    for field in omit:
        claims.pop(field)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "key-1", **(headers or {})})


def auth(value):
    return {"Authorization": "Bearer " + value}


def test_individual_access_and_scope_enforcement(oidc, key):
    assert oidc.get(ROOT + "/access").status_code == 401
    reader = auth(token(key, scope="orders:read"))
    access_response = oidc.get(ROOT + "/access", headers=reader)
    assert access_response.headers["cache-control"] == "no-store"
    access = access_response.json()
    assert access["auth_mode"] == "oidc" and access["actor"].startswith("oidc:")
    assert access["permissions"] == ["orders:read"]
    assert oidc.get(ROOT + "/orders/search", headers=reader).status_code == 200
    assert oidc.post(ROOT + "/orders", headers=reader, json={"uc_id": "OIDC-1", "reason": "test"}).status_code == 403
    assert oidc.patch(ROOT + "/orders/1", headers=reader, json={"version": 1, "notes": "test"}).status_code == 403
    assert oidc.post(ROOT + "/queue/UC-1004/orders", headers=reader, json={}).status_code == 403
    writer = auth(token(key))
    created = oidc.post(ROOT + "/orders", headers=writer, json={"uc_id": "OIDC-1", "reason": "test"})
    assert created.status_code == 201
    assert oidc.patch(ROOT + f"/orders/{created.json()['id']}", headers=writer, json={"version": 1, "status": "EM_ANDAMENTO"}).status_code == 200
    assert oidc.get(ROOT + "/access", headers=writer).json()["permissions"] == ["orders:read", "orders:write"]


@pytest.mark.parametrize("changes,omit,headers", [
    ({"iss": "https://attacker.invalid"}, (), {}),
    ({"aud": "another-api"}, (), {}),
    ({"exp": 1}, (), {}),
    ({"iat": 9999999999}, (), {}),
    ({"nbf": 9999999999}, (), {}),
    ({"exp": int(time.time()) + 7200}, (), {}),
    ({"sub": ""}, (), {}),
    ({"scope": ["orders:write"]}, (), {}),
    ({}, ("exp",), {}),
    ({}, ("iat",), {}),
    ({}, ("sub",), {}),
    ({}, (), {"kid": "unknown"}),
])
def test_invalid_claims_and_key_ids_fail_closed(oidc, key, changes, omit, headers):
    credential = token(key, changes=changes, omit=omit, headers=headers)
    response = oidc.get(ROOT + "/orders", headers=auth(credential))
    assert response.status_code == 401
    assert credential not in response.text


def test_wrong_signature_and_symmetric_algorithm_are_rejected(oidc, key):
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert oidc.get(ROOT + "/orders", headers=auth(token(attacker))).status_code == 401
    unsigned_identity = jwt.encode({"sub": "attacker"}, "x" * 32, algorithm="HS256", headers={"kid": "key-1"})
    assert oidc.get(ROOT + "/orders", headers=auth(unsigned_identity)).status_code == 401
    assert oidc.get(ROOT + "/orders", headers=auth("x" * 9000)).status_code == 401


def test_malformed_nested_jwt_header_is_rejected_without_parser_failure(oidc):
    from base64 import urlsafe_b64encode
    header = b'{"alg":"RS256","kid":"key-1","x":' + b'[' * 1200 + b'0' + b']' * 1200 + b'}'
    credential = urlsafe_b64encode(header).rstrip(b'=').decode() + ".e30.invalid"
    assert oidc.get(ROOT + "/orders", headers=auth(credential)).status_code == 401


def test_weak_rsa_key_is_not_accepted_even_when_registered(oidc, monkeypatch):
    from types import SimpleNamespace
    weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    jwk = jwt.PyJWK.from_dict({
        **jwt.algorithms.RSAAlgorithm.to_jwk(weak.public_key(), as_dict=True),
        "kid": "key-1", "alg": "RS256", "use": "sig",
    })
    monkeypatch.setattr("app.core.order_access._jwks_client", lambda url: SimpleNamespace(get_signing_keys=lambda refresh=False: [jwk]))
    with pytest.warns(Warning, match="RSA key is 1024"):
        credential = token(weak)
    assert oidc.get(ROOT + "/orders", headers=auth(credential)).status_code == 401


def test_token_urls_are_not_trusted_and_operator_is_not_taken_from_request(oidc, key, caplog):
    credential = token(key, headers={"jku": "https://attacker.invalid/jwks"})
    first = oidc.get(ROOT + "/access", headers=auth(credential)).json()
    other = oidc.get(ROOT + "/access", headers=auth(token(key, sub="operator-b"))).json()
    assert first["actor"] != other["actor"]
    with caplog.at_level(logging.INFO, logger="app.services.inspections"):
        created = oidc.post(ROOT + "/orders", headers=auth(credential), json={"uc_id": "OIDC-2", "reason": "private-reason"})
    assert created.status_code == 201
    event = next(r for r in caplog.records if r.message == "inspection_order_created")
    assert event.actor == first["actor"]
    assert "operator-a" not in event.actor and credential not in caplog.text and "private-reason" not in caplog.text
    forged_actor = oidc.post(ROOT + "/orders", headers=auth(credential), json={"uc_id": "OIDC-3", "reason": "test", "actor": "admin"})
    assert forged_actor.status_code == 422


def test_no_scope_and_service_token_have_no_oidc_permissions(oidc, key):
    assert oidc.get(ROOT + "/orders", headers=auth(token(key, scope="unrelated"))).status_code == 403
    assert oidc.get(ROOT + "/orders", headers=auth("old-service-" + "s" * 32)).status_code == 401


def test_unavailable_identity_provider_does_not_authorize(oidc, key, monkeypatch):
    def unavailable(url):
        raise jwt.PyJWKClientConnectionError("test outage")
    monkeypatch.setattr("app.core.order_access._jwks_client", unavailable)
    assert oidc.get(ROOT + "/orders", headers=auth(token(key))).status_code == 503


@pytest.mark.parametrize("options", [
    {"APP_ENV": "production"},
    {"ORDERS_AUTH_MODE": "oidc"},
    {"ORDERS_AUTH_MODE": "oidc", "OIDC_ISSUER": "http://id.test", "OIDC_AUDIENCE": AUDIENCE, "OIDC_JWKS_URL": ISSUER + "/jwks"},
    {"ORDERS_AUTH_MODE": "oidc", "OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE, "OIDC_JWKS_URL": "https://user:password@id.test/jwks"},
    {"ORDERS_AUTH_MODE": "oidc", "OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE, "OIDC_JWKS_URL": ISSUER + "/jwks", "ORDERS_WRITE_TOKEN": "s" * 40},
])
def test_unsafe_authentication_configuration_is_rejected(options):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **options)


def test_production_configuration_accepts_individual_identity():
    config = Settings(_env_file=None, APP_ENV="production", ORDERS_AUTH_MODE="oidc",
        OIDC_ISSUER=ISSUER, OIDC_AUDIENCE=AUDIENCE, OIDC_JWKS_URL=ISSUER + "/jwks")
    assert config.ORDERS_AUTH_MODE == "oidc"
