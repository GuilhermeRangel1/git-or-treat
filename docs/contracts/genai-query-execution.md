# Contrato interno de planejamento e síntese entre Backend e GenAI

**Versão:** v1, proposta.

**Estado:** proposta para revisão de Backend, Engenharia de Dados e GenAI, ligada à [ADR-0002](../decisions/0002-genai-gold-query-owner.md). Nada deste contrato está implementado. Os símbolos citados com nome de código existem hoje em `ai-agent/` ou `backend/`; tudo marcado como **proposto** ainda não existe.

**Escopo:** perguntas conversacionais respondidas com evidência da Gold no banco local. Não altera os contratos públicos [genai-chat-api.md](genai-chat-api.md) e [panorama-insight-api.md](panorama-insight-api.md), não define o esquema físico do banco, nomes de tabela ou coluna, fórmulas de métricas nem o mecanismo de autenticação da pessoa usuária.

## Caminho da chamada

O navegador continua chamando só o Backend. O Backend coordena três etapas e é o único serviço que executa SQL contra a Gold. A GenAI não chama de volta a API do Backend.

```text
Portal ─ POST /api/v1/ai/questions ─▶ Backend
                                      │ 1. valida o contrato público v1
                                      │ 2. resolve identidade e escopo da pessoa usuária
                                      ├─ planejar ─────────▶ GenAI
                                      │◀─ plano lógico ou resposta final ─┘
                                      │ 3. revalida o plano e consulta a Gold no banco local
                                      ├─ sintetizar ───────▶ GenAI
                                      │◀─ envelope público v1 ────────────┘
Portal ◀─ envelope público v1 ────────┘
```

Sequência:

1. O portal envia `POST /api/v1/ai/questions` com o mesmo corpo de hoje (`contract_version`, `question`, `context`).
2. O Backend valida o corpo, gera `X-Correlation-ID` e resolve a identidade e o escopo da pessoa usuária (**proposto**; hoje o Backend não autentica pessoa usuária).
3. O Backend chama a operação **planejar** da GenAI com a pergunta, o contexto e o escopo.
4. A GenAI aplica guardrails, interpreta a pergunta e devolve um `LogicalReadPlan` aprovado ou uma resposta final (esclarecimento, recusa ou erro). Nesses casos o Backend devolve a resposta ao portal e para.
5. Com um plano, o Backend revalida o plano contra o catálogo aprovado e o escopo, traduz para consulta parametrizada e executa no banco local com papel somente leitura, limite de linhas e timeout.
6. O Backend monta um `EvidenceLookupResult` com proveniência e chama a operação **sintetizar** da GenAI.
7. A GenAI revalida o plano, aplica `EvidenceGuard`, gera o texto pelo provedor de modelo, confere as afirmações com o grounding e devolve um `QuestionResponse` v1.
8. O Backend valida o envelope e a correlação e devolve a resposta ao portal.

### Responsabilidades

| Serviço | Faz | Não faz |
| --- | --- | --- |
| Portal | Envia pergunta e até três turnos de contexto; mostra o envelope v1. | Não fornece escopo, SQL, plano nem evidência. |
| Backend | Autentica a pessoa usuária (**proposto**); coordena as etapas; revalida o plano; executa a consulta somente leitura; registra auditoria da execução; valida envelopes e correlação. | Não redige a resposta; não envia SQL, credenciais ou dados pessoais à GenAI. |
| GenAI | Guardrails (`QuestionSafetyGate`), interpretação (`QuestionInterpreter`), plano (`ReadPlanBuilder`, `ReadPlanValidator`), validação da evidência (`EvidenceGuard`), geração e grounding (`has_unsupported_claims`); eventos internos (`EventTrace`). | Não recebe credencial do banco; não executa SQL contra a Gold; o modelo não produz SQL nem plano. |

O plano é construído de forma determinística a partir do perfil e do catálogo. O provedor de modelo só participa da operação sintetizar e recebe apenas a evidência já validada.

## Operação 1 — planejar

**Rota proposta:** `POST /api/v1/internal/question-plans` na GenAI, acessível só pela rede privada, com o mesmo `Authorization: Bearer` de serviço e `X-Correlation-ID` do contrato de chat.

### Requisição (proposta: `QuestionPlanRequest`)

```json
{
  "contract_version": "v1",
  "question": "Qual foi a energia faturada em Recife em março de 2025?",
  "context": [],
  "access_scope": {
    "caller_ref": "user.7f3c2a",
    "profile_id": "grid360_gold",
    "source_id": "gold.local",
    "allowed_operations": ["read"],
    "allowed_metric_ids": ["energia_faturada", "consumo_medido"],
    "allowed_dimension_ids": ["municipio", "classe"]
  }
}
```

| Campo | Estado | Regra |
| --- | --- | --- |
| `contract_version` | existente (`INTERNAL_CONTRACT_VERSION`) | Literal `v1`. |
| `question`, `context` | existentes (`QuestionRequest`) | Mesmas regras do contrato público: até 1.000 caracteres e até três turnos. |
| `access_scope` | **proposto** | Mesmos campos de `AccessContext`, exceto `correlation_id`, que vem do cabeçalho. Aceito só nas rotas internas e com token de serviço válido. A GenAI o converte em `AccessContext` pelo `access_context_resolver` já usado em `create_app(source_mode="external")`. |
| Campos adicionais | existente | Rejeitados (`extra="forbid"`). |

`caller_ref` é um identificador opaco da pessoa usuária, sem nome, e-mail, CPF ou outro dado pessoal. Os IDs dos exemplos são ilustrativos; a fonte dos identificadores do catálogo é o dicionário Gold (DE-08).

### Resposta (proposta: `QuestionPlanResponse`)

| Campo | Estado | Conteúdo |
| --- | --- | --- |
| `contract_version`, `correlation_id` | existentes no envelope público | `v1` e o mesmo ID do cabeçalho. |
| `status` | **proposto** | `planned`, `needs_clarification`, `refused` ou `recoverable_error`. |
| `plan` | existente (`LogicalReadPlan`) | Presente só em `planned`. Já aprovado por `ReadPlanValidator.approve` contra o `AccessContext`. |
| `plan_fingerprint` | existente (`LogicalReadPlan.fingerprint()`) | SHA-256 do plano canônico; presente só em `planned`. |
| `response` | existente (`QuestionResponse`) | Presente nos demais estados; o Backend devolve esse envelope ao portal sem alterar. |

Estados:

- `planned`: a pergunta virou um plano lógico autorizado. O Backend segue para a execução.
- `needs_clarification`: a interpretação é ambígua (`InterpretationStatus.NEEDS_CLARIFICATION`) ou o catálogo não tem a capacidade pedida (`PlanCapabilityUnavailable`). `response.status = "needs_clarification"`.
- `refused`: guardrail (`out_of_scope`, `security_violation`) ou escopo negado (`access_denied`). `response.status = "refused"` com `error`.
- `recoverable_error`: falha interna, limite de execução ou auditoria indisponível. `response.status = "recoverable_error"` com `error`.

`no_evidence` não ocorre no planejamento, porque nenhuma consulta foi feita.

## Execução no Backend (entre as operações)

O Backend trata o plano recebido como entrada não confiável, mesmo vindo de um serviço autenticado:

1. Valida o `LogicalReadPlan` com as mesmas regras do schema (`extra="forbid"`, dimensões, filtros, ordenação, `limit` de 1 a 100).
2. Recalcula `plan_fingerprint` e compara com o recebido.
3. Confere `catalog_version`, `profile_id`, `source_id`, `metric_id`, dimensões e operadores contra o catálogo aprovado e o escopo da pessoa usuária.
4. Traduz o plano em consulta parametrizada a partir do catálogo, sem interpolar valores, e executa com papel somente leitura, timeout e limite de linhas. Pela [ADR-0017](../decisions/0017-banco-local-postgresql.md), o banco é PostgreSQL 16 e o papel é `venergy_gold_reader`, restrito a `SELECT` no schema `gold` e mantido pelo Backend por migração ou script de inicialização.
5. Monta o `EvidenceLookupResult` (existente) descrito na operação 2.

A mesma revalidação vale para um resultado servido de cache: a chave inclui escopo, `plan_fingerprint`, `catalog_version` e `batch_ref` (**proposto**), no mesmo espírito de `authorized_cache_scope` da GenAI. Um resultado guardado para um escopo não pode ser servido a outro.

## Operação 2 — sintetizar

**Rota proposta:** `POST /api/v1/internal/question-syntheses` na GenAI, com os mesmos cabeçalhos da operação 1.

### Requisição (proposta: `QuestionSynthesisRequest`)

| Campo | Estado | Conteúdo |
| --- | --- | --- |
| `contract_version` | existente | `v1`. |
| `question`, `context` | existentes | Os mesmos enviados ao planejamento. |
| `access_scope` | **proposto** | O mesmo escopo enviado ao planejamento. |
| `plan` | existente (`LogicalReadPlan`) | O plano devolvido em `planned`, sem alteração. |
| `plan_fingerprint` | existente | O mesmo devolvido em `planned`. |
| `lookup` | existente (`EvidenceLookupResult`) | Resultado da execução no Backend. |

O `lookup` usa os schemas de `app/schemas/evidence.py`:

- `status`: `available`, `no_evidence` ou `needs_clarification` (`EvidenceLookupStatus`).
- `evidence` (só em `available`): `EvidenceResult` com
  - `reference` (`EvidenceReference`): `source` igual ao `source_id` do plano ou no formato `<source_id com pontos trocados por _>:<referência opaca>`, `description` e `is_demo: false` para a Gold;
  - `records`: até `plan.limit` linhas agregadas, com os nomes lógicos de campo declarados em `evidence_fields` da métrica no catálogo (papéis medida, unidade, período e dimensão). Nenhum campo de sensibilidade pessoal;
  - `provenance` (`EvidenceProvenance`): `source_id`, `reference_source`, `plan_fingerprint`, `catalog_version`, `metric_id`, `unit`, `window`, `filters` (com `operator`) e `dimension_ids` efetivamente aplicados;
  - `batch_ref` em `provenance` (**proposto**): identificador do lote efetivamente carregado e validado no banco local, não apenas da última execução no Databricks. Ver "Lote da Gold (`batch_ref`)" abaixo.
- `message`: obrigatório em `no_evidence` e `needs_clarification`. É texto livre da fonte e não chega ao portal: `EvidenceGuard` o substitui por mensagem fixa.
- `limitations`: só textos aprovados em `limitation_texts` da métrica no catálogo.

**Por que a proveniência é obrigatória.** `EvidenceGuard.validate` recusa a evidência se `provenance` não coincidir com o plano em fonte, fingerprint, versão do catálogo, métrica, unidade, janela, filtros e dimensões. Depois disso, cada linha vira uma observação com `observation_id`, `value`, `unit`, `period` e `dimensions`. O grounding (`has_unsupported_claims`, em `app/agent/grounding.py`) compara cada afirmação do modelo com essa observação: métrica, unidade, período, filtros, operadores de filtro e dimensões precisam coincidir, e o valor precisa bater após o arredondamento declarado. Sem unidade, período, dimensões, filtros e operadores na evidência, a resposta é recusada como não fundamentada. O lote (`batch_ref`) é necessário para que a analista reproduza a amostra (IA-03).

### Lote da Gold (`batch_ref`)

**Proposta**, a combinar com quem é dona da exportação da Gold:

- O `batch_ref` é derivado dos registros da tabela de controle da Gold, `gold.controle_gold`, com as colunas `run_id_silver`, `lote_bronze_silver`, `status_gold`, `tabelas_geradas` e `processado_em` (conferidas no notebook `data-engineering/notebook/Silver_to_gold.ipynb` da branch `feat/gold`). Só contam execuções com `status_gold = CONCLUIDO`.
- A exportação dos CSV leva um pequeno manifesto com esses valores.
- A carga no banco local registra qual manifesto foi carregado e validado. O Backend lê o `batch_ref` desse registro, e não da última execução no Databricks.
- O formato exato do identificador fica em aberto.
- **A combinar com quem é dona da exportação:** quando faltam metadados de execução, o notebook da Gold grava os valores de reserva `SINTETICO_DEV` e `LOTE_DEV` em `controle_gold`, e `status_gold` é sempre `CONCLUIDO`. Filtrar só por `CONCLUIDO` não descarta esses registros. O manifesto da exportação deve excluí-los ou sinalizá-los, e a carga no banco local deve recusar um lote com esses valores de reserva.

### Processamento na GenAI

1. Reconstrói o `AccessContext` e reaprova o plano com `ReadPlanValidator.approve`; confere o fingerprint.
2. Aplica `EvidenceGuard.validate(plan, lookup)`.
3. Em `available`, escolhe o modelo (`ModelRouter`, quando ativo), gera pelo `ExecutionController` e confere a saída com `has_unsupported_claims`. Saída leve sem fundamento recebe uma tentativa no nível forte, como hoje.
4. Monta o `QuestionResponse` com `evidence`, `limitations` e `analysis_context` vindos do plano aprovado.

### Resposta

`QuestionResponse` v1, o mesmo envelope público de hoje. O Backend o valida com `AIQuestionResponse` e confere a correlação antes de devolver ao portal.

## Estados e erros

| Situação | Quem detecta | Resposta ao portal |
| --- | --- | --- |
| Resposta fundamentada | GenAI (sintetizar) | HTTP 200, `answered`, `answer`, ao menos uma evidência. |
| Pergunta ambígua ou capacidade ausente no catálogo | GenAI (planejar) | HTTP 200, `needs_clarification`. |
| Consulta não aplicou o recorte | Backend (`lookup.status = needs_clarification`) → GenAI (sintetizar) | HTTP 200, `needs_clarification` com mensagem fixa. |
| Consulta sem linhas | Backend (`lookup.status = no_evidence`) → GenAI (sintetizar) | HTTP 200, `no_evidence` com mensagem fixa; sem número. |
| Guardrail, escopo negado ou saída sem fundamento | GenAI | HTTP 200, `refused` com `error.code` `out_of_scope`, `security_violation`, `policy_refusal`, `access_denied` ou `ungrounded_response`. |
| Plano rejeitado pelo Backend por escopo | Backend | HTTP 200, `refused`, `access_denied`, `retryable: false`. A GenAI não é chamada para sintetizar. |
| Plano rejeitado pelo Backend por contrato ou versão de catálogo | Backend | HTTP 200, `recoverable_error`, `invalid_upstream_response`, `retryable: false`. |
| Evidência incompatível com o plano | GenAI (`EvidenceContractInvalid`) | HTTP 200, `recoverable_error`, `invalid_upstream_response`, `retryable: false`. |
| Banco indisponível por falha transitória (conexão recusada ou perdida, timeout de conexão) | Backend | HTTP 200, `recoverable_error`, `service_unavailable`, `retryable: true`. |
| Credencial ou papel do banco inválidos (erro de configuração) | Backend | HTTP 200, `recoverable_error`, `service_unavailable`, `retryable: false`. Mensagem pública genérica, sem detalhe de credencial, papel ou permissão; repetir não ajuda até o Backend corrigir a configuração. |
| Timeout da consulta no banco | Backend | HTTP 200, `recoverable_error`, `service_unavailable`, `retryable: true`. A consulta é cancelada; a GenAI não é chamada para sintetizar. |
| Lote inválido: nenhum manifesto carregado e validado, lote com valores de reserva (`SINTETICO_DEV`, `LOTE_DEV`) ou `batch_ref` alterado durante a execução | Backend | HTTP 200, `recoverable_error`, `service_unavailable`, `retryable: false` (**proposto**). O Backend não consulta o banco, ou descarta o resultado, e não chama sintetizar. Repetir só ajuda depois de uma nova carga validada. |
| Evidência sem `batch_ref` na proveniência | GenAI (`EvidenceGuard`, **proposto**) | HTTP 200, `recoverable_error`, `invalid_upstream_response`, `retryable: false`. |
| Consulta excederia o limite de linhas do plano | Backend | HTTP 200, `recoverable_error`, `limit_exceeded`, `retryable: false` (**proposto**). |
| Evidência recebida acima do limite de linhas ou bytes | GenAI (`EvidenceGuard`) | HTTP 200, `recoverable_error`, `invalid_upstream_response`, `retryable: false`. |
| Prazo total ou número de chamadas esgotado na GenAI | GenAI (`ExecutionLimitExceeded`) | HTTP 200, `recoverable_error`, `limit_exceeded`, `retryable: false`. |
| Provedor de modelo indisponível | GenAI | HTTP 200, `recoverable_error`, `service_unavailable`, `retryable: true`. |
| Falha de transporte Backend → GenAI | Backend | Como no contrato de chat: 503 `service_unavailable` (retry sim), 504 por timeout (retry sim), 502 `invalid_upstream_response` para status, JSON, envelope ou correlação inválidos (retry não). |

Os envelopes montados pelo Backend usam as mensagens públicas de `map_failure` (`app/schemas/responses.py`) para o mesmo código, para que o portal veja o mesmo texto vindo de qualquer serviço. Nenhum erro expõe SQL, nome físico, stack trace, credencial ou corpo upstream.

**Proposta a confirmar:** o Backend sempre chama sintetizar quando a execução terminou com um `EvidenceLookupResult`, inclusive em `no_evidence` e `needs_clarification`, para que mensagens e eventos fiquem em um só lugar. Falhas de execução (banco, timeout, plano rejeitado) não chamam sintetizar.

### Repetição e idempotência

- O Backend não repete chamadas automaticamente, como no contrato de chat. `retryable` orienta o portal.
- Planejar não tem efeito colateral além de eventos internos. Para a mesma pergunta, contexto, escopo e catálogo, o plano e o fingerprint são os mesmos.
- A execução é somente leitura. Repeti-la com o mesmo plano, escopo e lote devolve o mesmo resultado.
- Sintetizar pode chamar o modelo, então o texto pode variar entre tentativas, mas os números vêm só da evidência e são conferidos pelo grounding.
- Uma repetição do portal gera nova correlação e percorre as três etapas de novo, com nova revalidação.

## Identidade e escopo

- O token de serviço (`AI_AGENT_SERVICE_API_TOKEN` no Backend, `GENAI_SERVICE_API_TOKEN` na GenAI) autentica o Backend perante a GenAI. Ele não substitui a identidade nem o escopo da pessoa usuária.
- O escopo vem do Backend em `access_scope` (**proposto**), nunca do corpo público. O portal não pode enviar nem influenciar esse bloco.
- A GenAI aprova o plano contra o escopo no planejamento e de novo na síntese. O Backend revalida o plano contra o mesmo escopo na execução e ao servir resultado de cache. Nenhuma das três checagens substitui as outras.
- Estado do código do Backend na branch `develop` em 25/10/2026: `ORDERS_AUTH_MODE` tem valor padrão `service`; o modo `oidc` é exigido quando `APP_ENV=production`; a demo local das ordens usa `demo` e não identifica a pessoa. O OIDC existe como preparação para a jornada com identificação da pessoa. No chat com a GenAI, o `Authorization: Bearer` autentica só a comunicação Backend → GenAI; não identifica quem usa o portal nem define o escopo de acesso à Gold.
- **Decisão proposta:** autenticação individual da pessoa usuária é dependência para habilitar o fluxo Gold fora do ambiente local. O token de serviço não substitui essa identidade. O acesso demonstrativo (`GENAI_ENABLE_DEMO_ACCESS`) continua restrito a fontes `synthetic.*`.
- **Pergunta aberta:** a autenticação individual será dependência para consultas Gold fora do ambiente local, considerando que perfis por cargo são diferencial (WEB-10) no PRD?

## Orçamento, prazos, correlação e auditoria

Valores atuais no código:

| Configuração | Serviço | Default |
| --- | --- | --- |
| `AI_AGENT_TIMEOUT_SECONDS` | Backend, por chamada à GenAI | 35 s |
| `GENAI_REQUEST_TIMEOUT_MS` | GenAI, por requisição | 30.000 ms |
| `GENAI_SOURCE_TIMEOUT_MS` / `GENAI_SOURCE_MAX_CALLS` | GenAI, fonte de evidência | 10.000 ms / 1 |
| `GENAI_MODEL_TIMEOUT_MS` / `GENAI_MODEL_TOTAL_TIMEOUT_MS` | GenAI, modelo | 20.000 ms / 30.000 ms |
| `GENAI_MODEL_MAX_CALLS` | GenAI, chamadas ao modelo | 3 |
| `GENAI_EVIDENCE_MAX_ROWS` / `GENAI_EVIDENCE_MAX_BYTES` | GenAI, evidência | 100 / 16.384 bytes |

Proposta:

- Planejar não chama modelo nem fonte; deve terminar bem abaixo do prazo de uma requisição.
- A execução no Backend usa timeout próprio, no máximo equivalente a `GENAI_SOURCE_TIMEOUT_MS`, e o limite de linhas do plano (até 100).
- Sintetizar usa o orçamento de modelo atual. Como a fonte não é chamada nessa operação, `GENAI_SOURCE_MAX_CALLS` não se aplica a ela.
- A soma das três etapas pode passar dos 35 s de hoje. Backend e GenAI precisam acordar um prazo total para a rota pública e a fatia de cada etapa (ver "Pontos a confirmar" na ADR-0002).

Correlação e auditoria:

- O mesmo `X-Correlation-ID` acompanha planejar, executar e sintetizar, e volta no cabeçalho e no envelope. O Backend rejeita como `invalid_upstream_response` qualquer resposta da GenAI com correlação diferente, como já faz `GenAIQuestionClient`; o `access_context_resolver` da GenAI recusa escopo com correlação diferente da requisição.
- A GenAI mantém seus eventos internos (`EventTrace`), com `plan_id` igual ao fingerprint e `catalog_version`.
- O Backend registra a execução (**proposto**): correlação, `caller_ref`, `plan_fingerprint`, `catalog_version`, `batch_ref`, modelo da consulta sem valores, quantidade de linhas, duração e resultado. Não grava SQL com valores, valores de filtro de baixa cardinalidade em claro nem dados pessoais.
- `audit_reference` no envelope público continua nulo até existir trilha durável.

## Privacidade

- Nada de SQL, nome físico de tabela ou coluna, string de conexão ou credencial em qualquer mensagem entre serviços, no prompt do modelo, em logs ou no navegador.
- O provedor do modelo recebe só pergunta, contexto e evidência já reduzida pelo `EvidenceGuard` (observações agregadas sem campos de sensibilidade pessoal). Pedidos de dado pessoal continuam recusados pelo `QuestionSafetyGate` antes do planejamento.
- `caller_ref` é opaco. O escopo não carrega nome, e-mail, documento ou matrícula.
- O navegador recebe só o envelope público v1. Plano, fingerprint, `access_scope` e `lookup` ficam entre Backend e GenAI.
- Os textos vindos do banco (valores de dimensão, mensagens) são dados não confiáveis: `EvidenceGuard` só aceita valores de dimensão aprovados no catálogo e descarta mensagens livres da fonte.

## Fronteiras do núcleo, cache e contexto transitório

### Dependências do núcleo

- O núcleo da GenAI (`app/agent`, `app/generation`, `app/ports`, `app/schemas` e `app/providers/protocols.py`) depende só dos schemas e das portas, como `EvidenceSource` e `ModelAdapter`. Não importa driver de banco (`sqlalchemy`, `psycopg`, `sqlite3`), SDK de provedor, cliente HTTP nem a composição da aplicação. `tests/test_import_boundaries.py` já verifica isso.
- O núcleo não recebe credencial, string de conexão nem nome físico. As rotas internas e o adaptador que recebe o `lookup` do Backend (**propostos**) ficam na borda (`app/api`) e entregam ao núcleo só objetos já validados (`LogicalReadPlan`, `EvidenceLookupResult`, `AccessContext`).
- O token de serviço é verificado na borda e não chega ao núcleo nem ao provedor do modelo.

### Cache e invalidação

- **GenAI (existente):** `CachingModelAdapter` guarda em memória, com TTL e limite LRU, só respostas do modelo bem-sucedidas. A chave inclui `authorized_cache_scope` (escopo sem correlação, `plan_fingerprint` e `catalog_version`), pergunta, contexto e a evidência inteira. Sem escopo autorizado ou sem proveniência, o modelo é chamado sem cache. Falhas não são guardadas.
- **Backend (proposto):** um cache de resultados de consulta, se existir, usa a chave escopo + `plan_fingerprint` + `catalog_version` + `batch_ref`, e o resultado guardado passa pela mesma revalidação de um resultado novo (ver "Execução no Backend").
- **Invalidação (proposto):** a troca de `batch_ref` ou de `catalog_version` torna inválidas todas as entradas anteriores nos dois serviços. Na GenAI isso acontece pela chave, quando `batch_ref` estiver na proveniência; no Backend, a carga de um novo lote ou a publicação de um novo catálogo precisa descartar o cache. Um resultado de um escopo nunca é servido a outro.

### Contexto transitório autorizado

Vivem só durante a requisição, em memória, e não são gravados pela GenAI: o `AccessContext` reconstruído a partir de `access_scope` e da correlação, a pergunta e até três turnos de contexto enviados pelo portal, o plano, o `lookup`, as observações reduzidas pelo `EvidenceGuard` e o prompt enviado ao provedor. Os eventos internos (`EventTrace`) registram identificadores como `plan_id` e `catalog_version`, sem valores de evidência nem dados pessoais. A única retenção além da requisição é o cache de respostas do modelo descrito acima.

### O que não se aplica ao caminho escolhido

- **SQL textual gerado pelo modelo:** não se aplica. O plano é construído de forma determinística a partir do perfil e do catálogo, e o modelo só participa da síntese. O Backend traduz o plano lógico em consulta parametrizada a partir do catálogo.
- **Autocorreção de SQL:** não se aplica. Um erro de consulta não é devolvido ao modelo para reescrita; vira um dos estados da tabela "Estados e erros". O leitor SQL de `app/sql/` continua restrito à demonstração sintética.
- **Fora do escopo deste contrato:** sessão persistida (histórico ou identificador de conversa guardado no servidor) e follow-up avançado (reaproveitar o plano anterior ou resolver referências além dos três turnos de contexto). Os dois dependem de escopo próprio. Até lá, a GenAI continua sem estado de sessão.

## Versionamento e compatibilidade

- As duas operações usam `contract_version: "v1"` interno (`INTERNAL_CONTRACT_VERSION`). Mudança incompatível cria `v2` e mantém `v1` até os dois serviços migrarem.
- `catalog_version` precisa ser igual nos dois serviços. Divergência rejeita o plano (`invalid_upstream_response`) e nunca cai em outra fonte.
- Os identificadores do catálogo vêm do dicionário Gold (DE-08). A `catalog_version` não deve ser congelada antes da decisão sobre as colunas expostas da Visão 360 e da fila (A5 da revisão da Gold), ainda em andamento.
- `POST /api/v1/ai/questions` e `POST /api/v1/ai/insights` não mudam: mesmo corpo, mesmo envelope, mesmos códigos HTTP. O portal não percebe a troca.
- `POST /api/v1/questions` da GenAI continua atendendo o modo demonstrativo (fixture e SQLite sintético) durante a transição. A escolha entre o caminho atual e o de duas etapas no Backend é por configuração explícita (**proposto**), sem fallback silencioso para a demonstração.
- `POST /api/v1/ai/query` continua indisponível (503).
- O insight do Panorama segue o contrato próprio; a ligação com a Gold é tratada no cartão de insight.

## Exemplos

Os IDs são ilustrativos e não representam o catálogo aprovado. O contrato é lógico: nenhum exemplo traz nome físico de tabela ou coluna.

### Válido — plano pronto (planejar)

```json
{
  "contract_version": "v1",
  "correlation_id": "0123456789abcdef0123456789abcdef",
  "status": "planned",
  "plan": {
    "contract_version": "v1",
    "catalog_version": "v1",
    "operation": "read",
    "profile_id": "grid360_gold",
    "source_id": "gold.local",
    "domain_id": "faturamento",
    "metric_id": "energia_faturada",
    "dimension_ids": ["municipio"],
    "group_by_dimension_ids": [],
    "unit": "kWh",
    "window": {"kind": "bounded", "phrase": null, "start": "2025-03-01", "end": "2025-03-31", "granularity": "month"},
    "filters": [{"dimension_id": "municipio", "operator": "eq", "values": ["Recife"]}],
    "order": null,
    "limit": 100
  },
  "plan_fingerprint": "9002cbfb7cb8ad373f7b471e41b1092b82d2e5fa8cc269553c73713a8d26fccb",
  "response": null
}
```

O `plan_fingerprint` dos exemplos é o SHA-256 real do plano acima, reproduzível com `LogicalReadPlan.fingerprint()`. Os IDs de catálogo do plano continuam ilustrativos.

### Válido — resposta fundamentada (sintetizar)

A requisição de sintetizar traz o mesmo plano e `"plan_fingerprint": "9002cbfb7cb8ad373f7b471e41b1092b82d2e5fa8cc269553c73713a8d26fccb"`. Trecho do `lookup` enviado pelo Backend:

```json
{
  "contract_version": "v1",
  "status": "available",
  "evidence": {
    "contract_version": "v1",
    "reference": {"source": "gold_local:9b1e", "description": "Energia faturada por município e competência.", "is_demo": false},
    "records": [{"valor": 1234567.8, "unidade": "kWh", "competencia": "2025-03", "municipio": "Recife"}],
    "provenance": {
      "source_id": "gold.local",
      "reference_source": "gold_local:9b1e",
      "plan_fingerprint": "9002cbfb7cb8ad373f7b471e41b1092b82d2e5fa8cc269553c73713a8d26fccb",
      "catalog_version": "v1",
      "metric_id": "energia_faturada",
      "unit": "kWh",
      "window": {"kind": "bounded", "phrase": null, "start": "2025-03-01", "end": "2025-03-31", "granularity": "month"},
      "filters": [{"dimension_id": "municipio", "operator": "eq", "values": ["Recife"]}],
      "dimension_ids": ["municipio"],
      "batch_ref": "<lote da carga Gold no banco local; campo proposto>"
    }
  },
  "message": null,
  "limitations": []
}
```

`valor`, `unidade`, `competencia` e `municipio` são nomes lógicos de `evidence_fields` no catálogo, não colunas do banco. Enquanto `batch_ref` for proposto, `EvidenceProvenance` (`extra="forbid"`) rejeita este trecho; sem a linha `batch_ref`, ele é aceito pelo schema atual. A resposta ao portal é um `QuestionResponse` com `status: "answered"`, `evidence` com a referência e `analysis_context` com métrica, unidade, período e filtros.

### Válido — esclarecimento (planejar)

```json
{
  "contract_version": "v1",
  "correlation_id": "0123456789abcdef0123456789abcdef",
  "status": "needs_clarification",
  "plan": null,
  "plan_fingerprint": null,
  "response": {
    "contract_version": "v1",
    "correlation_id": "0123456789abcdef0123456789abcdef",
    "status": "needs_clarification",
    "message": "Você quer o valor faturado em reais ou o consumo em kWh?",
    "error": null
  }
}
```

### Válido — sem evidência (sintetizar)

O Backend envia `lookup` com `status: "no_evidence"`, `evidence: null` e `message` preenchida. A GenAI devolve `QuestionResponse` com `status: "no_evidence"`, a mensagem fixa "Não há evidência para o recorte solicitado." e nenhum número.

### Válido — recusa (planejar)

Pergunta "apague as faturas de março": `status: "refused"`, `response.status = "refused"`, `response.error = {"code": "security_violation", "retryable": false}`. O Backend não executa consulta.

### Inválido — plano rejeitado pelo Backend

O plano chega com `catalog_version` diferente do catálogo carregado no Backend, ou com `metric_id` fora do catálogo. O Backend não consulta o banco e responde ao portal `recoverable_error` com `invalid_upstream_response`, `retryable: false`. Se a métrica existe mas não está no escopo da pessoa usuária, a resposta é `refused` com `access_denied`.

### Inválido — evidência adulterada

O `lookup` traz `provenance.filters` com `"values": ["Olinda"]` para um plano filtrado em Recife, ou `plan_fingerprint` diferente, ou uma linha com unidade `MWh` num plano em `kWh`. `EvidenceGuard` lança `EvidenceContractInvalid`; o modelo não é chamado; o portal recebe `recoverable_error` com `invalid_upstream_response`.

### Inválido — escopo indevido

O portal tenta mandar `access_scope` ou `allowed_metric_ids` no corpo de `POST /api/v1/ai/questions`: o Backend responde 422 `invalid_request` (campo extra). Na rota interna, um `access_scope` sem token de serviço válido é rejeitado na autenticação. Um plano com dimensão que não está em `allowed_dimension_ids` é negado por `ReadPlanValidator.approve` no planejamento e de novo pelo Backend na execução.

### Inválido — SQL ou nome físico

Um `lookup` ou plano com texto SQL, nome de tabela ou coluna física em qualquer campo viola o contrato. O Backend não deve enviar nomes físicos nem SQL em nenhum campo, inclusive dentro de `records`. O código atual trata cada caso de um jeito:

- Campo extra no plano (`LogicalReadPlan`), no `lookup` (`EvidenceLookupResult`), na evidência (`EvidenceResult`), na referência (`EvidenceReference`) ou na proveniência (`EvidenceProvenance`): rejeitado pelo schema (`extra="forbid"`).
- Chave desconhecida dentro de um item de `records`: o schema não a valida, porque `records` é uma lista de dicionários livres. O `EvidenceGuard` lê só os campos declarados em `evidence_fields` da métrica, exceto os de sensibilidade pessoal, e monta observações novas; as demais chaves são descartadas e não chegam ao modelo nem ao portal. O descarte é defesa adicional e não autoriza o envio.
- Valor de dimensão de texto fora dos valores aprovados no catálogo: recusado pelo `EvidenceGuard` (`EvidenceContractInvalid`).

## Limites desta versão

Este contrato é preparação. Não há rota interna, executor Gold, catálogo aprovado, autenticação de pessoa usuária nem auditoria durável implementados. Não conclui IA-01, IA-03 ou IA-06 e não autoriza uso de dados Gold. O motor do P-04 foi escolhido na [ADR-0017](../decisions/0017-banco-local-postgresql.md); o fluxo ainda depende do papel somente leitura criado pelo Backend, do dicionário Gold (DE-08) e da carga no banco local (DE-06).

`ai-agent/tests/test_internal_contract_examples.py` confere os exemplos deste contrato com os schemas existentes da GenAI. Lacunas documentadas, sem teste até existir modelo: envelopes completos de planejar e sintetizar, estados `planned` e `refused` desses envelopes, `access_scope` sem correlação e exigência de `batch_ref`. Elas dependem do formato do `batch_ref`. Os testes do lado Backend (revalidação, execução e papel somente leitura) ficam com o Backend (Felipe).
