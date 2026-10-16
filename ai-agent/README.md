# Agente de IA

Este diretório contém o serviço FastAPI isolado que será a base do agente Text-to-SQL e da lógica de insights. Há um adaptador Gemini isolado e opcional, desativado por padrão; ainda não há integração de evidências com Gold, backend do portal ou interface. Contrato e critérios: [guia do serviço](../docs/services/ai-agent.md) e [PRD](../docs/PRD.md).

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

Para preparar o adaptador Gemini opcional, instale `python -m pip install -e ".[dev,gemini]"` e configure no `.env` `GENAI_MODEL_PROVIDER=gemini`, `GENAI_GEMINI_MODEL=gemini-3.5-flash-lite` e `GENAI_GEMINI_API_KEY`. Para tarefas que precisem de mais capacidade geral, selecione `gemini-3.6-flash` em `GENAI_GEMINI_MODEL`. O identificador `gemini-3.5-flash` foi descontinuado e é redirecionado pelo provedor para 3.6 Flash. O timeout pode ser ajustado em `GENAI_MODEL_TIMEOUT_MS` (milissegundos). O padrão do provedor continua `unavailable`; a chave não é necessária para iniciar a aplicação nem para executar os testes. Neste checkpoint, a configuração e a factory do adaptador estão preparadas, mas o `create_app` ainda usa `UnavailableModelAdapter`; conectar o provedor ao fluxo HTTP ficará para o checkpoint 2.5. O adaptador só recebe pergunta, contexto limitado e evidências fornecidas; não tem ferramentas para consultar ou alterar o banco.

Gemini é uma implementação opcional baseada na recomendação do case, não uma decisão definitiva de provedor da equipe. O módulo continua com interfaces substituíveis. O teste automatizado usa cliente falso e não faz chamadas de rede ou faturáveis.

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
