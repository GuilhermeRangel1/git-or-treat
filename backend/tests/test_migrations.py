import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "gold_indicadores",
    "operational_inspection_orders",
    "operational_order_history",
}


def alembic_config(connection):
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


def assert_upgraded(connection):
    assert EXPECTED_TABLES <= set(inspect(connection).get_table_names())


def assert_downgraded(connection):
    assert not EXPECTED_TABLES.intersection(inspect(connection).get_table_names())


def run_migration_cycle(connection):
    config = alembic_config(connection)
    command.upgrade(config, "head")
    assert_upgraded(connection)
    connection.commit()

    command.downgrade(config, "base")
    assert_downgraded(connection)
    connection.commit()


def test_alembic_upgrade_and_downgrade_use_the_explicit_disposable_sqlite_database(
    tmp_path,
):
    database_path = tmp_path / "migration_test.db"
    engine = create_engine(f"sqlite:///{database_path}")
    try:
        with engine.connect() as connection:
            run_migration_cycle(connection)
    finally:
        engine.dispose()


def test_alembic_upgrade_and_downgrade_on_explicit_disposable_postgres_database():
    database_url = os.getenv("TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("TEST_POSTGRES_URL não aponta para banco descartável configurado.")

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(
        "_test"
    ):
        pytest.fail("TEST_POSTGRES_URL precisa apontar para PostgreSQL descartável *_test.")

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.dialect.name == "postgresql"
            config = alembic_config(connection)
            command.upgrade(config, "head")
            assert_upgraded(connection)
            connection.commit()

            from app.models.operational import InspectionOrder, OrderStatus

            with Session(engine) as session:
                order = InspectionOrder(
                    uc_id="CI-POSTGRES-TEST",
                    reason="PostgreSQL disposable integration test",
                )
                session.add(order)
                session.commit()
                order_id = order.id

            with Session(engine) as session:
                persisted = session.get(InspectionOrder, order_id)
                assert persisted is not None
                assert persisted.uc_id == "CI-POSTGRES-TEST"
                assert persisted.status == OrderStatus.PENDING
                assert persisted.created_at is not None
                assert persisted.updated_at is not None

            command.downgrade(config, "base")
            assert_downgraded(connection)
            connection.commit()
    finally:
        engine.dispose()
