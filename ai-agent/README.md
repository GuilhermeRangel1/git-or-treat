# Agente de IA

Este diretório contém o serviço FastAPI isolado que será a base do agente Text-to-SQL e da lógica de insights. As rotas e os contratos HTTP iniciais estão disponíveis; ainda não há integração com banco Gold, provedor de IA, backend do portal ou interface. Contrato e critérios: [guia do serviço](../docs/services/ai-agent.md) e [PRD](../docs/PRD.md).

As próximas etapas dependem da integração das fontes analíticas e do provedor de IA.

## Preparar o ambiente local

No PowerShell, a partir da raiz do repositório:

```powershell
Set-Location ai-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

O arquivo `.env` é local e ignorado pelo Git. Não adicione chaves ou credenciais ao `.env.example`.

## Executar e verificar

Execute os comandos dentro de `ai-agent/`:

```powershell
python -m uvicorn app.main:app --reload --port 8001
```

Em outro terminal, também dentro de `ai-agent/`:

```powershell
python -m pytest
python -m ruff check .
```

O serviço expõe a documentação OpenAPI em `http://127.0.0.1:8001/docs`. Nesta etapa, a aplicação sobe sem banco de dados e sem chave de provedor; a lógica analítica será adicionada em etapas posteriores.

## Contratos HTTP da etapa inicial

- `GET /health` informa somente que o processo está ativo.
- `GET /api/v1/capabilities` descreve a versão e a disponibilidade do contrato de perguntas, sem expor configuração interna.
- `POST /api/v1/questions` recebe `question` e até três mensagens de contexto (`role` `user` ou `assistant`), cada uma limitada a 1.000 caracteres.

Exemplo de pergunta no PowerShell:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/api/v1/questions `
  -ContentType 'application/json' `
  -Body '{"question":"Qual foi o consumo?"}'
```

A resposta inclui `status`, `answer`, `message` e `evidence`. Os estados são `answered`, `needs_clarification`, `refused`, `no_evidence` e `recoverable_error`. Sem adaptador de evidências configurado, a API responde `no_evidence`; não consulta um provedor externo nem inventa números. As fixtures de teste são sintéticas e vêm marcadas como demonstração.
