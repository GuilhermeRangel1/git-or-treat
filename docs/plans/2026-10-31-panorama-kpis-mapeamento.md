# Mapeamento dos KPIs do Panorama - pacote final

Pacote: `GOLD_20261031T020143Z_fd69c375`. Fonte: contrato CSV v2, dicionário Gold e schemas físicos. A investigação anterior considerou apenas `diagnostico_receita` e deixou de usar a projeção por UC/mês.

| Cartão | Origem e regra | Limite |
| --- | --- | --- |
| Valor faturado / consumo apurado / preço observado | Campos comparáveis de `diagnostico_receita`; somas e razão da mesma base | Valores observados; sem fechamento certificado |
| UCs faturadas no mês | DISTINCT `id_uc` em `consumo_mensal_uc`, competência e `tem_fatura=true`; dimensões em `visao_360_uc` por chave única | Cadastro atual; inclui faturadas sem leitura |
| UCs cadastradas no lote | DISTINCT `id_uc` em `visao_360_uc`; município/classe atuais; todos os status | Fotografia do lote; não é população ativa histórica nem comparação mensal. ID legado `ucsAtivas` preservado |
| Energia faturada | Sem coluna de kWh de faturamento comprovada, inclusive em `faturas_uc` | Manifesto declara `SEM_MEDIDA_COMPROVADA`; consumo medido não substitui energia faturada |

Ordens continuam operacionais e separadas das recargas. Fila usa `fila_inspecao`, chave `id_uc`, motivo/posição e estado de recuperação. Operação usa `indicadores_dec_fec`, grão alimentador/mês, com numeradores e denominadores já mapeados no contrato DEV-13.1. Não há mudança de regra desses domínios nesta correção.

A reconciliação deve contar conjuntos de IDs em memória a partir dos CSVs e comparar com API sem imprimir identificadores ou valores de negócio. Conferir global, município e classe, mês atual/anterior e ausência de leitura. Não somar fatos financeiros a partir de joins de faturas/leituras cruas.

## Evidencias executadas

- `python -m pytest backend/tests/test_panorama_uc_counts.py backend/tests/test_panorama.py -q`: 18 passaram. Cobre fatura sem leitura, UC sem cadastro, filtros, duas competencias, UC com leitura sem fatura e periodo ausente.
- `PANORAMA_CSV_DIR`, `PANORAMA_API_URL`, `PANORAMA_CREDENTIALS_FILE` explicitos, com `python -m pytest backend/tests/test_panorama_csv_reconciliation.py -q`: 1 passou contra lote final e API local. Compara conjuntos CSV independentes aos contadores publicados e referencia anterior, sem imprimir IDs ou valores de negocio. Login de validacao grava sessao operacional; consultas Gold apenas leem.
- `npm run build`: TypeScript/Vite passaram. Sem revisao visual nesta correcao.

Testes PostgreSQL ja existentes foram adaptados para criar as duas fontes adicionais; sua reexecucao em PostgreSQL descartavel nao foi realizada nesta correcao. Os testes de repositorio usam SQLite com schema anexado e a reconciliacao CSV exercita PostgreSQL real pela API.

Frontend: `npm run test -- src/features/panorama/PanoramaPage.test.tsx`: 19 passaram. Reconciliacao final CSV/API repetida apos incluir filtro combinado municipio/classe: 1 passou (17,82 s). `git diff --check`: passou.
