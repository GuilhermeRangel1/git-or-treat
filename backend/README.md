# Backend — V-Energy Grid 360

API FastAPI com conexão SQLAlchemy, migração Alembic e persistência inicial das ordens de inspeção. As rotas analíticas têm contratos versionados e um adaptador sintético em memória para desenvolvimento; elas não consultam a Gold. Os requisitos de produto permanecem pendentes de implementação e reconciliação com dados Gold.

PostgreSQL é o banco configurado para execução normal. SQLite é usado nos testes HTTP. O quality workflow executa também migrações e uma gravação/leitura ORM contra um serviço PostgreSQL descartável, com credenciais sintéticas definidas apenas no CI.

## Estrutura

```text
backend/
├── app/api/v1/endpoints/  # Rotas HTTP
├── app/core/              # Configuração e conexão SQLAlchemy
├── app/db/base.py         # Registro ORM independente do engine
├── app/models/            # Tabelas Gold e de ordens operacionais
├── app/schemas/           # Contratos Pydantic de entrada e saída
├── app/services/          # Regras e operações de domínio
├── alembic/               # Migrações de esquema
├── scripts/load_gold.py   # Esqueleto sem carga de dados implementada
├── tests/                 # Testes HTTP, ORM e migrações
└── requirements.txt       # Dependências Python
```

O fluxo das ordens passa pelas rotas HTTP, validação dos schemas, serviço de domínio, sessão SQLAlchemy e modelos. `app.db.base.Base` registra os metadados sem criar engine; `app.core.database` configura o engine, pooling, `SessionLocal` e `get_db`. `app.core.database.Base` continua disponível para compatibilidade.

## Execução local

Use Python 3.12, igual ao Docker e ao CI. Na pasta `backend`, crie e ative um ambiente virtual, instale as dependências e configure `DATABASE_URL` com a URL do seu PostgreSQL local em `.env`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `DATABASE_URL` em `.env` com a conexão local adequada. Aplique o esquema e inicie a API:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

O health check fica em `http://localhost:8000/api/v1/health`. Swagger UI: `http://localhost:8000/docs`; ReDoc: `http://localhost:8000/redoc`.

### Host, Docker Compose e testes

| Processo que abre a conexão | Configuração | Host do PostgreSQL |
| --- | --- | --- |
| API/Alembic executados no Windows/host | `DATABASE_URL` em `backend/.env` ou no ambiente do comando | `localhost` e a porta publicada, mesmo quando somente o banco roda no Docker |
| API/Alembic executados no serviço `backend` do Compose | `DATABASE_URL` em `backend/.env`, carregado pelo `env_file` do Compose | `db:5432`, na rede interna do Compose |
| Teste de migração PostgreSQL | `TEST_POSTGRES_URL` no ambiente do comando | `localhost` no runner/host; nome do serviço quando o teste roda na mesma rede Docker |

O exemplo `.env.example` atende à execução no host. Para executar o backend inteiro no Compose, ajuste a URL do arquivo local para `db`, usando usuário, senha e banco compatíveis com sua configuração local de `.env.db`. Na raiz, prepare `.env.db` a partir de `.env.db.example`, configure os valores e inicie `docker compose up -d db`. Aplique a migração no contexto correto com `docker compose run --rm backend alembic upgrade head` antes de `docker compose up -d backend`. Não versionar os arquivos locais com credenciais.

`db` é um nome de serviço da rede Docker; não é o endereço do banco para o Python executado no Windows. `localhost` dentro do contêiner aponta para o próprio contêiner. Ao alternar os modos, confira a URL antes de migrar. Os testes HTTP substituem `DATABASE_URL` por SQLite em memória; eles passarem não comprova que a conexão da aplicação foi configurada. Confira também o health check com `database=connected` no modo escolhido.

## Contratos analíticos de desenvolvimento

`ANALYTICS_SOURCE` aceita `unavailable` (padrão, retorna HTTP 503 nas rotas analíticas) ou `synthetic`. Para experimentar os contratos sem conectar ao PostgreSQL, configure a opção `synthetic` no ambiente antes de iniciar a API. Um valor desconhecido impede a inicialização. `/api/v1/kpis`, `/revenue`, `/ucs`, `/ucs/{uc_id}`, `/inspections/queue` e `/operations/continuity` usam a interface `get_analytics_repository`; filas de inspeção continuam separadas das ordens operacionais persistidas.

A fixture sintética `dev03-v1` cobre explicitamente janeiro e fevereiro de 2025 para faturamento e energia faturada; `/api/v1/revenue` publica o contrato 1.1.0 e inclui oito UCs distintas faturadas em cada extremo, com Recife e Olinda, mais de um bairro e as classes Comercial e Residencial nos dois meses. No período, os controles são BRL 1.727 faturados, BRL 1.710 pagos com valor conhecido, 1.585 kWh faturados e 407 kWh medidos com valor conhecido. Receita por competência e recorte usa apenas fatos de fatura; leituras e pagamento permanecem grandezas separadas. A cobertura das leituras medidas é parcial e não substitui cobertura financeira. O perfil de UC traz referência e nome fictícios; vencimento, pagamento e situação permanecem campos sintéticos. A decomposição preço-volume e as taxas de continuidade são demonstrativas, versionadas e não homologadas pela Gold. A fixture mantém leitura zero válida, leitura ausente, UC sem fatura, medidor retirado, alimentador sem denominador e o AL-02 distribuído entre Olinda e Paulista; limitações e nulidade aparecem na resposta.

Exemplo PowerShell para iniciar a API em modo demonstrativo:

```powershell
$env:ANALYTICS_SOURCE = "synthetic"
uvicorn app.main:app --reload --port 8000
```

## Acesso às ordens e limites de entrada

DEV-06: [contrato de criação pela fila e consulta paginada](../docs/contracts/inspection-orders-dev06.md). Aplicar `alembic upgrade head` antes de iniciar sobre banco existente. O portal básico usa `POST /inspections/queue/{uc_id}/orders` com `Idempotency-Key` e versões do detalhe; consulta por `/inspections/orders/search` e `/inspections/orders/{id}`. O prefixo completo é `/api/v1`. O proxy Vite de desenvolvimento recebe `ORDERS_DEV_PROXY_TOKEN` no servidor, com `VITE_API_URL=/`; produção continua dependendo de identidade/BFF próprios.

As rotas `/api/v1/inspections/orders` agora ficam bloqueadas sem autenticação de serviço. Configure no servidor `ORDERS_READ_TOKEN` e/ou `ORDERS_WRITE_TOKEN`, usando valores aleatórios distintos com pelo menos 32 caracteres. Leitor somente lista; escritor lista/cria/altera. O Swagger oferece o esquema `OrdersServiceToken` em Authorize. Não coloque esses valores em `VITE_*`, URLs, commits ou código frontend. Eles não são login de usuário; a futura UI operacional precisa de sessão/BFF ou identidade própria. Sem configuração, o Panorama sintético continua funcionando e ordens permanecem fechadas.

Para criar cada valor, execute localmente `python -c "import secrets; print(secrets.token_urlsafe(32))"` e armazene apenas em configuração privada. A alteração requer reiniciar/recriar o backend. Em produção, use HTTPS e rotacione as credenciais.

Entradas operacionais têm limites de tamanho; IDs de ordem são positivos até 2^63−1. JSON usa UTF-8, corpo até 64 KiB e até 32 níveis. Rejeições são 400/413/422. PENDENTE pode iniciar/cancelar; EM_ANDAMENTO pode concluir/cancelar; ordens encerradas não reabrem e conclusão exige resultado. Veja [ADR-0007](../docs/decisions/0007-contencao-seguranca-ordens-e-entradas.md) para detalhes e limites.

`BACKEND_ALLOWED_HOSTS` aceita lista JSON ou nomes separados por vírgulas. Configure os hosts reais do ingresso em produção; a lista padrão atende localhost/127.0.0.1, proxy backend e testes. Não use wildcard como configuração de implantação.

## Verificações

### Imagem Docker

O backend usa a base `dhi.io/python:3.12-alpine3.24-dev`, mantida pela Docker Hardened Images. A base verificada em 20/10/2026 contém Python 3.12.15 e zlib `1.3.2-r1`, já corrigida para CVE-2026-85091; não é necessário atualizar essa biblioteca no Dockerfile. A decisão e seus limites estão na [ADR-0005](../docs/decisions/0005-backend-python312-alpine.md).

A partir da raiz do repositório:

```powershell
docker build --pull --no-cache -f backend/Dockerfile -t git-or-treat-backend:dhi-check .
docker run --rm git-or-treat-backend:dhi-check python -m pip check
docker run --rm git-or-treat-backend:dhi-check python -m pytest -q
docker scout cves registry://dhi.io/python:3.12-alpine3.24-dev --platform linux/amd64 --format packages
docker scout cves local://git-or-treat-backend:dhi-check --platform linux/amd64 --format packages
```

Sem `TEST_POSTGRES_URL`, o teste PostgreSQL é ignorado. Para incluí-lo, forneça ao contêiner uma URL de banco descartável `*_test` e acesso à mesma rede desse banco. O CI constrói a imagem e executa a suíte dentro dela com PostgreSQL 16 descartável, além dos testes existentes no runner. O scanner acima é uma verificação manual; o workflow não executa Docker Scout.

A [documentação DHI](https://docs.docker.com/dhi/how-to/use/) orienta autenticar com `docker login dhi.io`. O pull local com configuração Docker vazia também funcionou na verificação desta entrega; o acesso no runner GitHub ainda precisa ser confirmado. Se o registry exigir autenticação, use o login interativo localmente e configure os secrets `DHI_USERNAME` e `DHI_TOKEN` no GitHub; o workflow faz login quando ambos estão presentes. Não colocar credenciais no Dockerfile ou no repositório.

### Ambiente local

```powershell
python -m pytest -q
python -m compileall -q app tests scripts
```

Os testes locais usam SQLite e uma URL temporária em `tmp_path` para o ciclo Alembic. O teste PostgreSQL só é ativado quando `TEST_POSTGRES_URL` aponta explicitamente para um banco descartável cujo nome termina em `_test`. O CI fornece um PostgreSQL efêmero para esse teste; não use uma URL de produção ou um banco pessoal nessa variável.

O usuário do teste PostgreSQL deve ser **sem SUPERUSER**, com propriedade/permissões para criar e remover os objetos no banco descartável. O usuário da aplicação não precisa receber essas permissões de migração. Na CI, `scripts/prepare_test_postgres.sql` prepara um papel dedicado no banco efêmero `v_energy_test`; o administrador serve apenas para essa preparação. As credenciais desse script são exemplos exclusivos da CI, não configuração de desenvolvimento ou produção.

Para executar localmente, crie previamente um banco vazio `*_test` e o usuário de migração apropriado. Na pasta `backend`, forneça a URL somente ao processo de teste:

```powershell
$env:TEST_POSTGRES_URL = "postgresql+psycopg://<USUARIO_MIGRACAO>:<SENHA>@localhost:<PORTA>/<BANCO_DESCARTAVEL_test>"
python -m pytest -q tests/test_migrations.py
Remove-Item Env:TEST_POSTGRES_URL
```

O teste recusa tabelas/views residuais ou uma revisão Alembic já aplicada antes de fazer alterações; uma tabela `alembic_version` vazia após um ciclo bem-sucedido é permitida. Se houver resíduos, recrie **somente o banco descartável** ou limpe seus objetos manualmente antes de repetir. Não há exclusão automática de objetos anteriores. A limpeza em `finally` reverte as migrações iniciadas pelo próprio teste, inclusive após falha de verificação.

Depois do upgrade, o teste compara o esquema com todos os modelos registrados usando `produce_migrations`, incluindo tipos e defaults de servidor. Uma diferença falha o gate da CI. Autogenerate tem limites (por exemplo, alterações de CHECK/enum não nativo); o teste separado de round-trip verifica os quatro nomes persistidos do enum. Também são verificados inserção SQL sem timestamps, upgrade/downgrade preservando ordens existentes e persistência em nova sessão.

`created_at` e `updated_at` têm defaults de inserção no servidor, adicionados por uma nova revisão Alembic. Os defaults e o `onupdate` da aplicação foram preservados. Um `UPDATE` SQL direto continua responsável por informar `updated_at`: não há trigger automática nesta entrega. O enum continua armazenado como `PENDING`, `IN_PROGRESS`, `COMPLETED` e `CANCELLED`; seus valores na API permanecem em português.

## Limites atuais

As ordens de inspeção usam a tabela operacional e já têm persistência básica. Regras completas de autorização, ciclo de estados, histórico e repetição ainda dependem de decisão e implementação. A carga da Gold não lê nem insere linhas e não oferece idempotência. Executar `python scripts/load_gold.py` informa que a carga ainda não está implementada; a presença de CSVs não significa que foram carregados.
