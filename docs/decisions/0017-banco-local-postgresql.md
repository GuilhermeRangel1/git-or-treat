# ADR-0017 — PostgreSQL como banco local da Gold

**Data:** 2026-10-27
**Estado:** aprovada em 27/10/2026, com base nos comentários de aprovação de Backend e Engenharia de Dados no PR #63 (ver "Pendências e aprovação").
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

1. **PostgreSQL (escolhida).**
   - Benefícios: já é o banco do Backend, do `docker-compose.yml` e do CI, com Alembic e driver instalados; papéis e `GRANT` permitem um papel de leitura com acesso só às tabelas Gold expostas; `statement_timeout` e `default_transaction_read_only` impõem limites no servidor; suporta acessos concorrentes do portal e do agente.
   - Custos e riscos: exige serviço em execução para portal e IA; diferenças de dialeto em relação ao SQLite usado nos testes padrão do Backend; cuidado com a forma dos identificadores (ver Consequências).
2. **SQLite.**
   - Benefícios: arquivo único, sem serviço; é o que a demonstração da GenAI já usa.
   - Custos e riscos: sem papéis nem `GRANT`. A restrição de leitura depende de abrir o arquivo somente leitura e de autorizador na aplicação, não de permissão no banco. Escrita concorrente limitada, sendo que o mesmo banco local também guarda dados operacionais (ordens); dois motores entre portal e Gold.
3. **Outro motor (por exemplo, DuckDB).**
   - Benefícios: bom para leitura analítica de CSV.
   - Custos e riscos: novo componente sem uso no repositório, sem papéis comparáveis ao PostgreSQL e sem justificativa de requisito que o exija.

## Decisão

Aprovada por Backend e Engenharia de Dados no PR #63:

1. **Motor, versão e dialeto.** PostgreSQL 16 é o banco local da Gold, no mesmo serviço já usado pelo Backend, alinhado à versão do CI. O dialeto alvo das consultas Gold é o do PostgreSQL.
2. **Executor único.** O Backend é o único serviço que conecta à Gold e executa consultas, como na ADR-0002. A GenAI não recebe credencial nem string de conexão do banco.
3. **Papel somente leitura.** A consulta Gold do Backend usa o papel `venergy_gold_reader`, sem permissão de escrita, restrito a `SELECT` no schema `gold`, sem acesso às tabelas operacionais e com timeout no servidor. O papel é criado e mantido pelo Backend, por migração ou script de inicialização versionado. A carga (DE-06) e as migrações usam outro papel.

Esta decisão não define nomes de tabelas ou colunas, fórmulas nem o formato do `batch_ref`.

## Consequências e verificação

- **Versão do `docker-compose.yml`.** O `docker-compose.yml` sobe hoje `postgres:18`, enquanto o CI e esta decisão usam a 16. O alinhamento do compose à versão 16 fica com o Backend e não é feito nesta mudança.
- **Nomes de colunas.** No PostgreSQL, identificadores sem aspas viram minúsculas. Uma coluna criada como `"DEC"` ou `"FEC"`, por exemplo copiando o cabeçalho do CSV entre aspas, não casa com `dec` em uma consulta sem aspas, e o contrário também vale. Os nomes físicos precisam ser congelados uma vez, por exemplo em minúsculas e `snake_case`, com o mapeamento do cabeçalho do CSV para a coluna registrado no dicionário Gold (DE-08). O carregador e o catálogo do executor usam esse mapeamento, e nenhum dos dois pode depender da grafia do CSV.
- **Carregador idempotente (DE-06).** O carregador precisa substituir ou ignorar o lote já carregado sem duplicar linhas, registrar o manifesto carregado e validado (origem do `batch_ref` no contrato) e recusar lotes com os valores de reserva `SINTETICO_DEV` e `LOTE_DEV`. O DE-06 também exige conferir esquema, contagens, chaves e agregados entre Databricks e banco. O `load_gold.py` atual não faz nada disso.
- **Separação entre Gold e dados operacionais.** As tabelas analíticas carregadas ficam no schema `gold` e não podem ser sobrescritas pelos dados operacionais do portal (PRD, seção do banco local). O `GRANT` de `venergy_gold_reader` se limita a esse schema.
- **Papel somente leitura e responsável.** O Backend cria e mantém `venergy_gold_reader` por migração ou script de inicialização e testa no PostgreSQL de CI que ele não grava, não lê tabela fora do schema `gold` e respeita o timeout. O teste de permissões da GenAI com dados artificiais pode servir de referência, mas não substitui o teste do Backend.
- **Leitor SQLite da demonstração.** O leitor SQLite de `ai-agent/app/sql/` continua só para testes e demonstrações sintéticas e não é ligado à Gold.
- **Testes do Backend.** Como os testes padrão usam SQLite em memória, as consultas Gold e o papel de leitura precisam de testes no PostgreSQL descartável do CI, para que diferenças de dialeto não passem sem ser vistas.
- **Revisão.** Se Backend ou Dados passarem a preferir SQLite ou outro motor, esta ADR é substituída e a ADR-0002 continua válida, porque o contrato lógico não depende do motor. A restrição de leitura, nesse caso, precisa ser demonstrada sem papel de banco.

## Pendências e aprovação

Aprovada em 27/10/2026 com base nos comentários de Backend (Fcc2187) e Engenharia de Dados (Biazita14) no PR #63. A aprovação não cria credencial, papel, carga nem consulta Gold real; cada uma depende das pendências abaixo.

1. Backend: alinhar o `docker-compose.yml` (`postgres:18`) à versão 16 usada pelo CI.
2. Backend: criar `venergy_gold_reader` por migração ou script de inicialização, com `SELECT` só no schema `gold`, e testá-lo no PostgreSQL do CI.
3. Congelar a convenção de nomes físicos e o mapeamento CSV → coluna no dicionário Gold (DE-08).
4. Confirmar o comportamento idempotente do carregador e o registro do manifesto (DE-06), com a pessoa dona da exportação da Gold.

## Complemento de implementação — preparação de publicação, 28/10/2026

A preparação na branch `feat/integracao-genai-gold` mantém o motor/executor aprovados. A migração `goldv1000003` move as relações analíticas v1 ao schema `gold`, preservando nomes e conteúdo; metadados operacionais da carga ficam separados e uma vista expõe a identidade mínima. O papel é provisionado por administrador fora das migrações comuns, pois o migrador de testes não tem `CREATEROLE`. Grants específicos evitam liberar automaticamente tabelas futuras; senha fica fora do código.

Para distinguir origem e publicação local, adota-se UUID4 persistido como `publication_id`, separado de cada `attempt_id`. Usar apenas hash dos arquivos confundiria ciclos distintos de publicação, como A → B → A. Origem, conteúdo e versão iguais retornam `unchanged`; outro run de origem gera nova publicação mesmo com arquivos iguais. Legados mantêm dados, mas só ganham identidade real após carga validada, sem backfill fictício.

Formato, exemplos e compatibilidade estão no contrato interno e em `gold-csv-v1.md`. A modelagem prepara GENAI-01; revisão entre equipes e execução do fluxo GenAI permanecem pendentes. As descrições anteriores deste documento retratam sua base histórica, não o estado atual do carregador.
