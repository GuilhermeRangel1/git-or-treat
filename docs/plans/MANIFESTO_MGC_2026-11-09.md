# Manifesto de congelamento — bateria MGC

- **Versão:** `MGC-2026-11-09-v3`
- **Data:** 09/11/2026
- **Estado:** 230 casos novos revisados e congelados para a linha de base; a avaliação Gemini completa ainda não foi executada.
- **Distribuição:** 170 perguntas individuais, 20 rankings/comparações, 10 coloquiais, 10 de continuidade, 10 compostas e 10 de ambiguidade/limites/segurança.
- **Cobertura de métricas:** 17 métricas do catálogo Gold v2, cada uma com pelo menos dez perguntas individuais. `billing.average_ticket` tem 11; MGC-006 consulta DEC e FEC conjuntamente, contando para ambas.
- **Divisão:** 186 diagnósticos / 44 holdout; 198 famílias semânticas, sem família repartida.
- **Gold v2:** lote `GOLD_20261103T173853Z_76c37784`; fingerprint `d1e9d3cb4455895155c09da82865807f5f83a608f832246be91e08063d158856`.
- **Publicação:** `9a42137a-399e-4974-876d-0169bdc530e0`.
- **Gabaritos independentes:** 219 casos com SQL esperado; 257 resultados caso/métrica/período; 2.001 linhas; zero conjuntos vazios e um NULL numérico esperado (MGC-041). Onze casos de estado não executam SQL.
- **Controles C05–C09:** seis consultas de rota (CTL-001–006) passaram com Gemini, Gold e reconciliação SQL independente. CTL-003 teve um 502 transitório do provedor e passou na repetição. Essa amostra de integração não substitui a baseline dos 186 casos diagnósticos.
- **Verificação estrutural:** 10 testes focados passaram, incluindo cobertura de todas as métricas, consistência do catálogo, split e relatório de referências. A baseline Gemini e o holdout continuam pendentes.
- **MGC-015:** comparação de consumo/receita reconciliada para as janelas solicitadas; não há decomposição preço-volume publicada para esse par, portanto não autoriza atribuição causal.
- **MGC-006:** DEC/FEC ponderados recalculados com numeradores somados e denominador constante contado uma vez; rota reconciliada e aviso de cobertura não certificada preservado.

## Hashes SHA-256 dos artefatos congelados

| Arquivo | SHA-256 |
| --- | --- |
| `docs/plans/CASOS_MELHORIA_GERAL_CHATBOT.json` | `e3eb44d0210343ff50e11ff9976a6a944ff75f749a6787db2ae7fab488fb51fb` |
| `backend/app/catalogs/gold_v2.json` | `c567d41d0240266141d2b112e2f32a1ad41ce91d987f1627f8dfb0344d2382c7` |
| `docs/plans/REFERENCIAS_GOLD_MGC_230.sql` | `9096c4bc2349167d0bbdc54dd557c5e9a5f92e6bac162ecd2cf6efb4046937e8` |
| `docs/plans/REFERENCIAS_SQL_MELHORIA_GERAL_CHATBOT.sql` | `959267c361458ed4feed063c58d79485211e77765f3f95f2cf01e684ce5b060e` |
| `docs/plans/GABARITOS_GOLD_MELHORIA_GERAL_CHATBOT.json` | `9fd344b2b9aecf2716eda814dc7fe9b064b99616301031b21c38259a7f518faa` |
| `docs/plans/GABARITOS_REFERENCIA_MELHORIA_GERAL_CHATBOT.md` | `4cad9f57eb5448e5eb3ab2020afb611f49ad6427f6bf8fe50cba08f89ac9277b` |
| `docs/plans/AMOSTRA_INICIAL_MELHORIA_GERAL_CHATBOT.md` | `6db5d615bee9c8873c0dcb06b2e006d16ce58dbe3c86cdc89fe8259d63efe80e` |
| `docs/plans/MATRIZ_COBERTURA_MELHORIA_GERAL_CHATBOT.md` | `56a3cd504c2f86ac63bedce093e0e7971d719e23d185deafd1f565e420611f75` |
| `docs/plans/REVISAO_SEMANTICA_MELHORIA_GERAL_CHATBOT.md` | `66a9a9de497d67d107c3dc79789ada09645c43edb46a79ee534ca3a045cc2697` |
| `docs/plans/TODO_Melhoria_Geral_Chatbot_VEnergy.md` | `6e444db1c7c346b5603ad2113f8cfe4ea1a8a22f57c8ebc2af638e52908d5374` |
| `backend/scripts/run_mgc_f1_baseline.py` | `1673564b16fffaa20598fdc1ac5cca5f03ff8f6752282dcb9a3d5d70d25435db` |
| `backend/tests/test_run_mgc_f1_baseline.py` | `0f3a01f6aae44a4d38309ed3c9a74efc724eee34a93dd26e277e91bb76adf345` |
| `backend/scripts/build_mgc_gold_reference_report.py` | `cfbc767beb21e927e796d217e8ce832a20876cd611bd3703ef702825ee5defed` |
| `backend/tests/test_melhoria_geral_case_set.py` | `f0b63d13105c2e5a25ef7fd2277dfaf3ab07855ce578b3e500a7cce22af23838` |
| `backend/tests/fixtures/genai_gold_released_controls_c05_c09.json` | `57e1b8335482c9733f2cc50a3fc9c4e402009144bc881b139dd914ed6509ad47` |
| `backend/tests/test_genai_sql_live_gold_route.py` | `2013c6612a243436b8e323592ab860e3d7795cf88c31c59ae162760b85ede496` |

Alterar qualquer artefato listado exige gerar nova versão do conjunto e recalcular os gabaritos afetados. O holdout deve permanecer fora dos ajustes.
