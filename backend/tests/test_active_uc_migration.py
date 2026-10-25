"""Preserve operational data; never silently cancel legacy duplicate orders."""
import os

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from tests.test_migrations import alembic_config, migrated_database


@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
def test_migration_refuses_duplicates_and_preserves_orders(tmp_path, dialect):
    if dialect == "postgresql":
        raw = os.environ.get("TEST_POSTGRES_URL")
        if not raw:
            pytest.skip("Defina TEST_POSTGRES_URL para banco descartável *_test.")
        url = make_url(raw)
        assert url.get_backend_name() == "postgresql" and url.database.endswith("_test")
    else:
        url = f"sqlite:///{(tmp_path / 'active_uc_test.db').as_posix()}"
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            if dialect == "postgresql":
                assert conn.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")) is False
                conn.rollback()
            with migrated_database(conn):
                config = alembic_config(conn)
                command.downgrade(config, "a6d060000001")
                conn.commit()
                for reference in ("old-reference-1", "old-reference-2"):
                    conn.execute(text(
                        "INSERT INTO operational_inspection_orders (uc_id, reason, priority, status, suspicion_reference) "
                        "VALUES ('LEGACY-UC', 'preserve', 'MEDIA', 'PENDING', :reference)"
                    ), {"reference": reference})
                conn.commit()
                before = list(conn.execute(text("SELECT id, reason, status, suspicion_reference FROM operational_inspection_orders ORDER BY id")))
                conn.commit()
                versions_before = set(conn.scalars(text("SELECT version_num FROM alembic_version ORDER BY version_num")))
                with pytest.raises(RuntimeError, match="ordens ativas duplicadas"):
                    command.upgrade(config, "head")
                conn.rollback()
                assert list(conn.execute(text("SELECT id, reason, status, suspicion_reference FROM operational_inspection_orders ORDER BY id"))) == before
                versions_after = set(conn.scalars(text("SELECT version_num FROM alembic_version ORDER BY version_num")))
                assert versions_after == versions_before
                assert "uq_orders_active_suspicion" in {i["name"] for i in inspect(conn).get_indexes("operational_inspection_orders")}
                # Explicit reconciliation in this disposable test, never in the migration.
                conn.execute(text("UPDATE operational_inspection_orders SET status = 'CANCELLED' WHERE suspicion_reference = 'old-reference-2'"))
                conn.commit()
                command.upgrade(config, "head")
                conn.commit()
                assert conn.scalar(text("SELECT count(*) FROM operational_inspection_orders")) == 2
                assert "uq_orders_active_uc" in {i["name"] for i in inspect(conn).get_indexes("operational_inspection_orders")}
                conn.commit()
                with pytest.raises(IntegrityError):
                    conn.execute(text(
                        "INSERT INTO operational_inspection_orders (uc_id, reason, priority, status) "
                        "VALUES ('LEGACY-UC', 'duplicate manual', 'MEDIA', 'PENDING')"
                    ))
                conn.rollback()
    finally:
        engine.dispose()
