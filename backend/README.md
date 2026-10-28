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
├── scripts/load_gold.py   # Carga transacional dos sete CSVs Gold v1
├── tests/                 # Testes HTTP, ORM e migrações
└── requirements.txt       # Dependências Python
```

O fluxo das ordens passa pelas rotas HTTP, validação dos schemas, serviço de domínio, sessão SQLAlchemy e modelos. `app.db.base.Base` registra os metadados sem criar engine; `app.core.database` configura o engine, pooling, `SessionLocal` e `get_db`. `app.core.database.Base` continua disponível para compatibilidade.

## Execução local

Use Python 3.12, igual ao Docker e ao CI. Na pasta `backend`, crie e ative um ambiente virtual, instale as dependências e configure `DATABASE_URL` com a URL do seu PostgreSQL local em `.env`:

Confira `python --version` antes de criar o ambiente: deve indicar `3.12.x`. Um venv criado com outra versão continua usando o interpretador original mesmo depois de atualizar o repositório.

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

## Perguntas ao serviço GenAI

`POST /api/v1/ai/questions` valida o contrato v1 e encaminha a pergunta ao serviço GenAI. Configure `AI_AGENT_BASE_URL` e `AI_AGENT_SERVICE_API_TOKEN` no Backend e o mesmo token em `GENAI_SERVICE_API_TOKEN` no GenAI. O token autentica somente a comunicação entre serviços; não identifica a pessoa usuária nem concede acesso à Gold. O contrato e os códigos de erro estão em [genai-chat-api.md](../docs/contracts/genai-chat-api.md).

No Docker Compose, o portal chama essa rota e o serviço GenAI fica acessível ao Backend pela rede interna. A conversa usa cenários artificiais e permanece em memória no navegador; não consulta Gold nem persiste histórico. Veja as variáveis locais em `.env.example` e no README da GenAI.

## Contratos analíticos de desenvolvimento

`ANALYTICS_SOURCE` aceita `unavailable` (padrão, retorna HTTP 503 nas rotas analíticas) ou `synthetic`. Para experimentar os contratos sem conectar ao PostgreSQL, configure a opção `synthetic` no ambiente antes de iniciar a API. Um valor desconhecido impede a inicialização. `/api/v1/kpis`, `/revenue`, `/ucs`, `/ucs/{uc_id}`, `/inspections/queue` e `/operations/continuity` usam a interface `get_analytics_repository`; filas de inspeção continuam separadas das ordens operacionais persistidas.

A fixture sintética `dev03-v1` cobre explicitamente janeiro e fevereiro de 2025 para faturamento e energia faturada; `/api/v1/revenue` publica o contrato 1.1.0 e inclui oito UCs distintas faturadas em cada extremo, com Recife e Olinda, mais de um bairro e as classes Comercial e Residencial nos dois meses. No período, os controles são BRL 1.727 faturados, BRL 1.710 pagos com valor conhecido, 1.585 kWh faturados e 407 kWh medidos com valor conhecido. Receita por competência e recorte usa apenas fatos de fatura; leituras e pagamento permanecem grandezas separadas. A cobertura das leituras medidas é parcial e não substitui cobertura financeira. O perfil de UC traz referência e nome fictícios; vencimento, pagamento e situação permanecem campos sintéticos. A decomposição preço-volume e as taxas de continuidade são demonstrativas, versionadas e não homologadas pela Gold. A fixture mantém leitura zero válida, leitura ausente, UC sem fatura, medidor retirado, alimentador sem denominador e o AL-02 distribuído entre Olinda e Paulista; limitações e nulidade aparecem na resposta.

Exemplo PowerShell para iniciar a API em modo demonstrativo:

```powershell
$env:ANALYTICS_SOURCE = "synthetic"
uvicorn app.main:app --reload --port 8000
```

## Acesso às ordens e limites de entrada

DEV-06: [contrato de criação pela fila e consulta paginada](../docs/contracts/inspection-orders-dev06.md). Aplicar `alembic upgrade head` antes de iniciar sobre banco existente. O portal básico usa `POST /inspections/queue/{uc_id}/orders` com `Idempotency-Key` e versões do detalhe; consulta por `/inspections/orders/search` e `/inspections/orders/{id}`, com filtros de estado, UC, prioridade e presença de resultado (`has_result`). O prefixo completo é `/api/v1`. O proxy Vite não injeta credenciais; a tela básica funciona sem login no modo demo sintético local (`APP_ENV=development`, `ANALYTICS_SOURCE=synthetic`, `ORDERS_AUTH_MODE=demo`). Login fica para uma etapa futura. Veja o [guia de entrega para o frontend](../docs/contracts/inspection-auth-handoff.md).

A revisão `a6d060000002` garante uma ordem ativa por UC, incluindo criações manuais e fontes/versões diferentes. Se houver duplicidades ativas antigas, o upgrade interrompe para reconciliação manual e não cancela registros. Reenvios confirmados da fila funcionam mesmo com a fonte analítica indisponível; conflitos mantêm a mensagem em `detail` e incluem código e ID em `error` para integração.

Na demo local sintética, as rotas operacionais dispensam login com `ORDERS_AUTH_MODE=demo`; esse modo concede leitura/escrita ao operador local e não identifica uma pessoa. Nos modos service/oidc, exigem autenticação. Em produção, configurar `APP_ENV=production`, `ORDERS_AUTH_MODE=oidc`, `OIDC_ISSUER`, `OIDC_AUDIENCE` e `OIDC_JWKS_URL`: assinatura RS256, subject individual, validade e scopes de leitura/escrita são verificados. `GET /api/v1/inspections/access` retorna a identidade opaca e permissões para a UI. O processo recusa produção com token compartilhado e OIDC configurado em paralelo com credenciais de serviço.

Em desenvolvimento por CLI/Swagger, `ORDERS_AUTH_MODE=service` mantém `ORDERS_READ_TOKEN` e/ou `ORDERS_WRITE_TOKEN`, aleatórios/distintos com pelo menos 32 caracteres. Leitor consulta; escritor consulta/cria/altera. O esquema Bearer `OrdersServiceToken` do Swagger mantém o nome por compatibilidade e também aceita o JWT individual no modo OIDC. Nunca colocar credenciais de serviço em `VITE_*`, URLs, commits ou frontend. Sem configuração/autorização, as ordens permanecem fechadas. Configurar o provedor real e HTTPS do ingresso antes da implantação compartilhada.

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

As ordens usam dados operacionais separados, controle de acesso DEV-06, histórico transacional, resultado, cancelamento identificado e versão DEV-07. Contratos, exemplos, migrações e limites no [guia DEV-07](../docs/contracts/inspection-lifecycle-dev07.md). A interface foi integrada e aprovada em 25/10; a reexecução com Python 3.12.15/container e PostgreSQL 16.13 descartável passou nos 320 testes, pip check e compileall. Consulte as [evidências e limites](../docs/plans/2026-10-25-dev07-evidencias.md). A carga Gold v1 está implementada: após `alembic upgrade head`, execute `python scripts/load_gold.py --directory data/gold/v1 --batch v1`. Ela valida e substitui as sete tabelas em uma transação; repetição idêntica não reinsere dados. Isso não ativa a fonte da API. Veja o [contrato provisório, organização e limites](../docs/contracts/gold-csv-v1.md).


## Carga sintética e recuperação — DEV-12

A revisão `goldv1000002` acrescenta versão explícita do esquema ao lote atual e histórico persistente em `gold_carga_tentativas`. Use `--schema-version gold-csv-v1`; versões desconhecidas são rejeitadas. O CLI retorna o UUID de cada tentativa e mantém erros sem conteúdo dos registros. Uma falha reverte a publicação; registrar sucesso e publicar são atômicos.

Para verificar sem dataset real, `venv/Scripts/python.exe scripts/generate_gold_sample.py --directory ../work/dev12-lote-01` cria sete CSVs inteiramente artificiais em um diretório novo. O controle independente é duas UCs mensais, 30 kWh e R$ 25,50. O [runbook DEV-12](../docs/contracts/gold-load-dev12.md) inclui banco isolado, execução/repetição, inspeção da auditoria e recuperação de cargas inválidas/interrompidas.

Os testes de carga usam `TEST_GOLD_POSTGRES_URL`, separada da `TEST_POSTGRES_URL` de migrações. Ambas devem apontar para bancos descartáveis vazios `*_test`, com usuário sem superusuário. A CI fornece as duas URLs ao runner e ao contêiner. Sem configuração, variantes PostgreSQL são ignoradas.

## Contrato de alterações das ordens — DEV-07

Todas as mutações exigem `version` inteiro positivo retornado pelo GET. Sem versão ou com tipo inválido: 422; versão obsoleta: 409 `version_conflict`, sem gravar ordem/histórico. Após 409, consulte novamente e permita que a pessoa revise a alteração. Não reenvie automaticamente a intenção com uma versão nova.

Cancelamento só é aceito por `POST /api/v1/inspections/orders/{id}/cancel`, com `confirmed_order_id` igual ao ID da rota e a versão atual. `PATCH` com CANCELADA retorna 422. Os exemplos do Swagger mostram início, resultado, cancelamento e conflito. Clientes DEV-06 precisam adaptar as alterações; criação/consulta não mudam. Não há nova migração de banco nesta revisão; reinicie o backend para carregar as rotas/schemas atualizados.
