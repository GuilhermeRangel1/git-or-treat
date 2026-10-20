# Backend — V-Energy Grid 360

API FastAPI com conexão SQLAlchemy, migração Alembic e persistência inicial das ordens de inspeção. As rotas de indicadores, receita, UC, fila, continuidade e IA ainda são placeholders; elas não consultam a Gold. Os requisitos de produto permanecem pendentes de implementação e reconciliação com dados Gold.

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

## Verificações

```powershell
python -m pytest -q
python -m compileall -q app tests scripts
```

Os testes locais usam SQLite e uma URL temporária em `tmp_path` para o ciclo Alembic. O teste PostgreSQL só é ativado quando `TEST_POSTGRES_URL` aponta explicitamente para um banco descartável cujo nome termina em `_test`. O CI fornece um PostgreSQL efêmero para esse teste; não use uma URL de produção ou um banco pessoal nessa variável.

## Limites atuais

As ordens de inspeção usam a tabela operacional e já têm persistência básica. Regras completas de autorização, ciclo de estados, histórico e repetição ainda dependem de decisão e implementação. A carga da Gold não lê nem insere linhas e não oferece idempotência. Executar `python scripts/load_gold.py` informa que a carga ainda não está implementada; a presença de CSVs não significa que foram carregados.
