# Contrato generativo F1 e consumidores

**Estado:** contratos e transporte privado implementados; geração desligada por padrão e execução de SQL ainda não integrada.
**Decisão:** [ADR-0025](../decisions/0025-text-to-sql-generativo.md).

## Candidato: `text-to-sql-f1-v1`

Implementações independentes: `ai-agent/app/schemas/sql_generation.py` e `backend/app/schemas/sql_generation.py`. Exemplos comuns: [vetores JSON](examples/text-to-sql-f1-v1.json). Teste cruzado compara schema, aceita os três exemplos válidos e rejeita os dez vetores inválidos em ambos os serviços, usando subprocesso Backend sem importar um serviço pelo outro.

Transporte decidido na ADR: `/api/v1/internal/sql-candidates` implementada com habilitação desligada por padrão; `/api/v1/internal/sql-syntheses` pendente. Exige autenticação técnica/correlação e saldo do prazo. Contrato do candidato é independente do envelope de transporte e dos contratos públicos, que permanecem atuais.

- `sql_candidate`: exige SQL não vazio, interpretação e colunas com aliases únicos e ao menos uma medida. Sem esclarecimento/limite misturados.
- `needs_clarification`: exige pergunta e campos pendentes; não admite SQL, parâmetros, interpretação pronta ou colunas.
- `unsupported`: exige motivo de capacidade F1; não concede nem nega autorização da sessão.
- Falha de provedor não é estado de interpretação: adaptador lança erro tipado, sem expor o texto do provedor.
- `context_version`: digest hexadecimal de 64 caracteres, conferido contra a referência de entrada pelo adaptador e futuramente pelo coordenador.
- `parameters`: até 32 parâmetros nomeados; string/integer/number/boolean/date/decimal, com checagem de tipo real e finitude. Decimal atravessa o contrato em string para preservar precisão.
- SQL: até 16.000 caracteres. Colunas propostas: até 32. Esses são limites do envelope inicial; orçamento operacional e política SQL são independentes.
- F1 representa total, série mensal, total agrupado, ranking e comparação. Janelas são meses completos, ordenadas, e comparação exige duas janelas. Cobertura efetiva ainda depende da prontidão Backend.

O contrato valida estrutura e coerência local. Uma string DELETE pode ser um candidato estruturalmente válido e é rejeitada pela revisão AST Backend. Testes preservam essa distinção. A análise estrutural independente descrita abaixo não substitui a validação de intenção, período, cobertura, prontidão e autorização final de execução.

## Contexto preparado no Backend

`build_sql_generation_context` recebe `QuestionPlanRequest` com escopo/cobertura já resolvidos pelo Backend. Seleciona no catálogo instalado somente receita em `diagnostico_receita`; libera `competencia`, `receita_total_reais` e colunas de município/classe autorizadas. Ignora outras fontes/métricas e valores de UC.

O digest incorpora pergunta, conversa, cobertura, publicação, catálogo, identidade e escopo. Identidade e concessões externas à F1 entram no digest, sem serem incluídas como objetos/credenciais no conteúdo enviado ao modelo. Ordem de conjuntos e redução do saldo de tempo não alteram a identidade semântica do contexto. O prazo é controlado separadamente pelo coordenador.

O contexto indica que deriva de modelos/catalogo instalados, não de introspecção do banco vivo. Limite de 64 KiB: excesso falha explicitamente, sem truncar cobertura ou restrições. Construção do contexto não consulta dados nem certifica grants/prontidão.

## Adaptador Gemini

`GeminiSqlGenerator` recebe cliente configurado, modelo, conteúdo e versão esperada. Usa schema fechado e prompt `text-to-sql-f1-1`; saída configurável até 4.096 tokens, temperatura de 0 a 1 (padrão 0) e timeout de até 20 s, reduzível pelo chamador. Não executa SQL nem faz retries próprios. O cliente SDK deve ter sua política de retries configurada pela composição antes do aceite operacional.

Testes com provedor falso cobrem candidato, JSON inválido, contexto divergente, truncamento, 429/503, rejeição e timeout. Não são evidência de qualidade do Gemini real nem de composição runtime. A fábrica `create_gold_app` ainda usa o planner antigo.

## Revisão estrutural Backend — etapa intermediária

`genai_sql_structure.review_sql_structure` reconstrói o contexto autorizado a partir do pedido Backend e confere seu digest contra o candidato. Analisa PostgreSQL com SQLGlot 30.24.0 (dependência Backend `>=30.24.0,<30.25`), usando lista positiva de nós e atributos. Aceita apenas um SELECT sobre a fonte física do contexto, sem CTE, JOIN, subconsulta, escrita, locks, funções externas ou casts. A resolução de colunas considera o único alias da fonte e as dimensões autorizadas; o resultado exige aliases iguais aos declarados no contrato.

O subconjunto inclui SUM da receita, agrupamento por competência/município/classe, comparações parametrizadas, IN, BETWEEN, AND/OR, ordenação por alias/dimensão agrupada, LIMIT literal de 1 a 100, SUM FILTER e subtração de medidas. Outros literais e comentários são recusados. Máximo de 512 nós e profundidade 32. Estes são limites do subconjunto inicial, não um cálculo de custo da consulta.

Os nomes dos parâmetros vêm da AST e devem coincidir exatamente com o envelope. Valores não são interpolados. A regeneração PostgreSQL produz placeholders `%(nome)s` para psycopg, verifica round-trip da AST e preserva parâmetros em tupla imutável. A diferença interna de representação de `:nome` e `%(nome)s` é normalizada apenas para essa comparação. Filtros da fonte F1 usam string porque competência e dimensões são textuais; a conversão genérica de date/Decimal permanece disponível para futuras fontes compatíveis.

O retorno `SqlStructureReview` é intermediário e **não pode autorizar execução**. Ainda faltam confrontar período/filtros/agrupamento/ranking com a intenção, validar cobertura e prontidão da publicação, impor os recortes efetivos de sessão e criar um artefato final vinculado à política. Uma estrutura permitida pode consultar um período errado ou omitir o período. A revisão não é chamada pelo coordenador público nem por um executor.

Inventário do validador demonstrativo: `ai-agent/app/sql/validator.py` e `test_sql_validator.py` já possuem traversal, qualificação, verificação de funções/limites e testes SQLite/PostgreSQL. Seus dicionários e parâmetros posicionais, bem como seu `ValidatedQuery`, não comprovam autorização por sessão/publicação Gold v2; não foram importados no Backend. Reutilizados os princípios de análise AST, regeneração e falha fechada, com fronteira Backend e parâmetros nomeados próprios.

API do parser conferida via Context7 na [documentação oficial SQLGlot](https://github.com/tobymao/sqlglot) em 05/11/2026: parse PostgreSQL, traversal de expressões, placeholders e geração com rejeição de construções não suportadas. Nenhum banco, grant ou role foi alterado.

## Matriz de consumidores e migração

| Fronteira e área responsável | Símbolo/arquivo atual | Mudança e prova exigida |
| --- | --- | --- |
| Composição GenAI | `app/gold_runtime.py:create_gold_app`, `app/agent/composition.py:compose_core` | Injetar gerador e estratégia; teste da fábrica real com caminho padrão preservado |
| Interpretação/plano GenAI | `QuestionAnalysisPlanner`, `ReadPlanBuilder`, `LogicalReadPlan` | Candidato em contrato próprio, sem plano fictício; regressões e casos fora do escopo |
| HTTP GenAI | `app/api/routes.py`; schemas internos | Novo transporte autenticado/versionado, prazo e estados de erro; testes de contrato |
| Coordenação Backend | `services/genai_client.py`, `genai_planning.py`, `genai_coordination.py` | Aceitar candidato só na estratégia nova; revalidar escopo/publicação/AST antes da execução |
| Acesso/prontidão Backend | `core/genai_gold_access.py`, `genai_gold_database.py`, `services/gold_readiness.py` | Extrair dependências reais e conferir concessões/controles; negativos e drift |
| Executor Backend | `services/genai_executor.py:execute_gold_plan` | Executor aprovado separado/reaproveitando snapshot, leitura, prazo e limites; teste PostgreSQL restrito |
| Evidência/síntese GenAI/Backend | `schemas/evidence.py`, `backend/app/schemas/genai_evidence.py`, `EvidenceGuard`, `ObservationSelection` | Resultado multi-medida e derivadas verificáveis; referência numérica e grounding |
| Continuidade Backend | `genai_continuation.py:canonical_question`, `ranked_result_anchor` | Âncora independente do plano antigo; teste mudança/remoção de filtros e expiração |
| Histórico/memória Backend | `services/ai_conversations.py`, `conversation_memory.py` | Preservar propriedade, retenção e ancoragem; testar histórico antigo e contexto novo |
| Auditoria/replay Backend | `services/genai_audit.py`, `genai_replay.py` | Versionar artefato/digest e reautorização do replay; reconstrução não aceita SQL arbitrário armazenado |
| Cache GenAI | `providers/caching.py:cache_key` | Diferenciar geração, resultado e síntese por escopo/contexto/versões/publicação; isolamento |
| Portal/visualização | `features/assistente/api.ts`, `contract.ts`, `visualization.ts`; Backend `chat_visualization.py` | Preservar envelope público e estender resultado com prova UI; sem SQL interno no navegador |
| Busca/insight preservados | `agent/documentation.py`, `agent/insights.py` | Não redirecionar conceitos para SQL nem mudar o recorte da tela; testes dos consumidores atuais |

## Implantação e reversão

### Testes existentes a ampliar por consumidor

Os nomes abaixo apontam pontos concretos de regressão; não indicam que o caminho generativo já esteja coberto por eles.

| Fronteira | Testes/artefatos |
| --- | --- |
| Fábrica GenAI e planejamento | `ai-agent/tests/test_gold_runtime.py`, `test_gold_planning_http.py` |
| Contrato interno e cliente | `backend/tests/test_genai_internal_contract.py`, `test_genai_client.py`; novo `ai-agent/tests/test_sql_generation_contract.py` |
| Coordenação/executor/prontidão | `backend/tests/test_genai_flow.py`, `test_genai_executor.py`, `test_gold_readiness_real.py` |
| Publicação e permissões | `backend/tests/test_genai_publication.py`, `test_genai_profile_access.py`, `test_genai_session_postgres.py` |
| Evidência/síntese | `ai-agent/tests/test_core_plan_synthesis.py`; fixtures `gold_evaluation_numeric.json` |
| Continuação e histórico | `backend/tests/test_genai_continuation.py`, `test_ai_conversations_contract.py`, `test_conversation_memory.py` |
| Cache/replay/auditoria | `ai-agent/tests/test_gold_cache_invalidation.py`, `backend/tests/test_genai_audit.py`, `test_genai_session_postgres.py` |
| Portal e visualização | `frontend/src/features/assistente/contract.test.ts`, `api.test.ts`, `AssistentePage.test.tsx`, `visualization.test.ts`; `backend/tests/test_chat_visualization.py` |
| Busca documental/insight | `backend/tests/test_genai_documentation.py`, `ai-agent/tests/test_gold_insights.py` |

### Experimentos anteriores nesta branch

- `GeminiIntentProposer`: manter como experimento de intenção para comparação; seu código não é usado como gerador SQL pronto. Reaproveitar contexto/schema/telemetria após revisão.
- `observe_interpretation`: preservar comparador de observação sem executor; não é validador de SQL nem gate de acesso.
- `semantic_provider_probe.py`: diagnóstico de intenção antiga; não substituir benchmark numérico F1 pelo sucesso desse probe.
- `p0_measurements.py` e fixtures: fontes de perguntas/controles e baseline de planejamento; oráculos de plano não se tornam automaticamente referências SQL.
- `sql_generation_live_probe.py`: uma chamada real sobre contexto artificial Backend, com saída privada em `work/`; não executa SQL nem demonstra sessão/prontidão reais.

1. Entregar contratos e suporte Backend com estratégia nova desligada.
2. Ligar contexto/gerador em observação sem execução real.
3. Integrar validador e executor somente após testes críticos e referências artificiais.
4. Integrar síntese/âncora mínima/portal; provar a mesma publicação e números em Gold autorizado.
5. Habilitar escopo aprovado por configuração no coordenador, medindo sucesso completo e regressões.
6. Reverter configuração para legado se necessário, invalidando apenas cache/âncoras incompatíveis; manter histórico/auditoria.

O envelope interno atual de plano não foi alterado nesta preparação. Não existe fallback silencioso de uma análise generativa para outra pergunta no legado. Retirada do legado exige inventário final, benchmark e rollback exercitado.

## Fontes e versões

Pydantic 2 é o padrão existente. Uso de `ConfigDict(extra='forbid')`, tipos estritos e `model_validator(mode='after')` conferido via Context7 em 05/11/2026 nas [regras de validadores](https://docs.pydantic.dev/latest/concepts/validators/) e [modo estrito](https://docs.pydantic.dev/latest/concepts/strict_mode/). A versão instalada da execução fica registrada no relato de verificação; atualização de biblioteca exige reexecutar fixtures cruzadas. Não houve introdução de framework novo.

## Verificações de 05/11/2026

- GenAI: `python -m pytest tests/test_sql_generation_contract.py tests/test_sql_generator.py tests/test_gold_language_evaluation.py tests/test_interpretation_shadow.py -q -p no:cacheprovider --tb=short`: **50 passaram em 5,56 s**.
- Backend: `python -m pytest backend/tests/test_genai_sql_context.py -q -p no:cacheprovider --tb=short` pela venv local de validação: **9 passaram em 0,14 s**.
- Referências SQL: `python -m pytest tests/test_text_to_sql_f1_reference.py -q -p no:cacheprovider --tb=short --junitxml=../work/text-to-sql-f1-reference.xml`, com `TEST_TEXT_TO_SQL_URL` apenas para PostgreSQL 16 descartável `text_to_sql_f1_test`: **13 passaram em 130,56 s**. Sete consultas iniciais, ausência de cobertura anual e casos de ano completo/zero/nulo/ausência/estorno. SQL escrito manualmente, não candidato do modelo. Container sem volume parado/removido ao final.
- Provedor real: `python -m tests.sql_generation_live_probe`: **uma solicitação**, candidato válido no contrato em **2.770,03 ms**, **753 tokens de entrada + 365 de saída = 1.118 reportados**. Relatório privado `work/text-to-sql-f1-live-probe.json`. SQL analisado offline como AST SELECT, **não executado**. Não comprova alinhamento semântico nem a segurança do SQL.
- Tentativa anterior do probe falhou na codificação do subprocesso antes de chamar o provedor; corrigida com Python UTF-8. Não é contada como chamada Gemini.
- Versões observadas: Python 3.12, Pydantic 2.13.4, google-genai 2.31.0, SQLGlot 30.24.0. Ruff dirigido aprovado. Testes completos dos dois serviços e jornada portal não foram executados nesta rodada.
- Tentativa suplementar de `SHOW server_version` no banco do portal encontrou o container parado. Não houve reinício nem inspeção do lote real; a evidência do dialeto alvo continua sendo ADR/configuração/fábrica e o PostgreSQL descartável.


## Transporte privado de candidatos — 05/11/2026

`POST /api/v1/internal/sql-candidates` recebe `SqlGenerationRequest` e retorna `SqlGenerationResponse`. Exige autenticação de serviço Gold, contexto versionado e orçamento restante; o cliente Backend confere correlação e versão do contexto. As fixtures HTTP comuns estão em `examples/text-to-sql-f1-http-v1.json`.

`GENAI_SQL_GENERATION_ENABLED=false` é o padrão. A habilitação compõe o adaptador Gemini somente na fábrica Gold, com auditoria durável e limites compartilhados de execução/modelo. A instância demonstrativa de `app.main:app` permanece sem geração SQL. O coordenador público ainda não chama esta rota; nenhum candidato é executado ou apresentado como evidência.

Verificações desta fatia: 145 testes dirigidos GenAI e 52 Backend aprovados, incluindo chamada entre cliente Backend e aplicação Gold em processo separado com provedor artificial. A suíte GenAI completa registrou 4.608 aprovados, 17 skips e uma falha em `test_concrete_adapters_do_not_import_the_agent_or_composition_root`: o experimento local anterior `intent_proposer.py` importa `app.agent.access`. A pendência foi preservada; a suíte completa não está aprovada. Não houve chamada Gemini real nem execução PostgreSQL nesta rodada.
