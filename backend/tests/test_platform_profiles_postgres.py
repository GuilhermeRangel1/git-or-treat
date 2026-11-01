"""Prova de provisionamento WEB-10 em PostgreSQL descartável real."""

import os
import sys

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import Session

from app.core.passwords import hash_password
from app.models.auth import AuthUser
from scripts import bootstrap_local_auth
from tests.support.migrations import migrated_database


DATABASE_URL = os.getenv("TEST_PLATFORM_PROFILES_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="Defina TEST_PLATFORM_PROFILES_POSTGRES_URL para PostgreSQL descartável *_test.",
)


def test_bootstrap_provisions_five_profiles_without_touching_unselected_account(
    tmp_path, monkeypatch, capsys,
):
    assert DATABASE_URL is not None
    url = make_url(DATABASE_URL)
    assert url.drivername == "postgresql+psycopg", "O teste exige um PostgreSQL psycopg descartável."
    assert url.database is not None and url.database.endswith("_test"), "Recusando banco sem sufixo _test."
    engine = create_engine(DATABASE_URL, poolclass=NullPool, hide_parameters=True)
    credentials_path = tmp_path / "private-credentials.txt"
    sentinel_hash = hash_password("artificial sentinel password")
    try:
        with engine.connect() as connection:
            identity = connection.exec_driver_sql(
                "SELECT current_database(), current_user, role.rolsuper "
                "FROM pg_roles AS role WHERE role.rolname = current_user"
            ).one()
            assert identity[0] == url.database and identity[2] is False, (
                "Banco ou papel PostgreSQL não corresponde a um alvo descartável sem privilégios."
            )
            public_objects = connection.exec_driver_sql(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
            ).scalars().all()
            public_views = connection.exec_driver_sql(
                "SELECT viewname FROM pg_catalog.pg_views WHERE schemaname = 'public'"
            ).scalars().all()
            assert not public_objects and not public_views, "Banco PostgreSQL de teste precisa iniciar vazio."

        with engine.connect() as connection, migrated_database(connection):
            with Session(engine) as db, db.begin():
                db.add(AuthUser(
                    id="unselected-account",
                    username="unselected-account",
                    password_hash=sentinel_hash,
                    permissions=["orders:write"],
                    profile=None,
                    is_active=True,
                ))

            monkeypatch.setattr(
                sys,
                "argv",
                [
                    "bootstrap_local_auth.py",
                    "--database-url",
                    DATABASE_URL,
                    "--output",
                    str(credentials_path),
                ],
            )
            assert bootstrap_local_auth.main() == 0
            output = capsys.readouterr().out
            assert "provisionadas" in output
            assert "password" not in output.casefold()

            with Session(engine) as db:
                selected = db.scalars(
                    select(AuthUser).where(AuthUser.username.in_(
                        ("commercial", "customer_service", "losses", "operations", "admin")
                    ))
                ).all()
                assert {user.username: user.profile for user in selected} == {
                    "commercial": "commercial",
                    "customer_service": "customer_service",
                    "losses": "losses",
                    "operations": "operations",
                    "admin": "admin",
                }
                sentinel = db.scalar(
                    select(AuthUser).where(AuthUser.id == "unselected-account")
                )
                assert sentinel is not None
                assert sentinel.password_hash == sentinel_hash
                assert sentinel.permissions == ["orders:write"]
                assert sentinel.profile is None

            private_credentials = credentials_path.read_text(encoding="utf-8")
            assert all(f"{profile} username: {profile}" in private_credentials for profile in (
                "commercial", "customer_service", "losses", "operations", "admin",
            ))
            assert private_credentials.count(" password: ") == 5
    finally:
        engine.dispose()
