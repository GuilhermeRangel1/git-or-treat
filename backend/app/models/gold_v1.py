"""Contrato físico observado nos sete CSVs v1; não homologa suas métricas.

Snapshot também utilizado pela migração goldv1000001. Uma mudança de contrato
deve usar nova revisão e módulo, preservando esta definição histórica.
"""
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, Float,
    Index, JSON, MetaData, Numeric, String, Table, Text,
)

METADATA = MetaData()  # Snapshot imutável da revisão goldv1000001.


def _table(name, key, strings, integers="", numbers="", money="", dates="", booleans=""):
    columns = []
    for names, factory in (
        (strings, Text), (integers, BigInteger), (numbers, Float),
        (money, lambda: Numeric(38, 2)), (dates, Date), (booleans, Boolean),
    ):
        for field in names.split():
            columns.append(Column(field, factory(), primary_key=field in key, nullable=field not in key))
    return Table(f"gold_{name}", METADATA, *columns)


TABLES = {
    "consumo_mensal_uc": _table("consumo_mensal_uc", {"id_uc", "competencia"}, "id_uc competencia", numbers="consumo_kwh", money="receita_reais"),
    "consumo_receita_bairro": _table(
        "consumo_receita_bairro", {"competencia", "municipio", "bairro", "classe_consumo"},
        "competencia municipio bairro classe_consumo", integers="qtd_ucs_distintas_faturadas_no_mes",
        numbers="consumo_total_kwh", money="receita_total_reais",
    ),
    "diagnostico_receita": _table(
        "diagnostico_receita", {"competencia", "municipio", "classe_consumo", "subgrupo_tarifario", "bandeira_tarifaria", "possui_gd"},
        "competencia municipio classe_consumo subgrupo_tarifario bandeira_tarifaria possui_gd",
        integers="qtd_ucs_distintas_faturadas_no_mes soma_faturamentos_mensais",
        numbers="consumo_total_kwh ticket_medio_reais_por_uc consumo_medio_kwh_por_uc tarifa_media_efetiva", money="receita_total_reais",
    ),
    "fila_inspecao": _table(
        "fila_inspecao", {"id_uc"}, "id_uc municipio bairro uf classe subgrupo alimentador status possui_geracao_solar prioridade_inspecao",
        integers="total_inspecoes_realizadas total_inspecoes_irregulares", numbers="media_consumo_historico", dates="data_ligacao",
    ),
    "indicadores_dec_fec": _table(
        "indicadores_dec_fec", {"id_alimentador", "competencia"}, "id_alimentador municipio competencia",
        integers="total_ucs_alimentador ucs_interrompidas frequencia_total_interrupcoes", numbers="duracao_total_interrupcoes_horas DEC FEC",
    ),
    "variacao_consumo_uc": _table(
        "variacao_consumo_uc", {"id_uc"}, "id_uc municipio bairro possui_gd", integers="meses_com_leitura_p1 meses_com_leitura_p2",
        numbers="consumo_medio_inicial consumo_medio_final variacao_kwh variacao_pct", booleans="queda_consumo_superior_30_pct",
    ),
    "visao_360_uc": _table(
        "visao_360_uc", {"id_uc"}, "id_uc municipio bairro uf classe subgrupo alimentador status possui_gd",
        integers="total_chamados_callcenter total_interrupcoes_sofridas",
        numbers="media_satisfacao_atendimento duracao_total_interrupcoes_horas media_consumo_historico", dates="data_ligacao",
    ),
}
Index("ix_gold_mensal_competencia", TABLES["consumo_mensal_uc"].c.competencia)
BATCH = Table(
    "gold_carga_atual", METADATA,
    Column("id", BigInteger, primary_key=True), Column("lote", String(100), nullable=False),
    Column("fingerprint", String(64), nullable=False), Column("importado_em", DateTime(timezone=True), nullable=False),
    Column("manifesto", JSON, nullable=False), CheckConstraint("id = 1", name="ck_gold_carga_unica"),
)
