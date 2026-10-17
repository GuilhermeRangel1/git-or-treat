# Agente de IA

Este diretório contém o serviço FastAPI isolado que serve de base ao agente analítico e aos insights. Há endpoints para perguntas e para insights com contexto de tela estruturado; o adaptador Gemini é opcional e fica desativado por padrão. As evidências ainda são sintéticas: não há integração com Gold, backend do portal ou interface. Contrato e critérios: [guia do serviço](../docs/services/ai-agent.md) e [PRD](../docs/PRD.md).

Os endpoints podem ser exercitados localmente com adaptadores simulados. Resultados sintéticos demonstram fluxo e contrato, não números reais nem requisitos concluídos no PRD.

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
- `POST /api/v1/insights` recebe um objeto `screen` com métrica, unidade, período, filtros, observações numéricas, referência e limitações. Nesta etapa, `reference.is_demo` precisa ser `true`.

Exemplo de pergunta no PowerShell:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/api/v1/questions `
  -ContentType 'application/json' `
  -Body '{"question":"Qual foi o consumo?"}'
```

A resposta inclui `status`, `answer`, `message` e `evidence`. Os estados são `answered`, `needs_clarification`, `refused`, `no_evidence` e `recoverable_error`. O fluxo padrão usa ferramentas e fixtures sintéticas; se não houver adaptador de modelo configurado para gerar a resposta, retorna indisponibilidade controlada. As fixtures vêm marcadas como demonstração.

O endpoint de insights devolve `observation` com os valores recebidos e `hypothesis` em campo separado. A hipótese é gerada pelo adaptador de modelo configurado; números que não aparecem no contexto são recusados. O serviço não persiste o contexto nem confirma que o backend está autorizado a enviar aqueles filtros. Um consumidor futuro deverá transmitir contexto já validado e autorizado pela sua própria camada.

Exemplo de payload exclusivamente demonstrativo:

```json
{
  "screen": {
    "metric": "consumo demonstrativo",
    "unit": "kWh fictícios",
    "period": {
      "start": "2025-01-01",
      "end": "2025-03-31",
      "granularity": "month"
    },
    "filters": {"classe": "residencial", "municipio": "Exemplo"},
    "observations": [{"label": "consumo total", "value": 420}],
    "reference": {
      "source": "synthetic_screen:consumption",
      "description": "Resultado artificial para teste local.",
      "is_demo": true
    },
    "limitations": ["Valor fictício, sem vínculo com a V-Energy."]
  }
}
```
