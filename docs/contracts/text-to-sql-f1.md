# Contrato generativo F1 e consumidores

**Estado:** contratos, transporte privado e executor interno implementados; geração desligada por padrão e fluxo público generativo ainda não integrado.
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

### Comparação com variação percentual derivada — evidência v2

Para comparações de dois totais aprovadas pelo subconjunto F1, o candidato SQL continua retornando somente os dois totais e a diferença em reais. Depois da execução, o Backend deriva `(período 1 - período 2) / período 2 * 100`, arredondado a duas casas com `ROUND_HALF_EVEN`; o período 1 é o mais recente e o período 2 é a referência anterior. A medida derivada não é SQL proposto pelo modelo. Se a referência anterior estiver ausente, for zero ou negativa, a variação percentual é indefinida e aparece como nula; não há divisão por zero nem substituição de nulo por zero.

A evidência e a apresentação novas usam `text-to-sql-f1-evidence-v2` e `text-to-sql-f1-presentation-v2`, com unidade `%`. Os leitores continuam aceitando contratos v1 já persistidos no histórico. O digest de execução cobre os resultados SQL brutos. O digest da evidência v2 também cobre a medida derivada pelo Backend, calculada para cada grupo quando houver agrupamento.

`build_sql_generation_context` recebe `QuestionPlanRequest` com escopo/cobertura já resolvidos pelo Backend. Seleciona no catálogo instalado somente receita em `diagnostico_receita`; libera `competencia`, `receita_total_reais` e colunas de município/classe autorizadas. Ignora outras fontes/métricas e valores de UC.

O digest incorpora pergunta, conversa, cobertura, publicação, catálogo, identidade e escopo. Identidade e concessões externas à F1 entram no digest, sem serem incluídas como objetos/credenciais no conteúdo enviado ao modelo. Ordem de conjuntos e redução do saldo de tempo não alteram a identidade semântica do contexto. O prazo é controlado separadamente pelo coordenador. Para F1, `caller_ref` precisa ser o pseudônimo `session:<sha256>` produzido pelo Backend; `prepare_sql_candidate` re-resolve o escopo atual e compara a publicação antes da geração, recusando revogação ou troca de lote.

O contexto indica que deriva de modelos/catalogo instalados, não de introspecção do banco vivo. Limite de 64 KiB: excesso falha explicitamente, sem truncar cobertura ou restrições. Construção do contexto não consulta dados nem certifica grants/prontidão.

Na admissão Backend, `assert_live_f1_catalog` confere no PostgreSQL ativo todas as colunas/tipos da projeção F1, Decimal/escala, grão/chave e privilégios `USAGE`/`SELECT` das colunas liberadas. A conferência é repetida dentro do snapshot somente leitura imediatamente antes da execução; divergência falha fechada. `check_genai_runtime.py` usa o mesmo controle. Os testes locais usam schema sintético; enquanto a URL/leitor da publicação ativa não estiver configurado, isso não comprova metadados/grants efetivos daquela instância. Nenhum JOIN é habilitado.

## Adaptador Gemini

`GeminiSqlGenerator` recebe cliente configurado, modelo, conteúdo e versão esperada. Usa schema fechado e prompt `text-to-sql-f1-9` (histórico; a versão corrente é `text-to-sql-f1-34`, ver a seção de 08/11/2026 no fim deste contrato), com formas SQL concretas por operação, regras de parâmetros e separação entre esclarecimento e operação não suportada. O schema enviado ao Gemini é reduzido às palavras-chave JSON Schema suportadas; a resposta continua sendo validada localmente pelo modelo Pydantic completo, que aplica limites, nomes de parâmetros, datas e coerência. Revisado com `google-genai 2.31.0` instalado e documentação oficial consultada via Context7 em 05/11/2026: [`response_json_schema` na documentação do SDK](https://github.com/googleapis/python-genai/blob/main/docs/source/index.rst) suporta apenas um subconjunto explícito; `patternProperties`, `const`, defaults, padrões e limites de texto não são enviados como restrições do provedor. A versão do prompt é emitida nos eventos de sucesso/uso e falha, junto de modelo, latência, tamanho do contexto, limite de saída, temperatura e tentativas; tokens permanecem nulos quando o provedor não os informa. Respostas inválidas recebem razão categórica limitada (`invalid_json`, `contract_validation`, `incomplete_generation`, `context_version_mismatch` ou `invalid_response_shape`), sem logar entrada, saída, SQL ou detalhes de validação. Conteúdo, pergunta, histórico, digest de contexto, parâmetros SQL e detalhes de exceção não são registrados. Saída configurável até 4.096 tokens, temperatura de 0 a 1 (padrão 0) e timeout de até 20 s, reduzível pelo chamador. O adaptador não repete chamadas; a composição SDK fixa uma tentativa e a chamada respeita o saldo do `ExecutionController` compartilhado.

Testes com provedor falso cobrem candidato, JSON inválido, contexto divergente, truncamento, 429/503, rejeição e timeout. A prova do prompt verifica a instrução e que pergunta/histórico não a substituem, mas não mede se o Gemini segue a política. Na avaliação sintética f1-2, 28/40 interpretações coincidiram e o revisor rejeitou 34/34 candidatos SQL; nenhum candidato foi executado. O piloto de f1-3 em seis casos teve três saídas inválidas e um 503, sem candidato válido. Estes resultados reprovam a qualidade atual e não devem ser tratados como aceite do gerador. `create_gold_app` compõe o candidato somente na rota interna opt-in; o coordenador público continua no planner antigo.

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

### Evidência SQL independente do plano legado — 05/11/2026

`text-to-sql-f1-evidence-v1` é implementado independentemente em `backend/app/schemas/sql_evidence.py` e `ai-agent/app/schemas/sql_evidence.py`. Os [exemplos compartilhados](examples/text-to-sql-f1-evidence-v1.json) são artificiais, não oráculos numéricos de negócio. Seis exemplos válidos e nove inválidos são conferidos nos dois serviços, com igualdade do JSON Schema e round-trip. Nenhum esquema de plano legado é criado para transportar a evidência SQL.

`genai_sql_evidence.build_sql_evidence` confere candidato/contexto/revisão contra a admissão e a execução, além do prazo e escopo atuais. Transporta referência Gold v2, métrica/fonte, períodos/filtros, versões de catálogo/dicionário, colunas/unidades e linhagem de medidas/dimensões derivada da AST. Valores monetários atravessam o contrato como decimais canônicos em texto, sem conversão para float ou arredondamento. Fonte/colunas são fechadas; campos SQL/plano extras são recusados. Empty, all_measures_null e available preservam ausência, nulo e zero sem inferir causas.

O executor agora calcula `result_digest` sobre colunas, linhagem, linhas exatas e estado. O digest de execução inclui esse resultado, a admissão e o SQL canônico. O envelope valida novamente o digest das linhas e o `evidence_digest` do conteúdo completo. Esses hashes detectam divergência, não autenticam um chamador: o futuro transporte de síntese continua exigindo autenticação técnica, contexto autorizado e controles de publicação. O envelope admite até 100 linhas, 32 colunas por linha e 32 KiB incluindo proveniência/digests; o materializador mantém seu teto anterior de 16 KiB.

Prova desta etapa: total e comparação realmente executados no PostgreSQL 16 com papel restrito/snapshot foram convertidos em evidência, mantendo 150.03, 80.00 e 70.03 no caso artificial. Metadados/prontidão de admissão continuam substituídos nesse teste, sem aceite Gold real. Não foi implementada a rota `/api/v1/internal/sql-syntheses`, e não há resposta pública ou nova chamada Gemini nesta rodada.

### Projeção de apresentação F1 — integrada, aceite TSQL-08 pendente

`text-to-sql-f1-presentation-v1` é uma projeção determinística criada pelo Backend a partir de `SqlEvidence`, incluída no retorno autenticado de `/api/v1/ai/sql-analyses` e consumida pelo Assistente quando o modo experimental opt-in está ativado. Ela oferece uma conclusão direta para total/comparação, descrição de série/grupos/ranking, período, filtros e universo agrupado em rótulos legíveis e uma tabela cujas células preservam exatamente os valores decimais canônicos da evidência. Unidade é metadado da coluna; `evidence_digest` vincula a apresentação à evidência. O envelope reconstitui a projeção no Backend; o Frontend confere digest, colunas e cada célula antes de exibir.

Para `billing.revenue`, a apresentação informa que faturamento não comprova recebimento/pagamento. Competências são descritas em português natural. A tabela com valores canônicos é navegável por teclado; a visualização identifica os filtros e o universo usado.

Os estados `empty` e `all_measures_null` geram mensagens distintas; não são convertidos em zero. A projeção não arredonda, não deriva percentual e não afirma causa. A visualização é derivada das mesmas linhas; a interface a suprime se meses não forem contínuos/ordenados ou se os valores excederem o limite de precisão segura para gráfico. A rota registra referência de auditoria sanitizada e falha sem devolver resultado se a confirmação não puder ser persistida. F1 permanece opt-in e não chama Gemini após o SQL: a resposta factual é determinística. A jornada Edge F1-01 a F1-08 passou por sessão e rota reais até PostgreSQL 16 descartável; candidato e readiness foram substituídos por determinísticos, e nenhum dado Gold ativo foi consultado. Testes de rota cobrem resultado vazio, indisponibilidade do provedor, troca da publicação e falha da auditoria final sem resposta quantitativa. O Frontend aceita campos nullable vazios somente nos estados sem resposta; campos preenchidos fora do estado correspondente são recusados. Ainda faltam cobertura estruturada para todas as partes de perguntas compostas e revisão humana de clareza/utilidade/naturalidade, contraste e leitor de tela. Narrativa Gemini tipada não foi implementada; TSQL-08 permanece aberta.

### Política para narrativa depois da consulta

Na F1, o Gemini não recebe a evidência para redigir uma segunda resposta. O modelo ajuda a interpretar a pergunta e propor o candidato SQL; depois da execução, o Backend produz a resposta factual determinística, o texto de limitação fixo (`billing.revenue` representa faturamento e não confirma recebimento/pagamento) e a tabela. Isso evita que a síntese altere números, inverta uma comparação ou omita o recorte.

Uma futura narrativa generativa precisa introduzir um contrato versionado separado da evidência: o Backend constrói um registro de alegações permitidas a partir das medidas/linhas e cálculos determinísticos; cada trecho gerado referencia IDs desse registro; o modelo não devolve valores numéricos livres, definições de métrica, causalidade, hipótese ou recomendação sem evidência tipada. O Backend rejeita referências ausentes/incompatíveis e mantém a resposta determinística como fallback. O contrato atual ainda não implementa essa extensão e não permite marcar a síntese Gemini como entregue.

### Conferência SQL/intenção — 05/11/2026

`genai_sql_semantics.review_sql_semantics` chama primeiro a revisão estrutural e confere os recortes SQL contra `SqlInterpretation`. Verifica cobertura mensal completa dos períodos, igualdade dos filtros de município/classe, dimensões agrupadas, direção e tamanho do ranking. Rankings exigem NULLS LAST para não promover receita ausente. Consultas sem ranking não podem usar LIMIT para truncar os grupos.

Recortes temporais são comparados como conjuntos de competências, aceitando igualdade, IN, BETWEEN e limites inclusivos/exclusivos; dimensões aceitam igualdade/IN. AND intersecta restrições, OR só une alternativas da mesma coluna. OR entre eixos diferentes ainda é rejeitado. Fora de uma operação de comparação, medidas condicionais continuam recusadas.

Para comparar duas janelas distintas, o subconjunto F1 exige três medidas: total da janela 0, total da janela 1 e diferença 0 menos 1. A AST determina a linhagem de cada alias em `SqlSemanticReview.measure_semantics`. O WHERE global deve selecionar exatamente a união dos períodos e os filtros comuns. Cada SUM FILTER precisa corresponder ao respectivo recorte após interseção com esse WHERE, e ambas as janelas precisam de cobertura completa.

A comparação admite agrupamento por município e/ou classe de consumo. Quando a interpretação pede ranking, o primeiro critério de ordenação é a diferença em reais na direção solicitada e com nulos ao final. O desempate usa todas as dimensões agrupadas em ordem crescente, com nulos ao final, e o LIMIT precisa coincidir com o pedido. A comparação sem ranking não admite LIMIT. Ausência de um total, diferença invertida, conversão de nulo em zero, ranking por percentual, JOIN, CTE e UNION seguem fora do subconjunto.

`genai_sql_observation.observe_sql_generation` compõe contexto Backend → cliente interno → revisão estrutural/semântica. Recebe o prazo absoluto já iniciado e o reduz pelo saldo do envelope; criação de contexto, provedor e revisão consomem o mesmo orçamento. Registra correlação, versões, IDs/colunas autorizados, contagens, tamanho e estado de truncamento; não registra pergunta, turnos, valores de dimensão, credenciais ou evidência. Recusa de contexto registra motivo tipado e tamanho sem conteúdo. Retorna esclarecimento/capacidade sem revisão, propaga falhas e não repete chamadas. É um caso de uso interno opt-in, ainda sem chamador no coordenador público, sem executor ou aprovação de acesso. Testes usam o cliente HTTP real com transporte artificial; não comprovam qualidade Gemini.

Esta checagem compara SQL e intenção declarada pelo modelo; não comprova que a intenção corresponde ao pedido em linguagem natural. Ainda depende de contexto conversacional validado, prontidão/grants, política de recortes, referência numérica independente e artefato final ligado à sessão/publicação. Nenhuma das revisões autoriza execução ou está conectada ao coordenador público.

### Executor interno e prova PostgreSQL — 05/11/2026

`genai_sql_executor.execute_sql_admission` revalida a admissão e entrega somente o SQL canônico/parametrizado ao driver psycopg. Exige engine PostgreSQL+psycopg com login `venergy_genai_reader` e parâmetros ocultos. Dentro de `GoldPublicationContext.execution_snapshot`, confere papel efetivo, ausência de superuser/bypass-RLS e transação READ ONLY; aplica statement_timeout de até 5 s reduzido pelo saldo, habilita cursor server-side com buffer unitário e chama o materializador. Escopo é conferido antes/depois; a saída do snapshot confere novamente a publicação. O resultado interno inclui digests de admissão/execução sem expor SQL no contrato público.

Admissão/preparação/execução agora exigem `engine` analítico e `readiness_engine` separados: o cliente de prontidão usa o observador operacional existente, enquanto os metadados/publicação e a consulta usam a credencial quantitativa. Não se transfere a credencial operacional ao executor candidato.

Cancelamento sinaliza parada da materialização e aguarda encerramento da thread/snapshot antes de devolver controle. SQL bloqueado depende do statement_timeout; não há promessa de cancelamento imediato. O teste artificial cobre cancelamento assíncrono; a prova PostgreSQL cobre timeout por bloqueio, rollback e conexão reutilizável, sem comprovar todas as falhas de rede/driver.

Quatro testes reais em PostgreSQL 16 descartável passaram: total com Decimal, dois totais e diferença, recusa de DELETE pelo papel leitor e timeout por lock com checkout final zero. A execução e o snapshot/publicação são reais, com verificação de cursor server-side; metadados e prontidão da admissão são substituídos explicitamente. Isso não prova carga Gold certificada, sessão real ou HTTP público. Versões: SQLAlchemy 2.0.52 e psycopg 3.3.6; streaming conferido via Context7 na [documentação oficial](https://docs.sqlalchemy.org/en/20/core/connections.html#using-server-side-cursors-a-k-a-stream-results). Container sem volume removido ao final.

### Materialização F1 — contrato e limites

`genai_sql_result.materialize_sql_result` recebe cursor e revisão semântica; não abre conexão nem executa SQL. Confere nomes/ordem/unicidade das colunas e converte cada linha para tuplas imutáveis. Medidas exigem Decimal finito, dimensões exigem texto/nulo. Valores numéricos com expoente/ordem de grandeza acima de 100 são recusados antes de formatar; não há conversão para float nem arredondamento nesta etapa.

A leitura incremental limita o resultado a 100 linhas e 16.384 bytes do envelope JSON (Decimal em string fixa). Excesso descarta tudo: não retorna parcial como total. Cursor fecha no sucesso e nas falhas. Os estados `empty`, `all_measures_null` e `available` distinguem ausência de linhas, medidas nulas e valores válidos, incluindo zero e estorno. O futuro adaptador de evidência ainda precisa interpretar esses estados e explicar suas causas conforme a fonte.

Limitação: fetchmany limita a materialização da aplicação; não comprova cursor server-side, memória do driver/banco, cancelamento ou devolução da conexão. O executor deve manter o snapshot, prazo SQL e papel restrito enquanto lê e revalidar publicação/escopo antes de divulgar resultado. Testes isolados do materializador usam cursores artificiais; a prova integrada PostgreSQL está descrita acima.

### Admissão interna e revalidação — 05/11/2026

`genai_sql_admission.admit_sql_candidate` recebe engine analítico, publicação capturada pelo servidor, resolvedor de escopo atual e controles aprovados da configuração. Confere escopo antes/depois das fronteiras assíncronas, relê cobertura/vocabulário com `GoldPublicationContext.planning_fields` e refaz a revisão contra esse contexto. Usa o cliente de prontidão existente para todos os meses de todas as janelas; exige `faturamento.receita` disponível sem razões. Lote misto, obsoleto, vazio, inválido ou indisponível é recusado. Lote parcial só é admitido se a capacidade de receita estiver disponível. A exceção de continuidade observada de DEC/FEC não libera receita.

O retorno `SqlAdmission` liga por digest a revisão canônica, parâmetros, candidato completo, contexto (identidade/escopo/catálogo), publicação, relatório de prontidão, controles aprovados, versão da política e validade monotônica. Usa cópias privadas validadas e detecta mutação dos objetos originais durante a admissão. É interno ao processo, não é token de navegador nem contrato público. Não possui concessão de acesso a banco por si só.

`revalidate_sql_admission` refaz admissão/metadados/prontidão sob o prazo original e exige igualdade integral do artefato. Não renova aprovação expirada com um prazo novo; troca de usuário, SQL, parâmetros, controles, política ou relatório invalida a reutilização. Alteração de publicação é propagada pelo controle existente. Ainda será necessário revalidar dentro da fronteira apropriada de execução e checar novamente publicação/escopo após materializar os resultados.

`genai_sql_observation.prepare_sql_candidate` compõe conferência inicial de escopo/publicação → geração → revisão → admissão sob o mesmo prazo. Esclarecimento não gera admissão. A preparação não executa SQL; o executor interno separado ainda não tem chamador público ou flag de ativação. Os testes desta rodada usam fronteiras I/O artificiais: comprovam composição e rejeições, não observação real Gold, grants ou cancelamento de SQL. A prova numérica PostgreSQL e o aceite Gold permanecem pendentes.

`POST /api/v1/internal/sql-candidates` recebe `SqlGenerationRequest` e retorna `SqlGenerationResponse`. Exige autenticação de serviço Gold, contexto versionado e orçamento restante; o cliente Backend confere correlação e versão do contexto. As fixtures HTTP comuns estão em `examples/text-to-sql-f1-http-v1.json`.

`GENAI_SQL_GENERATION_ENABLED=false` é o padrão. A habilitação compõe o adaptador Gemini somente na fábrica Gold, com auditoria durável e limites compartilhados de execução/modelo. A instância demonstrativa de `app.main:app` permanece sem geração SQL. O coordenador público ainda não chama esta rota; nenhum candidato é executado ou apresentado como evidência.

Verificações desta fatia: 145 testes dirigidos GenAI e 52 Backend aprovados, incluindo chamada entre cliente Backend e aplicação Gold em processo separado com provedor artificial. A suíte GenAI completa registrou 4.608 aprovados, 17 skips e uma falha em `test_concrete_adapters_do_not_import_the_agent_or_composition_root`: o experimento local anterior `intent_proposer.py` importa `app.agent.access`. A pendência foi preservada; a suíte completa não está aprovada. Não houve chamada Gemini real nem execução PostgreSQL nesta rodada.

## Assunto declarado, motivo e opções de esclarecimento (08/11/2026)

Extensão aditiva do candidato, decidida na [ADR-0026](../decisions/0026-assunto-declarado-e-motivos-de-recusa.md). Exemplos válidos e inválidos compartilhados entre GenAI e Backend: [`text-to-sql-f1-scope-v1.json`](examples/text-to-sql-f1-scope-v1.json).

| Campo | Onde | Regra |
| --- | --- | --- |
| `scope_assessment.status` | candidato, todo estado | `in_domain`, `out_of_domain` ou `uncertain`; `unresolved_terms` com até 3 termos de até 80 caracteres; sem raciocínio livre. Exigido pelo runtime novo, opcional no schema para ler contratos antigos. |
| `clarification.reason_code` | `needs_clarification` | `ambiguous_subject`, `missing_context` ou `insufficient_coverage`. |
| `unsupported_reason.reason_code` | `unsupported` | `out_of_domain`, `unsupported_capability`, `insufficient_coverage` ou `security_restriction`. |
| `clarification.options` | `needs_clarification` | Até 5 `{label, question}`; a `question` é reenviada como nova mensagem e reaprovada, nunca é permissão ou SQL. |

Regras de coerência (nos dois schemas espelhados e reaplicadas pelo Backend em `genai_question_feedback`): só `sql_candidate` com `in_domain` executa; `uncertain` exige esclarecimento; `out_of_domain` exige recusa (motivo externo ou de segurança); `out_of_domain` com `in_domain` declarado é contradição. Um esclarecimento rotulado `ambiguous_subject` com assunto conhecido é normalizado para `missing_context`; com assunto incerto, qualquer pergunta por município ou classe é substituída por uma pergunta neutra sobre o assunto. O Backend também responde `insufficient_coverage` sem chamar o modelo quando a pergunta pede ano completo (“2026 fechado”, “ano inteiro”, “janeiro a dezembro”) e faltam competências, oferecendo apenas o recorte já publicado.

**Versionamento.** Não há `text-to-sql-f1-v14`: a versão de geração identifica a métrica (`v1`…`v13`); esta extensão é independente dela e a geração que a produz é identificada pela versão do prompt (`text-to-sql-f1-34`). **Ordem de implantação:** Backend e portal compatíveis, depois a GenAI com o prompt novo. **Reversão:** restaurar as imagens da base; conversas salvas com os campos novos ficam indisponíveis para o Backend antigo (schema fechado) até a reimplantação.

**Limite.** A classificação é declarada pelo mesmo modelo; os validadores não provam entendimento semântico. A medição está em `ai-agent/reports/genai-feedback-live.json` (desenvolvimento, sem reserva humana).
