# Backend - V-Energy Grid 360

Serviço FastAPI que sustenta as jornadas web (WEB-01 a WEB-11) e o acesso controlado da IA (IA-01 a IA-06) conforme o [PRD](../docs/PRD.md) e o [guia do serviço](../docs/services/backend.md).

## Estrutura de Pastas

```text
backend/
├── app/
│   ├── api/v1/endpoints/  # Rotas de negócio (health, kpis, revenue, ucs, inspections, operations, ai)
│   ├── core/              # Configurações (Pydantic Settings) e conexão com banco (SQLAlchemy)
│   ├── models/            # Modelos ORM divididos em analíticos (Gold) e operacionais (Ordens)
│   ├── schemas/           # Schemas Pydantic e envelopes conceituais de resposta
│   ├── services/          # Regras de negócio e consultas analíticas
│   └── main.py            # Instância principal da aplicação FastAPI
├── data/
│   ├── gold/              # Diretório dos CSVs (mocks agora, exportados da Gold depois)
│   └── mocks/             # Mocks de apoio adicionais
├── scripts/
│   └── load_gold.py       # Script idempotente para carga dos CSVs no banco
├── tests/                 # Testes automatizados
├── requirements.txt       # Dependências Python
└── .env.example           # Modelo de variáveis de ambiente
```

## Como Executar

1. **Ative o ambiente virtual:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. **Copie o `.env.example` para `.env` e configure o PostgreSQL:**
   ```powershell
   cp .env.example .env
   ```
   Ajuste `DATABASE_URL` no `.env` com seu usuário, senha e porta do PostgreSQL:
   ```env
   DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/v_energy"
   ```

3. **Execute as migrações com o Alembic:**
   ```powershell
   alembic upgrade head
   ```
   *(Para gerar novas migrações após alterar modelos: `alembic revision --autogenerate -m "descricao"`)*

4. **Inicie o servidor de desenvolvimento:**
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```

5. **Acesse a documentação interativa:**
   - Swagger UI: `http://localhost:8000/api/v1/docs`
   - ReDoc: `http://localhost:8000/api/v1/redoc`

6. **Executar testes automatizados:**
   ```powershell
   pytest
   ```

7. **Carga de dados analíticos (Gold / Mocks):**
   - Coloque seus arquivos `.csv` em `backend/data/gold/`
   - Execute o script de ingestão:
     ```powershell
     python scripts/load_gold.py
     ```

