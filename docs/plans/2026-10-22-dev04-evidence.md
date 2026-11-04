# DEV-04 — Evidências e revisão da demonstração UC 360

**Data:** 22/10/2026. **Branch:** `dev04`, base `develop` `54534a7b79f5eef3739a3055b8289261854fd5de`. **Requisito:** WEB-03, ainda `Pendente` para aceite Gold. **Revisão:** esta sessão, após implementação separada por dois subagentes GPT-6 Luna/high.

## Escopo entregue

- API: busca legada da DEV-01 preservada; novos `GET /api/v1/ucs/{uc_id}/overview` e `GET /api/v1/ucs/{uc_id}/history/{section}` com comparação mensal, seis históricos, paginação e cobertura sintética declarada por UC/fonte/medida. `docs/contracts/uc360-dev04.md` e ADR-0009 registram a semântica.
- Portal: busca editável, seleção explícita, URL de UC/período/seção/página, quatro indicadores comparativos, histórico de consumo/faturas/pagamentos/medidores/GD/interrupções/chamados, contexto e distinção entre fatos e hipóteses. A fonte sintética é identificada na tela.
- Arquivos de produto: `backend/app/api/v1/endpoints/ucs.py`, `backend/app/repositories/analytics.py`, `backend/app/schemas/uc360.py`, `backend/app/services/uc_analytics.py`, `backend/tests/test_uc360_dev04.py` e nove arquivos em `frontend/src/features/uc360/`. O histórico e o diálogo ficaram em `UC360History.tsx`, com regras de apresentação compartilhadas na feature em `uc360-format.ts`. Não houve commit, PR ou merge nesta revisão.

## Verificação reproduzível

Backend em `backend/`, com Python 3.11.9 do ambiente `D:\rocketlab2026-2\backend\.venv\Scripts\python.exe` e `DATABASE_URL=sqlite:///:memory:`; a suíte completa deve rodar **sem** `ANALYTICS_SOURCE=synthetic` global para verificar falha fechada. A revisão executou `python -m pytest -q` após a correção de cobertura: **117 passed, 1 skipped**, um aviso de depreciação do TestClient Starlette/httpx. Os 12 testes HTTP UC 360 e `compileall -q app tests` passaram na execução do implementador. O caso ignorado exige PostgreSQL; Python 3.12, PostgreSQL real e CI remoto não foram verificados nesta sessão.

Frontend em `frontend/`: após a extração de componentes, a revisão repetiu `npm.cmd run check:boundaries` (**53 arquivos**), `npx.cmd prettier --check src/features/uc360`, `npm.cmd run lint`, `npm.cmd test -- --run` (**85 testes em oito arquivos**) e `npm.cmd run build` (TypeScript + Vite): todos passaram. `npm.cmd run format:check` global falhou em dez arquivos preexistentes fora de `features/uc360/` (rota de contratos, Panorama, layout, cliente de API, setup e Vite); nenhum está alterado na branch.

O revisor também executou `python -m compileall -q app tests scripts alembic` no backend e `git diff --check` na raiz: ambos passaram. Conferência de links relativos nos dez documentos alterados/criados encontrou **152 links locais, nenhum quebrado**. O `format:check` global acusa exatamente `src/app/dev-contracts-route.test.tsx`, `src/features/panorama/PanoramaArtwork.tsx`, `src/features/panorama/PanoramaPage.tsx`, `src/layouts/AppLayout.tsx`, `src/layouts/components/Header.tsx`, `src/shared/api/client.test.ts`, `src/shared/api/client.ts`, `src/shared/api/query-client.ts`, `src/test/setup.ts` e `vite.config.ts`, todos fora do diff da DEV-04. Por isso o gate global continua vermelho; a feature UC 360 passou seu próprio Prettier.

Smoke HTTP com `ANALYTICS_SOURCE=synthetic`, SQLite em memória e Uvicorn em `127.0.0.1:8014`: health `online`/banco `connected`; UC-1001 janeiro→fevereiro/2025 publicou consumo **100→90 kWh**, delta **−10 kWh (−10%)**, e faturado **R$ 100→R$ 105**, delta **+R$ 5 (+5%)**. O histórico de faturas da UC-1002 retornou duas faturas e página de tamanho 1. Os controles vêm de fixtures sintéticas; não representam valores da distribuidora.

Jornada independente no Chromium Playwright MCP com o portal Vite em `127.0.0.1:5173` e a API acima: busca vazia mostrou erro acessível; busca `1002` exibiu resultado canônico e seleção abriu UC-1002; fevereiro mostrou **R$ 82 faturados, R$ 70 pagos**, fatura parcial com pagamento em **05/03/2025**, e GD **4,2 kW** sem presumir compensação. UC-1004 mostrou fevereiro sem leitura, sem faturas e sem medidor vigente; histórico preservou janeiro **45 kWh** e fevereiro nulo, além do medidor MED-04 retirado em **31/01/2025**. Link direto UC inexistente mostrou 404 em linguagem de atendimento; parâmetro `uc` duplicado bloqueou consulta. Diálogo de detalhes abriu e Escape fechou com foco de volta ao botão. Em viewport 390 px, `body.scrollWidth` e `documentElement.scrollWidth` foram 390 px; inspeções de página inteira em 390 × 844 e 1440 × 1024 não mostraram transbordamento visível. Capturas locais temporárias em `.playwright-mcp/` não integram o produto. A revisão identificou e corrigiu a seleção UC-1005: o cadastro era listado, mas a cobertura de perfil inicialmente causava 503. Após ampliar apenas a cobertura de perfil, UC-1005 abriu no navegador com cadastro visível, medidas/contagens `null` e fontes `unavailable`. Não houve auditoria formal de zoom 200–400% nem reconciliação Gold.

## Revisão dos critérios e limites

| Checklist DEV-04 | Resultado demonstrado | Limite |
| --- | --- | --- |
| Busca e identificador inválido/inexistente | Busca editável, erro do formulário, lista vazia, 422 API e 404 no link direto | Gramática sintética; chave Gold não homologada. |
| Cadastro, consumo, faturas e pagamentos | Overview e históricos separados; pagamentos mantêm data própria | Sem reconciliação com fonte real/Gold. |
| Medidor, GD, interrupções e chamados | Seis seções disponíveis na mesma rota; snapshot de medidor e GD explicitados | Chamados sintéticos só têm ID, data e categoria; tratativas reais dependem de contrato Gold. |
| Paginação e ausências | API pagina por seção; cobertura distingue vazio, parcial e indisponível; UI indica lacuna de leitura e fatura ausente | Volume real e cobertura Gold não testados. |
| Fatos e hipóteses | UC-1001 apresenta consumo menor e valor maior, sem atribuir causa | Diagnóstico causal permanece sem evidência. |

WEB-03 não é marcado `Concluído`: faltam dicionário/chaves e cobertura Gold aprovados, reconciliação origem → Gold → banco → API → portal com amostra autorizada, execução PostgreSQL/CI e aceite de todos os estados com dados do case. O cartão Trello WEB-03 não pôde ser sincronizado: a consulta MCP ao quadro oficial retornou recurso inexistente ou sem acesso.
