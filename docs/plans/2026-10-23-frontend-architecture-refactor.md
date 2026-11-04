# Refatoração da arquitetura do frontend

## Escopo aprovado

A pessoa usuária aprovou cinco ajustes: consolidar botões e estrutura dos modais; mover recursos exclusivos do Panorama para a feature; dividir responsabilidades da UC 360; remover código sem uso e atualizar documentação; avaliar carregamento por rota com medida do bundle. Requisitos relacionados: WEB-01 a WEB-04, WEB-07 e organização ENT-03/ENT-04. Dependência: contratos demonstrativos existentes da DEV-01. A refatoração não conclui integração Gold.

### Ajuste de escopo durante a execução

A pessoa usuária adiou as mudanças do Panorama para sua futura revisão visual. A movimentação interna realizada na etapa 2 será desfeita; os arquivos atuais da página e seus recursos em shared serão preservados. As outras etapas continuam autorizadas. O Panorama mantém import estático; o carregamento sob demanda fica nas demais rotas. As medidas da etapa 2 abaixo são intermediárias e serão substituídas pelas medidas do escopo final na evidência.

## Restrições comuns

- Manter contratos HTTP, cálculos, filtros na URL, navegação e aparência vigente nos dois temas.
- Manter rascunhos locais e consultas com TanStack Query, decoder e cancelamento.
- Recursos específicos ficam na feature; shared contém recursos transversais concretos.
- Preservar semântica, Escape e retorno de foco dos diálogos.
- Sem dependências novas, commits ou push nesta execução.
- Implementação por subagentes Luna/high; coordenação e revisão pelo agente principal.

## Etapas

1. Consolidar variantes de Button e uma estrutura de Modal nativo compartilhado. Migrar filtros de Receita/Inspeções e fundamento de Inspeções, mantendo regras específicas na feature. Adaptar testes comportamentais pertinentes.
2. Mover módulos exclusivos de shared/analytics e shared/filters para features/panorama, atualizando consumidores e testes. Medir build antes/depois e aplicar React.lazy por rota se demonstrar redução do carregamento inicial, com Suspense preservando layout e testes de navegação.
3. Extrair busca, detalhe e controles coerentes de UC360Page sem copiar estado ou regras de URL. Remover QueueOverview/PriorityScore após confirmar ausência de consumidores. Atualizar guia arquitetural para descrever estado atual sem afirmações históricas contraditórias.
4. Revisar cada diff, executar suíte frontend e gates existentes, conferir fluxos no navegador quando disponível, registrar resultados e limitações no PRD e guia do serviço.

## Verificação

Testes existentes de navegação, Panorama, Receita, UC 360 e Inspeções; verificações de lint, fronteiras, formatação e build. Conferir filtros aplicar/cancelar/Escape/foco, fila/detalhe, busca/detalhe UC e navegação por rotas. Medidas de bundle serão tamanhos dos artefatos de produção, não alegações de latência sem medição.

## Progresso

- Base: 4db7de9; árvore limpa ao iniciar.
- Build inicial observado: Vite 8.3.4, JavaScript de entrada 474,91 kB (138,21 kB gzip), CSS 43,67 kB (9,04 kB gzip). `npm.cmd run build` passou.
- Etapa 1 implementada e revisada pelo principal: Modal compartilhado e variantes de Button adotados em Receita/Inspeções. Testes focados 43/43, lint, formatação, build e diff-check passaram. No navegador, filtros em 390/1440 px e claro/escuro mantiveram medidas e cores iguais entre páginas, sem overflow, com Escape e retorno de foco; fechar e reabrir funcionou. Relatório local: `work/architecture-ui-report.md`.
- Etapa 2 concluída no escopo revisado: movimentação do Panorama desfeita e diff dos arquivos preservados zerado contra a base; demais rotas usam lazy, com Panorama estático. Fonte React consultada via Context7: [lazy](https://react.dev/reference/react/lazy), React 19.2.8 do projeto, em 23/10/2026. Relatório local: `work/architecture-panorama-report.md`.
- Etapa 3 implementada e revisada: UC360Page passou de 876 para 188 linhas, com busca, detalhe, período, métricas e interpretação separados. Revisão corrigiu a ordem dos blocos, a ação de seleção de histórico e a duplicação de formatação. Dois componentes sem consumidores removidos e guias atualizados. Testes focados UC 360: 9/9. Relatório local: `work/architecture-uc360-report.md`.
- Etapa 4 concluída: suíte integral 131/131 em 16 arquivos, lint, fronteiras em 91 arquivos, formatação, build e diff-check passaram. Entrada JS final 351,27 kB / 109,63 kB gzip. Conferência no navegador de busca/detalhe/período/legado UC 360 e chunks de produção passou. [ADR-0013](../decisions/0013-composicao-ui-e-carregamento-frontend.md) e [evidências](2026-10-23-frontend-architecture-evidence.md) registram decisões e limites. Sem commits ou push nesta execução. Trello indisponível para o quadro indicado: sincronização pendente.
