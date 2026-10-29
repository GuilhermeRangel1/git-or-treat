---
name: git-or-treat-figma
description: Use when planning, creating, reviewing, or updating the V-Energy Grid 360 Figma prototype, its light and dark themes, reusable components, or user flows against the project PRD.
---

# Git-or-Treat — protótipo Figma

Produza um protótipo editável do portal interno V-Energy Grid 360, rastreável ao PRD. A habilidade cobre preparação, discussão visual, construção e revisão; execute a etapa solicitada e preserve decisões já aprovadas.

## Contexto e escopo

Leia [AGENTS.md](../../../AGENTS.md), [PRD](../../../docs/PRD.md) (§3, §6–9, §12 e §14), [guia frontend](../../../docs/services/frontend.md) e [dicionário](../../../docs/dicionario_gold.md). Para ordens ou IA, consulte também os respectivos guias [backend](../../../docs/services/backend.md) e [IA](../../../docs/services/ai-agent.md). Leia as regras da área antes de editar sua documentação. Resolva divergências antes de construir.

O PRD governa requisitos; as cinco referências visuais orientam alternativas. Apple HIG, Material Design 3 e WCAG 2.2 orientam usabilidade e acessibilidade na revisão solicitada. Campos, fórmulas, transições de ordens e contratos ausentes permanecem hipóteses identificadas. Use conteúdo sintético marcado como **ilustrativo**, sem dados reais ou imagens do enunciado. Separe faturado/pago, consumido/faturado, competência/pagamento, suspeita/irregularidade e DEC/FEC simplificados/conformidade regulatória.

## Preparar e decidir

1. Verifique branch e alterações existentes. Use a branch dedicada ao trabalho; preserve mudanças alheias.
2. Monte a matriz requisito → jornada → frame → estado → interação → evidência usando [cobertura e revisão](references/coverage-and-review.md). Diferenciais entram somente quando selecionados.
3. Consulte [referências visuais e de usabilidade/acessibilidade](references/visual-references.md) antes de propor direções ou revisar componentes. Registre exemplos, critérios e fontes; adapte os padrões ao portal web e escolha efeitos pela utilidade.
4. Quando a etapa solicitada incluir decisões visuais e a identidade estiver em aberto, apresente alternativas e use **grill-me**; use **grill-with-docs** para decisões de domínio/arquitetura a registrar. Investigue fatos antes de perguntar. Consolide direção, dispositivos, densidade, tipografia, cores, movimento e diferenciais acordados. Em pedidos apenas preparatórios, incluindo criação desta skill, registre as decisões adiadas e entregue a preparação; entrevista e construção ficam para a etapa seguinte.

## Construir pelo Figma MCP

Siga [execução no Figma](references/figma-workflow.md), carregando as skills oficiais aplicáveis antes das ferramentas. Use Figma Design com texto, componentes e instâncias editáveis. Um arquivo de código ou uma imagem de tela não substitui esse artefato.

Organize um único arquivo em quatro páginas:

1. **Componentes e estilos — modo claro**
2. **Componentes e estilos — modo escuro**
3. **Páginas e fluxos — modo claro**
4. **Páginas e fluxos — modo escuro**

As páginas de fluxos comportam múltiplas telas e estados. Compartilhe componentes e tokens semânticos com modos Claro/Escuro; os mostruários exibem a mesma biblioteca. Aplique o modo correto aos frames e preserve paridade de conteúdo e interação entre temas.

## Verificar e entregar

Revise a cobertura, os caminhos navegáveis, estados alternativos, vínculos de componentes/variáveis e aparência dos dois temas. Use evidência estrutural e capturas dos frames relevantes; corrija defeitos observados. Distinga simulação Figma de comportamento que exige aplicação real, incluindo teclado, segurança, cálculo e integração.

Entregue link do arquivo/frames, IDs afetados, verificações e pendências. Atualize o Registro de progresso conforme [workflow](../../../docs/agents/workflow.md), descrevendo preparação ou protótipo. Requisitos funcionais continuam abertos até terem sua evidência real; o protótipo não os conclui.
