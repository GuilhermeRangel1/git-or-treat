# Camada SQL somente leitura

Ensaio da borda SQL (IA-06): valida uma consulta contra um dicionário, executa **somente o SQL regenerado** em um executor de leitura e audita a tentativa. `SqlPlanReader` recebe o plano proposto e o contexto de acesso da chamada, reaplica `ReadPlanValidator` e então traduz o plano autorizado para uma agregação mensal parametrizada no SQLite artificial. Sem agrupamento, retorna uma linha por competência; com município em `group_by_dimension_ids`, retorna uma linha por competência e município. Uma dimensão apenas declarada, sem filtro nem agrupamento explícito, é recusada antes do SQL. Uma CTE conta os grupos antes do limite, permitindo sinalizar truncamento mesmo quando o teto do serviço SQL é igual ao limite do plano; somente até o limite autorizado é devolvido. Os testes mantêm zero como valor numérico e ausência de correspondências como conjunto vazio. A fonte foi composta com o planner em teste direto; a composição padrão da aplicação ainda usa a fixture, e não há Gold real. Isto não conclui IA-01, IA-03 nem IA-06 no PRD.

## Arquivos

| Arquivo | Papel |
| --- | --- |
| `dictionary.toml` | Lista branca **provisória**: tabelas, colunas e tipos, funções, tipos de `CAST`, colunas sensíveis, prefixos reservados e limites. |
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

- O dicionário é provisório e não vem de `docs/data-dictionary.md`. Tipos e nomes precisam ser confirmados com a Gold.
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
