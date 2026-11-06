# Receita — entendimento e plano de repaginação

**Data:** 05/11/2026. **Estado:** plano autorizado e implementado localmente; aceite integrado com publicação V3 real pendente.
**Escopo:** WEB-02, com interfaces em WEB-01/WEB-07 e ENT-01. Não altera os estados oficiais do PRD.
**Objetivo:** permitir que Henrique entenda o que mudou na receita, quanto veio de preço e volume, onde está a redução e quais explicações têm evidência.

## 1. Diagnóstico do estado atual

Análise documental e estática do código atual, sem nova inspeção do navegador ou reconciliação do ambiente Gold. Os problemas abaixo são inferências da composição; devem ser confirmados na validação visual da implementação.

| Existe hoje | Consequência para a leitura |
| --- | --- |
| `ReceitaPage.tsx` monta filtros, quatro cartões, decomposição, tabela de recortes e série na mesma página | Muitas camadas de informação sem uma sequência de perguntas explícita |
| `RevenueSummary.tsx`: valor faturado, consumo medido, preço observado e variação; cartões com altura mínima de 192 px | Ocupa o início da tela com medidas que não explicam sozinhas a mudança; não mostra percentual no resumo |
| Cartões e recortes usam competências inicial/final; `RevenueDecomposition.tsx` prefere `window_decomposition`, independente dessas competências | Uma mesma tela apresenta comparações temporais diferentes; o aviso existente não resolve a falta de contexto comum |
| Decomposição Gold exibe sete parcelas em uma lista com pequenas barras proporcionais | A separação existe, mas preço e volume disputam atenção com detalhes de composição |
| `RevenueBreakdown.tsx`: tabela com largura mínima de 880 px, paginação local de 20 linhas e agrupamento por dimensão | A descoberta da maior queda depende da leitura de tabela; não há uma investigação visual priorizada |
| Refinamentos, breadcrumb, modal de filtros, ajuda e série com dados numéricos já existem | Devem ser aproveitados, preservando histórico e acesso a valores exatos |
| `docs/revenue-diagnosis.md` contém narrativa executiva e análise territorial | O conhecimento existe fora do percurso da tela, mas exige vínculo com recorte, janela e publicação antes de ser apresentado como diagnóstico atual |

### Restrições que mudam o desenho

- Na Gold v2, `gold_revenue.comparison` publica comparação mensal e deixa percentual nulo; `quality` desabilita percentuais por falta de comprovação de fechamento contábil. Não contornar essa regra no navegador.
- A decomposição publicada usa o método V3 por pares UC/mês, agregado depois por recorte. Tem sete componentes, incluindo interação, entradas, saídas, sem leitura e outros. Não reduzir a identidade a apenas duas parcelas.
- O retorno atual de `window_decomposition` não expõe os faturamentos P0/P1 nem decomposição por item do agrupamento. O dicionário físico registra `faturamento_p0_reais` e `faturamento_p1_reais`: confirmar sua disponibilidade no leitor da publicação vigente antes de ampliar o contrato.
- O `breakdown` atual agrupa comparações mensais. Ele não sustenta um ranking dos efeitos nas janelas do diagnóstico.
- Volume é consumo medido; preço é observado na base comparável. Não são energia faturada e tarifa homologada.
- O documento de diagnóstico diferencia total de todas as classes e residencial. Os percentuais do enunciado não podem ser copiados para um cartão residencial ou para outro lote.
- Há divergência documental de maturidade: o diagnóstico se descreve como versão completa de Dados, ENT-01 permanece pendente no PRD e os guias ainda contêm descrições demonstrativas. Reconciliar esses textos antes da implementação, preservando o PRD como fonte de aceite.

## 2. Alternativas e recomendação

| Alternativa | Avaliação |
| --- | --- |
| Página única com seções expansíveis | Menor mudança, mas mantém a investigação longa e torna o estado inicial decisivo para a sobrecarga |
| Três abas com contexto compartilhado | Recomendada: separa diagnóstico, localização da queda e evolução sem criar novas rotas ou perder filtros |
| Fluxo obrigatório passo a passo | Conduz iniciantes, mas atrapalha quem precisa alternar rapidamente entre classes e territórios |

**Proposta, ainda não aprovada:** abas `Resumo`, `Investigar queda` e `Evolução mensal`. Modais apenas para método, fundamentos e valores completos. O diagnóstico principal permanece visível no Resumo.

## 3. Percurso proposto

### Contexto compartilhado

Cabeçalho compacto com classe, município/bairro, janela efetivamente analisada e botão de filtros. Breadcrumb único para o recorte, evitando repetir o bloco “Explorando” e o mesmo caminho em outros lugares. Atualização e origem acessíveis em fundamentos; alertas que invalidam a interpretação permanecem visíveis.

Resumo e Investigar usam **as mesmas janelas publicadas**. Evolução mensal tem período próprio, explicitamente rotulado. Alterar o período mensal não muda silenciosamente as janelas fixas. Filtros territoriais/de classe seguem compartilhados. Ao trocar de aba, manter o contexto e explicar a janela em uso.

### Aba Resumo — “O que aconteceu e quanto foi preço ou volume?”

1. Uma frase executiva calculada sobre a resposta atual: direção da receita, componente predominante e limite relevante. Não declarar “queda” se houver crescimento. Com dados insuficientes, explicar a indisponibilidade.
2. Três indicadores compactos: **variação da receita**, **efeito-preço** e **efeito-volume**, todos em R$. Variação traz também percentual quando elegível; efeitos trazem contribuição em pontos percentuais do faturamento P0 quando autorizada. Faturamentos P0/P1 aparecem como contexto da comparação, sem outra fileira de cartões.
3. Gráfico de cascata: faturamento P0 → preço → volume → demais componentes → faturamento P1. Somente com bases e reconciliação suficientes; quando parcial, usar barras divergentes de parcelas conhecidas e aviso, sem uma cascata que sugira fechamento.
4. “Demais componentes” pode agrupar visualmente interação, entradas/saídas, sem leitura e outros, com expansão que revela todas as parcelas e seus sinais. Não esconder nulidade ou incompletude dentro do agrupamento.
5. Bloco **“A pergunta de Henrique”**: o que se reproduz no recorte residencial, diferença entre premissa e resultado observado, o que a conta explica e o que ainda não tem causa comprovada. Ação `Investigar efeito-volume` abre a segunda aba com métrica e recorte preservados.
6. Ações secundárias: `Como calculamos`, `Ver valores` e `Ver fundamentos`, usando o Modal existente. As ressalvas sobre consumo medido, preço observado e base parcial não dependem de abrir modal.

### Aba Investigar queda — “Onde a redução está concentrada?”

- Barras horizontais divergentes, ordenadas inicialmente pelo efeito-volume mais negativo em R$. Oferecer troca para variação da receita e efeito-preço, sem misturar unidades.
- Agrupar por município, bairro ou classe. Caminho sugerido: total → município → bairro → classe. Classe também funciona como filtro transversal, permitindo investigar residencial desde o início.
- Selecionar uma barra aplica refinamento e avança ao próximo nível; breadcrumb permite voltar sem perder a comparação. Bairro sempre é identificado junto ao município. Selecionar classe encerra o caminho e mantém o recorte visível.
- Resumo curto do segmento selecionado: variação, efeitos e base. Não carregar uma consulta por linha; totais representam o universo completo, inclusive com paginação ou top-N visual.
- Opção `Ver tabela` preserva valores P0/P1, delta, percentuais elegíveis, componentes e reconciliação. Se mostrar apenas os maiores segmentos no gráfico, declarar o corte e manter acesso a todos; não eliminar “Não informado”.
- “Por quê?” distingue **observado**, **hipótese** e **evidência ausente**. GD, inadimplência, perdas ou continuidade não viram causas por associação. O primeiro incremento pode ser determinístico; não precisa criar geração de IA para funcionar.

### Aba Evolução mensal — “Quando mudou?”

Reaproveitar `RevenueSeries`, com gráfico como leitura principal e tabela completa sob demanda. Comparação entre competências claramente separada do diagnóstico por janelas. Consumo e preço observado entram em detalhes/seleção de métrica, sem repetir cartões do Resumo. Pagamento e energia faturada ausentes continuam identificados como ausentes.

### Destino dos KPIs atuais

| KPI atual | Destino |
| --- | --- |
| Valor faturado do mês final | Evolução mensal e Panorama; no Resumo usar os valores das duas janelas |
| Consumo medido absoluto | Contexto do volume e detalhe mensal |
| Preço observado absoluto | Explicação do efeito-preço e detalhe mensal |
| Variação absoluta | Indicador principal do Resumo, alinhado às janelas |

O Panorama já oferece indicadores gerais. Esta proposta não exige alterar sua implementação para remover duplicações de Receita.

## 4. Trabalho técnico necessário

### Etapa A — fechar contrato semântico e desenho

- [ ] Confirmar na publicação v2 autorizada as janelas, método V3, cobertura, bases P0/P1 e disponibilidade territorial/classe.
- [ ] Registrar no contrato de Receita a distinção entre comparação mensal e comparação por janelas e a política de percentuais observados. Não mudar silenciosamente a elegibilidade mensal existente.
- [ ] Definir denominadores: variação percentual = 100 × delta/P0; contribuição de componente em p.p. = 100 × componente/P0. Exigir P0 positivo, base e cobertura suficientes. Não confundir esses valores com percentual da variação líquida nem com variação física do consumo.
- [ ] Criar wireframe claro/escuro e mobile das três abas para revisão. Referência existente: frames Receita `15:331` / `16:1296` do arquivo registrado em `docs/design/grid360-prototype.md`; não presumir que o protótipo já representa a proposta.

### Etapa B — disponibilizar a mesma comparação em todos os recortes

- [ ] Evoluir aditivamente `GET /api/v1/revenue`: exposição das bases das janelas, elegibilidade/motivo dos percentuais e agrupamento dos componentes publicados por dimensão. Formalizar nomes e schema no contrato antes de codificar.
- [ ] Arquivos a revisar: `backend/app/services/gold_revenue.py`, repositório Gold que implementa `revenue_decomposition_rows`, `backend/app/schemas/analytics.py` e endpoint `backend/app/api/v1/endpoints/revenue.py`.
- [ ] Agregar a decomposição V3 publicada; não recalcular preço-volume com preço médio dos municípios. Validar aditividade dos componentes V3 no grão publicado; a regra demonstrativa por médias de grupos tem semântica diferente.
- [ ] Preservar autorização `revenue:read`, filtros parametrizados, publicação, nulidade, grupos incompletos e compatibilidade dos consumidores, incluindo Mapa Territorial. Consultas de agrupamento devem evitar N+1 e manter totais independentes da página visível.
- [ ] Não prever migração de banco: primeiro usar os campos físicos já documentados. Se houver lacuna real, registrá-la como dependência de Dados, sem fabricar valores.

### Etapa C — reorganizar a interface

- [ ] `ReceitaPage.tsx` coordena abas e contexto; evoluir `revenue-filters.ts` para estado compartilhável de aba/métrica, preservando URLs antigas, refinamentos e filtros legados.
- [ ] Adaptar `RevenueSummary.tsx`, `RevenueDecomposition.tsx`, `RevenueBreakdown.tsx` e `RevenueSeries.tsx`; extrair contexto e diagnóstico em componentes da própria feature conforme a responsabilidade exigir.
- [ ] Atualizar contrato/decoder em `frontend/src/shared/analytics/revenueContract.ts` e consumidor correspondente; `useRevenue.ts` mantém TanStack Query, identidade completa do contexto e cancelamento.
- [ ] Reutilizar Modal, Button e tokens locais. URL guarda filtros/aba/métrica; rascunhos e modais ficam em estado local. Não importar componentes internos do Panorama.
- [ ] Implementar abas por teclado, foco após drill-down/retorno, gráficos com alternativa textual e sinais além de cor; validar ambos os temas e reflow mobile.

### Etapa D — diagnóstico contextual e aceite integrado

- [ ] Derivar leitura numérica da resposta atual; recomendações do documento só aparecem com origem/janelas/recorte compatíveis. Divergência de publicação deve suspender números e conclusões antigas.
- [ ] Caso a explicação precise evoluir para GenAI, planejar uma fatia posterior usando o núcleo existente e a skill `genai-gold`; não condicionar o diagnóstico determinístico à disponibilidade do modelo.
- [ ] Atualizar guias e Registro de progresso do PRD com evidência reproduzível; sincronizar o cartão correspondente se o MCP Trello estiver conectado. Esta etapa de planejamento não conclui requisito.

## 5. Critérios de aceite da futura implementação

1. Na abertura, ficam visíveis comparação ativa, variação, preço, volume e leitura executiva; tabela longa e série não competem com esse resumo.
2. Henrique consegue partir do residencial, identificar município/bairro/classe com redução e voltar preservando os filtros.
3. Cartões, gráfico, ranking e diagnóstico usam a mesma população, janelas e publicação. A comparação mensal tem identificação própria.
4. Preço, volume e demais parcelas reconciliam com a variação quando completos; parcial não simula fechamento.
5. Percentuais têm denominador e elegibilidade claros. Zero, nulo, base pequena, P0 negativo/zero, ausência de cobertura e sem base comum têm tratamento explícito.
6. Valores exatos e todos os grupos continuam acessíveis; barras/cores não são a única forma de ler os dados.
7. A pergunta do case aparece no fluxo, com distinção entre total e residencial, preço e tarifa, consumo medido e energia faturada, decomposição e causa.
8. Não há novo painel redundante de KPIs gerais. Links antigos e o consumidor Mapa Territorial continuam funcionando.

## 6. Verificação planejada e limites desta análise

- Backend: testes dirigidos existentes `test_gold_revenue_decomposition.py`, `test_gold_revenue_v2_real.py`, `test_revenue_dev03.py`, `test_gold_revenue_coverage.py` e `test_territory_map_revenue.py`, mais contratos das novas bases/agrupamentos. Casos com sinais opostos, grupo sem base e nulidade precisam de esperados independentes do algoritmo.
- Frontend: `npm test -- src/features/receita src/shared/analytics/revenueClient.test.ts`; ampliar os casos de URL, abas, percentuais bloqueados, atualização e drill-down. Executar build, lint, format:check e check:boundaries.
- Integração: conferir totais P0/P1, sete componentes e agrupamentos contra SELECT independente somente leitura na mesma Gold v2. Conferir filtros herdados, bairro homônimo, classe, back/reload e falha de publicação.
- Navegador: desktop e mobile, claro/escuro, teclado, ausência/erro/parcial e valores completos. Realizar a jornada “quanto mudou → preço/volume → onde → limite causal”, registrando pontos de confusão.
- Nesta fase foram lidos código e documentos; não foram executados testes, API, consultas Gold ou revisão visual. Os valores do documento de diagnóstico não foram novamente validados. Nenhum código de produto, requisito ou estado do PRD foi alterado.

## 7. Pontos para revisão do plano

A proposta recomenda três abas e prioriza janelas publicadas no diagnóstico. Essas são escolhas de produto propostas, não decisões previamente aprovadas. A elegibilidade de percentuais das janelas precisa ser explicitada por Dados/Produto, sem converter cobertura de extração em certificação contábil. A implementação deve começar pela consistência temporal do contrato; reorganizar apenas o layout não resolve a principal ambiguidade atual.

## 8. Execução autorizada — 05/11/2026

A pessoa usuária aprovou a aplicação do plano. A implementação foi realizada na branch local `feat/receita-investigacao`, sem commit/push, preservando as alterações anteriores do diretório.

- **Contrato e backend:** `gold_revenue.py` reutiliza a leitura da decomposição para bases e agrupamentos, preserva a comparação mensal e não consulta a decomposição quando sua configuração não existe. `analytics.py` publica a extensão aditiva. A política conservadora de percentuais observados está explicitada no contrato; contagens de UCs não são somadas para alegar população global. Não houve alteração da fórmula V3, migração ou escrita Gold.
- **Frontend:** `RevenueOverview.tsx`, `RevenueInvestigation.tsx`, `revenue-presentation.ts` e `ReceitaPage.tsx` separam resumo, investigação e série. A cascata só aparece com bases completas; demais componentes são agrupados visualmente e detalhados no modal. Todos os recortes e suas sete parcelas continuam acessíveis na tabela. Aba/métrica ficam na URL; breadcrumbs preservam recortes. A chamada “Investigar efeito-volume” seleciona volume explicitamente.
- **Diagnóstico:** leitura determinística contextual, sem geração de IA ou cópia de números reais do diagnóstico documental para outro lote. As limitações da decomposição aparecem diretamente quando invalidam a comparação. A integração não conclui ENT-01.
- **Revisão independente:** identificou perda da tabela mensal quando janelas estavam indisponíveis, métrica transitória e motivo de indisponibilidade escondido; corrigidos e cobertos por regressões.
- **Verificações observadas:** 58 testes Backend de Receita/cobertura/Mapa passaram; Ruff dirigido passou; build, lint (dois avisos fora da fatia), formatação e fronteiras Frontend passaram. A primeira regressão Frontend completa teve 558 passes e duas falhas em testes do Assistente; a repetição isolada desse arquivo passou em 27 testes. A repetição completa com dois workers revelou uma fixture incompleta da investigação; após corrigir a fixture e aguardar o foco assíncrono, **560 testes Frontend passaram**, comando `npm.cmd test -- --maxWorkers=2 --reporter=json --outputFile=../work/receita-layout/frontend-tests-final.json`.
- **Navegador:** `node scripts/check-receita-layout.mjs` passou quatro jornadas com fixture artificial em 1440/390 px e claro/escuro: modal, município → bairro → classe, tabela da série, reload e ausência de overflow. Capturas locais em `work/receita-layout/`; não são evidência Gold real. Resumo desktop e mobile foram inspecionados visualmente.
- **Limite Gold:** `python -m scripts.check_revenue_windows` foi tentado contra o PostgreSQL local existente em conexão somente leitura com prazo de 5 s. O controle parou porque a publicação não tem decomposição V3 configurada. Nenhum valor, segredo ou arquivo de dados foi copiado para este documento. Próximo passo de aceite: disponibilizar publicação autorizada com V3, executar o script e conferir o fluxo autenticado com API real dessa publicação.
- **Trello:** conexão do membro respondeu, mas o quadro canônico não foi encontrado/acessível; busca por WEB-02 não retornou cartões. Sincronização pendente; não houve mudança de estado remoto.

As escolhas antes propostas foram autorizadas para implementação, com a política de percentuais observados registrada como decisão de implementação conservadora. O estado histórico de WEB-02 no PRD é preservado; esta revisão visual permanece em validação integrada e não cria novo aceite Gold.

### Continuação — processo local ainda com contrato anterior

A pessoa usuária encontrou “Não há decomposição publicada por recorte” na investigação por bairro. Conferência somente leitura de `http://127.0.0.1:8001/openapi.json` confirmou que o processo ativo ainda não expõe `RevenueData.window_breakdown`. A existência de decomposição geral nesse processo não comprova disponibilidade da nova extensão. É necessário reiniciar a API para carregar o código atualizado; o processo Uvicorn observado não usa `--reload`. O teste privado anterior foi contra o PostgreSQL disponível e não certifica que ele seja a mesma fonte configurada no processo 8001. Não foi encerrado/recriado esse processo sem conseguir recuperar sua configuração de inicialização.
