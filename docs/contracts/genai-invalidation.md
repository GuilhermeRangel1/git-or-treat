# GENAI-13 — Contrato de invalidação por lote, filtro e schema

**Cartão:** GENAI-13. **Requisitos:** IA-03, IA-04, IA-05, IA-06. **Natureza:** contrato e integração executável no servidor (fase 2). Não conclui requisitos; as provas de tela dependem do GENAI-11 e do GENAI-12. Base inspecionada: `develop` em `b804b58`.

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

O chat aceita, de forma **opcional e retrocompatível**, a publicação que a tela está exibindo, com o mesmo par já usado pela API analítica:

```json
{"question": "...", "context": [], "expected_publication": {"lote": "<lote exibido>", "fingerprint": "<64 hex>"}}
```

- Ausente: comportamento anterior (captura no servidor e detecção de troca durante a requisição).
- Presente e igual à publicação atual: o Backend converte o par no `batch_ref` atual e o planejamento exige capturar exatamente essa referência. Uma troca entre essa conferência e a captura é mudança em curso (409, `retryable=true`).
- Presente e diferente: 409 `invalid_context`, `retryable=false`, antes do planejamento, do SQL e do modelo.
- Malformada ou com campo extra: 422 `invalid_request`.
- Modo sintético: o campo é rejeitado (422), como já ocorre com `expected_lote` nas leituras analíticas.
- Publicação ausente ou não v2: 503 `service_unavailable`, `retryable=false`.

Esse valor não autoriza nada: apenas impede responder sobre um lote diferente do que a pessoa está vendo. O campo fica no modelo público `AIQuestionPublicRequest` (`backend/app/schemas/ai_question_publication.py`), subclasse de `AIQuestionRequest`; ele é removido antes de qualquer envelope interno ou chamada à GenAI, que não muda. O consumidor do portal fica com o GENAI-11.

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
| Coluna renomeada ou removida no schema `gold_v2` | A consulta falha fechada (503 `service_unavailable`, `retryable=false`); sem resposta parcial, sem coluna substituta, sem demo. O executor converte os SQLSTATE `42703`, `42P01`, `42883` e `42804` em incompatibilidade de catálogo. A carga v2 já rejeita schema divergente do contrato. |
| Tipo de coluna alterado | O mesmo: falha fechada na execução; não converter silenciosamente. |
| Fórmula, agregação ou relação alterada no catálogo | Novo digest do catálogo físico; chaves de cache antigas deixam de corresponder; exemplos e resultados dependentes são invalidados. |
| GenAI e Backend com catálogos físicos diferentes (implantação defasada) | O plano declara `physical_catalog`; o Backend recusa executar plano de outro catálogo (503, `retryable=false`) e a GenAI recusa evidência de catálogo diferente do seu perfil. Métrica ausente no catálogo do Backend também é 503, não erro interno. |
| Migração/rollback de schema incompatível | Publicação inexistente ou inválida → 503 `retryable=false`. Retorno a uma publicação anterior gera outro `publication_id` e, portanto, é troca de publicação (409). |
| Rollback para publicação v1 | O planejamento recusa publicação diferente de `gold-csv-v2` (503, `retryable=false`): o executor lê somente `gold_v2` e não pode responder com dados v2 sob identidade v1. |
| Catálogo antigo (v1) | Nunca serve de fallback do fluxo v2; referência v1 em fluxo v2 é rejeitada. |

### Identidade do catálogo físico

`physical_catalog` = `mapping_version` (`gold-catalog-v2`), `physical_schema` (`gold_v2`), `dictionary_version` (`gold-csv-v2`) e `digest`, SHA-256 do JSON canônico (`sort_keys`, separadores compactos, UTF-8) do catálogo. O Backend calcula o digest de `backend/app/catalogs/gold_v2.json`; a GenAI, de `GRID360_GOLD_MAPPING.model_dump(mode="json")`, que um teste existente exige ser idêntico ao arquivo. Nenhum serviço importa o outro.

O campo é opcional em `QuestionPlanResponse` (somente em `planned`) e em `EvidenceProvenance`, nos dois serviços, e não é serializado quando ausente. Compatibilidade:

- Plano sem `physical_catalog` (GenAI anterior): o Backend aceita. Evidência sem o campo (Backend anterior): a GenAI aceita. A conferência vale quando os dois lados declaram.
- Ordem de implantação: GenAI primeiro (passa a aceitar e emitir o campo), depois Backend. Um Backend novo enviando evidência com o campo para uma GenAI anterior seria recusado por campo extra.
- A composição implantável `create_gold_app` usa `GRID360_GOLD_RUNTIME_PROFILE`, que carrega a identidade; o perfil lógico `GRID360_GOLD_PROFILE` permanece sem ela.

## 10. Estado atual no código

### Implementado no servidor (fase 2)

- Publicação capturada e revalidada em todas as fronteiras do chat Gold, com 409 `invalid_context` `retryable=true` (`genai_publication.py`, `genai_coordination.py`, `endpoints/ai.py`), e snapshot `REPEATABLE READ READ ONLY` que descarta o resultado se a publicação mudar durante a consulta (existente).
- Publicação esperada opcional no chat, com 409 `retryable=false` quando diverge (`ai_question_publication.py`, `genai_expected_publication.py`).
- Recusa de publicação não v2 no planejamento.
- Catálogo físico declarado no plano (`routes.py` da GenAI) e na evidência (executor), conferido pelo Backend (`genai_planning.py`) e pelo `EvidenceGuard`.
- Métrica ausente no catálogo do Backend e deriva de schema convertidas em 503 `retryable=false` (`GoldCatalogIncompatible`).
- Chave do cache de modelo v2 com filtros normalizados e catálogo físico da proveniência; namespace com provedores, modelos e digest do prompt (existente); `authorized_cache_scope` com filtros normalizados. `cache_scope` do Backend com escopo, plano com filtros normalizados, `batch_ref`, catálogo físico e versão de prontidão. O `plan_fingerprint` não muda.
- Escopo reresolvido após SQL, síntese e auditoria (403), pinagem `expected_lote`/`expected_fingerprint` nas leituras analíticas e `loteVersao` no insight (existentes).
- O cache de modelo continua desligado por padrão (`GENAI_MODEL_CACHE_TTL_SECONDS=0`).

### Falta

| Lacuna | Dono |
| --- | --- |
| Assistente sem descarte de resposta atrasada por revisão de recorte em `develop` (identidade/rota está na branch do GENAI-11) e sem envio de `expected_publication` | GENAI-11 |
| Chave do insight no portal sem `fingerprint`; insight Gold ainda desabilitado (fonte não demonstrativa); corrida de filtros e revogação na tela | GENAI-12 |
| Tornar `physical_catalog` obrigatório depois que os dois serviços estiverem implantados | Decisão posterior, fora deste cartão |

## 11. Itens do cartão e provas

"Existente" está em `develop`. "Fase 2" são os arquivos novos `ai-agent/tests/test_gold_cache_invalidation.py`, `backend/tests/test_genai_invalidation.py` e `backend/tests/test_genai_invalidation_postgres.py` (este exige o PostgreSQL descartável `v_energy_test`). "Pendente" depende de outro cartão e não é marcado com skip ou xfail; permanece listado aqui até a prova.

| Item | Prova | Situação |
| --- | --- | --- |
| I1 — vincular plano, evidência, contexto de tela e cache às versões de catálogo, lote e escopo | Existentes: `test_genai_publication.py::test_changed_publication_blocks_each_boundary`, `test_resilient_adapters.py::test_cache_separates_identities_with_identical_question_and_evidence`, `test_groq_adapter.py::test_cache_namespace_separates_provider_order_models_and_prompt`. Fase 2: `test_gold_cache_invalidation.py::test_official_runtime_declares_physical_catalog_only_on_ready_plans`, `::test_cache_key_changes_with_catalog_batch_and_readiness`, `::test_cache_key_separates_prompt_and_model_through_namespace`; `test_genai_invalidation.py::test_matching_publication_pins_planning_to_the_captured_batch`; `test_genai_invalidation_postgres.py::test_executor_declares_catalog_and_scopes_cache_by_catalog_not_filter_order` | Servidor provado; contexto de tela pendente do GENAI-11/12 |
| I2 — invalidar dependentes de schema ou fórmula; rejeitar incompatibilidade com mensagem recuperável | `test_genai_invalidation_postgres.py::test_schema_drift_fails_closed_as_incompatible_and_recovers` (coluna renomeada, tipo alterado, tabela renomeada); `test_genai_invalidation.py::test_plan_from_another_physical_catalog_is_rejected_before_admission`, `::test_metric_missing_from_backend_catalog_is_incompatible_not_invalid`, `::test_metric_missing_in_coordinator_is_incompatible_before_sql`, `::test_route_maps_change_and_incompatibility_to_recoverable_errors`; `test_gold_cache_invalidation.py::test_formula_change_changes_catalog_digest`, `::test_evidence_from_other_physical_catalog_is_rejected_before_model` | Fase 2 |
| I3 — erro/desatualização prevalece sobre cache no cartão e no painel de insight | Servidor: `test_gold_cache_invalidation.py::test_error_after_valid_cache_prevails_over_cached_answer`. Tela: `PanoramaInsight.test.tsx` com 409 após cache (caso T-05) | Servidor provado; tela pendente do GENAI-12 |
| I4 — resposta atrasada não sobrescreve o recorte atual; mudanças rápidas e cancelamento | Casos T-01, T-02 e T-04 abaixo | Pendente do GENAI-11 e do GENAI-12 |
| I5 — detectar troca de lote durante a requisição; leitura consistente | Existentes: `test_genai_publication.py::test_change_during_query_keeps_snapshot_but_rejects_result`, `test_gold_analytics_postgres.py::test_gold_dependency_holds_repeatable_read_only_snapshot_across_publication`. Fase 2: `test_genai_invalidation.py::test_batch_change_between_sql_and_synthesis_never_synthesizes`, `::test_publication_replaced_before_capture_is_a_retryable_change` | Fase 2 |
| I6 — atualização de lote, catálogo antigo, recarga e rollback sem demo | Existentes: `test_genai_publication.py::test_same_run_with_new_publication_is_still_a_change`, `::test_invalidated_publication_does_not_allow_retry`, `test_external_source_composition.py::test_external_source_never_publishes_demo_evidence`. Fase 2: `test_genai_invalidation.py::test_rollback_to_v1_publication_is_rejected_before_planning`, `::test_missing_or_v1_publication_is_unavailable_without_fallback`, `::test_divergent_publication_is_a_non_retryable_conflict`, `::test_synthetic_mode_rejects_publication_and_forwards_the_unchanged_contract`; `test_gold_cache_invalidation.py::test_evidence_without_catalog_keeps_compatibility` | Fase 2 |
| R1 — chave com fonte, escopo, métrica, dimensões, filtros normalizados, janela, ordem, limite, unidade e versões; autorizar antes | Existente: `test_resilient_adapters.py::test_authorization_runs_before_cache_hit_and_separates_callers`. Fase 2: `test_gold_cache_invalidation.py::test_cache_key_normalizes_filter_order_without_changing_plan_fingerprint`, `::test_authorized_scope_isolates_access_and_ignores_filter_order`; `test_genai_invalidation_postgres.py::test_executor_declares_catalog_and_scopes_cache_by_catalog_not_filter_order` | Fase 2 |
| R2 — consistência do lote durante a leitura e antes de publicar | Mesmos testes de I5 e `test_genai_publication.py::test_change_before_query_does_not_enter_execution_block` | Fase 2 |
| R3 — schema renomeado, tipo/fórmula/relação alterados, migração/rollback; TTL sozinho não resolve | Testes de I2 e I6; `test_gold_cache_invalidation.py::test_catalog_change_invalidates_cache_before_ttl_expires` | Fase 2 |
| R4 — revisão/ID de pedido no recorte; ida e volta de filtros; revogação de escopo; erro após cache válido | Servidor: revogação → 403 (matriz pública existente) e `test_error_after_valid_cache_prevails_over_cached_answer`. Tela: casos T-04, T-05 e T-06 | Servidor provado; tela pendente do GENAI-11/12 |

### Casos de tela pendentes (GENAI-11 e GENAI-12)

Escritos aqui para a implementação nas telas; ainda não existem como teste marcado.

| ID | Tela | Caso | Resultado esperado |
| --- | --- | --- | --- |
| T-01 | Assistente | Pergunta enviada com o recorte A; troca para B antes da resposta | Resposta de A é descartada; nada é exibido como resposta de B |
| T-02 | Assistente | Troca de identidade ou de rota com pedido pendente | Pedido descartado e histórico local limpo (parte já existe na branch do GENAI-11) |
| T-03 | Assistente | Envio de `expected_publication` com o lote exibido; servidor responde 409 `retryable=false` | Mensagem pede recarregar a tela; não oferece repetir o mesmo pedido |
| T-04 | Insight | Filtros A → B → A rapidamente | Somente a resposta da revisão vigente é aplicada; resposta tardia é descartada |
| T-05 | Insight | Cache válido e, em seguida, 409 para o mesmo recorte | O erro de desatualização prevalece sobre o insight em cache |
| T-06 | Insight | Revogação de escopo com insight pendente ou em cache | Pendente descartado; cache daquela identidade não é exibido |
| T-07 | Insight | Mudança de `fingerprint` com o mesmo `loteVersao` | Insight anterior invalidado (a chave da consulta precisa incluir o fingerprint) |

## Continuação integrada de 01/11/2026

As tabelas anteriores descrevem o histórico dos PRs #95/#97 e as lacunas existentes naquela base. GENAI-11/12 já foram integrados à develop; a continuação `feat/genai-invalidacao-contexto` completa o fingerprint esperado do insight e a invalidação por revisão no portal. O Assistente envia a publicação analítica conhecida; sem essa publicação, usa a captura do servidor e invalida respostas anteriores quando o batch_reference muda. Erro de uma requisição antiga não invalida a publicação nova.

O insight Gold já está habilitado, sua chave inclui fingerprint e a geração local; desatualização conhecida não é exibida como carregamento nem como sucesso antigo. O resolvedor de publicação esperada usa `gold.publicacao_contexto` no PostgreSQL. O campo fingerprint do insight é opcional para compatibilidade do cliente anterior, validado quando presente e emitido pelo servidor Gold atual.

Mapa atualizado I1–I6/R1–R4, casos de tela, comandos, fonte real versus controlada e limites: [evidência integrada](../plans/2026-11-01-genai13-invalidacao-integrada.md). Os registros de pendência das seções 10/11 são históricos e devem ser lidos junto desta continuação. Não tornam `physical_catalog` obrigatório nem encerram requisitos oficiais automaticamente.
