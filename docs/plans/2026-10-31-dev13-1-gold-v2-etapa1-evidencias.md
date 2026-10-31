# DEV-13.1 — etapa 1: leitores da publicação física Gold v2

Data: 31/10/2026. Branch: `dev13.1`. Escopo autorizado: somente a primeira das quatro etapas; execução por subagentes GPT-6 Luna/high e revisão pelo agente principal GPT-6.1 Sol.

## Mudanças

- O contexto analítico aceita `gold-csv-v2` e recusa v1/versões desconhecidas. Lote, fingerprint, snapshot de leitura e autenticação mantêm suas regras.
- Panorama, fila/criação de ordens e Operação usam os modelos de `gold_v2_load`, que apontam ao schema `gold_v2`. A publicação e a auditoria compartilhadas conservam suas tabelas; snapshots e ciclo operacional das ordens permanecem independentes.
- Os três módulos de integração PostgreSQL usam tabelas físicas v2. A prova de ordens usa pacote artificial v2 com importação, repetição, falha e substituição da UC.
- Modelos históricos v1, importador v1, ambiente real e configuração de ativação não foram modificados nesta etapa.

## Verificação observada

Imagem temporária `git-or-treat-backend:stage1-v2-check`: imagem local Python 3.12 acrescida de `pwdlib[argon2]`, dependência já declarada pelo projeto e ausente da imagem antiga. PostgreSQL 16 descartável `grid360-dev131-stage1-tests`, sem porta publicada/volume e com usuário de testes sem superusuário, em bancos separados `grid360_analytics_test` e `grid360_orders_test`. Nenhum CSV real foi usado.

Com as duas URLs de teste selecionadas no processo, executado em `/app` com fontes montadas somente leitura:

```text
python -m pytest -q --tb=short -p no:cacheprovider tests/test_gold_context_v2.py tests/test_gold_analytics_postgres.py tests/test_gold_operations_http_postgres.py tests/test_gold_inspections_orders_postgres.py tests/test_panorama.py tests/test_operations_dev08.py tests/test_operations_summary.py tests/test_inspection_queue_dev05.py
```

Resultado final: **129 passaram**, 1 aviso preexistente Starlette/httpx, 12,28 s. Os testes exercitam publicação v2, recusa de v1/desconhecida, contexto consistente, consultas HTTP, criação/replay e preservação de ordem após recarga artificial. O primeiro ensaio revelou overflow do ticket médio artificial (precisão física v2 diferente) e caminho antigo do CSV no teste de recarga; ambos corrigidos sem retirar a asserção de receita grande ou de rollback.

A revisão independente identificou o default físico v1 ainda presente em `GoldMetadata`; corrigido para v2 e coberto no JSON Schema, mantendo a versão HTTP `2.0.0`. A rodada anterior teve 128 testes aprovados; o teste adicional de schema integra o resultado final acima. `git diff --check` passou. O contêiner PostgreSQL descartável foi removido após as verificações.

## Limites e próxima etapa

Etapa 1 concluída tecnicamente; DEV-13.1 e requisitos WEB/DE continuam sem aceite integral. Nenhuma ativação Gold ou prova HTTP no lote real foi realizada. As etapas 2–4 continuam pendentes.

A etapa 2 deve revisar os universos financeiros: `receita_total_reais` e `consumo_total_kwh` da v2 não implicam a mesma população; existem `receita_base_comparavel_reais` e `consumo_base_comparavel_kwh`. Também deve revisar motivo/ordenação/recuperação da fila e as limitações de continuidade conforme o dicionário atual. O simples redirecionamento físico não homologa essas métricas.
