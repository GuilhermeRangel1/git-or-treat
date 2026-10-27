from decimal import Decimal
import os
import json
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.gold_load import ATTEMPTS, BATCH, SCHEMA_VERSION, TABLES
from app.services.gold_import import GoldImportError, import_gold


# Dados artificiais, com total independente: 2 UCs, 30 kWh e R$ 25,50.
SAMPLES = {
    "consumo_mensal_uc": (
        "id_uc;competencia;consumo_kwh;receita_reais",
        ["FAKE-A;2025-01;10;10.10", "FAKE-B;2025-01;20;15.40"],
    ),
    "consumo_receita_bairro": (
        "competencia;municipio;bairro;classe_consumo;consumo_total_kwh;receita_total_reais;qtd_ucs_distintas_faturadas_no_mes",
        ["2025-01;Cidade fictícia;Bairro fictício;Residencial;30;25.50;2"],
    ),
    "diagnostico_receita": (
        "competencia;municipio;classe_consumo;subgrupo_tarifario;bandeira_tarifaria;possui_gd;qtd_ucs_distintas_faturadas_no_mes;soma_faturamentos_mensais;consumo_total_kwh;receita_total_reais;ticket_medio_reais_por_uc;consumo_medio_kwh_por_uc;tarifa_media_efetiva",
        ["2025-01;Cidade fictícia;Residencial;B1;VERDE;Não;2;2;30;25.50;12.75;15;0.85"],
    ),
    "fila_inspecao": (
        "id_uc;municipio;bairro;uf;classe;subgrupo;alimentador;data_ligacao;status;possui_geracao_solar;total_inspecoes_realizadas;total_inspecoes_irregulares;media_consumo_historico;prioridade_inspecao",
        ["FAKE-A;Cidade fictícia;Bairro fictício;PE;Residencial;B1;FAKE-AL;2020-01-01;ATIVA;Não;0;0;;REVISAR"],
    ),
    "indicadores_dec_fec": (
        "id_alimentador;municipio;competencia;total_ucs_alimentador;ucs_interrompidas;frequencia_total_interrupcoes;duracao_total_interrupcoes_horas;DEC;FEC",
        ["FAKE-AL;Cidade fictícia;2025-01;2;1;1;1;0.5;0.5"],
    ),
    "variacao_consumo_uc": (
        "id_uc;municipio;bairro;possui_gd;consumo_medio_inicial;meses_com_leitura_p1;consumo_medio_final;meses_com_leitura_p2;variacao_kwh;variacao_pct;queda_consumo_superior_30_pct",
        ["FAKE-A;Cidade fictícia;Bairro fictício;Não;;0;;0;;;false"],
    ),
    "visao_360_uc": (
        "id_uc;municipio;bairro;uf;classe;subgrupo;alimentador;data_ligacao;status;possui_gd;total_chamados_callcenter;media_satisfacao_atendimento;total_interrupcoes_sofridas;duracao_total_interrupcoes_horas;media_consumo_historico",
        ["FAKE-A;Cidade fictícia;Bairro fictício;PE;Residencial;B1;FAKE-AL;2020-01-01;ATIVA;Não;0;;1;1;10"],
    ),
}


@pytest.fixture
def batch(tmp_path):
    for name, (header, rows) in SAMPLES.items():
        folder = tmp_path / name
        folder.mkdir()
        (folder / "part-1.csv").write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return tmp_path


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request):
    url = "sqlite://"
    if request.param == "postgresql":
        url = os.getenv("TEST_GOLD_POSTGRES_URL")
        if not url:
            pytest.skip("Defina TEST_GOLD_POSTGRES_URL para banco Gold descartável *_test.")
        parsed = make_url(url)
        assert parsed.get_backend_name() == "postgresql" and parsed.database.endswith("_test")
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as connection:
        assert not inspect(connection).get_table_names(), "Use banco descartável vazio."
        if request.param == "postgresql":
            assert connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")) is False
    for table in [ATTEMPTS, BATCH, *TABLES.values()]:
        table.create(engine)
    try:
        yield engine
    finally:
        for table in reversed([ATTEMPTS, BATCH, *TABLES.values()]):
            table.drop(engine)
        engine.dispose()


def test_load_reconciles_money_and_repeated_batch_is_unchanged(database, batch):
    result = import_gold(database, batch, "v1")
    assert result["status"] == "loaded"
    assert result["tables"]["consumo_mensal_uc"]["rows"] == 2
    monthly = TABLES["consumo_mensal_uc"]
    with database.connect() as connection:
        assert connection.scalar(select(func.sum(monthly.c.receita_reais))) == Decimal("25.50")
        assert connection.scalar(select(func.sum(monthly.c.consumo_kwh))) == 30
        timestamp = connection.scalar(select(BATCH.c.importado_em))
    assert import_gold(database, batch, "v1")["status"] == "unchanged"
    with database.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(monthly)) == 2
        assert connection.scalar(select(BATCH.c.importado_em)) == timestamp


def test_failure_in_last_table_rolls_back_all_changes(database, batch):
    import_gold(database, batch, "v1")
    p = batch / "visao_360_uc" / "part-1.csv"
    p.write_text("wrong_header\nnot-valid\n", encoding="utf-8")
    with pytest.raises(GoldImportError, match="cabeçalho"):
        import_gold(database, batch, "v2")
    with database.connect() as connection:
        assert connection.scalar(select(BATCH.c.lote)) == "v1"
        assert connection.scalar(select(func.count()).select_from(TABLES["consumo_mensal_uc"])) == 2
        assert connection.scalar(select(func.count()).select_from(TABLES["visao_360_uc"])) == 1


def test_duplicate_key_in_another_part_is_rejected(database, batch):
    name = "consumo_mensal_uc"
    (batch / name / "part-2.csv").write_text(SAMPLES[name][0] + "\n" + SAMPLES[name][1][0] + "\n", encoding="utf-8")
    with pytest.raises(GoldImportError, match="Chave duplicada"):
        import_gold(database, batch, "v1")
    with database.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(BATCH)) == 0


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1,25", "not-a-number"])
def test_invalid_number_is_rejected_without_payload(database, batch, value):
    p = batch / "consumo_mensal_uc" / "part-1.csv"
    p.write_text(SAMPLES["consumo_mensal_uc"][0] + f"\nFAKE-A;2025-01;{value};25.50\n", encoding="utf-8")
    with pytest.raises(GoldImportError, match="tipo ou chave inválida") as error:
        import_gold(database, batch, "v1")
    assert value not in str(error.value)
    assert "FAKE-A" not in str(error.value)


def test_financial_mismatch_rolls_back(database, batch):
    p = batch / "consumo_mensal_uc" / "part-1.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("15.40", "15.41"), encoding="utf-8")
    with pytest.raises(GoldImportError, match="não reconciliam"):
        import_gold(database, batch, "v1")


def published_snapshot(engine):
    with engine.connect() as connection:
        return {
            table.name: [dict(row) for row in connection.execute(select(table)).mappings()]
            for table in [BATCH, *TABLES.values()]
        }


def test_attempts_keep_version_counts_controls_and_rejections(database, batch):
    first = import_gold(database, batch, "sample-01")
    previous = published_snapshot(database)
    repeated = import_gold(database, batch, "sample-01")
    assert published_snapshot(database) == previous
    (batch / "visao_360_uc" / "part-1.csv").write_text("invalid\n", encoding="utf-8")
    with pytest.raises(GoldImportError) as error:
        import_gold(database, batch, "sample-02")
    assert published_snapshot(database) == previous
    with database.connect() as connection:
        attempts = {row.id: row for row in connection.execute(select(ATTEMPTS))}
        assert len(attempts) == 3
        assert attempts[first["attempt_id"]].status == "loaded"
        assert attempts[repeated["attempt_id"]].status == "unchanged"
        rejected = attempts[error.value.attempt_id]
        assert rejected.status == "failed"
        assert rejected.erro_codigo == "validation_error"
        assert rejected.fingerprint != attempts[first["attempt_id"]].fingerprint
        assert len(rejected.fingerprint) == 64
        assert rejected.manifesto["consumo_mensal_uc"]["rows"] == 2
        assert rejected.manifesto["visao_360_uc"]["validated"] is False
        assert all(row.schema_version == "gold-csv-v1" and row.finalizado_em for row in attempts.values())
        assert connection.scalar(select(BATCH.c.schema_version)) == "gold-csv-v1"
        controls = attempts[first["attempt_id"]].manifesto["consumo_mensal_uc"]
        assert controls["rows"] == 2
        assert Decimal(controls["totals"]["receita_reais"]) == Decimal("25.50")
        assert Decimal(controls["totals"]["consumo_kwh"]) == Decimal("30")
        assert controls["validated"] is True
        assert controls["files"][0]["file"] == "part-1.csv"
        assert len(controls["files"][0]["sha256"]) == 64


@pytest.mark.parametrize("case,code", [
    ("missing", "validation_error"), ("schema", "unsupported_schema"), ("identifier", "invalid_batch"),
])
def test_preflight_failures_are_audited_without_replacing_current_batch(database, batch, case, code):
    import_gold(database, batch, "valid")
    previous = published_snapshot(database)
    kwargs = {}
    name = "rejected"
    if case == "missing":
        (batch / "fila_inspecao" / "part-1.csv").unlink()
    elif case == "schema":
        kwargs["schema_version"] = "unknown-v2"
    else:
        name = "private content / rejected"
    with pytest.raises(GoldImportError) as error:
        import_gold(database, batch, name, **kwargs)
    assert error.value.code == code
    assert published_snapshot(database) == previous
    with database.connect() as connection:
        attempt = connection.execute(select(ATTEMPTS).where(ATTEMPTS.c.id == error.value.attempt_id)).mappings().one()
        assert attempt["status"] == "failed"
        assert attempt["manifesto"] == {}
        assert attempt["erro_codigo"] == code
        assert "private content" not in json.dumps(attempt, default=str)


@pytest.mark.parametrize("name,old,new", [
    ("consumo_mensal_uc", "FAKE-A;2025-01", ";2025-01"),
    ("consumo_mensal_uc", "FAKE-A;2025-01", "   ;2025-01"),
    ("consumo_mensal_uc", "2025-01", "0000-01"),
    ("consumo_mensal_uc", "2025-01", "2025-13"),
    ("consumo_mensal_uc", "10.10", "10.101"),
    ("variacao_consumo_uc", "false", "yes"),
    ("fila_inspecao", "2020-01-01", "invalid-date"),
    ("fila_inspecao", "2020-01-01", "20200101"),
    ("fila_inspecao", ";0;0;", ";1.5;0;"),
    ("fila_inspecao", ";0;0;", ";9223372036854775808;0;"),
])
def test_physical_types_and_required_keys_reject_the_entire_batch(database, batch, name, old, new):
    import_gold(database, batch, "valid")
    previous = published_snapshot(database)
    path = batch / name / "part-1.csv"
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    with pytest.raises(GoldImportError):
        import_gold(database, batch, "invalid")
    assert published_snapshot(database) == previous


def test_success_repetition_and_failed_reload_preserve_orders_and_all_history(database, batch):
    from app.models.operational import InspectionOrder, OperationalOrderHistory, OrderAction, OrderStatus

    order_table = InspectionOrder.__table__
    history_table = OperationalOrderHistory.__table__
    order_table.create(database)
    history_table.create(database)
    try:
        with Session(database) as session:
            order = InspectionOrder(
                uc_id="FAKE-A", reason="Controle sintético", status=OrderStatus.IN_PROGRESS,
                notes="Preservar observação", result="Resultado parcial", idempotency_key="synthetic-order",
                suspicion_reference="fake-ref", suspicion_snapshot={"synthetic": True},
            )
            session.add(order)
            session.flush()
            session.add_all([
                OperationalOrderHistory(order_id=order.id, action=OrderAction.CREATED,
                    new_status=OrderStatus.PENDING, actor="synthetic-operator", order_version=1),
                OperationalOrderHistory(order_id=order.id, action=OrderAction.STATUS_UPDATED,
                    previous_status=OrderStatus.PENDING, new_status=OrderStatus.IN_PROGRESS,
                    details="Histórico sintético", actor="synthetic-operator", order_version=2),
            ])
            session.commit()

        def operations():
            with database.connect() as connection:
                return [list(connection.execute(select(table).order_by(table.c.id))) for table in [order_table, history_table]]

        previous = operations()
        assert import_gold(database, batch, "v1")["status"] == "loaded"
        assert operations() == previous
        assert import_gold(database, batch, "v1")["status"] == "unchanged"
        assert operations() == previous
        for path in batch.glob("*/*.csv"):
            path.write_text(path.read_text(encoding="utf-8").replace("FAKE-A", "FAKE-C"), encoding="utf-8")
        assert import_gold(database, batch, "v2")["status"] == "loaded"
        assert operations() == previous
        published = published_snapshot(database)
        (batch / "visao_360_uc" / "part-1.csv").write_text("broken\n", encoding="utf-8")
        with pytest.raises(GoldImportError):
            import_gold(database, batch, "v3")
        assert operations() == previous
        assert published_snapshot(database) == published
    finally:
        history_table.drop(database)
        order_table.drop(database)


def test_failure_to_record_success_rolls_back_the_data_publication(database, batch):
    import_gold(database, batch, "previous")
    previous = published_snapshot(database)

    def fail_audit(connection, cursor, statement, parameters, context, executemany):
        if context.compiled and context.compiled_parameters:
            values = context.compiled_parameters[0]
            if statement.startswith("UPDATE gold_carga_tentativas") and values.get("status") == "loaded":
                raise OperationalError("private SQL", {"sensitive": "private row"}, Exception("private failure"))

    event.listen(database, "before_cursor_execute", fail_audit)
    try:
        with pytest.raises(GoldImportError) as error:
            import_gold(database, batch, "next")
        assert published_snapshot(database) == previous
        with database.connect() as connection:
            rejected = connection.execute(select(ATTEMPTS).where(ATTEMPTS.c.id == error.value.attempt_id)).mappings().one()
            assert rejected["status"] == "failed"
            assert rejected["erro_codigo"] == "database_error"
            assert "private" not in json.dumps(rejected, default=str)
    finally:
        event.remove(database, "before_cursor_execute", fail_audit)


def test_audit_unavailable_prevents_any_publication(database, batch):
    import_gold(database, batch, "valid")
    previous = published_snapshot(database)
    ATTEMPTS.drop(database)
    try:
        with pytest.raises(GoldImportError) as error:
            import_gold(database, batch, "rejected")
        assert error.value.code == "audit_unavailable"
        assert published_snapshot(database) == previous
    finally:
        ATTEMPTS.create(database)


def test_changed_file_before_commit_preserves_the_previous_batch(database, batch):
    import_gold(database, batch, "valid")
    previous = published_snapshot(database)
    path = batch / "visao_360_uc" / "part-1.csv"

    def change_file(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO gold_visao_360_uc"):
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    event.listen(database, "before_cursor_execute", change_file)
    try:
        with pytest.raises(GoldImportError, match="arquivos mudaram"):
            import_gold(database, batch, "rejected")
        assert published_snapshot(database) == previous
    finally:
        event.remove(database, "before_cursor_execute", change_file)


def test_synthetic_generator_and_cli_load_repetition_failure_and_recovery(tmp_path):
    from pathlib import Path
    from tests.support.migrations import migrated_database

    backend = Path(__file__).resolve().parents[1]
    directory = tmp_path / "synthetic"
    command = [sys.executable, str(backend / "scripts/generate_gold_sample.py"), "--directory", str(directory)]
    generated = subprocess.run(command, capture_output=True, text=True)
    assert generated.returncode == 0, generated.stderr
    assert len(list(directory.glob("*/*.csv"))) == 7
    assert subprocess.run(command, capture_output=True).returncode != 0
    url = f"sqlite:///{tmp_path / 'cli_test.db'}"
    engine = create_engine(url)
    environment = {**os.environ, "DATABASE_URL": url, "APP_ENV": "development",
                   "ANALYTICS_SOURCE": "unavailable", "ORDERS_AUTH_MODE": "service"}
    cli = [sys.executable, str(backend / "scripts/load_gold.py"), "--directory", str(directory),
           "--batch", "synthetic-01", "--schema-version", "gold-csv-v1"]
    try:
        with engine.connect() as connection:
            with migrated_database(connection):
                first = subprocess.run(cli, env=environment, capture_output=True, text=True)
                assert first.returncode == 0, first.stderr
                result = json.loads(first.stdout)
                assert result["status"] == "loaded"
                assert result["schema_version"] == "gold-csv-v1"
                assert Decimal(result["tables"]["consumo_mensal_uc"]["totals"]["receita_reais"]) == Decimal("25.50")
                previous = published_snapshot(engine)
                repeated = subprocess.run(cli, env=environment, capture_output=True, text=True)
                assert repeated.returncode == 0, repeated.stderr
                assert json.loads(repeated.stdout)["status"] == "unchanged"
                assert published_snapshot(engine) == previous
                path = directory / "visao_360_uc" / "part-000.csv"
                original = path.read_text(encoding="utf-8")
                path.write_text("invalid;private-row-data\n", encoding="utf-8")
                rejected = subprocess.run(cli, env=environment, capture_output=True, text=True)
                assert rejected.returncode == 1
                assert "Tentativa:" in rejected.stderr
                assert "private-row-data" not in rejected.stderr
                assert "Traceback" not in rejected.stderr
                assert published_snapshot(engine) == previous
                path.write_text(original, encoding="utf-8")
                recovered = subprocess.run(cli, env=environment, capture_output=True, text=True)
                assert recovered.returncode == 0, recovered.stderr
                assert json.loads(recovered.stdout)["status"] == "unchanged"
                assert published_snapshot(engine) == previous
                with engine.connect() as reader:
                    statuses = list(reader.scalars(select(ATTEMPTS.c.status).order_by(ATTEMPTS.c.iniciado_em)))
                    assert statuses == ["loaded", "unchanged", "failed", "unchanged"]
    finally:
        engine.dispose()
