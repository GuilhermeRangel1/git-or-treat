"""B1/B7 com carga real de fixtures artificiais e PostgreSQL quando configurado."""

import pytest
from sqlalchemy import delete, null, select, text
from sqlalchemy.exc import DBAPIError

from app.models.gold_load import BATCH, TABLES
from app.repositories.gold_publication import (
    GoldPublicationChanged,
    GoldPublicationInvalid,
    GoldPublicationUnavailable,
    current_publication,
)
from app.services.genai_publication import GoldPublicationContext
from app.services.gold_import import import_gold
from tests import test_gold_import as gold_fixtures

gold_batch = gold_fixtures.batch
gold_database = gold_fixtures.database


@pytest.fixture
def publication_database(gold_database):
    # O fixture de carga cria tabelas, sem executar migrações. Reproduz a vista
    # de metadados da migração; o teste do papel restrito usa as migrações reais.
    if gold_database.dialect.name == "postgresql":
        with gold_database.begin() as connection:
            connection.exec_driver_sql(
                "CREATE VIEW gold.publicacao_atual AS "
                "SELECT schema_version, lote, publication_id FROM public.gold_carga_atual "
                "WHERE publication_id IS NOT NULL AND origem IS NOT NULL"
            )
    try:
        yield gold_database
    finally:
        if gold_database.dialect.name == "postgresql":
            with gold_database.begin() as connection:
                connection.exec_driver_sql("DROP VIEW gold.publicacao_atual")


def _replace_publication(engine, directory):
    gold_fixtures.write_origin(directory, "second")
    return import_gold(engine, directory)


def test_missing_publication_is_invalid_and_not_retryable(publication_database):
    with pytest.raises(GoldPublicationInvalid) as error:
        GoldPublicationContext.capture(publication_database)
    assert isinstance(error.value, GoldPublicationUnavailable)
    assert error.value.code == "publication_invalid"
    assert error.value.retryable is False


@pytest.mark.parametrize("expected", ["private invalid reference", "LOTE_DEV", "", 123])
def test_malformed_expected_reference_is_invalid_not_changed(
    publication_database, gold_batch, expected
):
    import_gold(publication_database, gold_batch)
    with (
        publication_database.connect() as connection,
        pytest.raises(GoldPublicationInvalid) as error,
    ):
        current_publication(connection, expected)
    assert error.value.retryable is False
    assert "private" not in str(error.value)


def test_corrupted_current_reference_is_invalid_not_changed(publication_database, gold_batch):
    loaded = import_gold(publication_database, gold_batch)
    with publication_database.begin() as connection:
        connection.execute(BATCH.update().values(publication_id="private invalid uuid"))
    with (
        publication_database.connect() as connection,
        pytest.raises(GoldPublicationInvalid) as error,
    ):
        current_publication(connection, loaded["batch_ref"])
    assert error.value.retryable is False
    assert "private" not in str(error.value)


def test_repeated_batch_preserves_reference_for_planning_and_synthesis(
    publication_database, gold_batch
):
    first = import_gold(publication_database, gold_batch)
    context = GoldPublicationContext.capture(publication_database)
    assert import_gold(publication_database, gold_batch)["status"] == "unchanged"

    assert context.planning_fields(publication_database) == {"batch_ref": first["batch_ref"]}
    assert context.synthesis_fields(publication_database) == {
        "expected_batch_ref": first["batch_ref"]
    }


@pytest.mark.parametrize("stage", ["planning_fields", "assert_current", "synthesis_fields"])
def test_changed_publication_blocks_each_boundary(publication_database, gold_batch, stage):
    import_gold(publication_database, gold_batch)
    context = GoldPublicationContext.capture(publication_database)
    _replace_publication(publication_database, gold_batch)

    with pytest.raises(GoldPublicationChanged) as error:
        getattr(context, stage)(publication_database)
    assert isinstance(error.value, GoldPublicationUnavailable)
    assert error.value.code == "publication_changed"
    assert error.value.retryable is True
    assert context.batch_ref not in str(error.value)
    # Uma nova requisição captura o lote atual; não reutiliza o contexto antigo.
    fresh = GoldPublicationContext.capture(publication_database)
    assert fresh.batch_ref != context.batch_ref
    assert fresh.synthesis_fields(publication_database)["expected_batch_ref"] == fresh.batch_ref


def test_same_run_with_new_publication_is_still_a_change(publication_database, gold_batch):
    first = import_gold(publication_database, gold_batch)
    context = GoldPublicationContext.capture(publication_database)
    for path in gold_batch.glob("*/*.csv"):
        path.write_text(
            path.read_text(encoding="utf-8").replace("FAKE-A", "FAKE-C"), encoding="utf-8"
        )
    second = import_gold(publication_database, gold_batch)

    assert first["lote"] == second["lote"]
    assert first["publication_id"] != second["publication_id"]
    with pytest.raises(GoldPublicationChanged):
        context.synthesis_fields(publication_database)


def test_invalidated_publication_does_not_allow_retry(publication_database, gold_batch):
    import_gold(publication_database, gold_batch)
    context = GoldPublicationContext.capture(publication_database)
    with publication_database.begin() as connection:
        connection.execute(BATCH.update().values(origem=null()))
    with pytest.raises(GoldPublicationInvalid) as error:
        context.synthesis_fields(publication_database)
    assert error.value.retryable is False


def test_execution_snapshot_is_explicitly_postgresql_only(publication_database, gold_batch):
    if publication_database.dialect.name == "postgresql":
        pytest.skip("Este cenário confere a recusa do dialeto SQLite.")
    import_gold(publication_database, gold_batch)
    context = GoldPublicationContext.capture(publication_database)
    with (
        pytest.raises(ValueError, match="exige PostgreSQL"),
        context.execution_snapshot(publication_database),
    ):
        pytest.fail("Não deve iniciar uma execução Gold em SQLite.")


def _require_postgresql(engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("A consistência do snapshot exige PostgreSQL real.")


def test_snapshot_is_read_only_and_does_not_leak_transaction_settings(
    publication_database, gold_batch
):
    _require_postgresql(publication_database)
    import_gold(publication_database, gold_batch)
    context = GoldPublicationContext.capture(publication_database)
    with context.execution_snapshot(publication_database) as connection:
        assert connection.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        assert connection.scalar(text("SHOW transaction_read_only")) == "on"
    with pytest.raises(DBAPIError), context.execution_snapshot(publication_database) as connection:
        connection.execute(delete(TABLES["consumo_mensal_uc"]))
    with publication_database.connect() as connection:
        assert connection.scalar(text("SHOW transaction_read_only")) == "off"
        assert len(connection.execute(select(TABLES["consumo_mensal_uc"])).all()) == 2


def test_change_before_query_does_not_enter_execution_block(publication_database, gold_batch):
    _require_postgresql(publication_database)
    import_gold(publication_database, gold_batch)
    context = GoldPublicationContext.capture(publication_database)
    _replace_publication(publication_database, gold_batch)
    with pytest.raises(GoldPublicationChanged), context.execution_snapshot(publication_database):
        pytest.fail("Não pode executar um plano de outra publicação.")


def test_change_during_query_keeps_snapshot_but_rejects_result(publication_database, gold_batch):
    _require_postgresql(publication_database)
    import_gold(publication_database, gold_batch)
    context = GoldPublicationContext.capture(publication_database)
    monthly = TABLES["consumo_mensal_uc"]
    query = select(monthly.c.id_uc).order_by(monthly.c.id_uc)

    with (
        pytest.raises(GoldPublicationChanged),
        context.execution_snapshot(publication_database) as connection,
    ):
        assert connection.scalars(query).all() == ["FAKE-A", "FAKE-B"]
        for path in gold_batch.glob("*/*.csv"):
            path.write_text(
                path.read_text(encoding="utf-8").replace("FAKE-A", "FAKE-C"), encoding="utf-8"
            )
        import_gold(publication_database, gold_batch)
        # Outra conexão publicou, mas a transação não mistura linhas dos lotes.
        assert connection.scalars(query).all() == ["FAKE-A", "FAKE-B"]
    with publication_database.connect() as connection:
        assert connection.scalars(query).all() == ["FAKE-B", "FAKE-C"]
