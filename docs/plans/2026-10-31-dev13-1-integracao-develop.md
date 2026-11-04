# DEV-13.1 — integração com a develop

**Data:** 31/10/2026. **PR:** [#86](https://github.com/GuilhermeRangel1/git-or-treat/pull/86). **Referências revisadas:** DEV-13.1 `24338148cfe3ed20d4e85871cce2dd7520ef22f7`; develop `90795e862a351f513e2254db7969fc6b57de59a4`.

## Integração e preservação

Merge normal da develop na DEV-13.1, preservando os dois históricos. O único conflito textual ocorreu no índice de decisões, pois os dois lados haviam usado ADR-0018. A decisão de janelas relativas GenAI mantém o número 0018 e o arquivo original; a decisão da API passa a [ADR-0021](../decisions/0021-api-gold-dev13-1.md), com referências atualizadas e conteúdo, data e estado preservados. O [contrato da API](../contracts/analytics-gold-dev13-1.md) agora distingue cookie de sessão do portal e Bearer exclusivo do modo de serviço.

Na combinação revisada, `ai-agent/`, o endpoint Backend `app/api/v1/endpoints/ai.py` e os módulos Backend `app/services/genai_client.py`, `genai_planning.py`, `genai_publication.py` e `app/schemas/genai_internal.py` ficaram idênticos à develop. A adaptação de autenticação por sessão da DEV-13.1 permanece conforme a [ADR-0020](../decisions/0020-autenticacao-backend-por-sessao.md).

## Verificações observadas

As suítes abaixo foram executadas durante a revisão do resultado combinado, antes dos ajustes finais de documentação. Esses ajustes não alteram o código testado. Python usou ambiente isolado com as dependências Backend declaradas; PostgreSQL 16 usou container descartável com fixtures artificiais, removido ao terminar.

| Área e comando | Resultado |
| --- | --- |
| `ai-agent/`: `python -m pytest -q -p no:cacheprovider --tb=short` | 3.686 passaram, 4 skips, 1 xfail conhecido; 47,97 s |
| `backend/`: `python -m pytest -q -p no:cacheprovider --tb=short` | 825 passaram, 100 skips de infraestrutura/execução opt-in; 243,82 s |
| `backend/` com PostgreSQL 16: `python -m pytest -q -p no:cacheprovider --tb=short tests/test_migrations.py tests/test_gold_analytics_postgres.py tests/test_gold_inspections_orders_postgres.py tests/test_gold_operations_http_postgres.py tests/test_gold_reader.py` | 17 passaram, 1 skip por pacote privado; 20,85 s |
| `frontend/`: `npm test -- --pool=threads --maxWorkers=2 --reporter=dot` | 344 passaram, 1 skip; 45 arquivos passaram |
| `frontend/`: `npm run build` | passou |
| `frontend/`: `npm run lint`, `npm run check:boundaries`, `npm run format:check` | passaram; lint com aviso `react(set-state-in-effect)` em AuthProvider |
| `backend/`: `python -m alembic heads` | único head `merge_gold_v2_auth` |
| Validador documental do workflow aplicado aos arquivos versionados | configurações/imports válidos; links verificados em 128 documentos |
| Comparação de conteúdo após os ajustes documentais | 145 arquivos de código DEV-13.1 preservados; núcleo e módulos GenAI conferidos idênticos à develop; conteúdo original da ADR da API preservado |
| Verificação de IDs/referências ADR e `git diff --cached --check` | IDs únicos; referências antigas removidas; diff válido e nenhum conflito pendente |

Os cinco checks do head original do PR estavam aprovados. A CI do novo commit combinado precisa ser conferida após sua publicação.

## Limites mantidos

- Não houve reconciliação com o pacote Gold privado nem revisão visual manual nesta rodada. Os skips não representam verificações executadas.
- Panorama expõe receita comparável (`receita_base_comparavel_reais`), enquanto `billing.revenue` GenAI usa receita total (`receita_total_reais`). A futura reconciliação portal/IA precisa comparar a mesma população e definição.
- As permissões de sessão `orders:read/write` não implementam escopos Gold da GenAI por domínio. Executor, coordenação, autorização Gold e insight real continuam nas respectivas entregas GENAI-05/06/07/12.
- As migrações operacionais e a provisão de contas precisam ser executadas explicitamente no ambiente escolhido. O merge não realiza essas operações.
- Nenhum requisito oficial WEB, IA ou DE muda para Concluído por esta integração. Os estados do PRD permanecem vigentes.
