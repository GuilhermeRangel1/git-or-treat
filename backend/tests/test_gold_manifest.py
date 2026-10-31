"""Contratos e publicação: amostras artificiais atravessam a carga real."""
import json
from uuid import UUID
from pathlib import Path

import pytest
from sqlalchemy import event, select

from app.models.gold_load import ATTEMPTS, BATCH
from app.repositories.gold_publication import GoldPublicationUnavailable, current_publication
from app.schemas.gold_publication import PublicationReference
from app.services.gold_import import GoldImportError, import_gold
from tests.test_gold_import import batch, database, published_snapshot, source_id


def update_manifest(batch, **changes):
    path = batch / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(changes)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("changes", [
    {"ambiente": "dev"}, {"ambiente": "test"}, {"ambiente": "SINTETICO_DEV"}, {"ambiente": None},
    {"run_id": None}, {"run_id": ""}, {"run_id": "batch_manual_20250101"},
    {"run_id": "LOTE_DEV"}, {"run_id_silver": "SINTETICO_DEV"}, {"lote_bronze_silver": "LOTE_DEV"},
    {"lote": source_id("other")}, {"schema_version": "gold-csv-v2"},
    {"tabelas_exportadas": []}, {"tabelas_exportadas": ["../private"]},
    {"data_processamento_gold": "private invalid date"}, {"status_gold": "FALHOU"},
    {"unexpected": "private payload"},
])
def test_invalid_origin_preserves_publication_and_hides_payload(database, batch, changes):
    import_gold(database, batch)
    previous = published_snapshot(database)
    update_manifest(batch, **changes)
    with pytest.raises(GoldImportError) as error:
        import_gold(database, batch)
    assert error.value.code == "invalid_manifest"
    assert "private" not in str(error.value)
    assert published_snapshot(database) == previous
    with database.connect() as connection:
        attempt = connection.execute(select(ATTEMPTS).where(ATTEMPTS.c.id == error.value.attempt_id)).mappings().one()
        assert attempt["status"] == "failed" and attempt["origem"] is None
        assert "private" not in json.dumps(attempt, default=str)


@pytest.mark.parametrize("case", ["missing", "both", "invalid_json", "repeated_key", "too_large"])
def test_manifest_discovery_is_unambiguous(database, batch, case):
    path = batch / "manifest.json"
    if case == "missing":
        path.unlink()
    elif case == "both":
        (batch / "manifesto").mkdir()
        (batch / "manifesto" / "manifest.json").write_bytes(path.read_bytes())
    elif case == "invalid_json":
        path.write_text("{invalid", encoding="utf-8")
    elif case == "repeated_key":
        path.write_text('{"ambiente":"prod","ambiente":"dev"}', encoding="utf-8")
    else:
        path.write_text(" " * 65537, encoding="utf-8")
    with pytest.raises(GoldImportError, match="Manifesto"):
        import_gold(database, batch)
    with database.connect() as connection:
        assert connection.execute(select(BATCH)).first() is None


def test_nested_manifest_and_legacy_explicit_version(database, batch):
    payload = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    payload.pop("schema_version")
    payload["ambiente"] = " PROD "
    payload["data_processamento_gold"] = "2025-01-01 00:00:00"
    (batch / "manifesto").mkdir()
    (batch / "manifesto" / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (batch / "manifest.json").unlink()
    with pytest.raises(GoldImportError, match="Manifesto"):
        import_gold(database, batch)
    result = import_gold(database, batch, schema_version="gold-csv-v1")
    assert result["status"] == "loaded"
    with database.connect() as connection:
        origin = connection.scalar(select(BATCH.c.origem))
        assert origin["ambiente"] == "prod"
        assert origin["data_processamento_gold"] == "2025-01-01T03:00:00Z"


def test_batch_argument_cannot_replace_the_manifest_run(database, batch):
    with pytest.raises(GoldImportError) as error:
        import_gold(database, batch, source_id("different"))
    assert error.value.code == "invalid_batch"


def test_publication_stable_on_repetition_and_new_for_new_origin(database, batch):
    first = import_gold(database, batch)
    repeated = import_gold(database, batch)
    assert first["status"] == "loaded" and repeated["status"] == "unchanged"
    assert first["publication_id"] == repeated["publication_id"]
    assert UUID(first["publication_id"]).version == 4
    assert first["batch_ref"] == repeated["batch_ref"]
    assert first["attempt_id"] != repeated["attempt_id"]
    assert first["publication_id"] not in {first["attempt_id"], repeated["attempt_id"]}
    with database.connect() as connection:
        attempts = connection.execute(select(ATTEMPTS.c.publication_id)).scalars().all()
        assert attempts == [first["publication_id"], first["publication_id"]]
    update_manifest(batch, run_id=source_id("new"), lote=source_id("new"))
    loaded = import_gold(database, batch)
    assert loaded["status"] == "loaded"
    assert loaded["publication_id"] != first["publication_id"]
    assert PublicationReference.parse(loaded["batch_ref"]).run_id == source_id("new")


def test_changed_content_with_same_run_creates_another_publication(database, batch):
    first = import_gold(database, batch)
    for path in batch.glob("*/*.csv"):
        path.write_text(path.read_text(encoding="utf-8").replace("FAKE-A", "FAKE-C"), encoding="utf-8")
    changed = import_gold(database, batch)
    assert changed["status"] == "loaded" and changed["lote"] == first["lote"]
    assert changed["publication_id"] != first["publication_id"]


def test_manifest_change_during_load_rolls_back(database, batch):
    import_gold(database, batch)
    previous = published_snapshot(database)
    update_manifest(batch, run_id=source_id("second"), lote=source_id("second"))

    def mutate(connection, cursor, statement, parameters, context, executemany):
        if context.compiled is not None and getattr(context.compiled.statement, "is_insert", False) and context.compiled.statement.table.name == "gold_visao_360_uc":
            update_manifest(batch, run_id=source_id("changed"), lote=source_id("changed"))

    event.listen(database, "before_cursor_execute", mutate)
    try:
        with pytest.raises(GoldImportError, match="arquivos mudaram"):
            import_gold(database, batch, schema_version="gold-csv-v1")
        assert published_snapshot(database) == previous
    finally:
        event.remove(database, "before_cursor_execute", mutate)


@pytest.mark.parametrize("database", ["sqlite"], indirect=True)
def test_reference_contract_rejects_a_different_publication(database, batch):
    # A prova aqui é do contrato, não de uma consulta de negócio concorrente.
    with database.connect() as connection:
        with pytest.raises(GoldPublicationUnavailable):
            current_publication(connection)
    first = import_gold(database, batch)
    with database.connect() as connection:
        assert current_publication(connection, first["batch_ref"]).batch_ref == first["batch_ref"]
    update_manifest(batch, run_id=source_id("new"), lote=source_id("new"))
    import_gold(database, batch)
    with database.connect() as connection:
        with pytest.raises(GoldPublicationUnavailable):
            current_publication(connection, first["batch_ref"])


@pytest.mark.parametrize("value", ["", "v1",
    "gold-csv-v1:LOTE_DEV:8b9502c2-c188-4528-ab3c-7dff79ed908f",
    "gold-csv-v1:GOLD_20250101T000000Z_aaaaaaaa:not-a-uuid",
    "gold-csv-v1:GOLD_20250101T000000Z_aaaaaaaa:8b9502c2-c188-4528-ab3c-7dff79ed908f:extra"])
def test_batch_reference_rejects_invalid_envelopes(value):
    with pytest.raises(ValueError):
        PublicationReference.parse(value)


def test_batch_reference_accepts_v2_publication():
    value = "gold-csv-v2:GOLD_20250101T000000Z_aaaaaaaa:8b9502c2-c188-4528-ab3c-7dff79ed908f"
    assert PublicationReference.parse(value).batch_ref == value


def test_shared_publication_envelope_examples():
    examples = json.loads((Path(__file__).parents[2] / "docs/contracts/examples/gold-publication-v1.json").read_text(encoding="utf-8"))
    assert PublicationReference.model_validate(examples["valid"]).batch_ref == examples["batch_ref"]
    assert PublicationReference.parse(examples["batch_ref"]).model_dump(mode="json") == examples["valid"]
    for changes in examples["invalid_changes"]:
        with pytest.raises(ValueError):
            PublicationReference.model_validate({**examples["valid"], **changes})


def test_shared_invalid_batch_references():
    path = Path(__file__).parents[2] / "docs/contracts/examples/gold-publication-v1.json"
    for value in json.loads(path.read_text(encoding="utf-8"))["invalid_batch_refs"]:
        with pytest.raises(ValueError):
            PublicationReference.parse(value)
