"""Pacotes controlados v2 atravessam o importador público e o banco real."""

import csv
import hashlib
import json
import os

import pytest
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    Text,
    create_engine,
    select,
)
from sqlalchemy.engine import make_url

from app.models.gold_v2_load import ATTEMPTS, BATCH, TABLES
from app.schemas.gold_publication_v2 import CSV_FORMAT
from app.services.gold_import_v2 import GoldV2ImportError, import_gold_v2
from tests.support.migrations import migrated_database


def spark_type(kind):
    if isinstance(kind, Numeric) and not isinstance(kind, Float):
        return f"decimal({kind.precision},{kind.scale})"
    for cls, name in (
        (Text, "string"),
        (BigInteger, "long"),
        (Integer, "integer"),
        (Float, "double"),
        (DateTime, "timestamp"),
        (Date, "date"),
        (Boolean, "boolean"),
    ):
        if isinstance(kind, cls):
            return name
    raise AssertionError("Tipo de fixture não declarado.")


def package(directory, label):
    directory.mkdir()
    run = "GOLD_20000101T000000Z_" + hashlib.sha256(label.encode()).hexdigest()[:8]
    controls = {}
    for name, table in TABLES.items():
        target = directory / name
        target.mkdir()
        with (target / (name + ".csv")).open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.writer(
                stream, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n"
            )
            writer.writerow(table.c.keys())
            if name in {"visao_360_uc", "cobertura_dominios"}:
                values = (
                    {"id_uc": "ARTIFICIAL_" + label}
                    if name == "visao_360_uc"
                    else {
                        "dominio": "atendimentos",
                        "competencia": "2000-01",
                        "recorte": "DOMINIO",
                        "estado_cobertura": "PARCIAL",
                        "qtd_registros": "0",
                        "qtd_sem_competencia": "0",
                        "zero_registros_confirmado": "false",
                    }
                )
                writer.writerow([values.get(c.name, r"\N") for c in table.c])
        controls[name] = {
            "registros": int(name in {"visao_360_uc", "cobertura_dominios"}),
            "versao_delta": 0,
            "schema": {
                "type": "struct",
                "fields": [
                    {
                        "name": c.name,
                        "type": spark_type(c.type),
                        "nullable": True,
                        "metadata": {},
                    }
                    for c in table.c
                ],
            },
        }
    manifest = {
        "schema_version": "gold-csv-v2",
        "ambiente": "prod",
        "lote": run,
        "run_id": run,
        "run_id_silver": "20000101T000000Z_bbbbbbbb",
        "lote_bronze_silver": "20000101T000000Z_cccccccc",
        "data_processamento_gold": "2000-01-01T00:00:00Z",
        "status_gold": "CONCLUIDO",
        "data_exportacao_csv": "2000-01-01T01:00:00Z",
        "export_id": "test_" + label,
        "cadastro_export_id": "restricted_not_loaded",
        "cadastro_schema_version": "gold-cadastro-v1",
        "tabelas_exportadas": list(TABLES),
        "controles_tabelas": controls,
        "formato_csv": CSV_FORMAT,
        "preco_volume_configuracao": {
            "estado": "NAO_CONFIGURADA",
            "janelas": {},
            "metodo": None,
        },
        "preco_volume_referencia": None,
        "limitacoes_medidas": {
            k: "Indisponível nesta amostra controlada."
            for k in (
                "energia_faturada_kwh",
                "energia_recuperavel_kwh",
                "fechamento_mensal",
                "valor_recebido_reais",
            )
        },
        "responsavel": "fixture_controlada",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request, tmp_path):
    if request.param == "postgresql":
        url = os.getenv("TEST_POSTGRES_URL")
        if not url:
            pytest.skip("Configure PostgreSQL descartável v_energy_test.")
        assert make_url(url).database == "v_energy_test"
    else:
        url = f"sqlite:///{(tmp_path / 'publication.db').as_posix()}"
    engine = create_engine(url, hide_parameters=True)
    if request.param == "sqlite":
        engine = engine.execution_options(
            schema_translate_map={"gold": None, "gold_v2": None}
        )
    try:
        with engine.connect() as connection, migrated_database(connection):
            yield engine
    finally:
        engine.dispose()


def snapshot(engine):
    with engine.connect() as c:
        current = dict(c.execute(select(BATCH)).mappings().one())
        rows = {
            name: [dict(r) for r in c.execute(select(table)).mappings()]
            for name, table in TABLES.items()
        }
    return current, rows


def test_v2_repetition_and_new_publication_preserve_identity_and_replace_facts(
    database, tmp_path
):
    first = package(tmp_path / "first", "first")
    initial = import_gold_v2(database, first)
    repeated = import_gold_v2(database, first)
    assert initial["status"] == "loaded" and repeated["status"] == "unchanged"
    assert repeated["batch_ref"] == initial["batch_ref"]
    changed = import_gold_v2(database, package(tmp_path / "second", "second"))
    assert (
        changed["status"] == "loaded" and changed["batch_ref"] != initial["batch_ref"]
    )
    current, rows = snapshot(database)
    assert [r["id_uc"] for r in rows["visao_360_uc"]] == ["ARTIFICIAL_second"]
    assert len(changed["tables"]) == 15
    assert current["manifesto"]["coverage_windows"] == [
        {
            "domain": "atendimentos",
            "scope": "DOMINIO",
            "start": "2000-01",
            "end": "2000-01",
            "rows": 1,
            "states": {"PARCIAL": 1},
            "is_certification": False,
        }
    ]


def test_v2_last_csv_failure_rolls_back_all_tables_and_keeps_failed_attempt(
    database, tmp_path
):
    import_gold_v2(database, package(tmp_path / "valid", "valid"))
    before = snapshot(database)
    broken = package(tmp_path / "broken", "broken")
    last = list(TABLES)[-1]
    (broken / last / (last + ".csv")).write_text("invalid_header\n", encoding="utf-8")
    with pytest.raises(GoldV2ImportError) as failure:
        import_gold_v2(database, broken)
    assert failure.value.code == "invalid_schema"
    assert snapshot(database) == before
    with database.connect() as c:
        attempt = (
            c.execute(select(ATTEMPTS).where(ATTEMPTS.c.id == failure.value.attempt_id))
            .mappings()
            .one()
        )
    assert attempt["status"] == "failed"
    assert all(
        attempt["manifesto"][name]["validated"] is True for name in list(TABLES)[:-1]
    )
    assert attempt["manifesto"][last]["validated"] is False


@pytest.mark.parametrize("coverage", ["empty", "gapped"])
def test_v2_coverage_windows_are_observations_not_closed_periods(
    database, tmp_path, coverage
):
    directory = package(tmp_path / "coverage", coverage)
    table = TABLES["cobertura_dominios"]
    path = directory / "cobertura_dominios" / "cobertura_dominios.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(
            stream, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n"
        )
        writer.writerow(table.c.keys())
        if coverage == "gapped":
            for period, state in (
                ("2000-01", "PARCIAL"),
                ("2000-03", "NAO_CERTIFICADA"),
            ):
                values = {
                    "dominio": "consumo",
                    "competencia": period,
                    "recorte": "DOMINIO",
                    "estado_cobertura": state,
                }
                writer.writerow([values.get(c.name, r"\N") for c in table.c])
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["controles_tabelas"]["cobertura_dominios"]["registros"] = (
        0 if coverage == "empty" else 2
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    import_gold_v2(database, directory)
    current, _ = snapshot(database)
    expected = (
        []
        if coverage == "empty"
        else [
            {
                "domain": "consumo",
                "scope": "DOMINIO",
                "start": "2000-01",
                "end": "2000-03",
                "rows": 2,
                "states": {"NAO_CERTIFICADA": 1, "PARCIAL": 1},
                "is_certification": False,
            }
        ]
    )
    assert current["manifesto"]["coverage_windows"] == expected
