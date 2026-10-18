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

Para preparar o adaptador Gemini opcional, instale `python -m pip install -e ".[dev,gemini]"` e configure no `.env` `GENAI_MODEL_PROVIDER=gemini`, `GENAI_GEMINI_MODEL=gemini-3.5-flash-lite` e `GENAI_GEMINI_API_KEY`. Para tarefas que precisem de mais capacidade geral, selecione `gemini-3.6-flash` em `GENAI_GEMINI_MODEL`. O identificador `gemini-3.5-flash` foi descontinuado e é redirecionado pelo provedor para 3.6 Flash. O timeout pode ser ajustado em `GENAI_MODEL_TIMEOUT_MS` (milissegundos). O padrão do provedor continua `unavailable`; a chave não é necessária para iniciar a aplicação nem para executar os testes. Quando configurado como `gemini`, o `create_app` seleciona o adaptador pela factory e o usa nos endpoints de perguntas e insights. O adaptador só recebe pergunta/contexto e evidências fornecidas; não tem ferramentas para consultar ou alterar o banco.

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
python -m tests.test_genai_regression --output reports/synthetic-regression-report.json
```

O serviço expõe a documentação OpenAPI em `http://127.0.0.1:8001/docs`. A aplicação sobe sem banco de dados e sem chave de provedor; o acesso a Gold real será integrado em etapas posteriores.

## Contratos HTTP do serviço

- `GET /health` informa somente que o processo está ativo.
- `GET /api/v1/capabilities` descreve a versão e a disponibilidade do contrato de perguntas, sem expor configuração interna.
- `POST /api/v1/questions` recebe `contract_version` (opcional; padrão `v1`), `question` e até três mensagens de contexto (`role` `user` ou `assistant`), cada uma limitada a 1.000 caracteres. Versão nula ou não suportada é rejeitada.
- `POST /api/v1/insights` recebe um objeto `screen` com métrica, unidade, período, filtros, observações numéricas, referência e limitações. Nesta etapa, `reference.is_demo` precisa ser `true`.

Exemplo de pergunta no PowerShell:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/api/v1/questions `
  -ContentType 'application/json' `
  -Body '{"contract_version":"v1","question":"Qual foi o consumo?"}'
```

A resposta dos endpoints de perguntas e insights segue o envelope público `v1`: `contract_version`, `status`, `answer` ou `message`, `evidence`, `limitations`, `error`, `correlation_id` e `audit_reference`. `answered` usa `answer` em perguntas ou `hypothesis` em insights; os outros estados usam `message`, sem misturar os campos. A resposta também envia o `correlation_id` no cabeçalho `X-Correlation-ID`. O identificador é gerado pelo serviço e serve para localizar a requisição; não representa uma trilha de auditoria. `audit_reference` permanece `null` até existir auditoria durável. O contexto normalizado de uma pergunta (`analysis_context`) também fica `null` enquanto a fonte não informar período, unidade e filtros efetivamente aplicados. Em insights, o contexto recebido fica separado das observações e da hipótese, mas ainda não é autenticado nem autorizado pelo serviço.

Recusas e falhas incluem `error.code` e `error.retryable`. Os erros de entrada HTTP usam status 422 e o mesmo envelope v1, com mensagem estável sem ecoar valores inválidos. Falhas inesperadas usam status 500 e mensagem genérica. A API não devolve linhas tabulares nem oferece paginação; perguntas retornam texto e referências. O contexto de insight aceita até 20 filtros, 20 observações e 20 limitações; limites excedidos são rejeitados, nunca truncados silenciosamente. Evidências internas aceitam até 100 registros, mas esse conjunto não é serializado na resposta pública. Cada campo de texto e lista tem limite no schema; não existe ainda um limite agregado de bytes no serviço.

O fluxo padrão usa ferramentas e fixtures sintéticas; se não houver adaptador de modelo configurado para gerar a resposta, retorna indisponibilidade controlada. As referências sintéticas vêm com `is_demo: true`.

Exemplo de erro de contrato:

```json
{
  "contract_version": "v1",
  "status": "error",
  "message": "A solicitação não segue o contrato esperado.",
  "error": {"code": "invalid_request", "retryable": false},
  "correlation_id": "0123456789abcdef0123456789abcdef",
  "audit_reference": null
}
```

Exemplo de resposta sintética a uma pergunta:

```json
{
  "contract_version": "v1",
  "status": "answered",
  "answer": "Demonstração sintética: Resposta de demonstração.",
  "message": null,
  "evidence": [
    {
      "source": "synthetic_fixture:consumption_demo",
      "description": "Medida artificial sem vínculo com uma unidade consumidora real.",
      "is_demo": true
    }
  ],
  "limitations": ["Valor inventado; não representa leitura ou consumo da V-Energy."],
  "analysis_context": null,
  "error": null,
  "correlation_id": "0123456789abcdef0123456789abcdef",
  "audit_reference": null
}
```

O endpoint de insights devolve `observation` com os valores recebidos e `hypothesis` em campo separado. A hipótese é gerada pelo adaptador de modelo configurado; números que não aparecem no contexto são recusados. O serviço não persiste o contexto nem confirma que o backend está autorizado a enviar aqueles filtros. Um consumidor futuro deverá transmitir contexto já validado e autorizado pela sua própria camada.

O relatório versionado de regressão sintética cobre os fluxos de perguntas e insights. A versão atual do conjunto é `2.0.0`; a saída contém status por caso, resumo, escopo e limitações e é determinística para o mesmo código e fixtures. O adaptador usado é fixo e não chama o Gemini.

No endpoint de perguntas, o consumidor pode reenviar até três turnos anteriores no campo `context`; o serviço não guarda histórico entre chamadas. Para uma continuação reconhecida, o interpretador herda a intenção da pergunta completa mais recente da pessoa usuária e substitui filtros informados na pergunta atual. Se a mensagem mais recente da pessoa usuária for ambígua, o serviço pede esclarecimento em vez de recuperar uma intenção mais antiga. A interpretação é lexical e limitada ao vocabulário configurado; não equivale a memória de conversa nem a resolução geral de linguagem. Como o serviço não autentica a origem dos turnos, o safety gate verifica tanto mensagens `user` quanto `assistant` do contexto antes de chamar ferramenta ou modelo.

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
