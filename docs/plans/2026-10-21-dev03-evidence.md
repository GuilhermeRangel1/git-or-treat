# DEV-03 — evidências e revisão integrada

**Data:** 21/10/2026. **Escopo:** exploração demonstrativa de Receita, WEB-02/WEB-07 e suporte a ENT-01. **Branch:** `dev03`, base `ebccc238bcec502bfa7a1b36ff32e01b0c6c4567`; revisão da árvore de trabalho, incluindo arquivos novos, antes do commit desta entrega.

Dois implementadores GPT-6 Luna/high trabalharam em backend e frontend. Esta sessão revisou requisitos e padrões das skills locais `backend-coding-standards`, `frontend-coding-standards`, `tdd` e `code-review`. [Desenho](../design/2026-10-21-dev03-design.md), [plano](2026-10-21-dev03-plan.md), [contrato](../contracts/revenue-dev03.md) e [ADR-0006](../decisions/0006-exploracao-demonstrativa-receita.md) fixam as definições provisórias. Nenhum dado real foi utilizado.

## Verificações executadas

| Área | Comando/verificação | Resultado |
| --- | --- | --- |
| Backend | Em `backend/`: `venv/Scripts/python.exe -m pytest -q` | Repetido antes do commit: 100 aprovados, 1 teste PostgreSQL ignorado por ausência de `TEST_POSTGRES_URL`. |
| Backend | `python -m compileall -q app tests scripts alembic` | Aprovado. |
| Frontend | Em `frontend/`: `npm.cmd test` | 65 aprovados em cinco arquivos, incluindo 20 testes de Receita. Os novos cenários mostram soma fechada e grupo não comparável com diferença não atribuída na interface. |
| Frontend | `npm.cmd run check:boundaries` | 45 arquivos verificados. |
| Frontend | `npm.cmd run lint`, `npm.cmd run format:check`, `npm.cmd run build` | Aprovados, incluindo tipos. Sem dependências novas; nove arquivos preexistentes receberam apenas normalização de fim de linha para corrigir o gate de formatação. |
| Integração | API HTTP real + Vite e preview de produção com API configurada explicitamente | Resumos, filtros, agrupamentos e retorno funcionais; nenhum transporte interceptado como prova de integração. |
| Auditoria independente | 21 consultas HTTP em sete universos não vazios × três dimensões, mais universo vazio | Extremos, somas dos grupos e deltas reconciliados diretamente com faturas sintéticas, sem chamar o serviço de cálculo. |
| Documentação | Auxiliar local `node work/dev03/verify-docs.mjs` e `git diff --check` | 51 documentos, links locais, configurações JSON e seis imports de instruções aprovados; 33 arquivos com conteúdo alterado/novo sem artefatos brutos ou assinaturas comuns de segredo. `diff --check` aprovado. |

Ambiente local: Python 3.11.9, FastAPI 0.141.1, Pydantic 2.11.7 e Vite 8.3.4. Docker/Python 3.12 e PostgreSQL não foram executados nesta entrega. O teste ignorado continua pendência do CI/ambiente descartável; a demonstração de Receita usa repositório sintético e nenhuma migração foi alterada.

## Controles de receita

Fonte explícita `ANALYTICS_SOURCE=synthetic`, lote `dev03-v1`, atualização `2026-10-21T00:00:00Z`: dez UCs, 16 faturas e oito UCs distintas faturadas em cada extremo de janeiro/fevereiro de 2025. Dinheiro em BRL e energia faturada em kWh.

| Consulta/cenário | Inicial → final | Resultado/limitação verificados |
| --- | --- | --- |
| Total janeiro → fevereiro | 800 → 927 | Δ +127, +15,88%; volume 730 → 855. Efeitos: volume +136,99, preço −8,53, interação −1,46, ajuste zero; soma +127. |
| Acumulado dos dois meses | Faturado 1.727; pago 1.710 | Energia faturada 1.585; medida conhecida 407, parcial. Acumulado distinto do valor final 927. |
| Classe Residencial | 620 → 725 | Δ +105, +16,94%. Recife/Residencial: 620 → 645, Δ +25. |
| Recife/Centro/Residencial | 390 → 405 | Δ +15 conhecido; percentual suprimido por base pequena. |
| Paulista | 0 → 0 | Zero financeiro conhecido com universo/cobertura declarados; preço e percentual indisponíveis por denominador/base. |
| Olinda/Comercial | Sem universo correspondente | Vazio/nulo e mensagem explícita; não se transforma em zero. |
| Janeiro → março | 800 → indisponível | Série mantém janeiro/fevereiro e lacuna em março; não substitui o extremo. Acumulados conhecidos permanecem consultáveis. |
| Controle HTTP independente de referência | 80.000 → 76.500; energia 100.000 → 90.000 | Δ −3.500, −4,375%; volume −8.000, preço +5.000, interação −500, ajuste zero. |
| Meios centavos negativos/positivos | −5,03 → +5,03 publicados | Δ publicado +10,06; ajuste de arredondamento explícito +0,01. |
| Grupos com subcentavos | Dois grupos publicados de 0,01; total publicado 0,01 | Soma publicada 0,02 preservada; reconciliação indisponível com limitação, sem esconder diferença mesmo com variação líquida zero. |

Os testes HTTP em `backend/tests/test_revenue_dev03.py` também cobrem bases 0/1/4/5 e múltiplas faturas por UC, energia zero, receita negativa, pagamentos desconhecidos, fatos financeiros nulos, mesma competência, lacuna intermediária, dimensões ausentes, nomes de bairros repetidos, colisão do identificador reservado e mistura de preços entre grupos. Efeitos recalculados nos grupos fecham sua própria variação; receitas e deltas absolutos são os controles aditivos entre níveis.

Os totalizadores acima permanecem no contrato/HTTP da API, herdados da DEV-01; a tela não os apresenta. Na revisão do escopo, removemos também a tabela de extremos redundante: início/fim e as variações já aparecem nos quatro cartões. A pedido da pessoa usuária, a versão final removeu o painel dedicado de método, cobertura e limitações. A tabela de recortes mostra receita inicial/final e variação de cada linha, soma conhecida e aviso de fechamento; quando há grupo não comparável, identifica a contagem e a diferença não atribuída. A decomposição segue identificada como demonstração, preço observado segue distinguido de reajuste homologado, e estados relevantes permanecem junto aos dados. No endpoint, os diagnósticos analíticos deixaram de ser repetidos em `metadata.limitations`; os campos estruturados permanecem para sustentar qualidade, cobertura e reconciliação.

## Histórico e justificativa dos campos

- Git `987106b` (`feat(dev01): preparar repositorio e dados sinteticos integrados`, autoria registrada `Fcc2187`, 20/10/2026) introduziu os campos de total da resposta `RevenueData`. Git `30e1e2e` (`feat(dev01): integrar indicadores e receita a fonte sintetica`, mesma autoria, minutos depois) implementou os cálculos no serviço e controles HTTP independentes; ambos entraram por PR #27/merge `ebccc23`. A documentação do contrato DEV-01 descreve Receita como “Totais, série, preço observado” e registra totais faturados/pagos/energias como controles da fonte sintética. O propósito documentado é contrato/controle analítico, não uma instrução para a tela DEV-03 mostrar os acumulados.
- O disclosure visual “Ver acumulados e extremos” não consta no histórico Git: surgiu sem commit nesta branch DEV-03. O plano/desenho desta sessão introduziu a ideia de distinguir acumulado da janela dos extremos. A pessoa usuária esclareceu que o frame tem esse bloco, mas orientou compor a tela pelos conteúdos da atividade. Por isso a tela omite os acumulados e a tabela repetida de extremos; os cartões preservam os valores inicial/final exigidos. Os campos da API permanecem por compatibilidade.
- O disclosure final de método/cobertura/limitações também foi removido da tela. Sua descrição duplicava proveniência e diagnósticos já expressos nos indicadores. A API conserva cobertura, qualidade, avisos de decomposição e reconciliação porque sustentam tratamento de base pequena, períodos incompletos, denominador zero e fechamento numérico; apenas a duplicação agregada desses diagnósticos no envelope foi removida.

## Jornada e fidelidade visual

- API real: Residencial → Recife → Centro → Total preservou classe e competências; voltar/avançar e reload restauraram contexto. Segunda jornada com município Recife e bairro Centro aplicados no formulário preservou ambos no retorno ao total. Agrupamentos município, bairro e classe são entregues pela API.
- O filtro Bairro depende de Município porque há bairros homônimos; no formulário, fica desativado até a seleção e então recebe somente as opções daquele município. O campo Alimentador foi removido da interface para corresponder aos filtros do protótipo; a API preserva o parâmetro por compatibilidade com chamadas legadas.
- Falha real de conexão mostrou erro e nova tentativa, sem resumo fictício nem fallback; ao reiniciar a API, nova tentativa recuperou os mesmos filtros. Resposta inválida, HTTP 503, parâmetros duplicados, URL inválida e resposta antiga retardada estão cobertos pelos testes públicos da página.
- Produção: build com `VITE_API_URL=http://127.0.0.1:8000`, preview em `4173`, API com CORS local explícito. `/receita` exibiu dados reais da API sintética; `/dev/contratos` redirecionou para `/panorama`. Após o ajuste final da tabela, HTTP real retornou 200 no preview e na API, com três grupos e reconciliação `available` de R$ 800 → R$ 927; a apresentação do novo rodapé foi verificada pelos testes da página. O browser conectado não estava disponível nessa verificação final, portanto a inspeção visual anterior não foi repetida para esse rodapé.
- Referências Figma somente leitura: [Receita clara 15:331](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=15-331) e [escura 16:1296](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=16-1296). Em 1440 × 1024, conteúdo x272/largura1088, barra y252/altura92, cartões y368/altura192, painel preço-volume y584/altura368 e tabela y976, nos dois temas. Conferidos hierarquia, superfícies, espaçamento e tipografia. Preço usa 32 px para quatro casas decimais; demais valores usam 36 px. Dados dinâmicos e indicadores de qualidade ampliam a tabela conforme necessário.
- Mobile 390 × 844 e largura intermediária 768: sem transbordamento global (largura do documento 375 e 753, respectivamente, descontada a barra de rolagem). Tabelas mantêm rolagem interna. Escape, Fechar e Aplicar retornam foco a Ajustar filtros; formulário usa diálogo modal nativo e controles rotulados. Movimento reduzido foi exercitado. Ampliação nativa do navegador não foi auditada nesta execução.
- Revisão visual final da série mensal: gráfico em tema claro/escuro, eixo Y em BRL, competências no eixo X, área de tendência e tooltip com competência/faturamento conferidos no browser com API sintética. Ponto aceita foco pelo teclado. Em viewport 390 × 844, documento não transborda (375 px) e o gráfico mantém rolagem horizontal interna. Em `prefers-reduced-motion: reduce`, animações computadas como `none` e traço estático.
- Uma sondagem adicional com CSS `zoom: 2` manteve o diálogo/Tab/Escape funcionais, mas produziu largura maior que a janela. CSS zoom não altera os breakpoints como a ampliação nativa do navegador; essa sondagem não foi usada como aprovação do item de zoom, que permanece aberto no plano.
- Capturas locais ignoradas pelo Git: `work/dev03/accepted-desktop-light.png`, `accepted-desktop-dark.png`, `accepted-mobile-dark.png`. Não são imagens do enunciado nem dados reais.

### Reprodução local da jornada

Sem usar banco real ou alterar `.env`, iniciar em dois terminais PowerShell:

```powershell
# backend/
$env:DATABASE_URL='sqlite://'
$env:ANALYTICS_SOURCE='synthetic'
$env:BACKEND_CORS_ORIGINS='["http://127.0.0.1:5173","http://127.0.0.1:4173"]'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# frontend/
$env:VITE_API_URL='http://127.0.0.1:8000'
npm.cmd run build
npm.cmd run preview -- --host 127.0.0.1 --port 4173
```

Abrir `/receita?competencia_inicio=2025-01&competencia_fim=2025-02`, aplicar Residencial, explorar Recife e Centro e voltar por Total. Conferir controles da tabela acima. Para vazio, aplicar Olinda/Comercial; para zero conhecido, Paulista; para lacuna, competência final `2025-03`.

## Refinamentos arquiteturais — 21/10/2026

### B4 — disponibilidade classificada pelo serviço

A classificação de `metadata.status` saiu da rota HTTP e passou para `revenue_metadata_status` em `backend/app/services/revenue_analytics.py`. A rota continua responsável por parâmetros, metadados e resposta HTTP. A precedência 1.1.0 foi preservada, inclusive envelope `partial` para universo conhecido com todas as coberturas indisponíveis e período único sem degradação causada apenas pela decomposição indisponível.

O novo controle HTTP caracteriza as quatro coberturas indisponíveis e o envelope parcial; os demais casos continuam nos testes existentes. Comandos em `backend/`: `venv/Scripts/python.exe -m pytest -q tests/test_revenue_dev03.py` → 33 aprovados; `venv/Scripts/python.exe -m pytest -q` → 101 aprovados, 1 PostgreSQL ignorado. Aviso preexistente de depreciação Starlette/HTTPX. `git diff --check` aprovado. Implementador GPT-6 Luna/high, revisão do controlador; sem alteração de fórmulas, schemas ou repositório.

### Limites desta rodada

Nenhum navegador estava conectado ao inventário de automação; a jornada visual não foi repetida nesta rodada. As evidências anteriores de navegador continuam identificadas acima, sem serem apresentadas como nova execução. Python 3.12, PostgreSQL e Gold permanecem pendentes. A nova tentativa de leitura do quadro Trello pelo MCP expirou; nenhum cartão foi alterado.

## Parecer e pendências

**Requisitos:** exploração sintética aprovada no escopo DEV-03. Série, extremos, deltas, recortes, preservação do contexto, método, reconciliação e casos de qualidade foram exercitados. Preço médio observado permanece distinto de tarifa homologada, cuja fonte não está disponível.

**Padrões:** revisão local aprovada sem achados importantes abertos neste escopo. Rotas delegam regras ao serviço, repositório injetável declara cobertura; cálculos usam Decimal. Frontend valida JSON em execução, mantém filtros na URL e inclui parâmetros/cancelamento na consulta. Corrigidos achados de desconhecido convertido em zero, cobertura nula, arredondamento oculto entre grupos, delta entre snapshots, fidelidade visual, overflow mobile e retorno de foco.

**Limites:** WEB-02, WEB-07 e ENT-01 permanecem `Pendente`. Faltam adaptador e reconciliação Gold → banco → API → portal, janelas anuais reais, definições homologadas, diagnóstico ENT-01 e outras telas de WEB-07. Trello não pôde ser sincronizado: o MCP retornou recurso não encontrado ou sem acesso ao quadro indicado. Nenhum cartão foi alterado. Não houve PR, merge ou publicação de produto nesta etapa.
