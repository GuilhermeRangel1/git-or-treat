# Mapa interativo da RMR — registro de evidências

**Data:** 03/11/2026
**Estado:** implementação revisada; critérios oficiais de WEB-01/02/07/10 permanecem inalterados.
**Rastreabilidade:** adicional sem ID próprio relacionado a WEB-01, WEB-02, WEB-07 e autorização WEB-10. Os estados canônicos desses requisitos permanecem inalterados.

## Geografia e correspondência

- A lista territorial de 14 municípios é a composição publicada pelo IBGE após a LC-PE 426/2020 (Goiana fora da RMR). A página do IBGE informa atualização em 29/07/2026, mas a planilha corrigida referente a 2025 não foi inspecionada; não se afirma que ela manteve a composição.
- frontend/public/geography/rmr.geojson: API de Malhas IBGE v3, qualidade mínima, período 2022; 14 feições públicas com propriedades code/name. SHA-256: 0b64b33f4c722aa48cf7349385bb5cc271ba49bf252c01306db508a22f898ded.
- Uma conferência do catálogo Gold v2 local aprovado encontrou uma grafia literal única por código IBGE nos 14 municípios e zero nomes municipais sem par. O registro contém correspondências explícitas; o runtime exige igualdade exata. A relação completa está apenas em work/mapa-rmr/gold-municipality-map.md (ignorado pelo Git); linhas/valores Gold não foram copiados para este relatório.
- Fontes, limitações, atribuição e contrato das camadas estão em docs/contracts/territory-map.md; preparação e validação detalhadas estão em work/mapa-rmr/geography-report.md.

## Backend

Foi adicionado backend/tests/test_territory_map_revenue.py para caracterizar GET /api/v1/revenue com fixture artificial Gold v2. Não houve mudança no código de produção do Backend.

Executado em backend/ com Python 3.12.10:
    .venv/Scripts/python.exe -m pytest -q tests/test_territory_map_revenue.py tests/test_revenue_dev03.py tests/test_platform_authorization.py
    76 passed, 1 warning in 36.74s

A fixture cobre séries, meses extremos/deltas, classe, bairros, zero versus ausência, percentual inelegível, entradas inválidas, permissões e publicação obsoleta. O aviso foi depreciação de starlette.testclient com httpx. Relatório: work/mapa-rmr/backend-report.md.

Suíte Backend completa executada com `ANALYTICS_SOURCE=synthetic` e diretório temporário isolado no workspace: 1.033 passaram, 114 foram ignorados e 1 aviso em 1.009,08s. Uma tentativa anterior contra o `.env` em modo Gold e banco de teste vazio falhou em casos de IA; o arquivo direcionado `test_ai_chat.py` passou 18/18 com a fonte de teste sintética. Nenhum `.env` ou configuração versionada foi alterado.

### Reconciliação Gold v2 → banco → API

Somente as 15 tabelas analíticas do pacote Gold v2 aprovado foram importadas em Postgres descartável. O CSV de origem, o banco isolado e `GET /api/v1/revenue` foram comparados em oito recortes: Igarassu/Recife × Comercial/Residencial × maio/junho de 2026. Resultado: zero divergências nos indicadores reconciliados. Os percentuais permaneceram inelegíveis na fonte e não foram criados pelo frontend. `/api/v1/analytics/options` retornou 200 para Admin/Comercial e 403 para Operação no backend isolado.

## Frontend e geografia

Executados em frontend/:
- node --test scripts/prepare-rmr-geography.test.mjs - 8 passaram, 0 falharam; inclui sincronização entre registro UI e preparador.
- npm.cmd test -- src/features/mapa/municipalities.test.ts - 5 passaram, 0 falharam; inclui 14 aliases Gold literais, igualdade exata e colisões.
- node scripts/prepare-rmr-geography.mjs - asset válido; 14 municípios; checksum confere.
- npx.cmd prettier --check src/features/mapa/municipalities.ts src/features/mapa/municipalities.test.ts scripts/prepare-rmr-geography.mjs scripts/prepare-rmr-geography.test.mjs - passou.

## Navegador Playwright - API Gold v2 local, somente leitura

Executado no Chromium Playwright contra http://127.0.0.1:5173, sem interceptação das APIs, com credenciais artificiais locais lidas somente pelo script. Comandos:
    node work/mapa-rmr/validate-browser.mjs --base-url http://127.0.0.1:5173 --credentials work/local-auth/credentials.txt --out work/mapa-rmr/browser
    node work/mapa-rmr/inspect-igarassu.mjs work/local-auth/credentials.txt

O summary não registra credenciais, linhas ou valores Gold. A prova observou:
- /mapa?municipio=2606804 carregou Igarassu após registrar o alias literal confirmado. Detalhe group_by=bairro retornou HTTP 200, cobertura parcial e 15 bairros; período publicado maio/junho de 2026. Resumo regional HTTP 200 com 14 geometrias; metadata.source.is_demo=false. Valores numéricos não foram registrados.
- Admin e Comercial abriram Mapa; Atendimento, Perdas e Operação receberam bloqueio de rota e não viram o link. Seleção por tabela/polígono, período, classes, quatro camadas, URL, recarga, voltar e link para Receita foram exercitados. Nove GETs de Receita observados na matriz foram HTTP 200 em agrupamentos municipal/bairro.
- Limpar filtros redefine o rascunho (inclui município), mantém a query da URL antes de Aplicar e remove o município depois de Aplicar. O painel selecionado não apresenta linha textual percentual. Capturas específicas revisadas: work/mapa-rmr/browser/igarassu-1440-light.png e work/mapa-rmr/browser/igarassu-filters-cleared-draft.png.
- Comparação visual Panorama/Mapa revisada em 1440×900 e 390×844, claro/escuro, filtros fechados e modais abertos. Capturas locais: `work/mapa-rmr/browser/comparison-closed-{1440,390}-{light,dark}.png` e `comparison-filters-{1440,390}-{light,dark}.png`. O Mapa usa o mesmo `FilterSelect` compartilhado, resumo compacto e modal Ajustar filtros do Panorama. Em mobile, tabela tem rolagem interna sem overflow horizontal do documento. O bloco Dados desta consulta e IDs brutos estão ausentes.
- Oito combinações viewport/tema sem overflow horizontal. Foco de teclado visível, outline 2 px; prefers-reduced-motion: reduce resultou em transição 0 s; Escape restaurou foco ao acionador. Font-family computado declarou DM Sans no corpo/filtros e Manrope nos títulos/legenda.

### Erros e limites da sessão

- 12 requisições GET /css2 e 12 erros de console correspondentes foram bloqueados pela política de egress do browser. A sessão não comprova download/uso dos arquivos das fontes.
- Quatro chamadas de API foram canceladas durante navegação/troca de filtros com ERR_ABORTED.
- /api/v1/ai/insights retornou HTTP 503 no Panorama, fora do escopo da jornada do Mapa.
- /api/v1/analytics/options retornou HTTP 403 para Comercial no backend servido pelo Vite existente. A API do backend isolado retornou 200 para Comercial/Admin e 403 para Operação conforme `revenue:read`; a discrepância de sessão/runtime do browser permanece sem diagnóstico e não deve ser mascarada como sucesso.
- Matriz completa: fatalError=null e 24 capturas; exit code 1 devido a erros de rede/console. A API/backend/Gold foi reconciliada separadamente; a suíte de contrato testa ausência e zero. Capturas/summary estão em diretório local ignorado e contêm telas com valores privados; não são para publicação/commit.

Gates direcionados do Frontend: 78 testes em 11 arquivos e 10 testes de roteamento passaram; build, lint, análise de fronteiras (221 arquivos) e formatação passaram. Restaram dois avisos de lint preexistentes em AuthProvider e Assistente. A suíte global do Vitest não fechou: incluiu um teste `node:test` que não é compatível com o runner Vitest e atingiu falta de espaço; não classificar isso como suíte integral aprovada. Os testes direcionados de mapa, contrato, filtros, Receita e roteamento passaram.

O smoke browser foi lido sem gravação de valores Gold. A reconciliação numérica CSV/banco/API é independente para os oito recortes descritos acima; o navegador confirmou a tela e os requests HTTP, mas não gravou uma comparação textual dos números renderizados no portal. Esse último cruzamento permanece como pendência de evidência.

## Direção de apresentação aprovada - 03/11/2026

A pessoa usuária aprovou o resumo de filtros e modal Ajustar filtros do Panorama; solicitou remover do Mapa o bloco visível Dados desta consulta, IDs brutos, timestamps e lista extensa de limitações; também removeu a linha textual de variação percentual do painel. Proveniência técnica continua nos contratos/API. Unidades, período e ressalvas pertinentes permanecem junto às métricas. Panorama não foi alterado. Estados WEB-01/02/07/10 permanecem inalterados.
