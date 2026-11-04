"""Snapshot físico observado das quinze tabelas analíticas Gold v2.

O cadastro de titulares pertence a um pacote e schema restritos separados.
Este módulo não o registra nem concede acesso a ele.
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
)

SCHEMA = "gold_v2"
METADATA = MetaData()


def _table(name: str, primary_key: tuple[str, ...], fields: tuple[tuple[str, object], ...]) -> Table:
    columns = [
        Column(field, column_type, primary_key=field in primary_key, nullable=field not in primary_key)
        for field, column_type in fields
    ]
    return Table(name, METADATA, *columns, schema=SCHEMA)


TABLES = {
    "diagnostico_receita": _table("diagnostico_receita", (
        "competencia", "municipio", "classe_consumo", "subgrupo_tarifario", "bandeira_tarifaria", "possui_gd",
    ), (
        ("competencia", Text()), ("municipio", Text()), ("classe_consumo", Text()),
        ("subgrupo_tarifario", Text()), ("bandeira_tarifaria", Text()), ("possui_gd", Text()),
        ("receita_total_reais", Numeric(38, 2)), ("receita_com_leitura_reais", Numeric(38, 2)),
        ("receita_sem_leitura_reais", Numeric(38, 2)), ("consumo_total_kwh", Float()),
        ("receita_base_comparavel_reais", Numeric(38, 2)), ("consumo_base_comparavel_kwh", Float()),
        ("qtd_ucs_distintas_faturadas_no_mes", BigInteger()), ("qtd_ucs_com_leitura", BigInteger()),
        ("soma_faturamentos_mensais", BigInteger()), ("qtd_leituras_observadas", BigInteger()),
        ("qtd_leituras_validas", BigInteger()), ("ticket_medio_reais_por_uc", Numeric(34, 6)),
        ("consumo_medio_kwh_por_uc", Float()), ("tarifa_media_efetiva", Float()),
    )),
    "indicadores_dec_fec": _table("indicadores_dec_fec", ("id_alimentador", "competencia"), (
        ("id_alimentador", Text()), ("municipio", Text()), ("competencia", Text()),
        ("total_ucs_alimentador", BigInteger()), ("ucs_interrompidas", BigInteger()),
        ("frequencia_total_interrupcoes", BigInteger()), ("duracao_total_interrupcoes_horas", Float()),
        ("DEC", Float()), ("FEC", Float()),
    )),
    "fila_inspecao": _table("fila_inspecao", ("id_uc",), (
        ("id_uc", Text()), ("municipio", Text()), ("bairro", Text()), ("uf", Text()),
        ("classe", Text()), ("subgrupo", Text()), ("alimentador", Text()), ("data_ligacao", Date()),
        ("status", Text()), ("possui_geracao_solar", Text()), ("total_inspecoes_realizadas", BigInteger()),
        ("total_inspecoes_irregulares", BigInteger()), ("media_consumo_historico", Float()),
        ("prioridade_inspecao", Text()), ("motivo_prioridade", Text()),
        ("ordem_prioridade_inspecao", Integer()), ("posicao_fila_inspecao", Integer()),
        ("media_historica_recuperacao_kwh_por_inspecao", Float()),
        ("intervalo_historico_recuperacao_inferior_kwh", Float()),
        ("intervalo_historico_recuperacao_superior_kwh", Float()),
        ("referencia_media_historica_recuperacao", Text()), ("estado_media_historica_recuperacao", Text()),
        ("energia_estimada_recuperavel_kwh", Float()), ("intervalo_recuperacao_inferior_kwh", Float()),
        ("intervalo_recuperacao_superior_kwh", Float()), ("estado_estimativa_recuperacao", Text()),
        ("metodo_estimativa_recuperacao", Text()), ("validacao_recuperacao_json", Text()),
    )),
    "visao_360_uc": _table("visao_360_uc", ("id_uc",), (
        ("id_uc", Text()), ("municipio", Text()), ("bairro", Text()), ("uf", Text()),
        ("classe", Text()), ("subgrupo", Text()), ("alimentador", Text()), ("data_ligacao", Date()),
        ("status", Text()), ("possui_gd", Text()), ("total_chamados_callcenter", BigInteger()),
        ("media_satisfacao_atendimento", Float()), ("total_interrupcoes_sofridas", BigInteger()),
        ("duracao_total_interrupcoes_horas", Float()), ("media_consumo_historico", Float()),
    )),
    "consumo_mensal_uc": _table("consumo_mensal_uc", ("id_uc", "competencia"), (
        ("id_uc", Text()), ("competencia", Text()), ("consumo_kwh", Float()),
        ("receita_reais", Numeric(30, 2)), ("receita_com_leitura_reais", Numeric(30, 2)),
        ("receita_sem_leitura_reais", Numeric(30, 2)), ("receita_base_comparavel_reais", Numeric(30, 2)),
        ("consumo_base_comparavel_kwh", Float()), ("tem_fatura", Boolean()), ("tem_leitura", Boolean()),
        ("qtd_faturas", BigInteger()), ("qtd_leituras_observadas", BigInteger()),
        ("qtd_leituras_validas", BigInteger()),
    )),
    "consumo_receita_bairro": _table("consumo_receita_bairro", (
        "competencia", "municipio", "bairro", "classe_consumo",
    ), (
        ("competencia", Text()), ("municipio", Text()), ("bairro", Text()), ("classe_consumo", Text()),
        ("receita_total_reais", Numeric(38, 2)), ("receita_com_leitura_reais", Numeric(38, 2)),
        ("receita_sem_leitura_reais", Numeric(38, 2)), ("consumo_total_kwh", Float()),
        ("receita_base_comparavel_reais", Numeric(38, 2)), ("consumo_base_comparavel_kwh", Float()),
        ("qtd_ucs_distintas_faturadas_no_mes", BigInteger()), ("qtd_ucs_com_leitura", BigInteger()),
        ("soma_faturamentos_mensais", BigInteger()), ("qtd_leituras_observadas", BigInteger()),
        ("qtd_leituras_validas", BigInteger()),
    )),
    "variacao_consumo_uc": _table("variacao_consumo_uc", ("id_uc",), (
        ("id_uc", Text()), ("municipio", Text()), ("bairro", Text()), ("possui_gd", Text()),
        ("consumo_medio_inicial", Float()), ("meses_com_leitura_p1", BigInteger()),
        ("consumo_medio_final", Float()), ("meses_com_leitura_p2", BigInteger()),
        ("variacao_kwh", Float()), ("variacao_pct", Float()), ("queda_consumo_superior_30_pct", Boolean()),
    )),
    "faturas_uc": _table("faturas_uc", ("id_fatura",), (
        ("id_fatura", Text()), ("id_uc", Text()), ("mes_referencia", Text()), ("data_emissao", Date()),
        ("data_vencimento", Date()), ("data_pagamento", Date()), ("valor_energia", Numeric(20, 2)),
        ("tributos", Numeric(20, 2)), ("valor_total", Numeric(20, 2)), ("bandeira_tarifaria", Text()),
        ("status", Text()), ("valor_fatura_declarada_em_aberto_reais", Numeric(20, 2)),
        ("valor_em_aberto_reais", Numeric(20, 2)), ("situacao_pagamento_analitica", Text()),
        ("flag_paga", Boolean()), ("flag_tem_pagamento", Boolean()), ("flag_valor_inconsistente", Boolean()),
        ("flag_data_pagamento_inconclusiva", Boolean()), ("flag_paga_sem_data_valida", Boolean()),
        ("flag_pagamento_antes_emissao", Boolean()), ("flag_pagamento_sentinela", Boolean()),
        ("flag_pagamento_futuro", Boolean()), ("flag_emissao_sentinela", Boolean()),
        ("flag_emissao_futura", Boolean()), ("flag_vencimento_sentinela", Boolean()),
        ("flag_valor_negativo", Boolean()), ("data_processamento_gold", DateTime(timezone=True)),
    )),
    "medidor_uc": _table("medidor_uc", ("id_medidor",), (
        ("id_medidor", Text()), ("id_uc", Text()), ("modelo", Text()), ("tipo", Text()),
        ("data_instalacao", Date()), ("data_retirada", Date()), ("status", Text()),
        ("flag_instalacao_sentinela", Boolean()), ("flag_instalacao_futura", Boolean()),
        ("flag_retirada_sentinela", Boolean()), ("flag_retirada_futura", Boolean()),
        ("ingestao_data", DateTime(timezone=True)), ("situacao_na_referencia", Text()),
    )),
    "atendimentos_uc": _table("atendimentos_uc", ("protocolo",), (
        ("protocolo", Text()), ("id_uc", Text()), ("canal", Text()), ("assunto", Text()),
        ("subassunto", Text()), ("data_abertura", DateTime(timezone=True)),
        ("data_fechamento", DateTime(timezone=True)), ("nota_satisfacao", Float()),
        ("qtd_tratativas", Integer()), ("_abertura_futura", Boolean()), ("_fechamento_futura", Boolean()),
        ("_nota_negativa", Boolean()), ("_nota_invalida", Boolean()),
        ("ingestao_data", DateTime(timezone=True)),
    )),
    "ocorrencias_uc": _table("ocorrencias_uc", ("id_ocorrencia", "id_uc"), (
        ("id_ocorrencia", Text()), ("id_uc", Text()), ("alimentador", Text()), ("tipo", Text()),
        ("causa", Text()), ("data_abertura", DateTime(timezone=True)),
        ("data_encerramento", DateTime(timezone=True)), ("duracao_min", Float()),
        ("flag_duracao_incompativel", Boolean()), ("flag_abertura_futura", Boolean()),
        ("flag_encerramento_futuro", Boolean()), ("ingestao_data", DateTime(timezone=True)),
    )),
    "gd_uc": _table("gd_uc", ("id_uc",), (
        ("id_uc", Text()), ("potencia_kwp", Float()), ("data_conexao", Date()), ("modalidade", Text()),
        ("flag_conexao_futura", Boolean()), ("flag_conexao_sentinela", Boolean()),
        ("data_processamento_gold", DateTime(timezone=True)),
    )),
    "tratativas_uc": _table("tratativas_uc", ("protocolo", "posicao_historico"), (
        ("protocolo", Text()), ("id_uc", Text()), ("posicao_historico", Integer()),
        ("sequencia_origem", Integer()), ("data_tratativa", DateTime(timezone=True)),
        ("acao_categoria", Text()), ("canal", Text()), ("flag_data_invalida", Boolean()),
        ("flag_data_futura", Boolean()), ("flag_sequencia_invalida", Boolean()),
        ("data_processamento_gold", DateTime(timezone=True)),
    )),
    "cobertura_dominios": _table("cobertura_dominios", ("dominio", "competencia", "recorte"), (
        ("dominio", Text()), ("competencia", Text()), ("recorte", Text()), ("natureza_temporal", Text()),
        ("estado_cobertura", Text()), ("qtd_registros", BigInteger()), ("qtd_sem_competencia", BigInteger()),
        ("zero_registros_confirmado", Boolean()), ("data_corte_evidencia", DateTime(timezone=True)),
        ("referencia_evidencia", Text()), ("motivo", Text()), ("origem_janela", Text()),
        ("natureza_certificacao", Text()), ("reconciliacao_extracao_json", Text()),
        ("run_id_silver", Text()), ("lote_bronze_silver", Text()),
        ("data_processamento_gold", DateTime(timezone=True)),
    )),
    "decomposicao_receita": _table("decomposicao_receita", (
        "municipio", "bairro", "classe_consumo", "inicio_p0", "fim_p0", "inicio_p1", "fim_p1",
    ), (
        ("municipio", Text()), ("bairro", Text()), ("classe_consumo", Text()),
        ("qtd_ucs_base_comum", BigInteger()), ("qtd_ucs_entrantes", BigInteger()),
        ("qtd_ucs_saintes", BigInteger()), ("qtd_ucs_observadas", BigInteger()),
        ("faturamento_p0_reais", Float()), ("faturamento_p1_reais", Float()),
        ("efeito_volume_reais", Float()), ("efeito_preco_observado_reais", Float()),
        ("efeito_interacao_reais", Float()), ("variacao_entradas_reais", Float()),
        ("variacao_saidas_reais", Float()), ("variacao_sem_leitura_fora_base_reais", Float()),
        ("variacao_outros_fora_base_reais", Float()), ("estado_decomposicao", Text()),
        ("variacao_faturamento_total_reais", Float()), ("residuo_reconciliacao_reais", Float()),
        ("inicio_p0", Text()), ("fim_p0", Text()), ("inicio_p1", Text()), ("fim_p1", Text()),
        ("metodo", Text()), ("run_id_silver", Text()), ("lote_bronze_silver", Text()),
        ("data_processamento_gold", DateTime(timezone=True)),
    )),
}


Index("ix_gold_v2_consumo_mensal_competencia", TABLES["consumo_mensal_uc"].c.competencia)
Index("ix_gold_v2_consumo_bairro_competencia", TABLES["consumo_receita_bairro"].c.competencia)
Index("ix_gold_v2_diagnostico_competencia", TABLES["diagnostico_receita"].c.competencia)
Index("ix_gold_v2_dec_fec_competencia", TABLES["indicadores_dec_fec"].c.competencia)
for _name in ("faturas_uc", "medidor_uc", "atendimentos_uc", "ocorrencias_uc", "tratativas_uc", "gd_uc"):
    Index(f"ix_gold_v2_{_name}_id_uc", TABLES[_name].c.id_uc)
Index("ix_gold_v2_cobertura_competencia", TABLES["cobertura_dominios"].c.competencia)
