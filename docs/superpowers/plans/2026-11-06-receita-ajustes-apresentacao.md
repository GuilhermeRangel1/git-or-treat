# Receita — plano de ajustes antes da apresentação

> **Para execução por agentes:** usar `superpowers:executing-plans` para implementar e validar tarefa por tarefa. Este documento contém planejamento; nenhuma tarefa abaixo está implementada por sua criação.

**Objetivo:** finalizar a experiência da Receita para que a diretoria entenda a variação, localize o impacto de preço/volume e chegue às evidências do mesmo município, bairro e classe, com clareza e consistência visual.

**Arquitetura:** preservar Resumo, Investigação e histórico sob demanda. A URL continua sendo a fonte dos filtros aplicados e da navegação; rascunhos permanecem locais e consultas continuam nos hooks existentes. Ajustes previstos no frontend, sem alteração de fórmulas, schemas ou endpoints.

**Stack:** React 19, TypeScript, Vite, Tailwind, React Router, TanStack Query, Vitest/Testing Library e Playwright, nas versões instaladas no projeto.

**Especificação:** [avaliação da página](../../reviews/2026-11-06-receita-avaliacao-ux.md), ajustes solicitados nesta conversa, [PRD](../../PRD.md) — WEB-02, WEB-07 e apoio a ENT-01 — e [contrato DEV-03](../../contracts/revenue-dev03.md).

## Escopo e decisões

Inclui todos os ajustes discutidos, sem deixar os acabamentos para depois da apresentação:

| Nº | Ajuste | Resultado esperado |
| --- | --- | --- |
| 1 | Retirar Alimentador da seleção comum | Apenas município, bairro e classe no formulário; links legados tratados explicitamente |
| 2 | Modal com recorte efetivo | O formulário abre com o mesmo território e classe mostrados na tela |
| 3 | Limpeza limitada aos campos visíveis | Limpar recorte não muda meses ocultos do histórico |
| 4 | Contraste da aba ativa | Texto usa o token do sistema nos dois temas |
| 5 | Atalho para diagnóstico | Investigação leva ao Resumo do mesmo recorte |
| 6 | Métrica e ordenação claras | Usuário sabe que compara impacto monetário, não queda percentual de energia |
| 7 | Seletores padronizados | Modal e Investigação com altura, seta, borda e foco consistentes |
| 8 | Fim do drill-down explícito | Selecionar classe encerra a exploração sem oferecer outro nível fictício |
| 9 | Estado sem redução | Título e mensagem refletem crescimento, estabilidade ou ausência de dados |
| 10 | Linguagem comercial | R$ e períodos inicial/final na interface, preservando unidades e valores exatos |
| 11 | Comparação separada do recorte | Janelas publicadas e filtros territoriais têm responsabilidades visuais distintas |

**Preservar:** gráfico único de decomposição, achados objetivos Gold do recorte, composição completa e valores brutos sob demanda, histórico em diálogo, avisos de base parcial e navegação compartilhável por URL.

**Fora deste ajuste:** novas métricas/gráficos no histórico, decomposição para janelas arbitrárias, novos KPIs, diagnóstico gerado por IA, mudanças de Gold ou inferência causal sobre GD. O histórico continua sendo apoio; consumo na tabela não transforma o gráfico de faturamento em uma série de volume.

**Escopo temporal da comparação:** a UI apresenta o único par P0/P1 publicado pela Gold. O histórico mensal tem período próprio e não altera a comparação principal.

## Restrições e pontos de revisão

- Não transformar ausência em zero nem esconder erro, fonte parcial ou percentual indisponível.
- Preservar o significado de preço observado, consumo medido, população faturada e associação com GD.
- Não importar componentes de outra feature; `shared/filters` tem ownership excepcional do Panorama. Reutilizar tokens e padrões permitidos antes de criar abstrações.
- Não mudar silenciosamente o tratamento de links legados: documentar a ação explícita de remoção de Alimentador.
- Não alterar estado oficial do PRD por planejamento ou fixtures; ENT-01 depende de evidência e aceite próprios.
- Casos críticos: município/bairro vindos de drill-down; competências ocultas; link legado com Alimentador; grupos com valores nulos ou todos não negativos; classe já selecionada e navegação por teclado.

## Etapa 1 — filtros coerentes e histórico preservado

**Arquivos:** `frontend/src/features/receita/ReceitaPage.tsx`, `RevenueFiltersForm.tsx`, `revenue-filters.ts` e `ReceitaPage.test.tsx`. Criar `frontend/src/features/receita/revenue-filters.test.ts` para transições de URL que ainda não tenham cobertura direta.

**Interfaces existentes:** `RevenueBaseFilters`, `updateRevenueBaseParams(current, filters)`, composição entre `parsed.base` e refinamentos, `initialFilters`/`showPeriod` do formulário. Manter esses contratos onde possível.

- [ ] Acrescentar e executar regressões que reproduzam: explorar município/bairro, abrir filtros, alterar apenas classe e manter território; cancelar sem aplicar; trocar município e invalidar bairro; limpar com período oculto e preservar exatamente as competências.
- [ ] Remover o seletor Alimentador e o espaço vazio correspondente da barra. Em URL legada com Alimentador, manter o valor visível e o aviso de incompatibilidade, com ação explícita **“Remover filtro de alimentador”**; a ação remove somente essa chave e preserva os demais parâmetros.
- [ ] Inicializar o modal com filtros efetivos, incluindo refinamentos. Ao aplicar, consolidar o recorte editado nos filtros base e remover refinamentos redundantes, mantendo resultado equivalente e agrupamento compatível. O breadcrumb passa a partir dessa base consolidada; não deve sugerir retorno a um território que deixou de fazer parte da base.
- [ ] Fazer a limpeza atuar no rascunho de município, bairro e classe. Com `showPeriod=false`, preservar meses; com período visível, manter o comportamento documentado para esses campos. Não apagar Alimentador legado ocultamente.
- [ ] Garantir que aplicar, cancelar, remover Alimentador e limpar preservem aba, métrica e histórico conforme o escopo de cada ação. URLs inválidas/repetidas continuam recuperáveis pelo formulário.
- [ ] Executar os testes dirigidos e revisar requests: resumo, investigação e diagnóstico devem receber o mesmo recorte efetivo após aplicar.

**Aceite:** a pessoa vê o mesmo recorte na barra, no modal e nos resultados; alterar classe não amplia território; limpar campos visíveis não altera meses ocultos; Alimentador não é oferecido como escolha normal.

## Etapa 2 — contexto, contraste e controles padronizados

**Arquivos:** `ReceitaPage.tsx`, `RevenueFiltersForm.tsx`, `RevenueInvestigation.tsx`, testes correspondentes e `frontend/scripts/check-receita-layout.mjs`. Referências: `shared/ui/Button.tsx`, `styles/tokens.css` e acabamento dos filtros de Operação/Panorama, sem importar suas implementações internas.

- [ ] Separar a barra em **“Comparação”** (período inicial/final) e **“Recorte”** (município, bairro, classe e ação de filtros), preservando layout compacto. Datas são contexto publicado; botão **“Filtrar recorte”** esclarece o que será editado.
- [ ] Substituir o branco forçado da aba ativa por `text-[var(--accent-goiaba-text)]`, mantendo fundo, seleção semântica, foco e navegação por setas/Home/End existentes.
- [ ] Uniformizar seletores com altura mínima de 44 px, borda, padding, ícone de seta, foco e estados desabilitados. Manter `select` nativo acessível; não introduzir biblioteca ou dropdown customizado. Reutilizar o estilo dentro da feature; criar componente compartilhado apenas se houver necessidade real entre features.
- [ ] Validar visualmente em 1440 px e 390 px, temas claro/escuro, incluindo nomes longos. Medir contraste computado da aba: mínimo de 4,5:1 para texto normal. Confirmar ausência de overflow horizontal da página e foco visível.
- [ ] Exercitar abertura/fechamento do modal por teclado, Escape e retorno de foco ao botão que o abriu.

**Aceite:** contexto compreensível sem explicação oral, contraste suficiente e controles consistentes com o portal, sem duplicação de indicadores ou novos painéis.

## Etapa 3 — ranking, encerramento da exploração e estados honestos

**Arquivos:** `RevenueInvestigation.tsx`, `ReceitaPage.tsx`, `revenue-filters.ts`, `RevenueInvestigation.test.tsx`, `ReceitaPage.test.tsx`.

**Interfaces:** manter `onExplore(item: RevenueWindowItem)` para seleção de grupo e filtros na URL. Acrescentar `onViewDiagnosis: () => void` ao componente de Investigação; a página implementa a troca para `resumo`, preservando query e movendo foco para o título do Resumo.

- [ ] Trocar o rótulo para **“Comparar impacto na receita”**, com opções **“Efeito-volume (R$)”**, **“Efeito-preço (R$)”** e **“Variação da receita (R$)”**. Explicar em uma frase: **“Valores em reais, do menor para o maior. O efeito-volume mostra o impacto da quantidade de energia na receita.”** Não apresentar esse ranking como variação percentual de kWh.
- [ ] Substituir o bloco genérico de hipóteses por uma ação **“Ver diagnóstico deste recorte”**. A ação abre os achados existentes no Resumo; loading, erro e falta de evidência continuam explícitos ali.
- [ ] Preservar município → bairro → classe. No agrupamento por classe, permitir selecionar uma classe diferente para formar o recorte, mas usar rótulo **“Selecionar classe …”**, sem seta que prometa mais um nível. A classe já aplicada aparece como selecionada, sem ação redundante. Aplicar a mesma regra às barras e à tabela.
- [ ] Calcular o título a partir de valores conhecidos da métrica selecionada: havendo negativo, **“Onde está a queda?”**; havendo valores conhecidos sem negativos, **“Como os recortes contribuíram?”**, com **“Nenhum recorte com valor disponível apresenta redução nesta métrica.”**; sem valores conhecidos, **“Contribuição dos recortes”**, com estado de indisponibilidade. Todos nulos nunca equivalem a ausência comprovada de queda.
- [ ] Preservar ordem crescente, top 10 declarado, tabela completa, sinais e base parcial. Em dados mistos, avisar que grupos sem valor disponível não permitem conclusão sobre redução.
- [ ] Cobrir com testes: negativos/mistos; todos positivos; todos zero; todos nulos; nenhum grupo; mudança de métrica; seleção de classe diferente/atual; diagnóstico mantendo município, bairro, classe, meses e métrica; reload e retorno por breadcrumb.

**Aceite:** é possível localizar impacto negativo e abrir a evidência correspondente sem reconstruir filtros; crescimento e ausência não recebem mensagens de queda indevidas; não existe nível fictício depois da classe.

## Etapa 4 — linguagem e histórico do recorte

**Arquivos:** `RevenueOverview.tsx`, `RevenueInvestigation.tsx`, `RevenueSeries.tsx`, `RevenueHistory.tsx`, `RevenueFindings.tsx` e testes que verificam textos/nomes acessíveis desses componentes.

- [ ] Trocar texto visível `BRL` por `R$` e `P0/P1` por **“período inicial/final”**, incluindo títulos, tabelas, detalhes e nomes acessíveis. Manter `currency: "BRL"` nos formatadores e nomes técnicos do contrato; não fazer substituição global no código.
- [ ] Explicar percentuais e pontos percentuais sem confundi-los: variação percentual da receita versus contribuição relativa ao faturamento inicial. Preservar denominador e limitações nos detalhes existentes.
- [ ] No histórico, mostrar o recorte efetivo e texto curto: **“Este período altera apenas o histórico mensal; a comparação de receita mantém as janelas publicadas.”** Manter competências editáveis somente nesse percurso quando há janelas fixas.
- [ ] Conferir tabela inline, unidades, foco, rolagem interna do diálogo e leitura mobile, sem abrir modal dentro de modal. Não remover valores exatos nem o consumo disponível na tabela.
- [ ] Atualizar testes de textos apenas quando necessário para o comportamento; evitar snapshots de marcação ou testes que só espelham classes CSS.

**Aceite:** rótulos compreensíveis para apresentação comercial e responsabilidade temporal explícita, sem perda de precisão ou alteração dos cálculos.

## Etapa 5 — validação integrada e material de apresentação

**Arquivos:** `frontend/scripts/check-receita-layout.mjs`, `docs/services/frontend.md`, `docs/contracts/revenue-dev03.md`, `docs/reviews/2026-11-06-receita-avaliacao-ux.md` e `docs/PRD.md` (Registro de progresso). Atualizar este plano com resultados e pendências.

- [ ] Executar no diretório `frontend`: `npm.cmd test -- src/features/receita src/shared/analytics/revenueClient.test.ts --maxWorkers=2`; depois `npm.cmd test -- --maxWorkers=2`, `npm.cmd run build`, `npm.cmd run lint`, `npm.cmd run format:check` e `npm.cmd run check:boundaries`. Esperado: testes/build/checks aprovados; avisos preexistentes identificados separadamente.
- [ ] Ampliar o roteiro Playwright existente e executar `node scripts/check-receita-layout.mjs` com o servidor de fixtures esperado pelo script ativo. Cobrir os quatro cenários desktop/mobile × claro/escuro, filtros após drill-down, limpeza preservando histórico, link legado, seleção final de classe, CTA de diagnóstico, ausência de queda e teclado. Capturas artificiais locais, sem adicioná-las como dados reais.
- [ ] Executar a jornada autenticada com Gold v2 autorizada: começar em Residencial, explorar município/bairro/classe, editar classe pelo modal, abrir diagnóstico, histórico e recarregar URL. Conferir recorte e publicação nas respostas, sem registrar dados pessoais ou credenciais. Fixtures comprovam interação; não substituem essa etapa.
- [ ] Se API permanecer inalterada, não reiniciar serviço nem ampliar testes backend sem motivo. Se surgir necessidade de alterar contrato/cálculo, registrar a mudança de escopo e executar padrões e regressões backend antes de aceitá-la.
- [ ] Atualizar o contrato: modal representa recorte efetivo; aplicação consolida base; limpeza respeita campos visíveis; Alimentador legado tem remoção explícita; CTA preserva contexto. Atualizar guia e revisão com o que foi realmente entregue.
- [ ] Registrar no PRD comandos/resultados e limites reais, sem novo aceite de ENT-01 por melhoria de interface. Sincronizar cartão do mesmo ID no Trello se a conexão tiver acesso; registrar indisponibilidade se persistir.
- [ ] Preparar quadro **“Mantivemos / Ajustamos / Por quê”** e roteiro de demonstração: comparação e recorte → gráfico único → investigação → diagnóstico contextual → histórico sob demanda. Explicar dados parciais e associação com GD sem prometer causalidade.

## Critério de pronto para apresentação

- [ ] Os 11 ajustes da tabela têm evidência de implementação e validação.
- [ ] Não há perda silenciosa de território/classe nem alteração de período oculto.
- [ ] Navegação, legibilidade, foco e contraste foram conferidos nos dois temas e em desktop/mobile.
- [ ] Resumo e diagnóstico correspondem ao recorte/publicação consultados; indisponibilidades continuam honestas.
- [ ] Equipe consegue distinguir impacto monetário de volume, variação física de consumo e hipótese causal.
- [ ] Documentação registra limites e roteiro; nenhuma pendência é descrita como concluída.

**Ordem recomendada:** filtros → contexto e padronização → investigação → linguagem/histórico → validação integrada e apresentação. Execução no mesmo contexto, sem redesenho adicional.

## Registro desta execução

- Implementados: modal com recorte efetivo; consolidação na URL; limpeza territorial sem redefinir competências ocultas; Alimentador somente como legado removível; subtítulos Comparação/Recorte; token de texto da aba; rótulos de impacto e estados sem redução; CTA que preserva o recorte e move foco ao Resumo; unidade R$ e linguagem de períodos; texto que separa histórico mensal da janela publicada.
- A comparação principal apresenta a configuração P0/P1 da publicação. O histórico mensal mantém período independente.
- Validação observada: 564 testes completos passaram antes do ajuste de expectativa do rótulo; 50/50 testes dirigidos de Receita passaram depois; build passou; lint passou com dois avisos preexistentes em AuthProvider e AssistentePage; Prettier e checagem de fronteiras passaram; Playwright artificial passou em 1440/390 px, claro/escuro, modal, drill-down, reload e overflow.
- Limite ainda pendente para aceite de apresentação: jornada autenticada com publicação Gold v2 não foi repetida nesta execução. As fixtures de navegador validam interação e layout, não dados reais. ENT-01 permanece sem novo aceite.
