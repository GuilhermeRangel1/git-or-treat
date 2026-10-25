"""Prova opcional de permissões contra PostgreSQL descartável e dados artificiais."""

import os
from decimal import Decimal
from secrets import token_urlsafe
from uuid import uuid4

import pytest

from app.sql.executors import PostgresReadOnlyExecutor
from app.sql.validator import validate_sql
from tests.sql_support import load_test_dictionary


@pytest.mark.skipif(
    not os.environ.get("GENAI_TEST_POSTGRES_ADMIN_DSN"),
    reason="defina um DSN administrativo para o banco descartável grid360_ia_test",
)
def test_postgres_reader_role_cannot_write_or_read_an_ungranted_table() -> None:
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    admin_dsn = os.environ["GENAI_TEST_POSTGRES_ADMIN_DSN"]
    suffix = uuid4().hex[:12]
    schema = f"genai_synthetic_{suffix}"
    role = f"genai_reader_{suffix}"
    password = token_urlsafe(32)
    dictionary = load_test_dictionary()

    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        if admin.info.dbname != "grid360_ia_test":
            pytest.fail("a prova só pode criar objetos no banco descartável grid360_ia_test")
        admin.execute("REVOKE TEMPORARY ON DATABASE grid360_ia_test FROM PUBLIC")
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            admin.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            admin.execute(
                sql.SQL("CREATE TABLE {}.gold_indicadores "
                        "(competencia text, municipio text, receita_total numeric)").format(
                    sql.Identifier(schema)
                )
            )
            admin.execute(
                sql.SQL("CREATE TABLE {}.restrita (segredo text)").format(sql.Identifier(schema))
            )
            admin.execute(
                sql.SQL("INSERT INTO {}.gold_indicadores VALUES "
                        "('2025-01', 'Municipio Ficticio A', 3500.5)").format(
                    sql.Identifier(schema)
                )
            )
            admin.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    sql.Identifier(schema), sql.Identifier(role)
                )
            )
            admin.execute(
                sql.SQL("GRANT SELECT ON {}.gold_indicadores TO {}").format(
                    sql.Identifier(schema), sql.Identifier(role)
                )
            )
            admin.execute(
                sql.SQL("ALTER ROLE {} SET search_path TO {}").format(
                    sql.Identifier(role), sql.Identifier(schema)
                )
            )

            connection_settings = conninfo_to_dict(admin_dsn)
            connection_settings.update(user=role, password=password)
            reader_dsn = make_conninfo(**connection_settings)
            executor = PostgresReadOnlyExecutor.from_dsn(
                reader_dsn, max_rows=5, timeout_ms=2000, dictionary=dictionary
            )
            approved_query = validate_sql(
                "SELECT SUM(receita_total) AS total FROM gold_indicadores LIMIT 5",
                dictionary,
                "postgres",
            )
            assert executor.execute(approved_query).rows == ((Decimal("3500.5"),),)

            with psycopg.connect(reader_dsn) as reader:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    reader.execute("INSERT INTO gold_indicadores VALUES ('2025-02', 'X', 1)")
                reader.rollback()
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    reader.execute("SELECT segredo FROM restrita")
                reader.rollback()
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    reader.execute("CREATE TEMP TABLE escrita_fora_do_escopo (valor int)")
                reader.rollback()
        finally:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
