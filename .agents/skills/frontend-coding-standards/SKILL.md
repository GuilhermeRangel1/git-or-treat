---
name: frontend-coding-standards
description: Use ao criar, revisar ou refatorar páginas React, componentes TypeScript, hooks, consultas, formulários ou estilos Tailwind do portal; também ao verificar limites de módulos, temas, acessibilidade e fidelidade ao Figma.
---

# Padrões de frontend — React, TypeScript e Tailwind

Evolua a interface a partir do código, da arquitetura e do Figma deste projeto. A solicitação atual, os `AGENTS.md`, o PRD e as decisões aprovadas prevalecem sobre esta referência auxiliar.

## Contexto obrigatório

Leia [as regras locais](../../../frontend/AGENTS.md), [a arquitetura](../../../docs/architecture/frontend.md), [o guia do portal](../../../docs/services/frontend.md) e o requisito do [PRD](../../../docs/PRD.md). Para alterações visuais, identifique o frame e as decisões aplicáveis no [registro do Figma](../../../docs/design/grid360-prototype.md); confira a referência atual antes de reproduzir uma tela.

## Referência por tarefa

| Tarefa | Ler |
| --- | --- |
| Organizar páginas, componentes, hooks e imports | [Arquitetura e composição](references/architecture-and-components.md) |
| Consumir API, organizar estado, filtros e formulários | [Dados e estado](references/data-and-state.md) |
| Estilizar, tratar temas, teclado e movimento | [Tailwind e acessibilidade](references/tailwind-and-accessibility.md) |
| Conferir Figma, comportamento e evidências | [Validação visual e funcional](references/visual-validation.md) |

## Critérios de revisão

- Preserve o layout persistente, os limites de importação e as responsabilidades das features.
- Reutilize componentes e tokens locais antes de introduzir abstrações ou dependências.
- Use URL para recortes aplicados, TanStack Query para estado remoto e estado local para interações transitórias.
- Valide respostas externas em execução; tipagem TypeScript não valida JSON.
- Mantenha ausência, zero, erro e dados parciais distintos. Vincule números e insights ao recorte correto.
- Preserve semântica HTML, foco, teclado, contraste e movimento reduzido nos dois temas.
- Verifique a fatia alterada no navegador e pelos gates existentes. Aparência e fixtures não comprovam integração Gold.

Para performance React, consulte também `vercel-react-best-practices`, selecionando as recomendações aplicáveis ao Vite. Consulte Context7 para APIs de bibliotecas quando disponível.

## Base e origem

A base principal é a arquitetura local, os componentes existentes e o [Figma Grid 360](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K). A [skill de msb7-jpg](https://github.com/msb7-jpg/visagio-atividade-v-energy-360/tree/d90fe16c26e3b6cc2cdcea4e5f2c116ded73ceb5/.agents/skills/frontend-coding-standards), consultada em 20/10/2026, contribuiu pontualmente com separação de responsabilidades e disciplina de consultas. Esta versão em português não adota a stack visual daquele repositório. Veja [origem e diferenças](../../../docs/agents/tooling.md#skills-de-padrões-de-backend-e-frontend).
