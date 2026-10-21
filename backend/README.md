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

## Contratos analíticos de desenvolvimento

`ANALYTICS_SOURCE` aceita `unavailable` (padrão, retorna HTTP 503 nas rotas analíticas) ou `synthetic`. Para experimentar os contratos sem conectar ao PostgreSQL, configure a opção `synthetic` no ambiente antes de iniciar a API. Um valor desconhecido impede a inicialização. `/api/v1/kpis`, `/revenue`, `/ucs`, `/ucs/{uc_id}`, `/inspections/queue` e `/operations/continuity` usam a interface `get_analytics_repository`; filas de inspeção continuam separadas das ordens operacionais persistidas.

A fixture determinística declara faturamento BRL 182, pagamentos BRL 170, energia faturada de 170 kWh e energia medida conhecida de 407 kWh no período janeiro–fevereiro de 2025. Faturado e pago usam fatos de fatura; energia medida e faturada têm campos separados. O perfil de UC traz uma referência e um nome fictícios. Vencimento, pagamento e situação de cada fatura são campos propostos, podendo ser nulos quando desconhecidos. A decomposição preço-volume endpoint e as taxas de continuidade são demonstrativas, versionadas e não homologadas pela Gold. A fixture inclui leitura zero válida, leitura ausente, UC sem fatura, medidor retirado, alimentador sem denominador e o AL-02 distribuído entre Olinda e Paulista; limitações e nulidade aparecem na resposta.

Exemplo PowerShell para iniciar a API em modo demonstrativo:

```powershell
$env:ANALYTICS_SOURCE = "synthetic"
uvicorn app.main:app --reload --port 8000
```

## Verificações

### Imagem Docker

O backend usa a base `dhi.io/python:3.12-alpine3.24-dev`, mantida pela Docker Hardened Images. A base verificada em 20/10/2026 contém Python 3.12.15 e zlib `1.3.2-r1`, já corrigida para CVE-2026-85091; não é necessário atualizar essa biblioteca no Dockerfile. A decisão e seus limites estão na [ADR-0003](../docs/decisions/0003-backend-python312-alpine.md).

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

## Limites atuais

As ordens de inspeção usam a tabela operacional e já têm persistência básica. Regras completas de autorização, ciclo de estados, histórico e repetição ainda dependem de decisão e implementação. A carga da Gold não lê nem insere linhas e não oferece idempotência. Executar `python scripts/load_gold.py` informa que a carga ainda não está implementada; a presença de CSVs não significa que foram carregados.
