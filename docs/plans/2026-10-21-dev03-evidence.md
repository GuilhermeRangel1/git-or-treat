# DEV-03 — evidências e revisão integrada

**Data:** 21/10/2026. **Escopo:** exploração demonstrativa de Receita, WEB-02/WEB-07 e suporte a ENT-01. **Branch:** `dev03`, base `ebccc238bcec502bfa7a1b36ff32e01b0c6c4567`; revisão da árvore de trabalho, incluindo arquivos novos, antes do commit desta entrega.

Dois implementadores GPT-6 Luna/high trabalharam em backend e frontend. Esta sessão revisou requisitos e padrões das skills locais `backend-coding-standards`, `frontend-coding-standards`, `tdd` e `code-review`. [Desenho](../design/2026-10-21-dev03-design.md), [plano](2026-10-21-dev03-plan.md), [contrato](../contracts/revenue-dev03.md) e [ADR-0008](../decisions/0008-exploracao-demonstrativa-receita.md) fixam as definições provisórias. Nenhum dado real foi utilizado.

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

### B1 — destinos de retorno centralizados

`revenueRefinementDestination` em `frontend/src/features/receita/revenue-filters.ts` concentra a transformação do destino de Total/Município; `ReceitaPage.tsx` usa o mesmo resultado para o endereço do link e para a navegação pelo clique. A classe continua independente: retornar ao Município remove somente o bairro; retornar ao Total remove somente `recorte_*`, preservando filtros base, período e agrupamento.

Registro histórico: a retenção de classe refinada no retorno ao Município foi substituída pela política explícita de retorno descrita na revisão de feedback abaixo. A centralização dos destinos foi preservada.

`ReceitaPage.test.tsx` acrescenta regressões de destino e jornada com endereços esperados literais, município/classe base, histórico e consistência entre `href` e clique. Em `frontend/`: `npm.cmd test` → 67 aprovados; `npm.cmd run check:boundaries` → 45 arquivos; `npm.cmd run format:check`, `npm.cmd run lint` e `npm.cmd run build` aprovados. Documentação e `git diff --check` aprovados. Implementador GPT-6 Luna/high, revisão do controlador; sem novas pastas, dependências, alterações visuais ou de contrato.

### B5 — contexto e comparação compartilhados pelos recortes

`backend/app/services/revenue_analytics.py` passou a usar `_RevenueContext`, `_metric_coverage` e `_comparison_summary` para compartilhar os dados filtrados e o cálculo entre agregado e grupos. `_build_breakdown` recebe o contexto e a comparação total já calculada; particiona faturas/leituras por identidade e calcula apenas os resultados necessários às linhas. Não monta série, acumulados, preço-volume ou opções completos para cada grupo nem recalcula o total. O controle privado de recursão e seu placeholder sem outros consumidores foram removidos; o contrato HTTP permanece 1.1.0.

O controlador revisou o diff completo e executou uma comparação diferencial contra o serviço do commit `bbb59d2`: 10.080 combinações de resultados/erros idênticas. Foram exercitadas fontes sintéticas normal, sem cobertura, com faturamento nulo no extremo final e com universo vazio; seis janelas, município/bairro/classe e combinações de filtros conhecidos/desconhecidos. O auxiliar local ignorado `work/dev03/compare-revenue-refactor.py` carrega o código anterior por `git show` e compara o resultado integral das duas implementações; comando a partir de `backend/`: `venv/Scripts/python.exe ../work/dev03/compare-revenue-refactor.py --baseline bbb59d2`.

Os testes HTTP existentes mantêm os controles independentes de resultado; não foram acrescentados testes de chamadas internas. Em `backend/`: `venv/Scripts/python.exe -m pytest -q` → 101 aprovados, 1 PostgreSQL ignorado; `venv/Scripts/python.exe -m compileall -q app tests scripts` aprovado. Documentação e `git diff --check` aprovados. Implementador GPT-6 Luna/high, revisão e comparação pelo controlador. Sem novas dependências, arquivos de produto ou alteração do repositório analítico. Consultas Gold e suas definições continuam fora desta refatoração.

### Feedback — finais de linha no Windows

O relato de falha em massa não se reproduziu inicialmente neste checkout já formatado: `npm.cmd run format:check` passou. A causa de portabilidade foi reproduzida sem alterar o arquivo de produto: Prettier 3.9.10 aceitou a versão LF de `ReceitaPage.tsx` e rejeitou o mesmo conteúdo convertido para CRLF. O Git local tinha `core.autocrlf=true` e não havia política versionada de EOL.

`.gitattributes` agora define `/frontend/** text=auto eol=lf`; `frontend/.prettierrc.json` explicita `endOfLine: "lf"`. A regra é limitada ao frontend e mantém detecção de binários. Doze arquivos de texto locais foram normalizados para LF sem diferenças lógicas no índice; o commit não carrega reformatação em massa. O README explica como normalizar um checkout existente preservando trabalho local.

Verificações: `git check-attr text eol` confirmou `text: auto` e `eol: lf`; `git -c core.autocrlf=true cat-file --filters HEAD:frontend/src/features/receita/ReceitaPage.tsx` produziu bytes LF; `npm.cmd run format:check`, validação documental e `git diff --check` aprovados. Referências oficiais consultadas via Context7: documentação de `endOfLine` do Prettier, com opção LF; fonte/versão e documentação Git constam no README. Configuração global do Git e código de produto preservados.

### Feedback — receita independente da disponibilidade energética

Confirmado o bloqueio indevido: a comparação financeira exigia simultaneamente cobertura de valor e energia faturados. Agora `revenue_analytics.py` usa disponibilidade de valor para delta BRL/percentual e de energia para delta kWh. Preço observado e decomposição exigem as bases comparáveis correspondentes; a reconciliação em BRL pode fechar mesmo com snapshot parcial por energia. A classificação geral do envelope permanece compatível com o controle B4. Contrato, desenho e ADR-0008 registram essa correção coordenada.

Os novos controles HTTP verificam: cobertura energética ausente apesar de valores observados; energia nula com cobertura declarada; lacuna energética intermediária com preços extremos conhecidos; receita incompleta com energia completa. BRL 500 → 550 mantém delta +50 e +10%, com reconciliação financeira `available` e energia/preço-volume indisponíveis. Janela com lacuna energética intermediária mantém delta financeiro +150 (+30%) e preços por extremo 1,0000 → 1,0833, sem inventar delta energético ou preço acumulado comparável.

Verificações em `backend/`: `venv/Scripts/python.exe -m pytest -q tests/test_revenue_dev03.py` → 37 aprovados; suíte completa → 105 aprovados, 1 PostgreSQL ignorado; `compileall app tests` aprovado. Aviso preexistente Starlette/HTTPX. Documentação e `git diff --check` aprovados. Implementador GPT-6 Luna/high, revisão do controlador; nenhum dado real, schema físico, migração ou biblioteca acrescentado.

### Feedback — filtro legado e repetição de parâmetros

Confirmado que o frontend ignorava `alimentador` do link e o removia ao aplicar o formulário, embora a API já aceitasse o filtro. A feature agora preserva o valor no parser, na query HTTP, na chave TanStack e no rascunho/aplicação, sem criar seletor novo. O contexto utiliza os filtros efetivos de `metadata` quando há resposta; a URL é apenas o fallback anterior à resposta.

O parser rejeita repetição de qualquer chave bruta, inclusive `alimentador`, `group_by` e nomes não usados pela consulta. Aplicar um formulário válido remove repetições, inclusive as que não têm um campo editável, preservando parâmetros desconhecidos únicos sem enviá-los como filtros HTTP. Alimentador vazio ou com mais de cem caracteres não dispara consulta.

Em `frontend/`: `npm.cmd test` → 75 aprovados; Receita → 30 aprovados; `check:boundaries` → 45 arquivos; `format:check`, `lint` e `build` aprovados. Após o ajuste final da fonte do contexto, Receita/build/formatação/lint foram repetidos e passaram. Os testes percorrem AL-01 → aplicar Município → AL-02, endereços inválidos e recuperação pelo formulário. Documentação e `git diff --check` aprovados. Implementador GPT-6 Luna/high, revisão do controlador. Desenho/contrato sincronizados; não se trata de introduzir dados Gold nem de corrigir o layout amplo cuja integração está prevista na DEV-02.

### Feedback — retorno explícito pelos recortes

A retenção de classe refinada ao retornar ao Município era uma interpretação anterior, agora substituída pela política explícita do contrato: Total remove os três refinamentos; Município remove bairro/classe refinados; Bairro remove classe refinada. Filtros base, incluindo classe e alimentador, período e agrupamento permanecem. Bairro é link quando há classe refinada abaixo dele; sem esse refinamento permanece como item atual. Endereço e clique continuam usando o mesmo destino calculado.

Em `frontend/`: `npm.cmd test` → 77 aprovados; `npm.cmd run check:boundaries` → 45 arquivos; `format:check`, `lint` e `build` aprovados. As regressões verificam endereços literais, navegação/histórico dos três destinos, preservação de filtros base e classe refinada sem bairro. Documentação e `git diff --check` aprovados. Implementador GPT-6 Luna/high, revisão do controlador; contrato/desenho/ADR sincronizados.

Validação adicional do controlador, sem interceptação de HTTP: API Uvicorn temporária em `127.0.0.1:18003`, fonte `synthetic` e SQLite em memória; parser e decoder TypeScript reais carregados por transpilação local. Quatro URLs (`alimentador=AL-01`; AL-02/Residencial; Recife/AL-01 por bairro; Recife/Centro/AL-01 por classe) geraram consultas 200 com agrupamento e filtros efetivos idênticos ao pedido. Repetições de alimentador, `group_by` e nome desconhecido foram bloqueadas no parser; chamada HTTP direta com alimentador repetido retornou 422. O servidor temporário foi encerrado. Isso verifica as fronteiras de filtros/API, sem equivaler a nova inspeção visual no navegador.

O ajuste amplo de responsividade foi reservado à integração da DEV-02. Dados fictícios continuam sendo a demonstração explícita aprovada; o aceite Gold segue pendente. O relato de 404 foi tratado como questão de execução local, sem alterar a rota funcional: nesta branch, fonte não configurada retorna 503, e os caminhos corretos foram exercitados com 200 na checagem acima.

### Limites desta rodada

Nenhum navegador estava conectado ao inventário de automação; a jornada visual não foi repetida nesta rodada. As evidências anteriores de navegador continuam identificadas acima, sem serem apresentadas como nova execução. Python 3.12, PostgreSQL e Gold permanecem pendentes. A nova tentativa de leitura do quadro Trello pelo MCP expirou; nenhum cartão foi alterado.

## Parecer e pendências

**Requisitos:** exploração sintética aprovada no escopo DEV-03. Série, extremos, deltas, recortes, preservação do contexto, método, reconciliação e casos de qualidade foram exercitados. Preço médio observado permanece distinto de tarifa homologada, cuja fonte não está disponível.

**Padrões:** revisão local aprovada sem achados importantes abertos neste escopo. Rotas delegam regras ao serviço, repositório injetável declara cobertura; cálculos usam Decimal. Frontend valida JSON em execução, mantém filtros na URL e inclui parâmetros/cancelamento na consulta. Corrigidos achados de desconhecido convertido em zero, cobertura nula, arredondamento oculto entre grupos, delta entre snapshots, fidelidade visual, overflow mobile e retorno de foco.

**Limites:** WEB-02, WEB-07 e ENT-01 permanecem `Pendente`. Faltam adaptador e reconciliação Gold → banco → API → portal, janelas anuais reais, definições homologadas, diagnóstico ENT-01 e outras telas de WEB-07. Trello não pôde ser sincronizado: o MCP retornou recurso não encontrado ou sem acesso ao quadro indicado. Nenhum cartão foi alterado. Não houve PR, merge ou publicação de produto nesta etapa.
