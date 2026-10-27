# DEV-07 — conclusão do ciclo operacional de ordens

> Execução: dois subagentes GPT-6 Luna, esforço high, em sequência; o agente principal revisa especificação e qualidade após cada entrega e valida a integração final. A solicitação da pessoa usuária autoriza iniciar a execução deste plano.

**Objetivo:** concluir a jornada WEB-05 de alteração de estado, resultado, cancelamento e histórico pela página de Ordens, integrada ao backend DEV-07.

**Arquitetura:** evoluir o cliente HTTP e o diálogo contextual já existentes. TanStack Query mantém detalhe, lista e histórico; rascunhos ficam no componente. O servidor confirma as alterações e controla transições, auditoria e concorrência por versão.

**Tecnologias:** React, TypeScript, Vite, TanStack Query, Tailwind, FastAPI, SQLAlchemy e Alembic existentes.

**Especificação:** [PRD WEB-05](../PRD.md), [contrato DEV-07](../contracts/inspection-lifecycle-dev07.md), [guia frontend](../services/frontend.md) e [guia backend](../services/backend.md). Dependência: DEV-06.

## Skills e regras de execução

- Aplicar [frontend-coding-standards](../../.agents/skills/frontend-coding-standards/SKILL.md) na implementação e revisão da interface, contratos HTTP, cache, temas, acessibilidade e testes.
- Aplicar [backend-coding-standards](../../.agents/skills/backend-coding-standards/SKILL.md) na conferência dos schemas, endpoints, transações, erros e concorrência que a interface consome; qualquer correção de backend descoberta exige a mesma revisão.
- Aplicar [vercel-react-best-practices](../../.agents/skills/vercel-react-best-practices/SKILL.md) às recomendações pertinentes ao React/Vite; executar testes comportamentais significativos.
- Ler os AGENTS.md da raiz e de cada área alterada. O PRD e o contrato aprovado definem o comportamento.
- Trabalhar na branch dev-07 existente. Há integração de develop previamente preparada no índice; preservar essas alterações e revisar a implementação nova pelo diff do diretório de trabalho contra o índice. Não misturar commits ou alterar o índice durante as tarefas delegadas.
- Não alterar autenticação, modelos ou migrações sem falha concreta encontrada na integração. Não incluir segredos, dados reais ou capturas no Git.
- Preservar barra/modal de filtros, paginação, fundamentos e ação contextual por registro da DEV-06.
- Registrar progresso e evidências reais; não marcar WEB-05 concluído apenas com testes simulados. Commit e push ficam para solicitação própria.

## Pontos de atenção da revisão

1. Uma tela obsoleta recebe 409; nenhuma escrita é repetida automaticamente com a nova versão.
2. Perda de resposta não comprova rollback: reconciliar o estado e preservar o rascunho sem anunciar sucesso.
3. Abrir, fechar ou reabrir uma ordem cancelada/concluída não dispara escrita nem libera edição.
4. Clique repetido enquanto há envio não duplica alteração, resultado ou cancelamento.
5. Histórico legado pode estar vazio ou ter ator/versão nulos; apresentar essa ausência sem inventar eventos.

## Tarefa 1 — cliente HTTP e contrato DEV-07

**Responsável:** subagente 1, GPT-6 Luna/high. Revisão: agente principal.

**Arquivos:** `frontend/src/shared/api/orders.ts`, `orders.test.ts` e fixtures dos testes que consomem ordens (incluindo páginas, roteador e criação pela fila).

**Interfaces produzidas:**

- `Order`/`OrderDetail` com `version: number` positiva e `cancellation_reason: string | null`.
- `UpdateOrderPayload` com versão obrigatória; PATCH não admite CANCELADA.
- `registerOrderResult(id, {version, result, notes?})`, usando POST `/orders/{id}/result`, retornando `OrderDetail`.
- `cancelOrder(id, {version, confirmed_order_id, reason?})`, usando POST `/orders/{id}/cancel`, retornando `OrderDetail`.
- `getOrderHistory(id, signal?)`, retornando eventos tipados e validados com os campos de `OrderHistoryResponse`. Ações: CRIACAO, ATUALIZACAO_STATUS, REGISTRO_RESULTADO, CANCELAMENTO.

- [x] Conferir os schemas reais e escrever testes que recusem JSON inválido, versões ausentes/inválidas, estado/ação desconhecidos e histórico malformado; aceitar ator/versão legados nulos.
- [x] Implementar tipos, decoders e funções com `apiClient<unknown>`, preservando AbortSignal na leitura.
- [x] Atualizar fixtures para o contrato atual sem remover asserções comportamentais existentes; não adaptar ainda o diálogo, reservado à tarefa 2.
- [x] Verificar rotas, métodos e payloads, inclusive confirmação de ID no cancelamento, e executar os testes focados do cliente.
- [x] Agente principal revisa o diff e o contrato antes de liberar a tarefa 2. Incompatibilidades transitórias de tipos no diálogo antigo são resolvidas na tarefa seguinte.

## Tarefa 2 — ações e histórico na interface

**Responsável:** subagente 2, GPT-6 Luna/high, após aprovação da tarefa 1. Revisão: agente principal.

**Arquivos:** `frontend/src/features/ordens/OrderActionsDialog.tsx`, seu teste, `order-actions.ts`, novo `OrderHistory.tsx` e seu teste, e integração de Ordens quando necessária.

**Interfaces consumidas:** funções/tipos da tarefa 1; propriedades atuais de `OrderActionsDialog`; componentes Button/Modal e tokens semânticos existentes.

- [x] Adaptar as interações às ações válidas: PENDENTE pode iniciar; EM_ANDAMENTO pode registrar resultado e concluir; ambas podem cancelar; estados finais ficam somente para consulta.
- [x] Usar uma ação explícita “Registrar resultado e concluir”, exigindo texto não vazio de até 4.000 caracteres e enviando a versão atual. Remover a mensagem antiga que afirma que registrar resultado não conclui a ordem.
- [x] Usar a rota dedicada de cancelamento com código da ordem e UC na confirmação, `confirmed_order_id` e versão atuais, e motivo opcional. Voltar da confirmação não escreve e preserva o rascunho.
- [x] Consultar e exibir histórico no diálogo, com data, ação, estados e detalhes; identificar ator/versão ausentes como não informados. Distinguir carregamento, vazio e falha com opção de repetir consulta.
- [x] Após sucesso validado, atualizar detalhe/invalidate lista e histórico. Bloquear submissões simultâneas; consultar o estado atual ao reabrir.
- [x] Em 409, mostrar o conflito e reconciliar os dados sem reenviar a escrita; preservar rascunhos e exigir nova interação consciente. Em erro de rede, informar ausência de confirmação.
- [x] Atualizar os testes da interface para transições, resultado/conclusão, confirmação identificada, histórico, conflitos, erro de rede e clique repetido. Cobrir reabertura de cancelada sem PATCH/POST e tentativas de edição bloqueadas.
- [x] Conferir foco, teclado, rótulos e estados terminais nos temas claro/escuro. Agente principal revisa especificação e qualidade.

## Tarefa 3 — verificação integrada e documentação

**Responsável:** agente principal, como revisor e integrador.

- [x] Executar testes focados de Ordens/cliente e, depois, uma execução da suíte frontend; executar `npm.cmd run check:boundaries`, `format:check`, `lint` e `build` em `frontend/`.
- [x] Executar a suíte backend pertinente ao ciclo, contratos e DEV-06; usar PostgreSQL descartável nas verificações específicas de persistência/concorrência, sem atingir banco de desenvolvimento.
- [x] Com API real e dados sintéticos isolados, criar pela fila, iniciar, registrar resultado/concluir e cancelar outra ordem; consultar histórico e confirmar resultado após reload e reinício da API.
- [x] Exercitar duas consultas concorrentes, repetir envio e tentar transição inválida; conferir 409/422 sem efeitos duplicados. Reabrir ações de cancelada e confirmar ausência de reativação.
- [x] Conferir interface no navegador em desktop/mobile, claro/escuro, preservando filtros/paginação e fundamentos da DEV-06.
- [x] Atualizar `docs/contracts/inspection-lifecycle-dev07.md`, guias afetados e registro de progresso do PRD com comandos/resultados reais e limites. Sincronizar Trello WEB-05 se disponível e autorizado pelo fluxo do projeto; se não disponível, registrar a pendência.
- [x] Atualizar este plano com as etapas concluídas e evidências. Falhas ou evidências faltantes mantêm o aceite em validação.

## Critério de conclusão

O ciclo criação → início → resultado/conclusão e a alternativa criação → cancelamento funcionam pela interface, persistem no banco operacional após reload/reinício e possuem histórico. Transições inválidas, alterações obsoletas e repetições indevidas não produzem efeitos. Reabrir ações não reativa uma ordem cancelada. A revisão final confronta cada item do checklist DEV-07 com sua evidência; o estado global de WEB-05 segue as condições do PRD.


## Registro de execução — 25/10/2026

- Tarefas 1 e 2 executadas por subagentes GPT-6 Luna/high; revisão do agente principal corrigiu decoders, callbacks tardios, cache por versão e overflow de texto longo.
- Integração de develop corrigida após falhas observadas: routers públicos de IA restaurados, testes de resposta indisponível e rollback multibranch reconciliados; nenhuma migração ou regra GenAI nova.
- Frontend: 213 testes em 28 arquivos; fronteiras em 121 arquivos, formatação, lint e build/tipos aprovados. Backend: 320 testes aprovados sem ignorados em Python local 3.11.9/PostgreSQL 18.1 e, na reexecução solicitada, 320 aprovados em Python 3.12.15/container com PostgreSQL 16.13 descartável. Pip check e compileall também aprovados na imagem.
- API real e SQL independente confirmaram persistência após reload/reinício, replays sem eventos duplicados, recusas 409/422 e cancelada sem reativação. Matriz de quatro larguras nos dois temas sem overflow; filtros, paginação, fundamentos e Escape/foco preservados.
- A pessoa usuária aprovou a interface em 25/10; a ressalva de validação no alvo Python 3.12 foi encerrada pela reexecução. WEB-05 mantém o estado Em validação do PRD. Trello sem recurso acessível; serviços de revisão mantidos em 5187/8017 para inspeção solicitada. Índice preservado; sem commits/push nesta execução.
- Evidências: [registro completo](2026-10-25-dev07-evidencias.md).
