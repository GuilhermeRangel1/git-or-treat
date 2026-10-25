# DEV-06 — ajuste do frontend de Ordens ao protótipo

**Objetivo:** implementar a seção `05 · Ordens` aprovada no Figma, conectada às ordens reais do backend demonstrativo, com temas claro/escuro e composição responsiva.

**Referência:** arquivo `oTjmpIBgbA7OOYb9ZmMG9K`; lista desktop `16:640`/`16:1894`, mobile `195:8099`/`198:8416`; ações `16:710`/`16:1964` e `195:8186`; erro `211:4904`; confirmação `211:4967`. Contextos completos e screenshots consultados em 24/10/2026. A solicitação define o protótipo como direção aprovada, sem redesenho.

**Arquitetura:** manter React/Vite, TanStack Query, URL para filtros/página, transporte JSON existente, layout persistente, Button/Modal e tokens. Reproduzir hierarquia, tabela de cinco colunas, registros mobile, painéis e confirmação, com semântica HTML e comportamento real. Não copiar os dados demonstrativos do Figma nem seus textos que dizem que nada é persistido. O erro de resultado será consequência da validação do formulário, sem botão artificial de simulação.

**Esclarecimento de interface:** a pessoa usuária pediu conferir a camada 05 para distinguir abertura dos ajustes da ordem de um fluxo de filtros. A seção consultada especifica `Abrir ações`/`Ações da ordem`, com estado, resultado e cancelamento. Não acrescentar barra/modal de filtros nessa tela. Reutilizar a estrutura de modal já padronizada no portal, preservando foco/Escape; o suporte aos filtros do contrato continua na URL/API, incluindo o recorte por UC vindo da fila.

## Responsabilidades

1. **Subagente Luna/high — lista e página.** `frontend/src/features/ordens/OrdensPage.tsx`, componente de tabela, parser de URL e testes da página. Cabeçalho existente, origem/atualização verdadeira, tabela/registro mobile, carregamento, vazio, erro, dados anteriores sinalizados, filtros UC/estado/prioridade e paginação na URL. Ações por ordem, feedback somente após servidor, botão de retorno à fila e fundamentos. Sem barra/modal de filtros adicional ao fluxo da camada 05.
2. **Subagente Luna/high — painéis e integração.** `OrderActionsDialog.tsx`, `OrderFoundationsDialog.tsx`, testes próprios e `shared/api/orders.ts`/teste. Acrescentar consulta por ID e PATCH com decoders, validar resultado e transições, confirmação de cancelamento, bloquear mutações de ordens finais e reconciliar 409. Incrementos reutilizáveis em Button/Modal/tokens somente quando necessários para expressar o Figma.
3. **Agente principal — integração e execução local.** Revisar os dois diffs; adicionar inicializador de demo persistente, ajustar metadados da rota se necessário e documentar evidências. Fazer gates e jornada com API real em navegador, nos dois temas e em larguras estreita/intermediária/desktop.

## Interfaces entre tarefas

- `OrderActionsDialog({order, open, onClose, triggerRef, onSaved})`: `order: Order | null`, `onSaved: (order: Order, message: string) => void`; props de abertura/fechamento/foco seguem `Modal`.
- `OrderFoundationsDialog({order, open, onClose, triggerRef})`, mesma identidade e foco, consulta detalhe por ID. Não importar internals da feature Inspeções.
- API: manter `createQueueOrder` e `searchOrders`; acrescentar `getOrderDetail(id, signal?)` e `updateOrder(id, payload)` com JSON validado, `OrderDetail` contendo snapshot opcional. Filtros e estados usam os nomes aceitos pelo backend.
- PENDENTE permite iniciar/cancelar; EM_ANDAMENTO permite concluir/cancelar; conclusão exige resultado; CONCLUIDA/CANCELADA são finais. A interface não reabre ordens. Resultado pode ser salvo em ordem ativa sem concluir automaticamente.

## Verificação e limites

- [ ] Testes de filtros/paginação/URL, estados remotos, ordem correta nas ações, resultado obrigatório, bloqueio durante envio, falha e conflito, confirmação e estado final.
- [ ] Lint, fronteiras, formatação, testes e build frontend; sem novas dependências.
- [ ] API real: criar pela fila, abrir Ordens, atualizar/registrar/cancelar, recarregar e verificar persistência; teclado/Escape/retorno de foco.
- [ ] Inspeção visual claro/escuro a 390 e 1440 px, reflow 320 e largura intermediária, com capturas em `work/`.
- [ ] Inicializador local com SQLite em arquivo, Alembic e demo sem login; verificar reinício sem perder ordem. Não tocar em bancos existentes ou `.env` privados.
- [ ] Atualizar PRD/guia frontend com evidências. WEB-05 permanece em validação enquanto Gold, homologação e auditoria durável estiverem pendentes. Preservar alteração alheia de `frontend/package-lock.json`.
