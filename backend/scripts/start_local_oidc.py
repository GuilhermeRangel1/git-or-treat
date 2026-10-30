"""Generate private credentials and start the isolated local Keycloak provider."""

from __future__ import annotations

import json
import secrets
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "work" / "local-oidc"
TEMPLATE = ROOT / "backend" / "local-oidc" / "realm.template.json"
COMPOSE = ROOT / "backend" / "local-oidc" / "compose.yaml"


def private_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        # Windows ACLs govern access; chmod is best-effort for POSIX hosts.
        pass


def configure_local_authorization(admin_password: str) -> None:
    base = "http://localhost:8082"
    discovery = base + "/realms/master/.well-known/openid-configuration"
    token_url = base + "/realms/master/protocol/openid-connect/token"
    for attempt in range(90):
        try:
            with urlopen(discovery, timeout=2):
                break
        except (OSError, URLError):
            if attempt == 89:
                raise RuntimeError("Keycloak não ficou pronto em até 180 segundos.")
            time.sleep(2)
    token_request = Request(
        token_url,
        data=urlencode({
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "local-admin",
            "password": admin_password,
        }).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(token_request, timeout=10) as response:
        admin_token = json.load(response)["access_token"]
    auth_headers = {"Authorization": "Bearer " + admin_token}
    admin_headers = {**auth_headers, "Content-Type": "application/json"}

    def request_json(path: str, method: str = "GET", payload: object | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(base + path, data=data, headers=admin_headers, method=method)
        with urlopen(request, timeout=10) as response:
            body = response.read()
        return json.loads(body) if body else None

    # Role-gated optional client scopes are the source of the standard OAuth
    # `scope` claim. Keycloak omits a requested scope when its user lacks the
    # scope's mapped role, so a reader cannot self-request write permission.
    roles: dict[str, dict] = {}
    for role_name in ("orders:read", "orders:write"):
        role_path = "/admin/realms/grid360/roles/" + role_name.replace(":", "%3A")
        try:
            roles[role_name] = request_json(role_path)
        except HTTPError as error:
            if error.code != 404:
                raise
            request_json("/admin/realms/grid360/roles", "POST", {"name": role_name})
            roles[role_name] = request_json(role_path)

    user_list = request_json("/admin/realms/grid360/users?max=100")
    users = {user["username"]: user for user in user_list}
    for username, assigned in {
        "reader": ("orders:read",),
        "operator": ("orders:read", "orders:write"),
    }.items():
        user = users[username]
        current = request_json(f"/admin/realms/grid360/users/{user['id']}/role-mappings/realm")
        current_names = {role["name"] for role in current}
        missing = [roles[name] for name in assigned if name not in current_names]
        if missing:
            request_json(f"/admin/realms/grid360/users/{user['id']}/role-mappings/realm", "POST", missing)

    all_scopes = request_json("/admin/realms/grid360/client-scopes")
    scope_by_name = {scope["name"]: scope for scope in all_scopes}
    for scope_name, role_name in (("orders:read", "orders:read"), ("orders:write", "orders:write")):
        scope = scope_by_name.get(scope_name)
        if scope is None:
            request_json("/admin/realms/grid360/client-scopes", "POST", {
                "name": scope_name,
                "protocol": "openid-connect",
                "attributes": {"include.in.token.scope": "true"},
            })
            all_scopes = request_json("/admin/realms/grid360/client-scopes")
            scope = next(item for item in all_scopes if item["name"] == scope_name)
            scope_by_name[scope_name] = scope
        scope_roles_path = f"/admin/realms/grid360/client-scopes/{scope['id']}/scope-mappings/realm"
        mapped = request_json(scope_roles_path)
        if role_name not in {role["name"] for role in mapped}:
            request_json(scope_roles_path, "POST", [roles[role_name]])

    web_clients = request_json("/admin/realms/grid360/clients?clientId=grid360-web")
    web_client = web_clients[0]
    web_client["fullScopeAllowed"] = False
    web_client.setdefault("attributes", {})["pkce.code.challenge.method"] = "S256"
    web_client.setdefault("attributes", {})["post.logout.redirect.uris"] = (
        "http://localhost:5173##http://127.0.0.1:5173"
    )
    request_json(f"/admin/realms/grid360/clients/{web_client['id']}", "PUT", web_client)

    api_clients = request_json("/admin/realms/grid360/clients?clientId=grid360-api")
    if not api_clients:
        request_json("/admin/realms/grid360/clients", "POST", {
            "clientId": "grid360-api",
            "name": "Grid 360 API resource",
            "enabled": True,
            "protocol": "openid-connect",
            "bearerOnly": True,
            "publicClient": False,
            "serviceAccountsEnabled": False,
        })
    mappers_path = f"/admin/realms/grid360/clients/{web_client['id']}/protocol-mappers/models"
    mappers = request_json(mappers_path)
    audience_mapper = next((mapper for mapper in mappers if mapper.get("name") == "Grid 360 API audience"), None)
    if audience_mapper is None:
        request_json(mappers_path, "POST", {
            "name": "Grid 360 API audience",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-audience-mapper",
            "consentRequired": False,
            "config": {
                "included.client.audience": "grid360-api",
                "id.token.claim": "false",
                "access.token.claim": "true",
            },
        })
    else:
        audience_mapper["config"]["included.client.audience"] = "grid360-api"
        audience_mapper["config"]["id.token.claim"] = "false"
        audience_mapper["config"]["access.token.claim"] = "true"
        request_json(mappers_path + "/" + audience_mapper["id"], "PUT", audience_mapper)
    for scope_name in ("orders:read", "orders:write"):
        path = f"/admin/realms/grid360/clients/{web_client['id']}/optional-client-scopes/{scope_by_name[scope_name]['id']}"
        try:
            request_json(path, "PUT")
        except HTTPError as error:
            # The link endpoint reports conflicts when the relation exists.
            if error.code != 409:
                raise
    mappers = request_json(mappers_path)
    for mapper in mappers:
        if mapper.get("name") == "Orders scopes":
            request_json(mappers_path + "/" + mapper["id"], "DELETE")


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    env_path = WORK / ".env"
    realm_path = WORK / "import" / "grid360-realm.json"
    credentials_path = WORK / "credentials.txt"
    # Keep credentials stable across reruns because Keycloak imports a realm
    # only when it does not already exist.
    if not (env_path.exists() and realm_path.exists() and credentials_path.exists()):
        admin_password = secrets.token_urlsafe(32)
        reader_password = secrets.token_urlsafe(32)
        operator_password = secrets.token_urlsafe(32)
        private_write(
            env_path,
            "KC_BOOTSTRAP_ADMIN_USERNAME=local-admin\n"
            f"KC_BOOTSTRAP_ADMIN_PASSWORD={admin_password}\n",
        )

        private_write(
            credentials_path,
            "Local Keycloak credentials (ignored work directory)\n"
            "Admin username: local-admin\n"
            f"Admin password: {admin_password}\n"
            "Reader username: reader\n"
            f"Reader password: {reader_password}\n"
            "Operator username: operator\n"
            f"Operator password: {operator_password}\n",
        )
    elif not (env_path.exists() and credentials_path.exists()):
        raise RuntimeError(
            "Dados privados OIDC locais incompletos; preserve work/local-oidc e restaure .env/credentials.txt antes de iniciar."
        )
    credential_values = dict(
        line.split(": ", maxsplit=1)
        for line in credentials_path.read_text(encoding="utf-8").splitlines()
        if ": " in line
    )
    private_write(
        env_path,
        "KC_BOOTSTRAP_ADMIN_USERNAME=local-admin\n"
        f"KC_BOOTSTRAP_ADMIN_PASSWORD={credential_values['Admin password']}\n",
    )
    # Refresh the ignored realm import from the tracked template every run;
    # user passwords remain stable across restarts.
    realm = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    realm["users"][0]["credentials"][0]["value"] = credential_values["Reader password"]
    realm["users"][1]["credentials"][0]["value"] = credential_values["Operator password"]
    private_write(realm_path, json.dumps(realm, indent=2))
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "up", "-d"],
        cwd=ROOT,
        check=True,
    )
    configure_local_authorization(credential_values["Admin password"])
    print("Keycloak inicializado em http://localhost:8082; credenciais privadas em work/local-oidc/credentials.txt")


if __name__ == "__main__":
    main()
