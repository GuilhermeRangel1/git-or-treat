from decimal import Decimal
import os

import pytest
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.models.gold_v1 import BATCH, TABLES
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
    for table in [BATCH, *TABLES.values()]:
        table.create(engine)
    try:
        yield engine
    finally:
        for table in reversed([BATCH, *TABLES.values()]):
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
    with pytest.raises(IntegrityError):
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
