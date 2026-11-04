# DEV-07 — evidências da integração frontend e revisão

Data: 25/10/2026. Requisito WEB-05, dependência DEV-06. Execução por dois subagentes GPT-6 Luna/high, com revisão de especificação, qualidade e integração pelo agente principal. [Plano executado](2026-10-25-dev07-conclusao.md).

## Mudança observável

O diálogo contextual de `/ordens` consulta a ordem atual antes de agir. Uma ordem pendente pode ser iniciada; uma ordem em andamento pode registrar resultado e concluir. O cancelamento usa confirmação que identifica OS e UC e aceita motivo opcional. Estados concluído/cancelado permitem consulta do resultado e histórico, sem controles de escrita.

O cliente valida `version`, `cancellation_reason` e os eventos de histórico em execução. As três mutações enviam a versão recebida; resultado/cancelamento usam suas rotas próprias. O histórico preserva estados e detalhes efetivamente registrados, inclusive eventos legados sem ator/versão. Um evento de resultado não implica conclusão quando o estado registrado não a confirma.

Envios simultâneos são bloqueados. Conflitos 409 consultam o estado atual e preservam o rascunho sem repetir a escrita; no cancelamento, a confirmação é encerrada para nova revisão da intenção. Fechar o diálogo não cancela uma gravação já enviada: a resposta posterior atualiza caches, mas não fecha outra sessão. Uma resposta atrasada com versão menor não substitui um detalhe mais recente nem anuncia sucesso de um estado ultrapassado.

## Revisão pelas skills

- `frontend-coding-standards`: fronteira HTTP com JSON desconhecido validado, TanStack Query para estado remoto, rascunhos locais, identidade da ordem, atualização do cache após servidor, temas, foco, erro/vazio/carregamento e ausência de informações legadas.
- `backend-coding-standards`: conferência dos schemas/rotas e das regras de transição, versão, confirmação do ID e transação entre ordem e histórico. O ciclo operacional existente foi mantido.
- `vercel-react-best-practices`: consultas limitadas ao contexto aberto, AbortSignal nas leituras e histórico como componente da feature, sem nova dependência.
- Referência técnica: Context7 `/tanstack/query`, documentação de invalidação após mutações e de ausência de repetição automática; pacote instalado `@tanstack/react-query` 5.104.4.

A revisão corrigiu campos inicialmente omitidos no retorno do decoder, uma fixture de resposta inconsistente, callbacks tardios, regressão de cache por versão e quebra de texto longo em grids. Os casos de concorrência têm testes comportamentais; o texto longo foi verificado no navegador.

## Checklist DEV-07

| Item | Implementação/evidência |
| --- | --- |
| Estados, transições e campos | Backend define PENDENTE → EM_ANDAMENTO/CANCELADA e EM_ANDAMENTO → CONCLUIDA/CANCELADA; conclusão exige resultado. A tela oferece ações correspondentes. |
| Validação no servidor | Ausência de versão retorna 422; transição de cancelada para andamento retorna 409 `invalid_transition`. |
| Resultado de campo | UI chamou POST `/orders/1/result`: HTTP 200, resultado persistido, estado CONCLUIDA e versão 3. |
| Histórico | OS 1 possui criação/início/resultado; OS 2 possui criação/cancelamento, com ator, versão e detalhes. Leitura SQL e HTTP concordam. |
| Cancelamento identificado | Confirmação mostrou OS-000002 e UC-1002; POST enviou `confirmed_order_id: 2`, versão 1 e motivo. Resposta CANCELADA, versão 2. ID divergente retornou 409 `confirmation_mismatch`. |
| Repetição e concorrência | Replays com versão atual retornaram 200 sem novos eventos. Escrita concorrente elevou OS 3 a versão 2; a UI tentou uma única escrita v1, recebeu 409 `version_conflict` e consultou a nova versão sem reenvio. |
| Reabrir cancelada | Reload e duas reaberturas de OS 2 mantiveram CANCELADA, resultado desabilitado e zero PATCH/POST disparados ao abrir. |

## Verificações executadas

Frontend, em `frontend/`:

- `npm.cmd test -- src/shared/api/orders.test.ts --maxWorkers=2`: 13 testes aprovados após revisão do cliente.
- `npm.cmd test -- --maxWorkers=2`: 213 testes em 28 arquivos aprovados na execução final da interface.
- Após o último reforço de sincronização do teste de resposta atrasada, o recorte cliente/diálogo/histórico/página foi repetido pelo agente principal: **41 testes em quatro arquivos aprovados**; formatação novamente aprovada.
- `npm.cmd run check:boundaries`: 121 arquivos verificados.
- `npm.cmd run format:check` e `npm.cmd run lint`: aprovados.
- `npm.cmd run build`: tipos e build de produção aprovados pelo agente principal.

Backend, em `backend/`, com `TEST_POSTGRES_URL` apontando exclusivamente para PostgreSQL descartável `*_test`, role sem SUPERUSER:

- `venv/Scripts/python.exe -m pytest -q`: **320 testes aprovados, nenhum ignorado**. Um aviso de depreciação Starlette/HTTPX, sem falha.
- Ambiente da primeira execução: Python 3.11.9 e PostgreSQL 18.1 locais. O alvo Python 3.12/container foi reexecutado depois da aprovação da interface, conforme o registro abaixo.
- `venv/Scripts/python.exe -m alembic upgrade head`: migração do banco demo novo até `a7d070000001` aprovada.

Antes da correção da integração, a suíte revelou 16 falhas: rotas públicas de chat/insight não montadas, dois testes esperando sucesso de consulta Gold indisponível e um teste supondo uma única head Alembic. Foram restaurados os dois routers de `develop`, reconciliadas as respostas 503 controladas e comparado o conjunto completo de revisions antes/depois do rollback. As migrações e a lógica GenAI não foram modificadas; 75 testes focados e a suíte completa posterior passaram.

### Reexecução no alvo Python 3.12/container

A pessoa usuária aprovou a interface em 25/10 e solicitou eliminar a ressalva do ambiente local antigo. A imagem foi reconstruída com o Dockerfile do projeto, base `dhi.io/python:3.12-alpine3.24-dev`, e o código atual. O contexto foi limitado a app/tests/alembic/scripts, requirements e alembic.ini: sem `.env`, banco ou dataset. As dependências foram instaladas novamente pelo próprio Dockerfile.

- Runtime confirmado: **Python 3.12.15**, Linux Alpine. Imagem validada: `git-or-treat-backend:dev07-validation312`, ID `sha256:73fad9204d24292376b9aa9cc7c77cb5d1ed3c24dcc6f17a83f3ba767922d53f`.
- Banco: **PostgreSQL 16.13**, mesma versão principal do serviço do CI, em container/rede exclusivos sem portas publicadas. O script `backend/scripts/prepare_test_postgres.sql` preparou a role de migração; consulta a `pg_roles` confirmou `rolsuper=false`.
- `docker run --rm --network dev07-validation312-net ... git-or-treat-backend:dev07-validation312 python -m pytest -q --junitxml=/reports/junit-python312-postgres.xml`: **320 aprovados, zero falhas e zero ignorados, 32,70 s**. Um aviso Starlette sobre a futura substituição de HTTPX pelo test client, sem falha.
- `docker run --rm git-or-treat-backend:dev07-validation312 python -m pip check`: `No broken requirements found.`
- `docker run --rm git-or-treat-backend:dev07-validation312 python -m compileall -q app tests scripts`: aprovado.
- Versões observadas: FastAPI 0.162.0, SQLAlchemy 2.1.6, Alembic 1.20.1, psycopg 3.3.6 e pytest 9.1.1. Relatório JUnit local em `work/dev07-execution/python312-reports/junit-python312-postgres.xml`, ignorado pelo Git.
- Ao concluir, o container PostgreSQL e sua rede exclusiva foram removidos; a prévia 5187/API 8017 e o banco usado na homologação foram preservados. Nenhuma correção de código foi necessária nesta reexecução.

O Python 3.11.9 era a versão usada para criar o venv local existente; um venv não troca seu interpretador ao atualizar o repositório. A versão de referência continua sendo 3.12, já indicada no README, Dockerfile e CI. Não há requisito para manter duas versões do backend.

## Navegador e persistência

- Prévia separada em `http://localhost:5187/ordens`, API 8017; serviço existente em 5173 preservado. Banco demo novo, distinto do banco dos testes e dos bancos de desenvolvimento.
- Criação a partir das suspeitas UC-1004 e UC-1002 pela interface. UC, motivo, referência e snapshot foram preservados. Todas as respostas de escrita usadas pela interface vieram da API real.
- Após recarregar a página e reiniciar a API, OS 1 permaneceu CONCLUIDA v3, com resultado e três eventos; OS 2 permaneceu CANCELADA v2, com motivo e dois eventos. Consulta independente via `psql` ao banco operacional confirmou os mesmos valores.
- Repetição de resultado/cancelamento não mudou as contagens de eventos (3 e 2). Reabertura de cancelada não escreveu. Versão ausente, transição inválida e confirmação de outro ID foram recusadas.
- Teclado: Escape fecha o diálogo e devolve foco ao botão contextual da ordem.
- Regressão DEV-06: descartar ajustes preservou a URL e restaurou o rascunho; aplicar “Com resultado” retornou apenas OS 1, inclusive após reload. “Sem resultado”, `page_size=1` e página 2 permaneceram na URL e na consulta após recarga. Os fundamentos de OS 1 preservaram motivo, referência, fonte sintética, janela e estimativa de 45 kWh.
- Matriz claro/escuro em 320, 390, 768 e 1440 px: página e diálogo sem overflow horizontal, inclusive com motivo de cancelamento de 4.000 caracteres sem espaços. O defeito inicial (scrollWidth 27.826 px em diálogo de 336 px) foi corrigido com limites de grid e quebra de texto em qualquer posição.
- Capturas conferidas pelo revisor em `work/dev07-execution/ordens-dark-390.png` e `ordens-light-1440.png`; arquivos locais ignorados, sem inclusão no repositório.

## Limites e estado

Fonte analítica exclusivamente sintética; nenhuma validação ou reconciliação Gold é afirmada. A aprovação da interface pela pessoa usuária e a validação do alvo Python 3.12 estão registradas acima. O estado de WEB-05 no PRD permanece **Em validação**; esta reexecução não altera seu escopo. Não houve alteração do modelo de autenticação nem nova migração.

O Trello está conectado, mas as buscas por WEB-05 e pelo quadro V-Energy não retornaram recursos acessíveis; sincronização pendente. O índice do merge já preparado foi preservado. Esta execução não criou commits nem realizou push. Os serviços de revisão permanecem disponíveis para a inspeção solicitada pela pessoa usuária.
