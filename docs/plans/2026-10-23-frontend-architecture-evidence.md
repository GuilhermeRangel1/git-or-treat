# Evidências da refatoração do frontend

## Escopo e base

Solicitação aprovada: consolidar botões/modais, dividir UC 360, remover componentes sem uso, atualizar documentação e avaliar carregamento por rota. A reorganização do Panorama foi adiada pela pessoa usuária durante a execução e será desfeita nesta entrega; sua implementação e import estático serão preservados. Base: `4db7de9`, branch `dev05`. [Plano](2026-10-23-frontend-architecture-refactor.md). Implementação por três subagentes Luna/high; revisão e conferência no navegador pelo principal.

## Evidência observada

- Etapa UI: 43 testes focados Receita/Inspeções aprovados, lint, Prettier e build aprovados. O modal mantém conteúdo renderizado somente enquanto aberto; seu ciclo nativo, Escape e foco ficam compartilhados.
- Navegador local com API sintética: filtros Receita/Inspeções em 390×844 e 1440×844, ambos os temas, sem overflow horizontal na página ou no modal; largura de 337,2 px no mobile e 720 px no desktop. Botões Aplicar com 44 px, fundo/texto claro `rgb(168,63,77)`/branco e escuro `rgb(238,135,148)`/`rgb(33,26,28)`. Escape retorna foco em todos os casos. Fechar/reabrir e fechamento nativo externo foram conferidos. Fundamento da UC-1004 mantém prioridade 0,92 e energia 45 kWh.
- Navegação nas sete áreas conservou o mesmo elemento de sidebar. Diagnóstico continua restrito ao desenvolvimento. Após o ajuste de escopo, `git diff --exit-code` confirmou ausência de mudanças nos arquivos do Panorama e nos recursos existentes em shared/analytics, shared/filters, MetricCard e ContentState.
- Build inicial: JavaScript de entrada 474,91 kB/138,21 kB gzip. Build final: 351,27 kB/109,63 kB gzip, redução de 26,0%/20,7% gzip, mantendo Panorama estático. Receita, UC 360 e Inspeções emitem módulos de 42,26/46,25/31,10 kB. Tamanhos dos artefatos não são medidas de latência.
- Preview local de produção em 4173 reconferido após o build final: Panorama usa o módulo de entrada; Receita e Modal só são solicitados ao navegar para Receita; UC360 e seu ícone só são solicitados ao abrir a busca. A sidebar permaneceu montada. O preview comprova entrega dos módulos; as jornadas com API sintética foram exercitadas em 5173.
- UC 360: busca por 1001 abriu a UC canônica UC-1001; editar período não mudou a URL antes de Aplicar. Aplicar fevereiro/2025 atualizou URL, período e métricas; zero permaneceu explícito. O link legado `?uc=UC-1001&start=2025-01&end=2025-02&section=invoices` redirecionou para o detalhe canônico preservando período/seção. Mobile 390×844 com largura de conteúdo 375 px e scrollWidth 375 px, sem overflow.
- UC360Page passou de 876 para 188 linhas. Busca, detalhe, período, resumo/comparação e interpretação têm responsabilidades próprias; a revisão preservou a ordem visual anterior e a seleção de histórico sem rolagem adicional. QueueOverview e PriorityScore foram removidos após confirmação de ausência de consumidores.

## Verificações finais

- `npm.cmd test -- --reporter=dot`: 131 testes aprovados em 16 arquivos, 15,03 s.
- `npm.cmd run lint`: passou.
- `npm.cmd run check:boundaries`: passou em 91 arquivos.
- `npm.cmd run format:check`: passou.
- `npm.cmd run build`: TypeScript e Vite 8.3.4 passaram, tamanhos finais acima.
- `git diff --check`: passou.
- Links locais dos seis documentos de arquitetura, serviço, decisão, índice, plano e evidências: válidos.
- Revisão pelo agente principal dos diffs e dos novos componentes; implementação por Luna/high. Nenhum arquivo backend foi alterado.

## Limites e acompanhamento

Estados do PRD preservados: esta refatoração não é aceite Gold. Reorganização e revisão visual do Panorama adiadas pela pessoa usuária. Leitura do quadro Trello retornou recurso inexistente/sem acesso; sincronização pendente. Não foram criados commits ou push nesta execução. A [ADR-0013](../decisions/0013-composicao-ui-e-carregamento-frontend.md) registra a decisão aprovada.

## Relatórios locais

`work/architecture-ui-report.md`, `work/architecture-panorama-report.md` e `work/architecture-uc360-report.md` são artefatos locais ignorados pelo Git; resultados essenciais serão consolidados neste documento e no PRD.
