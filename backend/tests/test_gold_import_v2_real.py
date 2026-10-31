"""Opt-in full-volume test for the real, uncommitted Gold CSV v2 package."""
import json
import os
import shutil
from pathlib import Path

import pytest
from app.models.gold_v2_load import BATCH
from app.schemas.gold_publication_v2 import read_export_manifest_v2
from app.services.gold_import_v2 import GoldV2ImportError, import_gold_v2
from sqlalchemy import create_engine, select

from tests.support.migrations import migrated_database

PACKAGE = os.getenv("GOLD_CSV_V2_DIR")
pytestmark = pytest.mark.skipif(
    not PACKAGE,
    reason="Configure GOLD_CSV_V2_DIR to run the full-volume test with the real 15-table export.",
)


def test_real_v2_package_load_is_repeatable_and_rejects_invalid_delivery(tmp_path):
    database_path = tmp_path / "real_gold_v2_test.db"
    url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(url, hide_parameters=True).execution_options(
        schema_translate_map={"gold": None, "gold_v2": None},
    )
    try:
        with engine.connect() as connection, migrated_database(connection):
                loaded = import_gold_v2(engine, PACKAGE)
                assert loaded["status"] == "loaded"
                assert loaded["scope"] == "analytical_only"
                assert loaded["complete_delivery"] is False
                assert loaded["cadastro_status"] == "not_imported"
                expected = {
                    name: control.registros
                    for name, control in read_export_manifest_v2(Path(PACKAGE)).controles_tabelas.items()
                }
                assert {name: item["rows"] for name, item in loaded["tables"].items()} == expected

                repeated = import_gold_v2(engine, PACKAGE)
                assert repeated["status"] == "unchanged"
                assert repeated["scope"] == "analytical_only"
                assert repeated["complete_delivery"] is False
                assert repeated["publication_id"] == loaded["publication_id"]
                assert repeated["tables"] == loaded["tables"]

                invalid_manifest = tmp_path / "invalid_manifest"
                invalid_manifest.mkdir()
                manifest_path = invalid_manifest / "manifest.json"
                shutil.copyfile(os.path.join(PACKAGE, "manifest.json"), manifest_path)
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                payload["schema_version"] = "gold-csv-v1"
                manifest_path.write_text(json.dumps(payload), encoding="utf-8")
                with pytest.raises(GoldV2ImportError):
                    import_gold_v2(engine, invalid_manifest)

                with engine.connect() as published_connection:
                    current = published_connection.execute(
                        select(BATCH.c.publication_id, BATCH.c.schema_version)
                    ).one()
                    assert current.publication_id == loaded["publication_id"]
                    assert current.schema_version == "gold-csv-v2"
    finally:
        engine.dispose()
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(f"{database_path}{suffix}").unlink(missing_ok=True)
