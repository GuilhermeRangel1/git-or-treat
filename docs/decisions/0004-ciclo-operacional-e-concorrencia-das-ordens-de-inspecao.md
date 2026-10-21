# ADR-0004 — Ciclo operacional, auditoria e concorrência das ordens de inspeção

**Data:** 2026-10-20  
**Estado:** aprovada  
**IDs do PRD afetados:** WEB-04, WEB-05, WEB-11  

## Contexto

O requisito [WEB-05](../PRD.md#62-portal-web-e-backend--web) exige que o usuário crie ordens de inspeção a partir da fila de suspeitas, altere o status, registre o resultado de campo e cancele ordens desnecessárias, impedindo transições inválidas e repetições indevidas.

Na validação manual do protótipo Figma (`docs/design/grid360-prototype.md`), identificou-se uma regressão: após cancelar a ordem `OS-DEMO-001`, reabrir as ações reexibia status simulado e permitia reativá-la. Além disso, o guia de backend (`docs/services/backend.md`) apontava a necessidade de definir estados formais, validação de transições no servidor, histórico auditável de alterações, política para ordens simultâneas na mesma UC e controle de concorrência.

## Opções consideradas

1. **Alteração direta de campos na tabela operacional sem validação formal de máquina de estados ou histórico:** simples e rápida, porém frágil: permite transições ilegais, não evita a reativação indevida de ordens canceladas, não oferece rastreabilidade para auditoria e permite sobrescritas concorrentes descontroladas.
2. **Máquina de estados estrita no servidor com controle de concorrência otimista, idempotência e tabela dedicada de histórico:** define estados e transições válidas, torna ordens canceladas e concluídas imutáveis, exige resultado de campo para encerramento, registra trilha de auditoria em tabela separada e protege contra repetições de cliques e conflitos concorrentes.
3. **Event sourcing completo com CQRS:** alta complexidade operacional e de modelagem, desproporcional à escala do case e à separação já estabelecida entre dados operacionais e analíticos Gold.

## Decisão

Adotou-se a **Opção 2**:

1. **Estados e transições:**
   - Estados: `PENDENTE`, `EM_ANDAMENTO`, `CONCLUIDA`, `CANCELADA`.
   - Transições permitidas:
     - `PENDENTE` → `EM_ANDAMENTO`, `CANCELADA`, `CONCLUIDA` (exige resultado).
     - `EM_ANDAMENTO` → `CONCLUIDA` (exige resultado de campo), `CANCELADA`.
     - `CONCLUIDA` → estado terminal imutável.
     - `CANCELADA` → estado terminal imutável.
   - Qualquer tentativa de reativar ou alterar uma ordem cancelada é recusada pelo servidor com HTTP 409 Conflict, eliminando a regressão identificada no protótipo.
2. **Campos obrigatórios:**
   - Criação: `uc_id` e `reason` não vazios; prioridade restrita a `BAIXA`, `MEDIA`, `ALTA`, `CRITICA` (padrão `MEDIA`).
   - Conclusão / Registro de resultado: `result` obrigatório e não vazio.
   - Cancelamento: identifica a ordem pelo identificador na rota (`/orders/{id}/cancel`) e suporta justificativa em `reason`.
3. **Histórico auditável:**
   - Tabela `operational_order_history` gravando chave da ordem, status anterior, status novo, tipo de ação (`CRIACAO`, `ATUALIZACAO_STATUS`, `REGISTRO_RESULTADO`, `CANCELAMENTO`), notas, detalhes textuais e timestamp UTC.
   - Endpoint de consulta: `GET /api/v1/inspections/orders/{order_id}/history`.
4. **Idempotência e repetições:**
   - Suporte a `idempotency_key` (via corpo JSON ou header `X-Idempotency-Key`). Requisições repetidas com a mesma chave retornam a ordem já criada sem duplicar registros ou histórico.
   - Regra de duplicidade ativa: não é permitido criar uma nova ordem para uma UC que já possua ordem em `PENDENTE` ou `EM_ANDAMENTO` (HTTP 409). Quando a ordem anterior for concluída ou cancelada, a UC pode ser priorizada novamente em um novo ciclo.
5. **Controle de concorrência:**
   - Coluna `version` (inteiro incremental com valor inicial 1).
   - Endpoints de atualização aceitam `version`; divergências entre a versão enviada e a versão no banco resultam em HTTP 409 Conflict informando a necessidade de recarregar a tela.

## Consequências e verificação

- O backend rejeita no servidor qualquer estado inconsistente ou transição proibida, inclusive se a interface cliente omitir validações.
- As migrações Alembic foram atualizadas com nova revisão (`c4b1a239d8e7`) que adiciona as colunas de ciclo de vida e a tabela de histórico, testada em SQLite e PostgreSQL descartáveis.
- O ciclo completo foi testado em 28 testes automatizados no backend cobrindo criação, transições, resultado obrigatório, cancelamento com identificação da ordem, histórico, idempotência, duplicidade ativa, concorrência otimista e prevenção da regressão do protótipo.
