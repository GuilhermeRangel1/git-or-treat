# TSQL-03 — schema ativo, grants e relações candidatas

Data: 06/11/2026. Escopo: preparar a admissão F1 contra drift e consolidar os caminhos candidatos a JOIN sem habilitar JOIN.

## Inspeção da publicação ativa

Em 06/11/2026, após o daemon Docker ficar disponível, a publicação ativa foi inspecionada localmente pelo papel efetivo `venergy_genai_reader`, em PostgreSQL `v_energy`, com consultas somente a catálogos/metadados e tabelas de controle. Cada consulta foi executada dentro de `BEGIN READ ONLY`, com `statement_timeout=5s`; nenhuma linha analítica foi consultada e nenhuma permissão ou objeto foi alterado. A tabela `gold.publicacao_atual` confirmou `schema_version=gold-csv-v2`.

Resultado físico: 15/15 tabelas e 239/239 colunas de `gold_v2`; todos os conjuntos de colunas, tipos PostgreSQL, chaves primárias e grãos coincidiram com `backend/app/models/gold_v2.py`. Não houve divergência de schema.

Resultado de autorização efetiva: o papel não é superuser e não tem CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS, membership em outros papéis, CREATE/TEMP no banco ou CREATE nos schemas da aplicação. Tem USAGE em `gold_v2`, SELECT de tabela nas três tabelas de controle `gold.publicacao_atual`, `gold.publicacao_linhagem` e `gold.publicacao_contexto`, e SELECT de coluna em exatamente 69 colunas Gold v2 distribuídas pela matriz aprovada. Varredura de schemas não sistêmicos encontrou zero SELECT adicional, zero privilégios de escrita em tabelas/colunas e zero acesso a sequências ou funções de aplicação. Não há SELECT nas superfícies pessoais/operacionais excluídas.

A checagem física foi comparada diretamente com os modelos versionados, sem tratar modelos como prova da instância. O verificador de prontidão completo `backend/scripts/check_genai_runtime.py` não foi executado porque também realiza outras ações operacionais; o guard de drift continua coberto pelos testes locais de admissão/executor. Nenhum drift foi provocado deliberadamente na publicação ativa.

## Barreira contra drift da publicação

Foi acrescentada `assert_live_f1_catalog` no Backend. Para a fonte `gold_v2.diagnostico_receita`, ela compara somente metadados com o modelo/catálogo instalado:

- conjunto de colunas e tipos;
- precisão e escala Decimal e sinal de timezone;
- chave primária/grão;
- `USAGE` do schema e `SELECT` efetivo nas colunas que o escopo F1 pode consultar.

A admissão chama a verificação ao resolver metadados de planejamento. O executor a repete dentro do snapshot PostgreSQL somente leitura, imediatamente antes de executar o SQL canônico. A readiness operacional `backend/scripts/check_genai_runtime.py` também usa a mesma barreira. A validação não consulta valores Gold e falha fechada quando o schema ou o privilégio necessário diverge. Isso prova a implementação contra fixtures locais; a execução sobre a publicação real e os grants reais permanece pendente.

## Mapa conservador de relações futuras

Os modelos físicos Gold v2 declaram grãos/chaves, mas não declaram Foreign Keys. Logo, a coluna “cardinalidade” abaixo é uma hipótese estrutural derivada do grão e da linhagem documentada, não uma relação verificada na instância publicada.

| Fontes candidatas | Chaves compartilhadas | Risco/cardinalidade estrutural | Próxima evidência antes de qualquer JOIN |
| --- | --- | --- | --- |
| `diagnostico_receita` ↔ `consumo_receita_bairro` | competência, município, classe | Muitos para muitos: o primeiro também varia por subgrupo, bandeira e GD; o segundo por bairro. Junção crua pode multiplicar faturamento. | Pré-agregação definida para ambos os lados e reconciliação por período/município/classe contra controles independentes. |
| `diagnostico_receita` ↔ `indicadores_dec_fec` | competência, município | Muitos para muitos: receita tem dimensões comerciais; DEC/FEC tem alimentador. Município e mês não identificam alimentador nem uma linha de receita. | Regra de atribuição município/alimentador e fórmula aprovada; proibir soma de DEC/FEC. |
| `visao_360_uc` ↔ `fila_inspecao` / `variacao_consumo_uc` | `id_uc` | Um para um pelo grão declarado de cada projeção, mas sem FK e sem prova de que coortes/snapshots coincidem. | Mesmo lote, validade temporal, cobertura de UC e igualdade de cardinalidade/chaves na publicação ativa. |
| projeções por UC ↔ `consumo_mensal_uc`, `faturas_uc`, `medidor_uc`, `atendimentos_uc`, `ocorrencias_uc`, `tratativas_uc` | `id_uc` (ou `protocolo` entre atendimento e tratativa) | Um para muitos segundo o grão mensal, de registro, protocolo ou histórico; uma junção pode multiplicar fatos independentes. | Cardinalidade e vigência observadas; agregação de cada fato no grão-alvo antes de juntar e reconciliação independente. |
| projeções por UC ↔ `gd_uc` | `id_uc` | Um para um pelo grão declarado de `gd_uc`; isso não comprova vigência temporal para uma competência. | Regra de vigência aprovada e conferência no mesmo lote. |

**F1 continua usando exclusivamente `diagnostico_receita`, sem JOIN.** O inventário não altera `review_sql_structure`, catálogo, grants nem capacidades. Uma futura relação só poderá ser habilitada em etapa própria, com chave, grão, vigência e controle contra fanout comprovados.

## Verificações

- `backend/tests/test_genai_sql_live_catalog.py`: fixture SQLite verifica schema compatível e bloqueia drift de tipo/grão; não comprova comportamento ou grants do PostgreSQL publicado.
- `backend/tests/test_genai_publication.py`: exercita snapshot/publicação local; cenários que exigem PostgreSQL ficaram ignorados neste ambiente.
- `backend/tests/test_genai_sql_admission.py` e `test_genai_sql_executor.py`: 38 testes passaram em execução dirigida; `pwdlib` ausente foi suprido apenas por stub de importação (nenhuma função de senha foi exercitada).
- Ruff passou nos arquivos alterados ignorando somente `S110` e `BLE001`, violações preexistentes do `check_genai_runtime.py`; compilação dos módulos alterados passou.
- Inspeção ativa somente leitura: PostgreSQL respondeu; publicação `gold-csv-v2`; comparação das 15 tabelas e 239 colunas sem divergências; grants efetivos e privilégios restritos confirmados como descrito acima.
- `backend/scripts/check_genai_runtime.py` não foi executado contra essa instância; a evidência de teste do bloqueio de drift permanece local.

**Estado:** inspeção do schema/grants ativos, barreira de runtime e inventário conservador de JOINs concluídos. TSQL-03 está concluída; isso não promove JOIN nem altera o escopo F1 de fonte única.
