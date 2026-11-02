# GENAI-13 — Invalidação integrada no portal

Data: 01/11/2026. Branch `feat/genai-invalidacao-contexto`, base `develop` em `15aa037`. Escopo: integração executável e conferência de identidade na Gold v2 local. Complementa os PRs #95/#97 sem copiar seus commits. Implementação desta continuação nos commits `35d3984` (Backend) e `3d1d1ae` (portal), com evidências e roteiro em commit próprio na mesma branch.

## Caminho e comportamento

Portal → Backend → planejamento GenAI → executor restrito/snapshot → síntese → auditoria → revalidação → consumidor. Nenhum novo executor ou catálogo paralelo.

O Assistente envia `expected_publication` quando já conhece a publicação analítica. A entrada direta, ainda sem esse metadado, preserva a captura do servidor; se uma resposta posterior declarar outro `batch_reference`, as respostas anteriores deixam de aparecer como atuais. Atualização da publicação invalida histórico de interpretação e retentativas. Erros atrasados não invalidam uma geração nova. 401/403/409 retiram evidências anteriores do contexto utilizável.

O insight envia o fingerprint visto nos KPIs. O Backend confere publicação esperada antes da prontidão/consulta/modelo, fixa a referência e confere novamente os metadados. A resposta declara fingerprint; o consumidor rejeita divergência mesmo com lote, timestamp ou números coincidentes. O resolvedor PostgreSQL usa `gold.publicacao_contexto`, preservando os privilégios mínimos existentes.

A revisão de publicação (geração, identidade e estado de desatualização) participa da chave do insight. Desatualização conhecida prevalece sobre cache e carregamento; respostas canceladas ou de revisão anterior não substituem o recorte vigente. O botão global de atualização cancela/reseta também as consultas de insight.

## Mapa de aceite

| Item | Evidência desta entrega e regressão existente |
| --- | --- |
| I1 — versões e escopo | fingerprint no pedido/resposta; `api.test.ts`, `GoldInsight.test.tsx`; catálogo/plano/cache em `test_gold_cache_invalidation.py` e `test_genai_invalidation_postgres.py`. |
| I2 — schema/fórmula incompatíveis | PostgreSQL: coluna, tipo e tabela alterados recusados e recuperação após restaurar; digest de fórmula e rejeição de catálogo divergente no núcleo. |
| I3 — erro prevalece sobre cache | `PanoramaInsight.test.tsx`, cartão/painel com desatualização explícita; roteiro Chromium com sucesso seguido de 409. |
| I4 — corridas e cancelamento | `InsightInvalidation.test.tsx`: A→B→A com transporte que ignora cancelamento; resposta antiga não é aplicada. Roteiro Chromium: sair da rota com chat pendente. |
| I5 — troca durante requisição | snapshot PostgreSQL e revalidação antes/depois da síntese; `test_genai_publication.py`, `test_genai_invalidation.py`; fingerprint e troca entre preflight/captura recusados. |
| I6 — recarga/rollback sem demo | regressões de publicação substituída, rollback v1, ausência e captura inválida; composição externa sem fallback. |
| R1 — chave completa e autorização | regressões do cache do núcleo e cache_scope do executor, filtros normalizados; geração de autorização/publicação no consumidor; permissões reaplicadas no servidor. |
| R2 — leitura/publicação consistentes | snapshot `REPEATABLE READ READ ONLY` e rejeição de troca concorrente no PostgreSQL. |
| R3 — semântica e migração | catálogo físico com digest, drift recusado, rollback v1 bloqueado; não depender apenas de TTL. |
| R4 — revisão, revogação e cache | resposta e erro atrasados após refresh, A→B→A, mudança de fingerprint com mesmo lote, 403 retirando evidência anterior, 409 após cache. |

## Verificações observadas

- Backend: `python -m pytest -q tests/test_genai_invalidation.py tests/test_genai_invalidation_postgres.py tests/test_genai_publication.py tests/test_gold_panorama_coordination.py tests/test_ai_insights.py --tb=short`: **96 passaram, quatro skips**. PostgreSQL 16 descartável, papel `venergy_migrator` sem superusuário; dados artificiais. Os skips pertencem à parametrização de dialetos: um caso de recusa SQLite não se aplica ao PostgreSQL e três provas de snapshot não se aplicam ao SQLite; as respectivas variantes aplicáveis passaram.
- Núcleo: `python -m pytest -q tests/test_gold_cache_invalidation.py --tb=short`: **12 passaram**. Sem alteração funcional no núcleo nesta continuação.
- Gold v2 local: somente leitura, publicação/fingerprint coincidentes entre operacional e leitor restrito; o mesmo resolvedor funciona com papel sem SELECT na tabela operacional. Fingerprint divergente recusado. Não houve nova chamada Gemini, carga ou alteração de permissões/publicação.
- Navegador: `INVALIDATION_BASE_URL=http://127.0.0.1:5185 npm run test:invalidation`: passou com Playwright 1.64.1/Chromium, portal real e sessão/respostas artificiais. Confere fingerprint enviado, sucesso seguido de 409, ocultação de hipótese anterior, chat vinculado à publicação e saída/retorno de rota com resposta pendente. Não constitui nova reconciliação numérica Gold nem avaliação do provedor.
- Context7/TanStack Query v5: cancelamento com `AbortSignal` e retorno ao estado anterior; a interface não presume que `enabled=false` apague cache. Fonte: https://github.com/tanstack/query/blob/main/docs/framework/react/guides/query-cancellation.md .

## Limites

Os resultados numéricos Gold e as jornadas com Gemini de GENAI-11/12 permanecem nas evidências originais. Esta entrega prova invalidação, não amplia a cobertura do lote, não certifica fechamento mensal e não conclui automaticamente IA-03/04/05/06. Cancelamento de transporte não afirma cancelamento imediato de SQL; o servidor continua impondo snapshot e prazos próprios. `physical_catalog` permanece opcional na compatibilidade entre serviços, conforme o contrato aprovado.


## Fechamento da revisão técnica

Dez aceites técnicos contemplados, sem redução dos critérios do cartão. Revisões separadas de especificação e padrões apontaram erros atrasados contaminando geração nova, carregamento indevido após stale, leitura de metadados operacionais e turnos antigos do chat direto; corrigidos e reconferidos, sem bloqueio remanescente.

Frontend: seleção Assistente/Panorama/publicação/aviso global — **80 passaram**. Após ampliar o caso A→B→terceira pergunta, os **19 testes de AssistentePage passaram** novamente. Build, format:check e fronteiras passaram; lint sem erros, com aviso preexistente em AuthProvider.tsx. Ruff dos seis arquivos Python alterados passou (EXE002 ignorado por bit executável artificial do volume Windows); diff-check passou. O roteiro Chromium teve uma asserção antecipada à conclusão da navegação, corrigida para aguardar a nova tela; reexecução passou.

O aceite técnico local não altera os estados oficiais IA nem presume produção. A entrega segue para revisão por PR; esta documentação não autoriza merge.
