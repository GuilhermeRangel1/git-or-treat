# Agente de IA

Este diretório contém o serviço FastAPI isolado que serve de base ao agente analítico e aos insights. Há endpoints para perguntas e para insights com contexto de tela estruturado; os adaptadores Gemini e Groq são opcionais e ficam desativados por padrão. As evidências ainda são sintéticas: não há integração com Gold, backend do portal ou interface. Contrato e critérios: [guia do serviço](../docs/services/ai-agent.md) e [PRD](../docs/PRD.md).

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

Por padrão, o serviço inicia sem identidade autorizada. Para testar as perguntas e insights com fixtures sintéticas, defina **ambas** `GENAI_ENVIRONMENT=local` e `GENAI_ENABLE_DEMO_ACCESS=true` no `.env` local. O modo demonstrativo concede acesso fictício às métricas não pessoais do perfil; não o habilite numa implantação com Gold ou dados reais. `GET /health` e a documentação OpenAPI funcionam sem essa opção.

Para preparar o adaptador Gemini opcional, instale `python -m pip install -e ".[dev,gemini]"` e configure no `.env` `GENAI_MODEL_PROVIDER=gemini`, `GENAI_GEMINI_MODEL=gemini-3.5-flash-lite` e `GENAI_GEMINI_API_KEY`. Para tarefas que precisem de mais capacidade geral, selecione `gemini-3.6-flash` em `GENAI_GEMINI_MODEL`. O identificador `gemini-3.5-flash` foi descontinuado e é redirecionado pelo provedor para 3.6 Flash. O timeout pode ser ajustado em `GENAI_MODEL_TIMEOUT_MS` (milissegundos). O padrão do provedor continua `unavailable`; a chave não é necessária para iniciar a aplicação nem para executar os testes. Quando configurado como `gemini`, o `create_app` seleciona o adaptador pela factory e o usa nos endpoints de perguntas e insights. O adaptador só recebe pergunta/contexto e evidências fornecidas; não tem ferramentas para consultar ou alterar o banco.

Gemini é uma implementação opcional baseada na recomendação do case, não uma decisão definitiva de provedor da equipe. O módulo continua com interfaces substituíveis. O teste automatizado usa cliente falso e não faz chamadas de rede ou faturáveis.

### Groq e fallback entre provedores

O adaptador Groq usa a API de chat compatível com OpenAI via `httpx`, em JSON mode, com o esquema da resposta no prompt de sistema. Instale o extra com `python -m pip install -e ".[dev,groq]"` (ou `".[dev,gemini,groq]"` para usar os dois provedores) e configure no `.env`:

| Variável | Valores aceitos | Padrão |
| --- | --- | --- |
| `GENAI_MODEL_PROVIDER` | `unavailable`, `gemini` ou `groq` | `unavailable` |
| `GENAI_GROQ_API_KEY` | chave do Groq; obrigatória quando `groq` está na cadeia | vazia |
| `GENAI_GROQ_MODEL` | ID de modelo do Groq | `openai/gpt-oss-120b` |
| `GENAI_MODEL_FALLBACK_PROVIDERS` | `gemini` e/ou `groq`, separados por vírgula ou como lista JSON | vazia |

O modelo padrão do Groq passou em uma execução do smoke test real em 20/10/2026, com dados sintéticos. O Groq remove modelos com o tempo: antes de usar, confira o nome do modelo na lista da sua conta e, se preciso, troque-o com `GENAI_GROQ_MODEL`.

Exemplo com Gemini primeiro e Groq depois:

```dotenv
GENAI_MODEL_PROVIDER=gemini
GENAI_GEMINI_API_KEY=<sua chave Gemini>
GENAI_GEMINI_FALLBACK_MODELS=gemini-3.6-flash
GENAI_MODEL_FALLBACK_PROVIDERS=groq
GENAI_GROQ_API_KEY=<sua chave Groq>
```

A cadeia resultante é `gemini-3.5-flash-lite` → `gemini-3.6-flash` → Groq. Os modelos de `GENAI_GEMINI_FALLBACK_MODELS` só entram quando o Gemini é o provedor principal; como fallback, o Gemini usa apenas `GENAI_GEMINI_MODEL`. `GENAI_MODEL_FALLBACK_PROVIDERS` não pode repetir provedores nem incluir o principal, e cada provedor da cadeia exige sua chave. O total de modelos, somando todos os provedores, precisa caber em `GENAI_MODEL_MAX_CALLS` (padrão 3); caso contrário, a factory recusa a configuração na inicialização.

O Groq segue a mesma classificação de erros do Gemini: 429, 5xx, timeout e falha de rede são indisponibilidade transitória e acionam o próximo provedor; os demais 4xx são rejeição definitiva e encerram a cadeia; resposta vazia, JSON inválido ou fora do esquema é resposta inválida. As mensagens são genéricas e não incluem chave, corpo da resposta nem pergunta. Com cache ligado, a chave do cache também inclui a ordem dos provedores, os modelos (inclusive o do Groq) e o digest do prompt de sistema, para que configurações diferentes nunca compartilhem respostas. Os testes automatizados simulam o Groq com `httpx.MockTransport` e não fazem chamadas de rede.

O serviço aplica orçamento total por solicitação e prazos próprios para fonte e modelo, inclusive ao esperar uma vaga de concorrência. Os valores e limites de chamadas podem ser ajustados pelas variáveis comentadas no `.env.example`. Prazo ou limite esgotado produz `limit_exceeded`, sem nova tentativa automática. Uma cadeia de fallback injetada precisa caber em `GENAI_MODEL_MAX_CALLS`, inclusive quando encapsulada pelo cache; a composição recusa cadeias maiores. O fallback só avança após indisponibilidade transitória; erro definitivo ou resposta inválida encerra a cadeia. O cache opcional usa identidade, permissões, plano, catálogo, evidência, prompt e modelos na chave; sem escopo autorizado ele é ignorado. Insights demonstrativos com observações enviadas pelo navegador não entram no cache.

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

### Smoke test real do Groq (opt-in)

`tests/live/test_groq_live_smoke.py` envia uma pergunta e evidência sintéticas do perfil Grid 360 ao Groq real e valida só o contrato: a saída é um `GeneratedAnswer` válido, os `observation_ids` existem na evidência enviada e o provedor não falhou. Ele é pulado no `pytest` padrão e no CI, e só roda com as duas variáveis definidas no ambiente do terminal (o teste não lê o `.env`):

```powershell
$env:GENAI_RUN_LIVE_SMOKE = "1"
$env:GENAI_GROQ_API_KEY = "<sua chave Groq>"
# Opcional: $env:GENAI_GROQ_MODEL = "<outro modelo>"
python -m pytest -m live -rs tests/live
Remove-Item Env:GENAI_RUN_LIVE_SMOKE, Env:GENAI_GROQ_API_KEY
```

A chamada é faturável conforme o plano da conta Groq. Use só dados sintéticos.

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

A resposta dos endpoints de perguntas e insights segue o envelope público `v1`: `contract_version`, `status`, `answer` ou `message`, `evidence`, `limitations`, `error`, `correlation_id` e `audit_reference`. `answered` usa `answer` em perguntas ou `hypothesis` em insights; os outros estados usam `message`, sem misturar os campos. A resposta também envia o `correlation_id` no cabeçalho `X-Correlation-ID`. O identificador é gerado pelo serviço e serve para localizar a requisição; não representa uma trilha de auditoria. `audit_reference` permanece `null` até existir auditoria durável. Em perguntas respondidas, `analysis_context` mostra o recorte lógico que a fonte declarou ter aplicado; a janela ainda pode ser uma frase do catálogo demonstrativo. Em insights, o contexto recebido fica separado das observações e da hipótese. O núcleo confere perfil, fonte e escopo de leitura do contexto de acesso; a API local usa identidade fictícia. Métrica e filtros da tela sintética ainda não são ligados a um plano Gold autorizado.

Recusas e falhas incluem `error.code` e `error.retryable`. Os erros de entrada HTTP usam status 422 e o mesmo envelope v1, com mensagem estável sem ecoar valores inválidos. Falhas inesperadas usam status 500 e mensagem genérica. A API não devolve linhas tabulares nem oferece paginação; perguntas retornam texto e referências. O contexto de insight aceita até 20 filtros, 20 observações e 20 limitações; limites excedidos são rejeitados, nunca truncados silenciosamente. Evidências internas aceitam por padrão até 100 registros e 16 KiB após serialização, com limites configuráveis; esse conjunto não é serializado na resposta pública. O ingresso HTTP ainda não tem um teto agregado em bytes.

O fluxo padrão usa ferramentas e fixtures sintéticas; se não houver adaptador de modelo configurado para gerar a resposta, retorna indisponibilidade controlada. As referências sintéticas vêm com `is_demo: true`.

O interpretador recebe um `DomainProfile` pela raiz de composição (`create_app(domain_profile=...)`). A configuração atual, `GRID360_DEMO_PROFILE`, mantém o vocabulário, métricas, dimensões e períodos de demonstração fora do mecanismo genérico. Os IDs são lógicos; unidades, granularidades, aliases, operadores e sensibilidades do catálogo são demonstrativos e não correspondem a uma definição Gold aprovada.

`app/agent/composition.py` monta os fluxos de pergunta e insight com o mesmo perfil, política, fonte, modelo, controlador de execução e destino opcional de eventos. `create_app` injeta as implementações locais; testes e futuros integradores podem fornecer `evidence_source`, `source_id`, `model_adapter`, `access_policy` e `event_sink` sem alterar os orquestradores. A fonte e sua política devem usar o mesmo ID lógico. As instruções genéricas de geração ficam em `app/generation/prompts.py`; vocabulário e exemplos de negócio continuam no perfil. O modelo apenas seleciona IDs de observações da evidência aprovada, e o serviço valida a seleção e monta a resposta pública. Eventos por estágio têm correlação e campos controlados; o destino padrão descarta os eventos, e auditoria durável ainda não está disponível.

O [guia de reuso e conformidade](../docs/services/ai-agent-reuse.md) mostra como compor outro perfil e fonte pelo contrato. A suíte `python -m pytest -q tests/test_reusable_core.py tests/test_import_boundaries.py` exercita Grid 360 e clima com dados artificiais, inclusive isolamento de cache, escopos e eventos.

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
  "answer": "Demonstração sintética: energy.consumption — período de demonstração: 420 unidades fictícias.",
  "message": null,
  "evidence": [
    {
      "source": "synthetic_fixture:consumption_demo",
      "description": "Evidência agregada validada pelo serviço.",
      "is_demo": true
    }
  ],
  "limitations": ["Valor inventado; não representa leitura, consumo ou unidade consumidora da V-Energy."],
  "analysis_context": {"metric": "energy.consumption", "unit": "unidades fictícias", "period": "período de demonstração", "filters": {}},
  "error": null,
  "correlation_id": "0123456789abcdef0123456789abcdef",
  "audit_reference": null
}
```

O endpoint de insights devolve `observation` com os valores recebidos e `hypothesis` em campo separado. O modelo seleciona IDs de observações; o serviço monta a hipótese pública a partir dos valores escolhidos, sem publicar o texto livre do modelo. O protótipo local rejeita padrões evidentes de dado pessoal ou instrução nos campos da tela. Sem identidade verificada no modo real, a resposta omite filtros, observações e referência do cliente. O serviço não persiste o contexto nem confirma que o backend está autorizado a enviar aqueles filtros. Um consumidor futuro deverá transmitir contexto já validado e autorizado pela sua própria camada.

O relatório versionado de regressão sintética cobre os fluxos de perguntas e insights. A versão atual do conjunto é `3.0.0`; a saída contém status por caso, resumo, escopo e limitações e é determinística para o mesmo código e fixtures. O adaptador usado é fixo e não chama o Gemini.

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
