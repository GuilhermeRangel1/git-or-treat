# ADR-0006 — Contrato de produto do Panorama em rota própria, ao lado do contrato analítico da DEV-01

**Data:** 2026-10-21
**Estado:** proposta implementada na árvore de trabalho; revisão pendente.
**IDs do PRD afetados:** WEB-01 (principal), WEB-02 a WEB-07 (dependem do mesmo padrão de leitura), DEV-01 (contrato analítico preservado).

## Contexto

A DEV-01 passou a servir um contrato analítico versionado em `GET /api/v1/kpis`, sobre o lote sintético `dev01-v1` (janeiro–fevereiro de 2025, envelope com `data.metrics[]` e estados de disponibilidade por métrica). Esse contrato é verificado pela página interna `/dev/contratos` e por testes HTTP próprios.

A WEB-01 exige indicadores com definição, unidade, competência, filtros e comparação; o PRD não fixa oito KPIs nem competências de 2024. Conforme a revisão de produto da DEV-02 em 22/10/2026, o protótipo atual apresenta quatro indicadores principais e outro período. Ele orienta organização e estilização, sem definir o contrato HTTP ou o calendário desta fixture.

A escolha de oito métricas, competências selecionáveis 2024-03 a 2024-05 e lote `panorama-sintetico-2024.04-v1` foi da implementação demonstrativa. A fonte é sintética e não reconciliada com Gold. O envelope de produto (`data.metricas` indexado por chave, `data.serieMensal`, `data.filtros` e `data.totalRegistros`) também é uma decisão da implementação.

Na revisão de 22/10, os quatro indicadores de destaque da implementação são receita faturada, receita paga, energia consumida e energia faturada, preservando as distinções solicitadas na DEV-02. Preço médio, UCs, DEC e FEC permanecem complementares, abaixo da série. Essa seleção não é apresentada como reprodução exata dos KPIs do protótipo. Os períodos da fixture foram preservados para manter os controles de teste existentes; o calendário final depende da Gold.

Alternar o payload de `/api/v1/kpis` entre o contrato da DEV-01 e o contrato de produto quebraria a página de verificação de contratos, os testes do envelope de disponibilidade e a separação entre o contrato analítico e a jornada de produto.

## Opções consideradas

1. Substituir o payload de `/api/v1/kpis` pelo contrato de produto: um endpoint, mas quebra o contrato versionado da DEV-01, a página `/dev/contratos` e a suíte correspondente.
2. Fazer `/api/v1/kpis` servir os dois envelopes conforme o filtro:Envelope ambíguo por parâmetro, sem versionamento possível e sem forma de evoluir um contrato sem quebrar o outro.
3. Publicar o contrato de produto em `GET /api/v1/panorama`, com repositório, serviço e base sintética próprios, mantendo `/api/v1/kpis` intacto.

## Decisão

Adotar a opção 3. A rota `/api/v1/panorama` segue a mesma arquitetura da DEV-01 (rota → serviço → repositório → base sintética em memória) e o mesmo controle de fonte: `ANALYTICS_SOURCE=synthetic` é obrigatório; qualquer outro valor devolve 503 `source_unavailable`, sem fallback silencioso.

A base do Panorama (`panorama-sintetico-2024.04-v1`, competências 2024-03 a 2024-05) é distinta do lote da DEV-01 (`dev01-v1`) e não é a mesma fonte. O contrato analítico da DEV-01 permanece sem alteração em `/api/v1/kpis`.

A entrada inválida (competência inexistente, comparação fora do conjunto, município ou classe inexistentes) responde 422 `invalid_query`. Combinação válida sem fatos responde 200 com `totalRegistros: 0`; essa diferença em relação à política da DEV-01 (que representa ausência com `null` e estado por métrica) está registrada como pendência de revisão no catálogo de contratos e precisa ser resolvida antes do aceite com Gold.

A série histórica e as comparações usam a mesma base sintética dos totais, sem constantes paralelas. Competências parciais preservam seus valores e sua série, mas não publicam valor anterior nem variações absoluta/percentual contra períodos completos. Percentual indisponível é `null`, distinto de zero. A URL é validada no portal antes da consulta, com erros por campo e restauração explícita; a API mantém sua validação independente. Fórmulas, definições e grandezas continuam declaradas em texto na resposta, e a origem sintética, a versão do lote e a limitação de demonstração acompanham o envelope.

## Consequências e verificação

- O portal consome `/api/v1/panorama`; a página `/dev/contratos` e seus testes seguem validando `/api/v1/kpis`.
- Existem duas fontes sintéticas independentes no backend. Cada uma declara origem, versão, atualização e limitação; nenhuma é fallback da outra.
- A página de produto usa exclusivamente a API, valida a resposta em execução e mostra erro com nova tentativa em caso de indisponibilidade. A fixture local existe para testes; não substitui uma falha do backend.
- Conectar a Gold exige um adaptador por contrato, reconciliar as duas bases com o dicionário e decidir se as rotas convergem para um contrato único de indicadores.
- Verificação: `python -m pytest -q` na pasta `backend` aprovou 76 testes com 1 ignorado; no frontend, `npm test` aprovou 55 testes em 6 arquivos, com `npm run lint`, `npm run check:boundaries`, `npm run format:check` e `npm run build` aprovados.

## Referências

[PRD](../PRD.md), [catálogo de contratos](../contracts/analytics-api.md), [ADR-0004](0004-contratos-analiticos-e-fonte-sintetica.md), [serviço de backend](../services/backend.md) e [serviço de frontend](../services/frontend.md).

## Revisão DEV-02 — 22/10/2026

Correção da atribuição indevida de decisões da implementação ao PRD/Figma. A fonte e atualização aparecem antes dos indicadores; quatro cartões principais precedem a série e quatro complementares ficam depois dela. O insight de IA está fora desta atividade. Evidência da revisão funcional no Registro de progresso do PRD.
