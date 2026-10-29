"""Gera sete CSVs inteiramente artificiais para verificar a infraestrutura DEV-12."""
import argparse
import json
from pathlib import Path

# Duas UCs fictícias; controle independente: 30 kWh e R$ 25,50.
SAMPLES = {'consumo_mensal_uc': ('id_uc;competencia;consumo_kwh;receita_reais',
                       ['FAKE-A;2025-01;10;10.10', 'FAKE-B;2025-01;20;15.40']),
 'consumo_receita_bairro': ('competencia;municipio;bairro;classe_consumo;consumo_total_kwh;receita_total_reais;qtd_ucs_distintas_faturadas_no_mes',
                            ['2025-01;Cidade fictícia;Bairro fictício;Residencial;30;25.50;2']),
 'diagnostico_receita': ('competencia;municipio;classe_consumo;subgrupo_tarifario;bandeira_tarifaria;possui_gd;qtd_ucs_distintas_faturadas_no_mes;soma_faturamentos_mensais;consumo_total_kwh;receita_total_reais;ticket_medio_reais_por_uc;consumo_medio_kwh_por_uc;tarifa_media_efetiva',
                         ['2025-01;Cidade '
                          'fictícia;Residencial;B1;VERDE;Não;2;2;30;25.50;12.75;15;0.85']),
 'fila_inspecao': ('id_uc;municipio;bairro;uf;classe;subgrupo;alimentador;data_ligacao;status;possui_geracao_solar;total_inspecoes_realizadas;total_inspecoes_irregulares;media_consumo_historico;prioridade_inspecao',
                   ['FAKE-A;Cidade fictícia;Bairro '
                    'fictício;PE;Residencial;B1;FAKE-AL;2020-01-01;ATIVA;Não;0;0;;REVISAR']),
 'indicadores_dec_fec': ('id_alimentador;municipio;competencia;total_ucs_alimentador;ucs_interrompidas;frequencia_total_interrupcoes;duracao_total_interrupcoes_horas;DEC;FEC',
                         ['FAKE-AL;Cidade fictícia;2025-01;2;1;1;1;0.5;0.5']),
 'variacao_consumo_uc': ('id_uc;municipio;bairro;possui_gd;consumo_medio_inicial;meses_com_leitura_p1;consumo_medio_final;meses_com_leitura_p2;variacao_kwh;variacao_pct;queda_consumo_superior_30_pct',
                         ['FAKE-A;Cidade fictícia;Bairro fictício;Não;;0;;0;;;false']),
 'visao_360_uc': ('id_uc;municipio;bairro;uf;classe;subgrupo;alimentador;data_ligacao;status;possui_gd;total_chamados_callcenter;media_satisfacao_atendimento;total_interrupcoes_sofridas;duracao_total_interrupcoes_horas;media_consumo_historico',
                  ['FAKE-A;Cidade fictícia;Bairro '
                   'fictício;PE;Residencial;B1;FAKE-AL;2020-01-01;ATIVA;Não;0;;1;1;10'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if args.directory.exists():
        parser.error("Use um diretório novo; os arquivos existentes não serão sobrescritos.")
    args.directory.mkdir(parents=True)
    for name, (header, rows) in SAMPLES.items():
        folder = args.directory / name
        folder.mkdir()
        (folder / "part-000.csv").write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    # Metadados inteiramente artificiais; prod exercita a validação do contrato.
    manifest = {
        "ambiente": "prod", "schema_version": "gold-csv-v1",
        "run_id": "GOLD_20250101T000000Z_aaaaaaaa", "lote": "GOLD_20250101T000000Z_aaaaaaaa",
        "run_id_silver": "20250101T000000Z_bbbbbbbb", "lote_bronze_silver": "20250101T000000Z_cccccccc",
        "data_processamento_gold": "2025-01-01T00:00:00Z", "tabelas_exportadas": list(SAMPLES),
        "responsavel": "Amostra inteiramente artificial",
    }
    (args.directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    print("Amostra sintética criada: 7 tabelas, 2 UCs mensais, 30 kWh e R$ 25,50.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
