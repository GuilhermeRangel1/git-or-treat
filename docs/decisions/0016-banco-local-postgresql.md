# ADR-0016 — PostgreSQL como banco local da Gold

**Data:** 2026-10-27
**Estado:** proposta, não aprovada. Aguarda aprovação de Backend e Engenharia de Dados (ver "Pendências e aprovação").
**IDs do PRD afetados:** P-04, DE-06, DE-08; relacionados IA-01, IA-03 e IA-06 pela [ADR-0002](0002-genai-gold-query-owner.md)
**Contrato relacionado:** [Contrato interno de planejamento e síntese entre Backend e GenAI](../contracts/genai-query-execution.md)

## Contexto

O P-04 do PRD continua aberto: "SQL local: SQLite/PostgreSQL/outro". O case permite SQLite, PostgreSQL ou outro banco local justificado e indica PostgreSQL quando o time precisar de concorrência, recursos analíticos ou controle de acesso mais robusto, sem fechar a escolha. A [ADR-0002](0002-genai-gold-query-owner.md) definiu o Backend como único executor das consultas Gold no banco local alimentado pelos CSV exportados do Databricks (DE-06) e deixou o motor em aberto.

Estado do repositório na branch `develop` em 27/10/2026:

- **Backend:** `DATABASE_URL` padrão `postgresql+psycopg://…` (SQLAlchemy 2 com psycopg 3, em `backend/app/core/config.py`); migrações Alembic em `backend/alembic/versions/`, incluindo a tabela provisória `gold_indicadores`; `docker-compose.yml` sobe `postgres:18` como serviço `db`. Os testes usam SQLite em memória por padrão e têm testes dedicados de migração e persistência em PostgreSQL descartável.
- **CI:** o job `CI Backend` de `.github/workflows/quality.yml` sobe `postgres:16` descartável e prepara um usuário de migração sem superusuário (`backend/scripts/prepare_test_postgres.sql`). A versão difere da usada no `docker-compose.yml` (18).
- **Carga:** `backend/scripts/load_gold.py` é um esqueleto: lista os CSV, não lê nem insere registros e não implementa idempotência.
- **GenAI:** a demonstração usa um leitor SQL com SQLite artificial (`ai-agent/app/sql/`). Há um executor PostgreSQL e um teste de permissões contra PostgreSQL descartável (`tests/test_sql_postgres_permissions.py`), ambos só com dados artificiais. Pela ADR-0002, esse leitor não é ligado à Gold.

Nenhuma credencial, papel ou esquema Gold real foi criado.

## Opções consideradas

1. **PostgreSQL (proposta).**
   - Benefícios: já é o banco do Backend, do `docker-compose.yml` e do CI, com Alembic e driver instalados; papéis e `GRANT` permitem um papel de leitura com acesso só às tabelas Gold expostas; `statement_timeout` e `default_transaction_read_only` impõem limites no servidor; suporta acessos concorrentes do portal e do agente.
   - Custos e riscos: exige serviço em execução para portal e IA; diferenças de dialeto em relação ao SQLite usado nos testes padrão do Backend; cuidado com a forma dos identificadores (ver Consequências).
2. **SQLite.**
   - Benefícios: arquivo único, sem serviço; é o que a demonstração da GenAI já usa.
   - Custos e riscos: sem papéis nem `GRANT`. A restrição de leitura depende de abrir o arquivo somente leitura e de autorizador na aplicação, não de permissão no banco. Escrita concorrente limitada, sendo que o mesmo banco local também guarda dados operacionais (ordens); dois motores entre portal e Gold.
3. **Outro motor (por exemplo, DuckDB).**
   - Benefícios: bom para leitura analítica de CSV.
   - Custos e riscos: novo componente sem uso no repositório, sem papéis comparáveis ao PostgreSQL e sem justificativa de requisito que o exija.

## Decisão proposta

A confirmar por Backend e Engenharia de Dados:

1. **Motor e dialeto.** PostgreSQL é o banco local da Gold, no mesmo serviço já usado pelo Backend. O dialeto alvo das consultas Gold é o do PostgreSQL. A versão de referência precisa ser uma só entre `docker-compose.yml` e CI (hoje 18 e 16).
2. **Executor único.** O Backend é o único serviço que conecta à Gold e executa consultas, como na ADR-0002. A GenAI não recebe credencial nem string de conexão do banco.
3. **Papel somente leitura.** A consulta Gold do Backend usa um papel próprio, sem permissão de escrita, com `SELECT` só nas tabelas Gold expostas no dicionário (DE-08), sem acesso às tabelas operacionais e com timeout no servidor. A carga (DE-06) e as migrações usam outro papel.

Esta proposta não define esquema físico, nomes de tabelas ou colunas, fórmulas nem o formato do `batch_ref`.

## Consequências e verificação

- **Nomes de colunas.** No PostgreSQL, identificadores sem aspas viram minúsculas. Uma coluna criada como `"DEC"` ou `"FEC"`, por exemplo copiando o cabeçalho do CSV entre aspas, não casa com `dec` em uma consulta sem aspas, e o contrário também vale. Os nomes físicos precisam ser congelados uma vez, por exemplo em minúsculas e `snake_case`, com o mapeamento do cabeçalho do CSV para a coluna registrado no dicionário Gold (DE-08). O carregador e o catálogo do executor usam esse mapeamento, e nenhum dos dois pode depender da grafia do CSV.
- **Carregador idempotente (DE-06).** O carregador precisa substituir ou ignorar o lote já carregado sem duplicar linhas, registrar o manifesto carregado e validado (origem do `batch_ref` no contrato) e recusar lotes com os valores de reserva `SINTETICO_DEV` e `LOTE_DEV`. O DE-06 também exige conferir esquema, contagens, chaves e agregados entre Databricks e banco. O `load_gold.py` atual não faz nada disso.
- **Separação entre Gold e dados operacionais.** As tabelas analíticas carregadas não podem ser sobrescritas pelos dados operacionais do portal (PRD, seção do banco local). Um esquema ou prefixo próprio para a Gold facilita o `GRANT` do papel de leitura; a forma exata fica a definir.
- **Papel somente leitura e responsável.** É preciso definir quem cria e mantém o papel (script versionado, migração ou provisionamento do ambiente) e testar no PostgreSQL de CI que ele não grava, não lê tabela fora do `GRANT` e respeita o timeout. O teste de permissões da GenAI com dados artificiais pode servir de referência, mas não substitui o teste do Backend.
- **Leitor SQLite da demonstração.** O leitor SQLite de `ai-agent/app/sql/` continua só para testes e demonstrações sintéticas e não é ligado à Gold.
- **Testes do Backend.** Como os testes padrão usam SQLite em memória, as consultas Gold e o papel de leitura precisam de testes no PostgreSQL descartável do CI, para que diferenças de dialeto não passem sem ser vistas.
- **Revisão.** Se Backend ou Dados preferirem SQLite ou outro motor, esta ADR é substituída e a ADR-0002 continua válida, porque o contrato lógico não depende do motor. A restrição de leitura, nesse caso, precisa ser demonstrada sem papel de banco.

## Pendências e aprovação

Aprovação necessária de **Backend** e **Engenharia de Dados**. Até lá, o P-04 continua aberto no PRD e esta ADR não autoriza credencial, papel, carga ou consulta Gold real.

1. Confirmar PostgreSQL e a versão de referência única entre `docker-compose.yml` e CI.
2. Congelar a convenção de nomes físicos e o mapeamento CSV → coluna no dicionário Gold (DE-08).
3. Definir quem cria e mantém o papel somente leitura e como ele é testado no CI.
4. Definir o esquema ou prefixo da Gold, separado das tabelas operacionais.
5. Confirmar o comportamento idempotente do carregador e o registro do manifesto (DE-06), com a pessoa dona da exportação da Gold.
