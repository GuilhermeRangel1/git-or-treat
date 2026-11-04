# Plano de ajustes do Panorama com Gold v2

> Para execução por agentes: usar `superpowers:executing-plans` ou `superpowers:subagent-driven-development`, conforme a forma de execução escolhida pela pessoa usuária. Executar por etapas e registrar evidências.

**Objetivo:** apresentar quatro KPIs coerentes, uma série de receita legível, fundamentos padronizados e filtros comprovadamente aplicados ao Panorama.

**Arquitetura:** preservar o fluxo filtros na URL → consulta autenticada → agregados da API → componentes do Panorama. Cálculos e regras de disponibilidade ficam no backend; o frontend apresenta os contratos e estados. Reutilizar componentes, tokens e modais existentes.

**Stack:** React, TypeScript, Vite, TanStack Query, FastAPI, SQLAlchemy, PostgreSQL e Playwright.

**Referências:** [PRD](../PRD.md), [contrato Gold DEV-13.1](../contracts/analytics-gold-dev13-1.md), [mapeamento dos KPIs](2026-10-31-panorama-kpis-mapeamento.md), [arquitetura frontend](../architecture/frontend.md), PDF local “Avaliação de Design - Grupo 1”, página 2, itens 1.1–1.6; página 6, item 5.1, quando se refere à consistência dos filtros do Panorama.

## Escopo e requisitos

- WEB-01: indicadores definidos, unidades, competência, comparação e reconciliação Gold.
- WEB-07: filtros com contexto visível e efeitos consistentes sobre cartões e gráfico.
- WEB-02: preservar a navegação para Receita e o contexto do recorte; este plano não conclui a exploração de receita dessa página.
- Usar obrigatoriamente [backend-coding-standards](../../.agents/skills/backend-coding-standards/SKILL.md) ao revisar contratos, consultas, serviços ou testes backend, e [frontend-coding-standards](../../.agents/skills/frontend-coding-standards/SKILL.md) ao ajustar componentes, filtros, modal, gráfico ou testes frontend.
- Usar `vercel-react-best-practices` na revisão React; consultar `supabase-postgres-best-practices` se alterar SQL, modelos ou índices.
- Ler os AGENTS.md das áreas afetadas e manter a semântica do dicionário Gold. Não alterar CSVs, publicar dados identificáveis ou inventar energia faturada.
- Plano executado nas etapas 0–4; estados canônicos do PRD foram preservados por não haver aceite integral de WEB-01/WEB-07.

## Inspeção inicial com Playwright — 31/10/2026

Página consultada em 1366×768, com lote `GOLD_20261031T020143Z_fd69c375` e dados reais. Capturas locais restritas geradas pelo Playwright; não incorporar números de negócio ou capturas ao Git.

- Cinco cartões ocupam duas linhas; o quinto deixa grande área vazia.
- O gráfico renderiza 48 competências simultaneamente; datas se sobrepõem e as barras não têm largura útil. Conteúdo invade visualmente a coluna lateral.
- A coluna de insight indisponível ocupa área equivalente à do gráfico sem agregar uma análise.
- O cartão cadastral mostra “Base sintética do cenário” e competência mensal apesar de representar fotografia do lote.
- Há mensagens contraditórias sobre comparação entre cartões e modal; o modal chega a apresentar variação quando o topo informa comparação indisponível.
- Fundamentos usa outro componente de cartão, rótulos e densidade; exibe grandezas indisponíveis junto aos indicadores principais, sem hierarquia clara.
- Bloqueio observado antes da inspeção: `expires_at` retorna offset `-03:00`, enquanto `session-api.ts` aceita somente UTC. Para visualizar a página, foi normalizada apenas essa data numa interceptação temporária de Playwright. Valores analíticos não foram interceptados. A validação final deve ocorrer sem interceptação.
- O código envia município/classe à API e os aplica a agregados e série. Isso indica intenção correta; falta comprovar a jornada de alteração/aplicação dos filtros em navegador nesta revisão.

## Etapa 0 — Garantir acesso reproduzível à página

Arquivos: `frontend/src/shared/auth/session-api.ts`, testes correspondentes e/ou serialização de sessão no backend.

- [x] Resolver a incompatibilidade de fuso da expiração conforme o contrato de sessão: definir UTC na saída da API ou aceitar ISO com offset válido no cliente. Não aceitar datas inválidas ou expiração passada como sessão válida.
- [x] Cobrir UTC e offset equivalente; entrar, recarregar e restaurar a sessão sem interceptações.

Aceite: Playwright acessa o Panorama com sessão real e recarrega sem erro. Esta é uma correção de compatibilidade necessária para validar a tela, sem ampliar escopo de perfis.

## Etapa 1 — Quatro KPIs no topo

Arquivos: `frontend/src/features/panorama/PanoramaPage.tsx`, `PanoramaMetricCard.tsx`, testes da página; `backend/app/services/panorama.py` se houver inconsistência na descrição ou nos estados.

- [x] Renderizar exatamente: **Valor faturado**, **Consumo apurado**, **UCs cadastradas no lote**, **UCs faturadas no mês**. Remover Energia faturada do topo.
- [x] Identificar em “Ver fundamentos” que receita e consumo usam a base comparável (`receita_base_comparavel_reais` e `consumo_base_comparavel_kwh`); manter os cartões livres de explicações técnicas. Não apresentar receita comparável como total financeiro irrestrito.
- [x] Usar o mesmo padrão de tipografia, unidade, espaçamento, altura e estados para os quatro cartões, com quatro colunas em desktop e quebra responsiva para duas/uma conforme espaço.
- [x] Corrigir o texto sintético no cadastro; mostrar “Cadastro do lote · todos os status”. Não mostrar competência mensal ou variação temporal como se fossem contagem histórica.
- [x] Usar `statusComparacao`/limitações reais da API para os demais cartões. Comparação observada parcial pode mostrar variação com ressalva de fechamento; não informar “sem dados” se a referência existe.
- [x] Evitar repetir a competência em cada cartão quando ela já estiver claramente vinculada ao grupo; manter identificada a referência temporal e destacar a exceção cadastral.
- [x] Preservar Energia faturada como limitação consultável nos fundamentos, sem fabricar substituição numérica ou concluir WEB-02.

Aceite: quatro cartões, sem origem sintética em Gold, sem mensagens contraditórias com fundamentos e sem comparação histórica da fotografia cadastral.

## Etapa 2 — Série de receita legível com o volume v2

Arquivos: `PanoramaSeriesChart.tsx`, `panorama-series-chart.css`, `PanoramaPage.tsx`, testes associados.

- [x] Apresentar inicialmente os últimos **12 meses até a competência selecionada**, com opção explícita de ampliar para **24 meses ou todo o histórico**. A janela visual não altera a competência dos KPIs.
- [x] Preferir série de linha para tendência mensal; ajustar espaçamento dos rótulos ao tamanho da tela, sem renderizar todas as datas como texto permanente quando não couberem. Usar tooltip/foco e tabela acessível para valor exato e competência.
- [x] Avaliar o componente de série já usado em Receita antes de criar infraestrutura nova; manter ownership e limites de módulos existentes.
- [x] Corrigir contenção, largura e escala; manter referência a zero e unidade monetária explícita. Diferenciar lacunas, zero, um ponto e duas competências sem linhas artificiais ou preenchimento de ausência.
- [x] Destacar a competência selecionada e identificar início/fim da janela; não confundir histórico com comparação de dois meses dos KPIs.
- [x] Dar ao gráfico a largura útil da seção em Gold; substituir a coluna alta de insight indisponível por aviso compacto, com linguagem de produto.
- [x] Reavaliar o resumo abaixo do gráfico: manter somente informação que ajude a leitura, evitando repetir os valores já acessíveis.
- [x] Nomear a ação de tabela como “Ver tabela da série”; manter “Explorar receita” para navegação, com destino e propósito distintos.

Aceite: 48 meses podem ser explorados sem datas sobrepostas, invasão de colunas ou perda de valores. Testar 1, 2, 12, 24 e 48 competências; desktop e mobile; temas claro e escuro.

## Etapa 3 — Padronizar “Ver fundamentos”

Arquivos: `PanoramaFoundations.tsx`, `PanoramaMetricCard.tsx`, `shared/ui/Modal.tsx` somente se necessário; testes da feature.

- [x] Organizar o modal em indicadores principais, fundamentos adicionais e proveniência. Incluir ressalvas junto aos indicadores pertinentes; não abrir uma seção geral separada de limitações. Evitar um segundo dashboard de nove cartões de igual peso.
- [x] Reutilizar tokens, títulos e apresentação numérica do Panorama. Compartilhar a apresentação específica da feature quando adequado, sem alterar indiscriminadamente MetricCard usado por outras telas.
- [x] Nos quatro indicadores principais, apresentar definição, fórmula, unidade, universo, competência ou fotografia do lote, filtros e comparação; expor detalhes de forma acessível.
- [x] Explicar grandezas indisponíveis, incluindo energia faturada, dentro dos fundamentos dos indicadores relacionados; preço observado e continuidade podem aparecer como fundamentos adicionais devidamente identificados.
- [x] Formatar datas para leitura humana, traduzir “todos/todas” e manter IDs técnicos de publicação em detalhes de proveniência. Evitar textos técnicos na mensagem principal.
- [x] Validar altura, scroll interno, cabeçalho, fechamento por Escape, foco inicial, contenção e retorno ao botão de abertura.

Aceite: nomes e estados concordam com o topo, não há texto sintético em Gold, modal legível nos dois temas e em mobile, com acesso por teclado.

**Ajuste de escopo solicitado depois do plano:** remover a seção geral “Limitações desta fonte” do modal e manter cada ressalva junto à definição do indicador correspondente.

## Etapa 4 — Comprovar filtros e padronizar termos

Arquivos: `shared/filters/FilterBar.tsx` e modal correspondente, `usePanoramaFilters.ts`, `shared/analytics/usePanoramaData.ts`, `backend/app/repositories/panorama.py`, `backend/app/services/panorama.py` e testes.

| Controle | KPIs financeiros/consumo | UCs faturadas | UCs cadastradas | Série de receita |
| --- | --- | --- | --- | --- |
| Competência | Valor daquele mês | Contagem daquele mês | Fotografia do lote | Último mês permitido na janela |
| Município/classe | Filtra | Filtra | Filtra cadastro atual | Filtra todos os pontos |
| Comparar com | Referência e variação | Referência e variação | Sem comparação histórica | Não troca o histórico por dois pontos |

- [x] Padronizar termos em barra, modal e fundamentos: “Competência”, “Comparar com”, “Município” e “Classe de consumo”. Usar “período” apenas para janela com início/fim.
- [x] Explicar que fechamento não declarado não significa mês aberto nem fechado. Não usar “Fechada - Referência” sem uma declaração comprovada.
- [x] Verificar Aplicar, Cancelar e Limpar: rascunho não afeta dados; Cancelar descarta rascunho; Aplicar atualiza URL, consultas e contexto; Limpar restaura padrões definidos. Preservar consistência com os controles compartilhados.
- [x] Validar global, município, classe e combinação; comparar pelo menos dois meses e referência anual; incluir recorte vazio e referência ausente.
- [x] Confirmar request, metadata/filtros e valores renderizados; o ponto do gráfico no mês selecionado deve conferir com o KPI da mesma medida. Contar UCs em grão UC/mês sem multiplicação por joins.
- [x] Verificar reload/link direto, cache por filtro, troca rápida de filtros e proteção contra resposta antiga. Preservar lote/fingerprint em toda a jornada.
- [x] Ampliar teste CSV/API existente para receita, consumo e série filtrados, além das contagens; comparar sem imprimir IDs ou valores privados.
- [x] Trocar navegação intermediária de continuidade por acesso direto a Operação com contexto compatível, se o modal apenas repete informação e contém outro botão de navegação. Não enviar classe como filtro suportado de DEC/FEC.

Aceite: mudança de filtro reflete o recorte correto, tabela/série/KPIs concordam com CSV e API; nenhuma influência temporal indevida na fotografia cadastral.

## Rastreabilidade do PDF de avaliação

| Item | Tratamento neste plano |
| --- | --- |
| 1.1 — Período de um mês e referência pouco claros | Etapas 1/4: competência e semântica de comparação/fechamento |
| 1.2 — Termos diferentes na tela e modal | Etapas 3/4: vocabulário único |
| 1.3 — Repetição de mês nos cartões | Etapa 1: contexto comum e exceção cadastral |
| 1.4 — Espaço do gráfico e comparação de dois pontos | Etapa 2: janela explícita, tendência real e proporção adequada |
| 1.5 — Utilidade da informação sob o gráfico | Etapa 2: revisar e reduzir resumo redundante |
| 1.6 — Botões de receita e continuidade confundem | Etapas 2/4: tabela versus exploração; navegação direta quando adequada |
| 5.1 — Consistência das ações dos filtros | Etapa 4: semântica e padrão visual dos botões |
| Geral — Hierarquia/distribuição de informação | Etapas 1–3: quatro KPIs, gráfico prioritário e fundamentos hierarquizados |

## Validação e conclusão

- [x] Testes dirigidos de componentes, filtros e agregados conforme cada mudança; integração CSV/API opt-in no pacote final, sem recarregar dados.
- [x] Frontend: `npm run check:boundaries`, `npm run format:check`, `npm run lint`, testes afetados e `npm run build`.
- [x] Playwright com sessão real sem interceptações: 1366×768, 1280×720, 1440×900 e mobile 390×844, zoom 100%, claro/escuro, modal e teclado. A página analítica pode rolar verticalmente; exigir ausência de scroll horizontal e conteúdo cortado.
- [x] Registrar quais itens do PDF foram atendidos e quais foram justificados; manter capturas restritas locais e evidência sanitizada na documentação.
- [x] Atualizar PRD, contrato e guias com comportamento e resultados observados. Só concluir requisitos após revisar o aceite completo; a ausência de energia faturada permanece limitação explícita do diagnóstico.

**Conclusão da implementação — 31/10/2026:** etapas 0–4 executadas. Testes e gates descritos no [PRD](../PRD.md) e em relatório local sanitizado (`work/panorama-plan-implementation-report.md`). A validação Playwright cobriu desktop/mobile, claro/escuro, filtros, recarga e modal. WEB-01 permanece em validação e WEB-07 pendente; o aceite integral não é declarado. Nenhum commit/push, recarga Gold ou alteração de dataset foi feito.

### Ajuste de apresentação dos KPIs — 31/10/2026

- Removidos dos cartões os textos técnicos sobre dados parciais, base comparável e fotografia do lote. Proveniência e ressalvas continuam em “Ver fundamentos”.
- Variação positiva aparece em verde e negativa em vermelho, como na referência `image.png`. Mensagens de comparação indisponível foram removidas dos cartões; a razão permanece nos fundamentos de cada métrica.
- Removidos do Panorama o timestamp/origem/lote junto aos filtros e a identificação Gold/fingerprint no rodapé. O gráfico usa legenda genérica de unidade.
- A API confirma que o filtro comparativo está ativo: UCs faturadas retornam variação observada, enquanto receita/consumo não fornecem variação quando há valores ausentes em uma das competências. A tela comunica essa insuficiência sem inventar uma comparação numérica.
