import os
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import produce_migrations
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Column, MetaData, String, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {"gold_indicadores", "operational_inspection_orders"}


def alembic_config(connection):
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def assert_clean_database(connection):
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    residual = sorted((tables - {"alembic_version"}) | set(inspector.get_view_names()))
    has_revision = "alembic_version" in tables and connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).first() is not None
    if residual or has_revision:
        pytest.fail(
            "O banco descartável precisa estar limpo antes do teste. "
            "Recrie somente o banco *_test ou limpe seus objetos manualmente; "
            "nenhuma tabela existente foi removida pelo teste."
        )


def assert_upgraded(connection):
    assert EXPECTED_TABLES <= set(inspect(connection).get_table_names())


def assert_downgraded(connection):
    assert not EXPECTED_TABLES.intersection(inspect(connection).get_table_names())


def assert_schema_matches_models(connection, metadata=None):
    if metadata is None:
        import app.models  # Registra todos os modelos antes da comparação.
        from app.db.base import Base

        metadata = Base.metadata
    context = MigrationContext.configure(
        connection, opts={"compare_type": True, "compare_server_default": True}
    )
    changes = produce_migrations(context, metadata).upgrade_ops
    assert changes.is_empty(), f"Modelo sem migração correspondente: {changes.as_diffs()}"


@contextmanager
def migrated_database(connection):
    assert_clean_database(connection)
    config = alembic_config(connection)
    connection.commit()
    original_error = None
    try:
        command.upgrade(config, "head")
        assert_upgraded(connection)
        assert_schema_matches_models(connection)
        connection.commit()
        yield connection
    except BaseException as error:
        original_error = error
        raise
    finally:
        try:
            connection.rollback()
            command.downgrade(config, "base")
            assert_downgraded(connection)
            connection.commit()
        except Exception as cleanup_error:
            if original_error is None:
                raise
            original_error.add_note(
                "A limpeza do banco descartável também falhou: "
                f"{type(cleanup_error).__name__}. Recrie o banco antes de repetir."
            )


def run_migration_cycle(connection):
    with migrated_database(connection):
        pass


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


def test_migration_cycle_refuses_residual_tables_with_cleanup_instructions():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("CREATE TABLE residual_data (id INTEGER)")
            connection.commit()
            with pytest.raises(pytest.fail.Exception, match="banco.*limpo"):
                run_migration_cycle(connection)
            assert "residual_data" in inspect(connection).get_table_names()
    finally:
        engine.dispose()


def test_migration_cycle_cleans_its_tables_when_a_check_fails():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            with pytest.raises(ValueError, match="simulated check failure"):
                with migrated_database(connection):
                    assert_upgraded(connection)
                    raise ValueError("simulated check failure")
            assert_downgraded(connection)
            run_migration_cycle(connection)
    finally:
        engine.dispose()


def test_schema_drift_detects_a_model_column_without_a_migration():
    from app.db.base import Base

    candidate = MetaData()
    for table in Base.metadata.sorted_tables:
        table.to_metadata(candidate)
    candidate.tables["operational_inspection_orders"].append_column(
        Column("unmigrated_field", String(30))
    )
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            with migrated_database(connection):
                with pytest.raises(AssertionError, match="unmigrated_field"):
                    assert_schema_matches_models(connection, candidate)
    finally:
        engine.dispose()


def assert_direct_insert_timestamps(engine):
    with engine.begin() as connection:
        record = connection.execute(
            text(
                "INSERT INTO operational_inspection_orders "
                "(uc_id, reason, priority, status) "
                "VALUES ('DIRECT-SQL-TEST', 'Server defaults test', 'MEDIA', 'PENDING') "
                "RETURNING id, created_at, updated_at"
            )
        ).one()
        assert record.created_at is not None
        assert record.updated_at is not None
        order_id = record.id
    with Session(engine) as session:
        from app.models.operational import InspectionOrder, OrderStatus

        persisted = session.get(InspectionOrder, order_id)
        assert persisted.status == OrderStatus.PENDING
        assert persisted.created_at is not None
        assert persisted.updated_at is not None
        if engine.dialect.name == "postgresql":
            assert persisted.created_at.utcoffset() is not None
            assert persisted.updated_at.utcoffset() is not None


def test_migrated_schema_populates_timestamps_for_direct_sql_insert(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'timestamps_test.db'}")
    try:
        with engine.connect() as connection:
            with migrated_database(connection):
                assert_direct_insert_timestamps(engine)
    finally:
        engine.dispose()


def assert_timestamp_migration_preserves_existing_orders(connection):
    config = alembic_config(connection)
    command.downgrade(config, "2d848fa6f44a")
    connection.commit()
    connection.execute(
        text(
            "INSERT INTO operational_inspection_orders "
            "(uc_id, reason, priority, status, created_at, updated_at) "
            "VALUES ('BEFORE-MIGRATION', 'Existing order', 'ALTA', 'IN_PROGRESS', "
            "'2025-01-01 12:00:00+00:00', '2025-01-02 12:00:00+00:00')"
        )
    )
    before = connection.execute(
        text("SELECT * FROM operational_inspection_orders WHERE uc_id = 'BEFORE-MIGRATION'")
    ).one()
    connection.commit()
    for target in ("head", "2d848fa6f44a", "head"):
        if target == "head":
            command.upgrade(config, target)
        else:
            command.downgrade(config, target)
        after = connection.execute(
            text("SELECT * FROM operational_inspection_orders WHERE uc_id = 'BEFORE-MIGRATION'")
        ).one()
        assert after == before
        defaults = {
            column["name"]: column["default"]
            for column in inspect(connection).get_columns("operational_inspection_orders")
        }
        for name in ("created_at", "updated_at"):
            assert (defaults[name] is not None) == (target == "head")
        connection.commit()


def test_timestamp_migration_and_rollback_preserve_existing_orders():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            with migrated_database(connection):
                assert_timestamp_migration_preserves_existing_orders(connection)
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
            assert not connection.scalar(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            ), "Use um usuário de migração sem SUPERUSER no banco descartável *_test."
            with migrated_database(connection):
                assert_timestamp_migration_preserves_existing_orders(connection)
                assert_order_persistence(engine)
                assert_direct_insert_timestamps(engine)
            with pytest.raises(ValueError, match="PostgreSQL check failure"):
                with migrated_database(connection):
                    raise ValueError("PostgreSQL check failure")
            assert_downgraded(connection)
            connection.execute(text("CREATE TABLE residual_test_data (id INTEGER)"))
            connection.execute(text("INSERT INTO residual_test_data VALUES (42)"))
            connection.commit()
            try:
                with pytest.raises(pytest.fail.Exception, match="banco.*limpo"):
                    run_migration_cycle(connection)
                assert connection.scalar(text("SELECT id FROM residual_test_data")) == 42
            finally:
                connection.rollback()
                connection.execute(text("DROP TABLE residual_test_data"))
                connection.commit()
    finally:
        engine.dispose()


def assert_order_persistence(engine):
    from app.models.operational import InspectionOrder, OrderStatus

    with Session(engine) as session:
        orders = [
            InspectionOrder(
                uc_id=f"CI-POSTGRES-{status.name}",
                reason="Disposable integration test",
                status=status,
            )
            for status in OrderStatus
        ]
        session.add_all(orders)
        session.commit()
        order_ids = [(order.id, order.status) for order in orders]

    with Session(engine) as session:
        raw_states = set(session.scalars(text("SELECT status FROM operational_inspection_orders")))
        assert raw_states == {"PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"}
        for order_id, expected_status in order_ids:
            persisted = session.get(InspectionOrder, order_id)
            assert persisted is not None
            assert persisted.status == expected_status
            assert persisted.created_at is not None
            assert persisted.updated_at is not None
