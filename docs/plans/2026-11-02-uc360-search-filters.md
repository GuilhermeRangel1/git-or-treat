# Filtros de busca da UC 360 — Implementation Plan

> **For agentic workers:** Executar este plano tarefa por tarefa, em sequência, com TDD por fatia.

**Goal:** Permitir buscar UCs por número, município e classe, isoladamente ou combinados, mantendo os critérios na URL e na volta do detalhe.

**Architecture:** O endpoint existente `/api/v1/ucs` aplica os critérios antes de ordenar e paginar, tanto na fonte sintética quanto na Gold v2. O frontend usa o catálogo `/api/v1/analytics/options`, guarda o recorte aplicado na URL e continua usando a rota de detalhe existente.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, React, TypeScript, React Router, TanStack Query, Vitest, pytest.

**Spec:** `docs/plans/2026-11-02-uc360-search-filters-design.md`

## Global Constraints

- WEB-03 permanece Em andamento; esta alteração não declara aceite funcional integral.
- Os valores de município e classe vêm do catálogo da publicação ativa; não introduzir listas fixas.
- Filtros da API precedem paginação e ordenação, preservando total/páginas.
- Sem número, município ou classe, a interface não dispara a consulta.
- Resultado e catálogo não podem misturar publicações Gold; não expor nome/referência pessoal na busca.
- Preservar compatibilidade com URLs atuais, incluindo rotas legadas `?uc=`.

## Review Focus

- Busca só por município/classe: a API retorna todos e pagina apenas as UCs correspondentes.
- Busca por texto combinada com filtros: critérios são intersectados, sem retornar unidade fora do recorte.
- URL sem critérios: a interface não consulta nem exibe uma listagem irrestrita.
- Opção inválida ou inexistente na URL: a consulta retorna zero resultados ou validação clara, sem erro interno.
- Mudança de publicação: catálogo e resultados não são combinados; os filtros aplicados continuam visíveis.

## Mapa de arquivos

- `backend/app/api/v1/endpoints/ucs.py`: parâmetros HTTP opcionais `municipio` e `classe`.
- `backend/app/services/uc_analytics.py`: assinatura e filtragem da busca sintética.
- `backend/app/services/gold_uc.py`: predicados exatos para o cadastro Gold v2.
- `backend/tests/test_analytics_ucs.py` e `backend/tests/test_gold_uc_v2.py`: contratos sintético e Gold.
- `frontend/src/features/uc360/uc360-state.ts`: estado aplicado `municipio`/`classe` e aplicação dos critérios.
- `frontend/src/features/uc360/uc360-state.test.ts`: validação e serialização da URL.
- `frontend/src/features/uc360/useUC360.ts`: chave/URL de consulta com critérios opcionais.
- `frontend/src/features/uc360/UC360SearchPanel.tsx`: controles, validação e estados do formulário/resultados.
- `frontend/src/features/uc360/UC360Page.tsx`: catálogo, execução, seleção e retorno ao contexto completo.
- `frontend/src/features/uc360/UC360Page.test.tsx` e `gold-provenance.test.tsx`: busca, combinação, filtro sem texto, paginação e retorno.
- `docs/services/frontend.md`, `docs/contracts/uc360-gold-v2.md` e `docs/PRD.md`: comportamento e evidência.

### Task 1: Filtrar busca no Backend

**Interfaces:** `build_uc_search(repository, q, municipio, classe, page, page_size, order_by)` e `gold_uc.search` recebem filtros opcionais; endpoint conserva resposta e paginação atuais.

- [x] Adicionar teste sintético de filtros isolados e combinados e confirmar falha antes de alterar código.
- [x] Implementar parâmetros opcionais no router e filtrar antes de `page_items`.
- [x] Adicionar teste Gold v2 que prove critérios exatos aplicados antes de `repository.page`; executar e corrigir.
- [x] Preservar validações anteriores de `q`, `order_by` e paginação; rodar `pytest -q tests/test_analytics_ucs.py tests/test_gold_uc_v2.py`.

### Task 2: Aplicar critérios do frontend na URL e na consulta

**Interfaces:** estado parseado expõe `municipio` e `classe`; `useUCSearch` recebe `(q, municipio, classe, page, enabled)`; submit recebe os três critérios.

- [x] Escrever testes de URL para leitura, aplicação/reset de página e critérios duplicados; confirmar falha.
- [x] Implementar parser e helper sem descartar período.
- [x] Escrever teste do hook que verifica parâmetros e identidade na query key; implementar a consulta com todos os critérios.
- [x] Rodar testes de estado e hook.

### Task 3: Montar a jornada no portal

**Interfaces:** `UC360Page` usa `useSourceOptions`; `UC360SearchPanel` recebe valores aplicados, catálogo, estado de carregamento/erro e callbacks de submit/retry.

- [x] Testar bloqueio de busca sem critérios e envio só com município, só com classe e com texto mais filtros; confirmar falhas.
- [x] Implementar selects “Todos” usando `municipio` e `classe` retornados pelo catálogo; manter busca por texto disponível se o catálogo falhar.
- [x] Testar mudança de página, seleção do resultado e retorno preservando texto, município, classe e período; confirmar falha antes do ajuste.
- [x] Serializar critérios no detalhe e no link “Voltar à busca”; desabilitar consulta enquanto detalhe está aberto.
- [x] Executar a suíte da feature UC360 e corrigir estados vazio, erro e carregamento.

### Task 4: Documentar e verificar a entrega

- [x] Atualizar guia do serviço, contrato UC Gold v2 e registro de progresso do PRD sem alterar o estado oficial WEB-03.
- [x] Rodar `pytest -q tests/test_analytics_ucs.py tests/test_gold_uc_v2.py` no Backend.
- [x] Rodar `npm.cmd test -- src/features/uc360 --run`, `npm.cmd run format:check`, `npm.cmd run lint`, `npm.cmd run build` e `git diff --check`.
- [x] Revisar o diff completo, preservando todas as alterações locais fora do escopo.
