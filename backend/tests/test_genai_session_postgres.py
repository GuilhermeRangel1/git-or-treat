"""Sessão real → dependências FastAPI → papel restrito no PostgreSQL descartável."""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import router as auth_router
from app.core.config import settings
from app.core.database import get_db
from app.core.genai_gold_access import get_genai_gold_access_resolver
from app.core.genai_gold_database import GOLD_READER_ROLE, get_genai_gold_engine
from app.core.passwords import hash_password
from app.models.auth import AuthSession, AuthUser
from app.models.gold_load import BATCH
from app.models.gold_v2_load import TABLES
from app.schemas.genai_internal import AccessScope
from app.services.genai_publication import GoldPublicationContext
from app.services.gold_import import import_gold
from tests.support.migrations import migrated_database
from tests.test_gold_import import batch  # noqa: F401 - fixture compartilhada


def test_session_selects_reader_and_database_denies_prohibited_access(batch, monkeypatch):  # noqa: F811
    admin_url = os.getenv("TEST_GOLD_READER_ADMIN_URL")
    migrator_url = os.getenv("TEST_POSTGRES_URL")
    if not admin_url or not migrator_url:
        pytest.skip("Configure PostgreSQL descartável com gold_reader_test.")
    address = make_url(admin_url)
    migrator = make_url(migrator_url)
    assert address.database == "gold_reader_test" and address.get_backend_name() == "postgresql"
    assert (address.host, address.port) == (migrator.host, migrator.port)
    owner_url = migrator.set(database="gold_reader_test")
    owner = create_engine(owner_url, hide_parameters=True)
    admin = create_engine(address, hide_parameters=True)
    created_engines = []
    revoked = {"after_admission": False}
    reader_sql = []

    def observe_sql(conn, _cursor, statement, _parameters, _context, _many):
        if conn.engine.url.username == GOLD_READER_ROLE:
            reader_sql.append(statement)

    event.listen(Engine, "before_cursor_execute", observe_sql)
    try:
        with owner.connect() as connection, migrated_database(connection):
            import_gold(owner, batch)
            with owner.begin() as write:
                write.execute(BATCH.update().values(schema_version="gold-csv-v2"))
                write.execute(TABLES["diagnostico_receita"].insert(), {
                    "competencia": "2001-01", "municipio": "Cidade Teste", "classe_consumo": "TESTE",
                    "subgrupo_tarifario": "T", "bandeira_tarifaria": "T", "possui_gd": "N",
                    "receita_total_reais": 12,
                })
            with Session(owner) as db:
                for name in ("reader", "operator"):
                    db.add(AuthUser(
                        id=str(uuid4()), username=name,
                        password_hash=hash_password("synthetic-test-password"),
                        permissions=["orders:read"] if name == "reader" else ["orders:write"],
                        is_active=True,
                    ))
                db.commit()
            sql = (Path(__file__).parents[1] / "scripts/provision_genai_gold_reader.sql").read_text(encoding="utf-8")
            sql = "\n".join(line for line in sql.splitlines() if not line.startswith("\\"))
            password = uuid4().hex
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as administrator:
                # A revisão de PUBLIC é explícita e ocorre apenas no banco descartável.
                administrator.exec_driver_sql("REVOKE TEMP ON DATABASE gold_reader_test FROM PUBLIC")
                administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql(f"ALTER ROLE {GOLD_READER_ROLE} PASSWORD '{password}'")
            reader_url = address.set(username=GOLD_READER_ROLE, password=password)
            monkeypatch.setattr(settings, "DATABASE_URL", owner_url.render_as_string(hide_password=False))
            monkeypatch.setattr(settings, "GENAI_GOLD_DATABASE_URL", SecretStr(reader_url.render_as_string(hide_password=False)))
            monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "session")

            def operational_db():
                with Session(owner) as db:
                    yield db

            api = FastAPI()
            api.include_router(auth_router, prefix="/api/v1/auth")
            api.dependency_overrides[get_db] = operational_db

            @api.get("/api/v1/probe")
            def probe(
                reader: Annotated[Engine, Depends(get_genai_gold_engine)],
                resolve: Annotated[Callable[[], AccessScope], Depends(get_genai_gold_access_resolver)],
            ):
                created_engines.append(reader)
                if revoked["after_admission"]:
                    with owner.begin() as write:
                        write.execute(update(AuthUser).values(permissions=[]))
                scope = resolve()
                publication = GoldPublicationContext.capture(reader)
                fields = publication.planning_fields(reader, scope)
                assert fields["temporal_coverage"]
                with reader.connect() as read:
                    assert read.scalar(text("SELECT current_user")) == GOLD_READER_ROLE
                    assert read.scalar(text("SELECT SUM(receita_total_reais) FROM gold_v2.diagnostico_receita")) == 12
                    assert read.scalar(text("SHOW statement_timeout")) == "5s"
                return {"caller": scope.caller_ref, "read_only": scope.allowed_operations == {"read"}}

            origin = {"Origin": "http://localhost:5173"}
            with TestClient(api) as client:
                assert client.get("/api/v1/probe").status_code == 401
                callers = []
                for name in ("reader", "operator"):
                    assert client.post("/api/v1/auth/login", headers=origin, json={
                        "username": name, "password": "synthetic-test-password",
                    }).status_code == 200
                    result = client.get("/api/v1/probe?session_id=admin&scope=all", headers={"X-Access-Scope": "admin"})
                    assert result.status_code == 200
                    assert result.json()["read_only"] is True
                    callers.append(result.json()["caller"])
                assert callers[0] != callers[1]
                # Retirada de permissão depois de criar o engine não admite a leitura.
                revoked["after_admission"] = True
                reader_sql.clear()
                assert client.get("/api/v1/probe").status_code == 403
                assert reader_sql == []
                revoked["after_admission"] = False
                with owner.begin() as write:
                    write.execute(update(AuthUser).values(permissions=["orders:read"]))
                assert client.post("/api/v1/auth/logout", headers=origin).status_code == 204
                assert client.get("/api/v1/probe").status_code == 401

            # Contorna a aplicação e o default READ ONLY: ACL efetiva ainda bloqueia.
            engine = created_engines[0]
            forbidden = [
                "SELECT id_uc FROM gold_v2.consumo_mensal_uc",
                "SELECT receita_reais FROM gold_v2.consumo_mensal_uc",
                "SELECT receita_sem_leitura_reais FROM gold_v2.diagnostico_receita",
                "SELECT * FROM gold_v2.atendimentos_uc",
                "SELECT * FROM public.auth_users",
                "SELECT * FROM public.auth_sessions",
                "SELECT * FROM public.operational_inspection_orders",
                "SELECT * FROM public.gold_carga_atual",
                "INSERT INTO gold_v2.diagnostico_receita DEFAULT VALUES",
                "CREATE TABLE gold_v2.forbidden (id integer)",
                "CREATE TEMP TABLE forbidden (id integer)",
                "ALTER TABLE gold_v2.diagnostico_receita ADD COLUMN forbidden integer",
            ]
            for statement in forbidden:
                with engine.connect() as read:
                    read.exec_driver_sql("SET TRANSACTION READ WRITE")
                    with pytest.raises(DBAPIError) as error:
                        read.exec_driver_sql(statement)
                    assert error.value.orig.sqlstate == "42501"
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as administrator:
                administrator.exec_driver_sql("GRANT SELECT ON public.auth_users TO PUBLIC")
                try:
                    with pytest.raises(DBAPIError):
                        administrator.exec_driver_sql(sql)
                    administrator.exec_driver_sql("ROLLBACK")
                finally:
                    administrator.exec_driver_sql("REVOKE SELECT ON public.auth_users FROM PUBLIC")
                administrator.exec_driver_sql("GRANT TEMP ON DATABASE gold_reader_test TO PUBLIC")
                try:
                    with pytest.raises(DBAPIError):
                        administrator.exec_driver_sql(sql)
                    administrator.exec_driver_sql("ROLLBACK")
                finally:
                    administrator.exec_driver_sql("REVOKE TEMP ON DATABASE gold_reader_test FROM PUBLIC")
                administrator.exec_driver_sql(sql)
            with owner.connect() as read:
                assert len(read.execute(select(AuthUser.id)).all()) == 2
                assert not read.execute(select(AuthSession.id)).all()
    finally:
        event.remove(Engine, "before_cursor_execute", observe_sql)
        for engine in created_engines:
            engine.dispose()
        owner.dispose()
        admin.dispose()
