# GENAI-13 — Contrato de invalidação por lote, filtro e schema

**Cartão:** GENAI-13. **Requisitos:** IA-03, IA-04, IA-05, IA-06. **Natureza:** preparação (contrato). Este documento não implementa nem conclui requisitos; fixa as regras que as fases de servidor e de tela devem provar. Base inspecionada: `develop` em `b804b58`.

Princípio: uma resposta, evidência, insight ou entrada de cache vale somente para a combinação de publicação, catálogo, schema, escopo, prompt e modelo sob a qual foi produzida. Mudança relevante invalida; incompatibilidade falha de forma explícita e recuperável; nenhuma falha aciona demonstração.

Referências: [coordenação Gold](genai-gold-coordination.md), [execução da consulta](genai-query-execution.md), [chat](genai-chat-api.md), [insight](panorama-insight-api.md), [prontidão](../gold-readiness.md) e [referência obrigatória Gold v2](../agents/genai-gold.md#referência-obrigatória-gold-v2).

## 1. Identidades versionadas

| Identidade | Forma | Onde nasce | Quem confere hoje |
| --- | --- | --- | --- |
| Publicação Gold (`batch_ref`) | `<schema_version>:<run_id>:<publication_id>`, com `schema_version=gold-csv-v2` e `publication_id` UUID4 | `GoldPublicationContext.capture` no Backend, a partir de `gold.publicacao_atual` | `current_publication(expected)` antes do planejamento, no snapshot de execução, depois do SQL, antes e depois da síntese; `EvidenceGuard` na GenAI |
| Publicação vista pela tela | `lote` + `fingerprint` (64 hex) | Metadados da API analítica (`load_gold_context`) | `expected_lote`/`expected_fingerprint` nas leituras analíticas; `loteVersao` no insight |
| Contrato lógico | `contract_version=v1`, `catalog_version=v1` no plano | Envelopes internos | Validação de envelope nos dois serviços. Não identifica a versão física dos dados |
| Catálogo físico | `mapping_version=gold-catalog-v2`, `physical_schema=gold_v2`, `dictionary_version=gold-csv-v2`, `profile_id=v-energy-grid-360-gold` | `backend/app/catalogs/gold_v2.json` e `ai-agent/app/profiles/grid360_gold*.py` | Carga validada no início de cada serviço e teste de contrato entre catálogo e perfil; **não há conferência em runtime entre os dois serviços** |
| Prontidão | `readiness_version=gold-readiness-v2` + `batch_ref` + capacidades | Gate do Backend | Coordenador e `EvidenceGuard` (`quality`) |
| Plano | `plan_fingerprint` = SHA-256 do `LogicalReadPlan` canônico | GenAI no planejamento | Backend revalida e a síntese exige plano idêntico |
| Escopo de acesso | `AccessScope` resolvido da sessão individual | Backend | Reresolvido após o SQL, após a síntese e após a confirmação de auditoria; divergência → 403 |
| Prompt | `PROMPT_VERSION` (`genai-grounding-v3`) e digest de `SYSTEM_INSTRUCTION` | GenAI | Eventos de auditoria e namespace do cache de modelo |
| Modelo | Provedores e modelos da cadeia configurada | Fábrica de provedores | Namespace do cache de modelo |

Regras:

1. A publicação de referência de uma requisição é sempre a capturada no servidor. Um valor enviado pelo navegador só pode **restringir** (provocar rejeição); nunca seleciona, autoriza nem substitui a captura.
2. `catalog_version=v1` e `/api/v1` não significam Gold v1. A versão física vem do catálogo, da publicação e do schema analítico.
3. Plano, evidência e síntese de uma requisição carregam o mesmo `batch_ref`, o mesmo `plan_fingerprint` e o mesmo escopo. Qualquer divergência interrompe antes de publicar a resposta.

## 2. Vínculos por artefato

| Artefato | Vinculado a | Regra de invalidação |
| --- | --- | --- |
| Plano lógico | catálogo físico, perfil, `batch_ref` do planejamento, escopo | Não é reaproveitado entre requisições; nova pergunta replaneja com a publicação atual. Plano produzido sob outro catálogo físico não executa. |
| Evidência | `plan_fingerprint`, `batch_ref`, `quality` (prontidão), unidade, janela, filtros, dimensões | Rejeitada se o lote, a qualidade ou o plano diferirem do esperado; nunca combina linhas de publicações distintas. |
| Contexto de conversa | texto das últimas trocas (máx. 3) | É contexto de interpretação, não evidência. Uma resposta anterior não sustenta número novo; cada pergunta passa por planejamento, prontidão e SQL atuais. |
| Contexto de tela (insight) | filtros + `loteVersao` exibidos | Backend recalcula o contexto; lote diferente → 409. Resposta para recorte anterior é descartada pela tela. |
| Cache de modelo | chave da seção 4 | Somente resposta `answered` fundamentada é armazenada; falha nunca é armazenada; autorização roda antes de qualquer acerto. |
| Referência de auditoria | plano, publicação, digest do cálculo, identidade | Replay reautoriza a identidade atual e falha se a publicação/catálogo não forem os auditados. |

## 3. Erros públicos

Todos usam o envelope seguro do respectivo contrato, com correlação, sem SQL, identificador de lote, stack ou detalhe privado.

| HTTP | Código | `retryable` | Quando | Mensagem recuperável (orientação) |
| --- | --- | --- | --- | --- |
| 409 | `invalid_context` (chat) | `true` | A publicação mudou durante a requisição (`GoldPublicationChanged` em qualquer fronteira) | "A publicação Gold mudou. Refaça a pergunta." Nova tentativa replaneja com o lote atual. |
| 409 | `invalid_context` (chat, publicação esperada informada) | `false` | O consumidor informou a publicação que está exibindo e ela difere da atual (seção 6) | "Os dados da tela foram atualizados. Recarregue a tela antes de perguntar." Repetir o mesmo pedido não muda o resultado; recarregar sim. |
| 409 | `invalid_context` (insight) | `false` | `loteVersao` do pedido difere do lote atual | "O lote dos indicadores mudou. Atualize o Panorama antes de gerar o insight." |
| 409 | `stale_batch` (API analítica) | — (envelope analítico) | `expected_lote`/`expected_fingerprint` diferem da publicação atual | "A publicação Gold mudou; recarregue os dados." |
| 422 | `invalid_query` / `invalid_request` | `false` | Expectativa malformada (fingerprint fora do padrão, referência inválida) | Corrigir o pedido; não é troca de lote. |
| 503 | `service_unavailable` | `false` | Publicação ausente ou corrompida (`GoldPublicationUnavailable`/`GoldPublicationInvalid`), catálogo/schema incompatível, gate de prontidão sem a capacidade ou de outro lote | "A publicação Gold não está disponível para esta consulta." Requer ação operacional. |
| 503 | `service_unavailable` | `true` | Falha transitória de banco (`SQLAlchemyError`) ou do serviço GenAI | "A consulta Gold está temporariamente indisponível." |
| 403 | `access_denied` | `false` | Escopo revogado ou alterado entre etapas | "A consulta não está autorizada com o acesso atual." |

Nenhum desses estados vira `no_evidence`, zero, resposta anterior ou resposta demonstrativa.

## 4. Chave de cache

Qualquer cache de resultado ou de resposta que o fluxo Gold venha a servir usa uma chave que inclui, no mínimo:

| Componente | Origem |
| --- | --- |
| Fonte e perfil | `source_id`, `profile_id` |
| Escopo/política | identidade confirmada (`caller_ref`), operações, métricas e dimensões permitidas |
| Métrica, dimensões, agrupamento | plano |
| Filtros normalizados | filtros ordenados por `dimension_id`, valores de `in` ordenados, grafia canônica do vocabulário |
| Janela e grão | `window` (tipo, início, fim, granularidade) |
| Ordem e limite | `order`, `limit` |
| Unidade | `unit` |
| Versões | `batch_ref`; `mapping_version` e digest do catálogo físico; `physical_schema`; `dictionary_version`; `readiness_version`; `PROMPT_VERSION`/digest do prompt; provedores e modelos |

Regras:

1. Autorizar antes de servir: a autorização da pessoa e do plano roda antes de consultar o cache; acerto de cache nunca dispensa autorização, `EvidenceGuard` ou validação de fundamentação.
2. Cache isolado por escopo: duas identidades com a mesma pergunta e evidência não compartilham entrada.
3. Erro prevalece: um erro ou desatualização na requisição atual é apresentado mesmo que exista resposta válida em cache para o mesmo recorte.
4. **TTL sozinho não basta.** Expiração não protege contra mudança de semântica, fórmula ou permissão; a chave precisa mudar quando qualquer componente acima muda.
5. A correlação e o ID da requisição não entram na chave (são transitórios).

## 5. Leitura consistente do lote

1. A publicação é capturada uma vez por requisição e comparada em cada fronteira: planejamento, prontidão, entrada e saída do snapshot de execução, antes e depois da síntese e após a confirmação de auditoria.
2. A consulta quantitativa roda em `REPEATABLE READ READ ONLY` no PostgreSQL; o resultado só é usado se a publicação continuar a mesma ao sair do snapshot.
3. Mudança detectada → rejeitar (409 `invalid_context`, `retryable=true`). Nunca recalcular parte do resultado, nunca juntar linhas de duas publicações e nunca publicar síntese baseada em evidência de outra publicação.
4. Prontidão e metadados de planejamento são lidos sob a mesma publicação esperada; relatório de outro lote bloqueia antes do SQL quantitativo.

## 6. Publicação esperada informada pelo consumidor

O chat passa a aceitar, de forma **opcional e retrocompatível**, a publicação que a tela está exibindo, com o mesmo par já usado pela API analítica (`lote`, `fingerprint`). Semântica:

- Ausente: comportamento atual (captura no servidor e detecção de troca durante a requisição).
- Presente e igual à publicação atual: segue o fluxo normal; a captura do servidor continua sendo a referência.
- Presente e diferente: 409 `invalid_context`, `retryable=false`, antes do planejamento, do SQL e do modelo.
- Malformada: 422 `invalid_request`.
- Modo sintético: o campo é rejeitado (422), como já ocorre com `expected_lote` nas leituras analíticas.

Esse valor não autoriza nada: apenas impede responder sobre um lote diferente do que a pessoa está vendo. O campo pertence ao envelope público `AIQuestionRequest`; a mudança é aditiva e precisa ser refletida no consumidor do portal pelo GENAI-11.

## 7. Resposta atrasada

1. Cada pedido de tela leva uma revisão local (ID do pedido ligado ao recorte: filtros, lote, identidade e rota).
2. Uma resposta só é aplicada se sua revisão for a vigente; caso contrário é descartada, **mesmo que o transporte não tenha cancelado o trabalho no servidor**.
3. Troca de identidade, de rota, de filtros ou de lote invalida a revisão.
4. Ida e volta rápida de filtros (A → B → A) não reaproveita a resposta antiga de A se o lote ou o escopo mudaram nesse intervalo.
5. Revogação de escopo descarta respostas pendentes e cache local daquela identidade.

## 8. Demonstração

Nenhuma falha Gold aciona o caminho demonstrativo: publicação ausente, troca de lote, catálogo/schema incompatível, gate bloqueado, falha de banco, de modelo ou de auditoria terminam em erro público ou esclarecimento. A composição externa (`create_gold_app`) recusa acesso demonstrativo e evidência `is_demo`; o Backend em modo Gold não chama o cliente sintético.

## 9. Schema, fórmula, catálogo e migração

| Mudança | Comportamento exigido |
| --- | --- |
| Coluna renomeada ou removida no schema `gold_v2` | A consulta falha fechada (503 `service_unavailable`); sem resposta parcial, sem coluna substituta, sem demo. A carga v2 já rejeita schema divergente do contrato. |
| Tipo de coluna alterado | O mesmo: falha fechada na execução ou na validação da evidência; não converter silenciosamente. |
| Fórmula, agregação ou relação alterada no catálogo | Novo digest do catálogo físico; chaves de cache antigas deixam de corresponder; exemplos e resultados dependentes são invalidados. |
| GenAI e Backend com catálogos físicos diferentes (implantação defasada) | O plano declara o catálogo sob o qual foi produzido; o Backend recusa executar plano de outro catálogo (503, `retryable=false`). |
| Migração/rollback de schema incompatível | Publicação inexistente ou inválida → 503 `retryable=false`. Retorno a uma publicação anterior gera outro `publication_id` e, portanto, é troca de publicação (409). |
| Catálogo antigo (v1) | Nunca serve de fallback do fluxo v2; referência v1 em fluxo v2 é rejeitada. |

## 10. Estado atual no código

### Já existe

- Publicação capturada e revalidada em todas as fronteiras do chat Gold, com 409 `invalid_context` (`backend/app/services/genai_publication.py`, `genai_coordination.py`, `endpoints/ai.py`).
- Snapshot `REPEATABLE READ READ ONLY` que descarta o resultado se a publicação mudar durante a consulta.
- Escopo reresolvido após SQL, síntese e auditoria (403).
- `EvidenceGuard` exigindo `expected_batch_ref` para fonte Gold e conferindo `quality` e `provenance.batch_ref`.
- Pinagem `expected_lote`/`expected_fingerprint` nas leituras analíticas (409 `stale_batch`) e `loteVersao` no insight (409).
- Cache de modelo autorizado antes do acerto, isolado por identidade, com namespace contendo provedores, modelos e digest do prompt, e chave contendo a evidência completa; desligado por padrão (`GENAI_MODEL_CACHE_TTL_SECONDS=0`). `cache_scope` do Backend com chamador, perfil, fonte, operações, métricas, dimensões, plano e `batch_ref`.
- Composição externa recusando demonstração e evidência `is_demo`.
- Consulta do insight no portal com chave `filters` + `loteVersao` e cancelamento por `AbortSignal`.

### Falta

| Lacuna | Fase |
| --- | --- |
| Catálogo físico (`mapping_version` + digest), `physical_schema` e `dictionary_version` fora da chave de cache e do `cache_scope`; o plano não declara o catálogo físico sob o qual foi produzido | 2 |
| Filtros não normalizados na chave (ordem de filtros e de valores de `in` muda a chave; gera falta de acerto, não acerto indevido) | 2 |
| Chat sem publicação esperada informada pelo consumidor | 2 (servidor); consumidor no GENAI-11 |
| Sem teste dedicado de schema renomeado/tipo alterado, rollback incompatível, catálogo defasado entre serviços e erro após cache válido no fluxo Gold | 2 |
| Busca do catálogo no coordenador por `next(...)` sem tratamento: métrica ausente no catálogo do Backend escaparia como erro interno em vez de 503 | 2 |
| Assistente sem descarte de resposta atrasada por revisão de recorte em `develop` (identidade/rota está na branch do GENAI-11) | 11 |
| Chave do insight no portal sem `fingerprint`; insight Gold ainda desabilitado (fonte não demonstrativa) | 12 |

## 11. Itens do cartão e provas

Testes "existente" estão em `develop`. "Fase 2" serão arquivos novos de servidor. "Pendente" depende de outro cartão e não será marcado com skip ou xfail silencioso; permanece listado aqui até a prova.

| Item | Prova | Situação |
| --- | --- | --- |
| I1 — vincular plano, evidência, contexto de tela e cache às versões de catálogo, lote e escopo | `backend/tests/test_genai_publication.py::test_changed_publication_blocks_each_boundary`; `ai-agent/tests/test_resilient_adapters.py::test_cache_separates_identities_with_identical_question_and_evidence`; `test_groq_adapter.py::test_cache_namespace_separates_provider_order_models_and_prompt`; novos `backend/tests/test_genai_invalidation.py` (catálogo físico no `cache_scope`) e `ai-agent/tests/test_gold_cache_invalidation.py` (catálogo/schema/prompt/modelo na chave) | Existente parcial + Fase 2 |
| I2 — invalidar dependentes de schema ou fórmula; rejeitar incompatibilidade com mensagem recuperável | Novos `test_genai_invalidation.py` (schema renomeado, tipo alterado, plano de catálogo defasado → 503 sem demo) | Fase 2 |
| I3 — erro/desatualização prevalece sobre cache no cartão e no painel de insight | Servidor: novo `test_gold_cache_invalidation.py` (erro após cache válido); tela: `PanoramaInsight.test.tsx` com 409 após cache | Fase 2 (servidor); tela pendente do GENAI-12 |
| I4 — resposta atrasada não sobrescreve o recorte atual; mudanças rápidas e cancelamento | Tela do Assistente e do insight (revisão por pedido) | Pendente do GENAI-11 e do GENAI-12 |
| I5 — detectar troca de lote durante a requisição; leitura consistente | `test_genai_publication.py::test_change_during_query_keeps_snapshot_but_rejects_result`; `test_gold_analytics_postgres.py::test_gold_dependency_holds_repeatable_read_only_snapshot_across_publication`; novo `test_genai_invalidation.py` (troca entre SQL e síntese → 409 sem resposta) | Existente + Fase 2 |
| I6 — atualização de lote, catálogo antigo, recarga e rollback sem demo | `test_genai_publication.py::test_same_run_with_new_publication_is_still_a_change`, `::test_invalidated_publication_does_not_allow_retry`; `ai-agent/tests/test_external_source_composition.py::test_external_source_never_publishes_demo_evidence`; novos `test_genai_invalidation.py` (rollback, catálogo antigo, publicação esperada divergente) | Existente + Fase 2 |
| R1 — chave com fonte, escopo, métrica, dimensões, filtros normalizados, janela, ordem, limite, unidade e versões; autorizar antes | `test_resilient_adapters.py::test_authorization_runs_before_cache_hit_and_separates_callers`; novo `test_gold_cache_invalidation.py` (cada componente altera a chave; filtros reordenados mantêm a chave) | Existente parcial + Fase 2 |
| R2 — consistência do lote durante a leitura e antes de publicar | Mesmos testes de I5 e `test_genai_publication.py::test_change_before_query_does_not_enter_execution_block` | Existente + Fase 2 |
| R3 — schema renomeado, tipo/fórmula/relação alterados, migração/rollback; TTL sozinho não resolve | Novos `test_genai_invalidation.py` e `test_gold_cache_invalidation.py` (mudança de catálogo invalida antes do TTL) | Fase 2 |
| R4 — revisão/ID de pedido no recorte; ida e volta de filtros; revogação de escopo; erro após cache válido | Servidor: revogação de escopo → 403 (matriz pública existente) e erro após cache (Fase 2); tela: revisão por pedido, A → B → A e revogação no insight | Servidor existente + Fase 2; tela pendente do GENAI-11/12 |
