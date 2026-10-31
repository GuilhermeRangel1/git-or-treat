# Camada SQL somente leitura

O autorizador SQLite verifica também as tabelas e colunas físicas acessadas durante a execução. Uma visão com nome permitido não concede acesso a uma tabela fora do dicionário. Essa barreira é aplicada além da validação do SQL e do modo somente leitura.

## Uso na demonstração HTTP

Com `GENAI_ENVIRONMENT=local`, `GENAI_ENABLE_DEMO_ACCESS=true`, `GENAI_DEMO_SOURCE=sqlite` e `GENAI_DEMO_SQLITE_PATH=<arquivo>`, `app.main:app` compõe o leitor como fonte de evidência da rota de perguntas. O perfil específico aceita faturamento, consumo, interrupções e chamados mensais por dois municípios fictícios em janeiro a março de 2025 e uma janela vazia em abril. A imagem Docker cria `/app/demo.sqlite` a partir de `app.sql.seed_demo`; fora do Docker, execute `python -m app.sql.seed_demo <arquivo>` explicitamente. Falha ou ausência do arquivo não devolve valores da fixture. O modo padrão ainda usa `synthetic.fixture`, e nenhum dos modos consulta Gold.

`tests/test_sql_demo_http.py` exercita resposta, esclarecimento, ausência, recusa anterior ao SQL, falha sem fallback e correlação da auditoria pela API. `tests/test_sql_postgres_permissions.py` é opt-in com `GENAI_TEST_POSTGRES_ADMIN_DSN` apontando somente para um banco descartável chamado `grid360_ia_test`: remove o privilégio padrão `TEMPORARY` de `PUBLIC`, cria um esquema e papel de leitura de teste, consulta a tabela permitida e confirma que o banco recusa escrita, tabela temporária e leitura não concedida; remove os objetos criados ao final. O leitor de planos da jornada HTTP continua específico de SQLite. O teste PostgreSQL prova a política de permissões de forma isolada, sem implicar que o adaptador Gold esteja pronto.

Ensaio da borda SQL (IA-06): valida uma consulta contra um dicionário, executa **somente o SQL regenerado** em um executor de leitura e audita a tentativa. `SqlPlanReader` recebe o plano proposto e o contexto de acesso da chamada, reaplica `ReadPlanValidator` e então traduz o plano autorizado para uma agregação mensal parametrizada no SQLite artificial. Sem agrupamento, retorna uma linha por competência; com município em `group_by_dimension_ids`, retorna uma linha por competência e município. Uma dimensão apenas declarada, sem filtro nem agrupamento explícito, é recusada antes do SQL. Uma CTE conta os grupos antes do limite, permitindo sinalizar truncamento mesmo quando o teto do serviço SQL é igual ao limite do plano; somente até o limite autorizado é devolvido. Os testes mantêm zero como valor numérico e ausência de correspondências como conjunto vazio. A fonte foi composta com o planner em teste direto; a composição padrão da aplicação ainda usa a fixture, e não há Gold real. Isto não conclui IA-01, IA-03 nem IA-06 no PRD.

## Arquivos

| Arquivo | Papel |
| --- | --- |
| `dictionary.toml` | Lista branca **provisória**: tabelas, colunas e tipos, funções, tipos de `CAST`, colunas sensíveis, prefixos reservados e limites. |
| `dictionary_gold.toml` | Lista branca das **7 tabelas reais da Gold v1** (nomes reais de colunas), com metadados semânticos de grão, chave, métricas, dimensões e colunas anuláveis. Só os testes e `scripts/check_gold_dictionary.py` o carregam; ver a seção abaixo. |
| `dictionary.py` | `load_dictionary(path)` gera um `SqlDictionary` imutável e recusa arquivo contraditório (coluna permitida e sensível ao mesmo tempo, identificador fora de `[a-z_][a-z0-9_]*`, prefixo reservado, limite não positivo). |
| `validator.py` | `validate_sql(sql, dictionary, dialect)` → `ValidatedQuery`, ou `SqlRejected(code, detail)`. |
| `executors.py` | `SqliteReadOnlyExecutor` e `PostgresReadOnlyExecutor`; exigem dicionário e revalidam o SQL de cada `ValidatedQuery` antes de conectar. |
| `audit.py` | `QueryAuditRecord`, `InMemoryAuditSink` (testes) e `LoggingAuditSink` (uma linha JSON no logger `app.sql.audit`). |
| `service.py` | `ReadOnlySqlService.run(sql, parameters=())`: valida → executa → audita (`accepted`, `rejected` ou `failed`). |
| `plan.py` | Catálogo físico injetado e leitor do recorte artificial: plano proposto e contexto atual → autorização pelo validador injetado → janela de meses completos e filtros de igualdade ou `IN` parametrizados → totais mensais ou por município, com ordenação por valor somente quando liberada para a métrica, limite e detecção de truncamento por CTE. |
| `evidence.py` | `SqlArtificialEvidenceSource` recebe plano e contexto atuais pela porta, chama o leitor fora do loop assíncrono e projeta o resultado em evidência demonstrativa. A função de projeção não aprova nem executa consultas. |

`dictionary.toml` e `tests/fixtures/sql_dictionary_test.toml` contêm nomes provisórios. Renomear uma tabela no validador isolado depende do dicionário, conforme `tests/test_sql_dictionary.py`; a integração Gold exigirá também decidir o dono da consulta, homologar métrica, grão, unidades, permissões, credencial e reconciliação. O leitor de planos não tem tabela padrão: recebe um catálogo artificial explícito.

`ReadOnlySqlService.run` é a borda de validação SQL do ensaio: recebe texto, valida e audita antes de chamar o executor. Um `ValidatedQuery` montado manualmente como entrada é recusado e auditado, sem execução. Os executores exigem o mesmo tipo de dicionário e revalidam o SQL recebido; uma instância fabricada que mencione objeto fora da lista permitida é recusada antes da conexão. A revalidação não comprova que houve aprovação de um `LogicalReadPlan`: uma chamada direta ao executor ainda evita a auditoria do serviço e a política de acesso do leitor. O tipo Python não é credencial de autorização. A integração real deve manter a execução atrás do componente dono da consulta e usar permissões de banco restritas.

O caminho parametrizado atual aceita placeholders posicionais `?` somente no dialeto SQLite e em predicados de valor, com quantidade e tipos conferidos antes da execução. No `SqlPlanReader`, o recorte demonstrativo permite filtros de igualdade e `IN` para o município mapeado no catálogo artificial. `LogicalReadPlan.group_by_dimension_ids` declara separadamente quais dimensões serão agrupadas; o campo opcional vazio mantém os planos anteriores sem agrupamento. Por ora, o catálogo de teste só permite município. A saída usa o ID lógico `geography.municipality`, sem expor nome físico da coluna, e ordena por competência e categoria. O limite conta grupos, não meses. Outras dimensões, agrupamentos múltiplos, operadores, agregações e PostgreSQL parametrizado continuam fora deste ensaio.

Cada `SqlMetricBinding` declara explicitamente `filter_operators`: um plano com operador ausente desse conjunto é recusado antes do serviço SQL, mesmo que o perfil lógico aceite o operador. O leitor artificial implementa somente `eq` e `in`; declarar outro operador no catálogo falha na construção do leitor. A lista de operadores do catálogo físico é uma restrição adicional, não concede acesso ao plano ou ao banco.

`SqlPlanCatalog.period_granularity` declara o grão físico da coluna de período. O leitor atual aceita somente `month` e `SqlMetricBinding.aggregation="sum"`; catálogo anual ou outra agregação não pode ser composto. Um plano anual recebido por um leitor mensal é recusado e auditado antes do serviço SQL. Isso explicita as capacidades do ensaio, sem atribuir fórmula ou grão à Gold real.

`project_artificial_sql_evidence` converte o `QueryResult` já obtido pelo leitor em `EvidenceLookupResult`. Cada linha mantém período, valor e unidade; agrupamentos acrescentam `category`, que um perfil com campo de dimensão classificado pode relacionar ao ID lógico. A referência recebe `is_demo=True`, a proveniência espelha o plano e a limitação declara que os valores são inventados. Zero produz evidência numérica; ausência de linhas produz `no_evidence`. Resultado truncado exige uma segunda limitação explícita, e linha com período fora da janela é recusada. `SqlArtificialEvidenceSource.retrieve(plan, access_context)` usa o leitor e a projeção sem guardar permissões entre chamadas. Um teste encadeia planner → fonte → SQLite → `EvidenceGuard` com perfil de teste que classifica período e município; outro faz uma leitura permitida seguida de escopo revogado na mesma fonte e confirma recusa anterior ao SQL. A soma filtrada sem agrupamento preserva período e valor sem exigir uma categoria que não veio no SQL; um plano agrupado continua exigindo categoria. Janela aceita pelo perfil, mas fora da capacidade mensal do leitor, vira esclarecimento sem execução. O perfil da aplicação ainda classifica apenas `value` e `unit`; a fonte SQL não está configurada em `app/main.py` nem no endpoint. Em Python 3.12, a chamada usa [`asyncio.to_thread`](https://github.com/python/cpython/blob/main/Doc/library/asyncio-task.rst): cancelar a espera não interrompe instantaneamente uma thread já em execução, conforme o contrato de [`Future.cancel`](https://github.com/python/cpython/blob/main/Lib/concurrent/futures/_base.py); o executor SQLite aplica seu próprio timeout.

Por padrão, os resultados seguem competência e categoria em ordem crescente. Quando `SqlMetricBinding.allow_value_order=True` no catálogo artificial e `ReadOrder.field_id` identifica a própria métrica, o leitor ordena pelo valor agregado em sentido ascendente ou descendente antes do limite; período e categoria resolvem empates. Uma ordenação não declarada no catálogo ou por outra dimensão é recusada antes do serviço SQL. Essa capacidade não implica suporte automático à ordenação de outras métricas ou de uma Gold real.

Um teste pelo `ReadOnlySqlService` confirma a ordem de três valores vinculados após a qualificação de SQL que combina CTE, filtro externo e subconsulta, com resultado fictício fixo de `2500.0`. Testes de recusa pela mesma borda cobrem placeholder usado como projeção, argumento de função, nome de função, origem e ordenação; coluna não permitida em CTE e coluna sensível em subconsulta também são recusadas antes do executor. Isso verifica o percurso SQLite observado, sem ampliar o contrato do dialeto PostgreSQL.

## Dicionário da Gold v1 (`dictionary_gold.toml`)

Declara as sete tabelas exportadas pela Gold: `diagnostico_receita`, `indicadores_dec_fec`, `fila_inspecao`, `visao_360_uc`, `consumo_receita_bairro`, `variacao_consumo_uc` e `consumo_mensal_uc`. Fonte, em `origin/develop` no commit `c9580cd`: [`docs/dicionario_gold.md`](../../../docs/dicionario_gold.md) para colunas, grão, unidades e regras; [`backend/app/models/gold_v1.py`](../../../backend/app/models/gold_v1.py) para tipos, chaves e colunas anuláveis observados nos CSVs ([contrato físico](../../../docs/contracts/gold-csv-v1.md)). `controle_gold` é tabela de linhagem, fora da exportação, e não entra. O dicionário não substitui `dictionary.toml`, que continua sendo o catálogo artificial, e **nenhuma composição da aplicação o carrega**: credencial, permissões e reconciliação não foram homologadas (`status = "gold-v1-nao-homologado"`).

O carregador usa só `version`, `status`, `[limits]`, `[policy]` e `tables.<nome>.columns`. As demais chaves são metadados semânticos que hoje apenas os testes leem e conferem contra as colunas permitidas:

| Chave | Conteúdo |
| --- | --- |
| `grain`, `key` | Grão em texto e chave verificada pelo notebook (ex.: `["id_alimentador", "competencia"]`). |
| `period_column` | Coluna de competência `AAAA-MM`. Ausente nas tabelas por UC e em `variacao_consumo_uc`, cujas janelas P1/P2 são fixas. |
| `metrics` | Coluna → `unit` (do dicionário de dados) e `aggregation`: `sum` (somável no mesmo período), `count` ou `ratio` (razão ou média já calculada, como `dec`, `fec`, `ticket_medio_reais_por_uc`, `variacao_pct`; só pode ser lida no grão da chave). |
| `dimensions` | Colunas para filtrar ou agrupar. |
| `excluded_columns` | Colunas do v1 deixadas de fora. Vazio nas sete tabelas: nenhuma projeta coluna pessoal ou de pipeline. O teste exige que permitidas ∪ excluídas = snapshot. |
| `nullable_columns` | Colunas que o Backend cria como anuláveis: todas as que estão fora da chave. O carregador ignora; os testes conferem que só apontam para colunas existentes. |
| `known_values` | Só domínios fechados pelas regras da Gold: `Sim`/`Não` nas colunas de GD e as cinco categorias de `prioridade_inspecao`. Classe, subgrupo e bandeira são exemplos da origem, não domínio fechado, e não são listados. |
| `[concepts]` | Único lugar do mapeamento conceito → coluna por tabela, para nomes diferentes entre tabelas: geração distribuída é `possui_gd` ou `possui_geracao_solar`; classe é `classe_consumo` ou `classe`; subgrupo é `subgrupo_tarifario` ou `subgrupo`; alimentador é `id_alimentador` ou `alimentador`. Não há alias nas colunas. |
| `relationships` | Cruzamentos autorizados. Vazio, porque o dicionário de dados não declara nenhum. |

**Coerência com as fontes.** `tests/test_sql_gold_dictionary.py` lê `docs/dicionario_gold.md` e exige que as colunas de cada uma das sete seções sejam exatamente as do snapshot e do dicionário, com o tipo conceitual compatível. Também lê `backend/app/models/gold_v1.py` sem importá-lo (análise sintática) e compara tipos e chaves com o snapshot. Uma mudança em qualquer fonte sem atualizar o TOML quebra esses testes.

**O que fica de fora e por quê.** Nenhuma das sete tabelas projeta CPF/CNPJ, nome, endereço, CEP, coordenadas ou metadados da Silver. Mesmo assim, `sensitive_columns` mantém as colunas pessoais (`cpf_cnpj`, `nome_titular`, `logradouro`, `numero`, `cep`, `latitude`, `longitude`) e os 11 metadados de pipeline com prefixo `_`: o validador recusa qualquer identificador com esses nomes, inclusive alias, e o autorizador do SQLite nega a leitura. Os metadados são listados um a um porque reservar o prefixo `_` recusaria os aliases que o próprio `sqlglot` gera (`_col_0`, `_q_0`) quando o executor revalida o SQL. Nenhuma coluna das sete tabelas está na lista. `id_uc` continua exposto: é o código da unidade usado pelo portal; isso não torna o conjunto anônimo.

**Conferir um lote local.** `scripts/check_gold_dictionary.py` compara um diretório de CSVs (`<dir>/<tabela>/*.csv`, separador `;`, UTF-8 com ou sem BOM) com este dicionário. Nomes de coluna são comparados **sem diferenciar maiúsculas de minúsculas**, para casar `DEC`/`FEC` com `dec`/`fec`. O tipo é conferido de forma grosseira nas primeiras linhas: inteiro cabe em `bigint`, `double` e `decimal`; data exige `AAAA-MM-DD`; booleano exige `true`/`false`; texto aceita tudo. A saída tem só tabela, coluna e `PASS`/`FAIL` com motivo (tabela ausente, coluna ausente, extra ou repetida, tipo incompatível), nunca valores ou contagens; código 1 indica falha. Dentro de `ai-agent/`:

```powershell
python scripts/check_gold_dictionary.py <diretório do lote> [--sample-rows 50]
```

Rodar só no ambiente autorizado para o lote; o resultado não substitui a reconciliação.

**Cruzamentos.** O validador **não lê** `relationships`: aceita `JOIN` entre quaisquer tabelas do dicionário cujas colunas existam, por exemplo `diagnostico_receita` com `visao_360_uc` por `municipio`, embora não tenham chave em comum (o grão de uma é competência × segmentação e o da outra é UC). Esse limite está fixado por um teste `xfail(strict=True)` em `tests/test_sql_gold_dictionary.py`. Hoje a proteção vem do leitor de planos, que gera SQL de uma única tabela; SQL textual livre continuaria aceitando o cruzamento.

**Banco de teste.** `tests/gold_mock.py` cria um SQLite em arquivo temporário com as 7 tabelas, nomes, tipos e chaves do snapshot `tests/fixtures/gold_dictionary_v1_snapshot.json` (inclusive `"DEC"`/`"FEC"` em maiúsculas) e poucas linhas **sintéticas** e determinísticas: UCs `UC100000`..`UC100005`, competências `2026-08` e `2026-09`, municípios e bairros `FICTICIO`, GD `Sim`/`Não` e alimentadores `ALIM-FIC-01`..`03`. A prioridade segue a ordem de regras do notebook. As três tabelas financeiras saem do mesmo consumo mensal por UC e reconciliam por competência. Como na Gold, `indicadores_dec_fec` só tem linha para alimentador/mês com ocorrência.

**O que a Gold v1 responde no mock.** Pelo plano de teste → SQL parametrizado → `ReadOnlySqlService` (validação e SQL regenerado) → SQLite:
- receita comercial do município fictício A: R$ 320,00 em 2026-08 e R$ 255,00 em 2026-09, por `consumo_receita_bairro`. `diagnostico_receita` dá o mesmo valor pelo `SqlPlanReader` existente;
- DEC de `ALIM-FIC-01`: 2,0 e 0,5 h por UC. DEC sem alimentador fixado não é somado e termina em sem evidência;
- UCs com prioridade alta: 2;
- consumo mensal por bairro: vem de `consumo_receita_bairro`, e o bairro que mais perdeu volume pode ser identificado. Antes, essa pergunta terminava em sem evidência;
- UCs com GD e queda acima de 30%: 2, por `variacao_consumo_uc`;
- consumo mensal de uma UC: vem de `consumo_mensal_uc`;
- média histórica por competência continua sem evidência, porque só existe nas tabelas por UC.

O planejador que escolhe a tabela pelos metadados existe só no teste. Quando duas tabelas declaram a mesma métrica, ele usa a primeira em ordem alfabética; um catálogo de produção precisará de regra explícita.

### Acrescentar ou alterar tabelas da Gold

1. Atualize `docs/dicionario_gold.md` (fonte) e confira `backend/app/models/gold_v1.py`; o teste de coerência lê os dois.
2. Atualize `tests/fixtures/gold_dictionary_v1_snapshot.json` com colunas, tipos, chave e o novo commit de origem.
3. Acrescente ou ajuste `[tables.<nome>]` com `description`, `grain`, `key`, `period_column`, `dimensions`, `excluded_columns`, `nullable_columns`, `[tables.<nome>.columns]` e `[tables.<nome>.metrics]`; se houver coluna de GD, classe, subgrupo ou alimentador, inclua-a em `[concepts]`. Atualize `version`.
4. Acrescente as linhas sintéticas da tabela em `GOLD_ROWS` de `tests/gold_mock.py`; o DDL sai do snapshot.
5. Se uma pergunta precisar cruzar a nova tabela com outra, declare o par em `relationships` e lembre que o validador ainda não impõe essa lista (seção “Cruzamentos”).

### Pontos abertos com o Backend

- **`DEC` e `FEC`.** Na Gold, no CSV e no banco do Backend as colunas se chamam `DEC` e `FEC`. `backend/app/models/gold_v1.py` cria `Column("DEC")`/`Column("FEC")`, e a migração `goldv1000001` executa `table.create()` com esse modelo. O SQLAlchemy põe entre aspas um nome com maiúsculas; no PostgreSQL a coluna fica `"DEC"`, sensível a caixa. O carregador deste dicionário só aceita minúsculas e declara `dec`/`fec`. SQLite e Spark resolvem sem diferenciar caixa, e por isso o mock passa. No PostgreSQL, `SELECT dec` sem aspas é dobrado para `dec` e **não encontra** `"DEC"`; o SQL regenerado pelo validador também usa o nome do dicionário. Não decidido aqui. Opções a combinar com o Backend: renomear para minúsculas numa nova revisão, criar uma visão de leitura com nomes minúsculos para o papel da IA, ou aceitar e citar identificadores com caixa no dicionário e no validador. Até lá, o executor PostgreSQL não deve ler `indicadores_dec_fec`.
- **Prefixo das tabelas.** O Backend grava as tabelas como `gold_<nome>` (`gold_diagnostico_receita`); o dicionário usa o nome da Gold, sem prefixo. Uma leitura no banco do Backend exige alinhar os nomes, por visão ou por dicionário, junto com a decisão anterior.

## Regras do validador

Tudo funciona como lista branca: o que não estiver no dicionário é recusado. A análise falha fechada, ou seja, um erro inesperado gera `validation_error`.

| Código | Quando |
| --- | --- |
| `empty`, `too_long`, `parse_error` | Entrada vazia, maior que `limits.max_sql_chars` ou não analisável. |
| `too_many_tables` | A árvore da consulta excede `limits.max_tables` referências a tabelas, inclusive autojunções e origens em subconsultas/CTEs. |
| `multiple_statements` | Mais de uma instrução. |
| `not_select` | A raiz não é `SELECT` ou `UNION`/`INTERSECT`/`EXCEPT` de selects, com `WITH` opcional. |
| `forbidden_construct` | DML/DDL em qualquer ponto da árvore (inclusive CTE com `DELETE`/`UPDATE ... RETURNING`), `SELECT INTO`, `FOR UPDATE/SHARE`, `LATERAL`, `UNNEST`, `VALUES`, parâmetros de sessão, acesso com ponto (`pg_catalog.pg_sleep`), `NATURAL JOIN`. |
| `invalid_parameters` | Placeholder sem valor, valor sem placeholder, tipo/posição não autorizados ou uso fora do ensaio SQLite. |
| `recursive_cte` | `WITH RECURSIVE`. |
| `cte_shadowing` | CTE com o nome de uma tabela do dicionário. |
| `sensitive_column` | Qualquer identificador (coluna, alias, CTE, tabela) que esteja em `sensitive_columns`, comparado em `casefold`: `"CPF_CNPJ"` e `Nome_Titular` também são recusados. |
| `reserved_identifier` | Identificador que começa com `pg_`, `sqlite_` ou `information_schema` (por exemplo `pg_user`, `sqlite_master`). |
| `function_not_allowed` | Função fora de `allowed_functions`: `current_user`, `session_user`, `version()`, `pg_sleep`, `pg_read_file`, `set_config`, `dblink`, `load_extension`, `generate_series`, `ROW_NUMBER` etc. |
| `cast_not_allowed` | `CAST` para tipo fora de `allowed_cast_types` (por exemplo `::regclass`). |
| `select_star` | `*` ou `t.*`; só `COUNT(*)` é aceito. |
| `unknown_table`, `schema_qualified`, `table_function`, `unsupported_source` | Tabela fora do dicionário (também em junção por vírgula ou subconsulta), nome com esquema (`public.x`), função como tabela, origem que não seja tabela ou subconsulta. |
| `ambiguous_identifier` | O mesmo nome usado como tabela/alias e como coluna. No PostgreSQL, `SELECT c FROM t AS c` devolve a linha inteira, com colunas fora do dicionário. |
| `unknown_column` | Coluna que não pode ser resolvida contra o esquema do dicionário. |
| `invalid_limit` | `LIMIT`/`OFFSET` não literal ou negativo, `LIMIT ALL`, `FETCH ... PERCENT` ou `WITH TIES`. |

**Operadores não são funções.** No sqlglot, `AND`/`OR` (`Connector`), `CASE`, `IF`, `CAST` e `EXISTS` herdam de `Func`. O validador os trata como sintaxe. `LIKE`, `IN`, `BETWEEN`, `NOT` e `IS` também estão na lista de exceções, para que a regra continue correta se uma versão futura os modelar como `Func`. Um teste cobre um `WHERE` com todos esses operadores nos dois dialetos.

**Qualificação.** Depois das checagens, `sqlglot.optimizer.qualify` resolve cada coluna contra um esquema que contém **somente as colunas permitidas**, e o executor recebe o SQL qualificado (`"gold_indicadores"."bairro"`). Uma referência sem qualificação, por exemplo dentro de um `EXISTS` correlacionado, sai presa à tabela autorizada. Assim o banco não pode resolvê-la para uma coluna física fora do dicionário. A única coluna aceita sem tabela é um alias da projeção citado no `ORDER BY`. Comentários são descartados na regeneração.

**LIMIT.** O teto é `limits.max_rows`. `LIMIT` ausente é injetado no SELECT externo; `LIMIT` acima do teto é reduzido; `FETCH FIRST n ROWS ONLY` é normalizado para `LIMIT`. Um `LIMIT` só na subconsulta não conta como teto do resultado. `ValidatedQuery` e a auditoria registram `original_limit`, `applied_limit` e `limit_adjusted`.

**Referências a tabelas.** `limits.max_tables` limita o total de nós de tabela encontrados na AST, incluindo referências repetidas da mesma tabela em autojunções e subconsultas/CTEs. O dicionário artificial atual permite cinco referências; a sexta é recusada antes da execução, mesmo se os nomes forem todos autorizados. Isso limita a complexidade estrutural, mas não estima cardinalidade nem substitui timeout, limite de linhas ou permissões do banco.

## Executores

- **SQLite:** revalida a consulta contra o dicionário e abre `file:...?mode=ro` com `uri=True` e `PRAGMA query_only = ON`. Um autorizador permite apenas `SELECT`, `READ` e `FUNCTION` e nega a leitura de colunas sensíveis declaradas no dicionário, o que bloqueia também `WITH RECURSIVE`, `ATTACH` e `PRAGMA`. O timeout usa `set_progress_handler`, e o teto de linhas usa `fetchmany(max_rows + 1)`, que marca `truncated`.
- **PostgreSQL:** revalida a consulta contra o dicionário antes de conectar, executa `SET TRANSACTION READ ONLY` e `set_config('statement_timeout', ..., true)` (válido só na transação), roda a consulta com `prepare=True` (o protocolo estendido não aceita várias instruções) e faz `fetchmany(max_rows + 1)` seguido de `ROLLBACK`. `57014` vira `timeout`. Instale o extra opcional `postgres`. **A credencial do DSN também precisa ser de um papel somente leitura**, com `SELECT` apenas nas tabelas Gold: a transação read-only é defesa em profundidade, não substitui permissão no banco.
- Erros viram `QueryExecutionError(kind, error_type)` (`timeout`, `database_error`, `connection_error`) sem a mensagem do banco, que pode conter valores.

## Auditoria

Cada chamada a `ReadOnlySqlService.run` gera um `QueryAuditRecord` com: id, horário UTC, status, código do motivo, dialeto, versão do dicionário e tamanho do SQL recebido. Quando a chamada parte de `SqlPlanReader`, o registro também contém o fingerprint do plano revalidado, a versão do catálogo artificial e o `correlation_id` do contexto de acesso da chamada. Após aprovação do SQL, registra o template normalizado da consulta, com literais substituídos por `?`, aliases livres generalizados e o SHA-256 desse template, tabelas, limites original/aplicado e se houve ajuste, número de linhas, truncamento, duração e classe do erro. Chamadas diretas ao serviço SQL deixam a identificação do plano, do catálogo e da requisição vazia; esses campos não conferem autorização por si só.

Se o leitor recusar o plano **antes** de montar SQL, ele pede ao serviço um registro `rejected` com código fixo (`access_denied`, `unsupported_plan`, `plan_out_of_catalog`, `unsupported_window` ou `unsupported_filter`), dialeto, versão do dicionário e `correlation_id` quando há contexto de acesso. Esse registro não contém SQL, template, impressão do plano, filtros, texto da pergunta ou detalhes da exceção; `received_sql_chars` é zero. A recusa não chama `ReadOnlySqlService.run` nem o executor, e cada tentativa gera um registro. O identificador não está ligado à requisição do portal no ensaio atual, que compõe a fonte apenas em teste direto.

O registro **não** guarda linhas de resultado, a pergunta da pessoa, o texto SQL recebido ou um hash do SQL bruto. Consultas rejeitadas pelo serviço SQL registram metadados do plano quando fornecidos e o motivo, sem template nem fingerprint do SQL recebido. Em consultas aprovadas ou com falha na execução, o template derivado da AST aprovada omite valores literais. O SQL completo não entra na auditoria. O fingerprint do plano é um hash estável que inclui filtros no seu cálculo: não é anonimização e não deve ser considerado proteção suficiente para dados reais de baixa cardinalidade. Retenção, acesso, destino durável e estratégia de correlação para produção ainda precisam de decisão.

**Decisão em aberto:** retenção, acesso e destino durável da trilha. Até a equipe decidir, só existem os destinos em memória e de log do processo. Nenhum arquivo ou tabela de auditoria é criado.

## Por que sqlglot

- Analisa SQL em árvore com dialetos `sqlite` e `postgres`. Isso permite validar por tipo de nó, e não por regex sobre texto, e **regenerar** o SQL a partir da árvore aprovada.
- Traz `qualify` e `traverse_scope`, que resolvem colunas por escopo (CTE, subconsulta, correlação) contra um esquema fornecido. É isso que torna possível limitar a resolução às colunas do dicionário.
- É Python puro, sem serviço externo nem acesso ao banco para validar, com licença MIT.
- Faixa declarada: `sqlglot>=30.23,<31.0` em `pyproject.toml`; a prova parametrizada foi testada com **30.24.0**. As classes do AST mudam entre versões maiores, e a suíte de ataques precisa rodar a cada atualização. Fontes: [repositório oficial](https://github.com/tobymao/sqlglot) e [documentação de qualificação consultada via Context7](https://github.com/tobymao/sqlglot/blob/main/posts/onboarding.md).
- `psycopg` 3 (testado com 3.3.6) é o driver do executor PostgreSQL, como extra opcional.

## Limites conhecidos

- O dicionário é provisório e não vem de `docs/dicionario_gold.md`. Tipos e nomes precisam ser confirmados com a Gold.
- A lista branca de funções é deliberadamente pequena. Funções de janela, datas e strings adicionais precisam ser incluídas no TOML com teste.
- Um nome de tabela em `CTE`/alias que coincida com o nome de uma coluna é recusado mesmo quando seria inofensivo.
- `SqlPlanReader.read` exige o contexto de acesso e reaplica o `ReadPlanValidator` injetado antes de chamar o serviço SQL; contexto ausente ou escopo revogado impede a consulta. A fonte foi composta com o planner apenas em teste direto; identidade e permissões reais do banco não foram comprovadas.
- Não há teste contra um PostgreSQL real no gate local: o teste de integração roda só com `GENAI_TEST_POSTGRES_DSN` definido. Os demais usam uma conexão falsa que confere as instruções emitidas.
- `SqlArtificialEvidenceSource` implementa a porta `EvidenceSource` sobre o leitor, mas ainda não compõe uma resposta HTTP ao usuário. O leitor reaplica a política de acesso com o contexto atual e valida o recorte do catálogo físico. Recusas anteriores ao SQL geram registros mínimos, com correlação do contexto quando presente e sem filtro; retenção e ligação à requisição do portal dependem da composição da aplicação.

## Verificar

O recorte aprovado usa `SqlPlanCatalog` artificial `v1`, dicionário de teste
carregado de `tests/fixtures/sql_dictionary_test.toml`, `sqlglot` 30.24.0 e
dialeto SQLite com parâmetros posicionais `?`. Os testes constroem um banco
temporário com registros inventados; não requerem Gold nem DSN PostgreSQL.
Dentro de `ai-agent/`:

```powershell
python -m pip install -e ".[dev,postgres]"
python -m pytest -q tests/test_sql_validator.py tests/test_sql_executors.py tests/test_sql_service.py tests/test_sql_dictionary.py tests/test_sql_plan_reader.py
python -m pytest -q --tb=short
python -m ruff check .
```

Na execução registrada de 22/10/2026, antes do limite `max_tables`, a seleção
SQL passou com **329 testes** e **1 teste PostgreSQL opcional pulado**; a suíte
GenAI completa passou com **761 testes** e **2 opcionais pulados**. Após a
alteração do limite, a seleção focada de dicionário, validador, serviço SQL e
assinatura da fonte passou com **277 testes**, pelo comando
`python -m pytest -q --basetemp .pytest-tmp-read-review tests/test_sql_dictionary.py tests/test_sql_validator.py tests/test_sql_service.py tests/test_scenarios.py`.
A suíte GenAI completa não foi reexecutada nesta mudança.

O resultado artificial fixado nos testes inclui **3500,5 unidades fictícias**
para janeiro de 2025 no município fictício A, **800,25** para o município B
no mesmo mês, `0` como valor legítimo e lista vazia quando não há linhas.
Três meses no município A produzem **3500,5**, **3600,75** e **970,1**, nessa
ordem; limite 2 devolve duas linhas e indica truncamento. O filtro `IN` usa
valores vinculados, e tentativas de escrita, objetos proibidos ou escopo
revogado são recusados antes de executar. Esses números verificam somente a
mecânica do ensaio: a API ainda usa a fixture e nenhuma resposta foi
reconciliada com Gold.
