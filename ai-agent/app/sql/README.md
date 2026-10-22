# Camada SQL somente leitura

Ensaio da borda SQL (IA-06): valida uma consulta contra um dicionário, executa **somente o SQL regenerado** em um executor de leitura e audita a tentativa. `SqlPlanReader` recebe o plano proposto e o contexto de acesso da chamada, reaplica `ReadPlanValidator` e então traduz o plano autorizado para uma agregação mensal parametrizada no SQLite artificial, incluindo janelas com vários meses completos e uma linha de resultado por competência. Uma CTE conta os grupos antes do limite, permitindo sinalizar truncamento mesmo quando o teto do serviço SQL é igual ao limite do plano; somente até o limite autorizado é devolvido. Os testes mantêm zero como valor numérico e ausência de correspondências como conjunto vazio. Esse leitor ainda não está ligado ao planner da aplicação, aos insights nem aos providers; não há Gold real. Isto não conclui IA-01, IA-03 nem IA-06 no PRD.

## Arquivos

| Arquivo | Papel |
| --- | --- |
| `dictionary.toml` | Lista branca **provisória**: tabelas, colunas e tipos, funções, tipos de `CAST`, colunas sensíveis, prefixos reservados e limites. |
| `dictionary.py` | `load_dictionary(path)` gera um `SqlDictionary` imutável e recusa arquivo contraditório (coluna permitida e sensível ao mesmo tempo, identificador fora de `[a-z_][a-z0-9_]*`, prefixo reservado, limite não positivo). |
| `validator.py` | `validate_sql(sql, dictionary, dialect)` → `ValidatedQuery`, ou `SqlRejected(code, detail)`. |
| `executors.py` | `SqliteReadOnlyExecutor` e `PostgresReadOnlyExecutor`; aceitam somente `ValidatedQuery`. |
| `audit.py` | `QueryAuditRecord`, `InMemoryAuditSink` (testes) e `LoggingAuditSink` (uma linha JSON no logger `app.sql.audit`). |
| `service.py` | `ReadOnlySqlService.run(sql, parameters=())`: valida → executa → audita (`accepted`, `rejected` ou `failed`). |
| `plan.py` | Catálogo físico injetado e leitor do recorte artificial: plano proposto e contexto atual → autorização pelo validador injetado → janela de meses completos e filtros de igualdade ou `IN` parametrizados → totais mensais em ordem cronológica, com limite e detecção de truncamento por CTE. |

`dictionary.toml` e `tests/fixtures/sql_dictionary_test.toml` contêm nomes provisórios. Renomear uma tabela no validador isolado depende do dicionário, conforme `tests/test_sql_dictionary.py`; a integração Gold exigirá também decidir o dono da consulta, homologar métrica, grão, unidades, permissões, credencial e reconciliação. O leitor de planos não tem tabela padrão: recebe um catálogo artificial explícito.

O caminho parametrizado atual aceita placeholders posicionais `?` somente no dialeto SQLite e em predicados de valor, com quantidade e tipos conferidos antes da execução. No `SqlPlanReader`, o recorte demonstrativo permite filtros de igualdade e `IN` para o município mapeado no catálogo artificial. Outras dimensões, operadores, agregações e PostgreSQL parametrizado continuam fora deste ensaio.

## Regras do validador

Tudo funciona como lista branca: o que não estiver no dicionário é recusado. A análise falha fechada, ou seja, um erro inesperado gera `validation_error`.

| Código | Quando |
| --- | --- |
| `empty`, `too_long`, `parse_error` | Entrada vazia, maior que `limits.max_sql_chars` ou não analisável. |
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

## Executores

- **SQLite:** abre `file:...?mode=ro` com `uri=True` e `PRAGMA query_only = ON`. Um autorizador permite apenas `SELECT`, `READ` e `FUNCTION` e nega a leitura de colunas sensíveis, o que bloqueia também `WITH RECURSIVE`, `ATTACH` e `PRAGMA`. O timeout usa `set_progress_handler`, e o teto de linhas usa `fetchmany(max_rows + 1)`, que marca `truncated`.
- **PostgreSQL:** executa `SET TRANSACTION READ ONLY` e `set_config('statement_timeout', ..., true)` (válido só na transação), roda a consulta com `prepare=True` (o protocolo estendido não aceita várias instruções) e faz `fetchmany(max_rows + 1)` seguido de `ROLLBACK`. `57014` vira `timeout`. Instale o extra opcional `postgres`. **A credencial do DSN também precisa ser de um papel somente leitura**, com `SELECT` apenas nas tabelas Gold: a transação read-only é defesa em profundidade, não substitui permissão no banco.
- Erros viram `QueryExecutionError(kind, error_type)` (`timeout`, `database_error`, `connection_error`) sem a mensagem do banco, que pode conter valores.

## Auditoria

Cada chamada a `ReadOnlySqlService.run` gera um `QueryAuditRecord` com: id, horário UTC, status, código do motivo, dialeto, versão do dicionário e tamanho do SQL recebido. Quando a chamada parte de `SqlPlanReader`, o registro também contém o fingerprint do plano revalidado e a versão do catálogo artificial. Após aprovação do SQL, registra o template normalizado da consulta, com literais substituídos por `?`, aliases livres generalizados e o SHA-256 desse template, tabelas, limites original/aplicado e se houve ajuste, número de linhas, truncamento, duração e classe do erro. Chamadas diretas ao serviço SQL deixam a identificação do plano e do catálogo vazia; esses campos não conferem autorização por si só.

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
- `SqlPlanReader.read` exige o contexto de acesso e reaplica o `ReadPlanValidator` injetado antes de chamar o serviço SQL; contexto ausente ou escopo revogado impede a consulta. A composição com o planner e a porta `EvidenceSource` ainda não foi feita. A identidade e as permissões reais do banco também não foram comprovadas.
- Não há teste contra um PostgreSQL real no gate local: o teste de integração roda só com `GENAI_TEST_POSTGRES_DSN` definido. Os demais usam uma conexão falsa que confere as instruções emitidas.
- O leitor de plano ainda não implementa a porta `EvidenceSource` nem compõe resposta ao usuário. Ele reaplica a política de acesso com o contexto atual e valida também o recorte que este catálogo físico consegue executar. Recusas anteriores ao serviço SQL não geram `QueryAuditRecord` nesta camada; a composição deverá decidir como registrá-las sem incluir valores do plano.

## Verificar

Dentro de `ai-agent/`:

```powershell
python -m pip install -e ".[dev,postgres]"
python -m pytest -q tests/test_sql_validator.py tests/test_sql_executors.py tests/test_sql_service.py tests/test_sql_dictionary.py tests/test_sql_plan_reader.py
python -m ruff check .
```
