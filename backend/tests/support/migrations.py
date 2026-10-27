"""Helpers for migration tests and disposable database checks."""

from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import produce_migrations
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TABLES = {
    "gold_carga_atual",
    "gold_consumo_mensal_uc",
    "gold_consumo_receita_bairro",
    "gold_diagnostico_receita",
    "gold_fila_inspecao",
    "gold_indicadores_dec_fec",
    "gold_variacao_consumo_uc",
    "gold_visao_360_uc",
    "gold_indicadores",
    "operational_inspection_orders",
    "operational_order_history",
}


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
        import app.models  # noqa: F401 - registra modelos para Alembic.
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
