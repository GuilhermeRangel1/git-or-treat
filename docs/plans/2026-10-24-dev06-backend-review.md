# Revisão do backend DEV-06 — 24/10/2026

## Escopo e fontes

Base fixa: `57d2275602fd225297ab0896a47c44a8ee70b7dd`. Estado revisado: `aba1fe4`, incluindo o histórico integrado pelo merge `7205275` e as quatro correções de `9bdf782`.

Comando do diff: `git -c safe.directory=D:/git-or-treat diff 57d2275...aba1fe4 -- backend`. Dois agentes independentes revisaram Standards e Spec, conforme `.agents/skills/code-review/SKILL.md`.

Spec: checklist DEV-06 enviado pela pessoa usuária nesta conversa, WEB-05 no [PRD](../PRD.md), [contrato DEV-06](../contracts/inspection-orders-dev06.md), [ADR-0011](../decisions/0011-ordem-ativa-por-uc.md) e revisão vigente da [ADR-0012](../decisions/0012-autenticacao-individual-das-ordens.md). O acesso ao Trello não foi necessário para obter os requisitos.

Standards: `AGENTS.md`, `backend/AGENTS.md`, guia backend, skill `backend-coding-standards` e referências de camadas, dependências, Python e testes; skill de PostgreSQL para índices parciais e concorrência. Aplicada também a baseline de smells da skill de review, como heurísticas subordinadas às regras locais.

## Standards

**S1 — P3, corrigido: dependências sem `Annotated`.** Na versão `aba1fe4`, novos handlers em `backend/app/api/v1/endpoints/inspections.py:57`, `:70–72`, `:89` e `:95` usavam parâmetros com `Depends` como valor padrão. A referência `dependency-injection.md:5` pede `Annotated[T, Depends(factory)]`. As dependências dos nove handlers do módulo agora usam `Annotated`, mantendo objetos `Depends` nos decorators `dependencies=[...]`. Não foi identificado defeito funcional decorrente do padrão anterior.

**S2 — P3, corrigido: retornos públicos sem anotação.** Na versão `aba1fe4`, novos handlers em `backend/app/api/v1/endpoints/inspections.py:57`, `:66`, `:84` e `:95` não declaravam retorno Python. A referência `python-idioms-and-quality.md:7` pede retorno explícito nas funções públicas. Os nove handlers agora declaram o retorno real: modelos analíticos/Pydantic, `InspectionOrder` ou lista ORM nas operações, e união com `JSONResponse` onde há conflito 409. Os `response_model` HTTP foram preservados, sem acrescentar conversões em execução.

Não foram identificadas outras violações comprováveis em propriedade de transação, rollback, sincronismo, separação Gold/operacional, constraints de idempotência/unicidade ou snapshot. A baseline de smells não produziu achados acionáveis adicionais.

**Total Standards: 2 achados P3 corrigidos; nenhum achado aberto neste eixo.**

## Spec

**R1 — P2 documental, corrigido: contrato exige autenticação sem ressalvar demo.** Na versão `aba1fe4`, `docs/contracts/inspection-orders-dev06.md:7` apresentava Bearer obrigatório na criação; `:45`, token obrigatório na leitura; `:55`, token privado na configuração. O contrato agora distingue demo local sem Bearer e modos serviço/OIDC autenticados, conforme a revisão vigente da ADR-0012. Também esclarece que o token de escrita de serviço permite leitura e que a demo pode recusar origens de navegador com 403.

O recorte backend contempla persistência existente, criação pela suspeita, validação no servidor, preservação de UC/motivo/referência/snapshot, filtros/paginação e retorno após commit. As quatro correções estão presentes: replay antes da fonte, 409 estruturado, rollback/recuperação pós-commit e unicidade ativa por UC entre versões/origens. A preparação OIDC é registrada em decisão aprovada e não bloqueia a demo. Gold e o ciclo completo de WEB-05 não foram confundidos com o checklist DEV-06.

**Total Spec: 1 achado P2 documental corrigido; nenhum achado aberto neste eixo e nenhum defeito funcional demonstrável no recorte revisado.**

## Execução com PostgreSQL descartável

- PostgreSQL **18.1**, cluster novo em `work/dev06-review-20261024-pg18`, bind exclusivo `127.0.0.1:55446`. Banco `dev06_review_test`, papel `dev06_review` com `rolsuper=false`; nenhuma conexão a banco operacional existente.
- Python local **3.11.9**, ambiente `backend/.venv`. O alvo Docker/CI continua Python 3.12; esta execução não substitui a matriz desse ambiente.
- A primeira execução com PostgreSQL teve **251 aprovados e 1 falha**. `test_order_postgres_security.py` cria seu próprio `TestClient` e herdava o modo demo local, sem usar a fixture `client` já isolada.
- Ajustado somente esse teste para selecionar explicitamente `APP_ENV=development` e `ORDERS_AUTH_MODE=service`, mantendo as expectativas de autenticação. O agente de Standards revisou e aprovou esse ajuste de isolamento, sem novo achado.
- Com `TEST_POSTGRES_URL` apontando somente para o banco descartável, `.venv/Scripts/python.exe -m pytest -q --junitxml=../work/dev06-review-20261024-junit.xml` → **252 aprovados, nenhum ignorado**, em 16,91 s; um aviso Starlette/httpx.
- Incluídos os quatro testes PostgreSQL antes ignorados: ciclo Alembic/persistência, migração recusando duplicidades sem perda de registros, segurança/transições e concorrência com mesma chave, chaves diferentes, versões diferentes e criação manual versus fila.
- `.venv/Scripts/python.exe -m compileall -q app tests scripts` aprovado; `.venv/Scripts/python.exe -m pip check` sem incompatibilidades.
- Após a suíte, o banco continha apenas `alembic_version` vazia. Cluster encerrado por `pg_ctl stop`; artefatos sintéticos e JUnit permanecem em `work/`, fora do versionamento.

## Correções e revalidação

- Implementador solicitado pela pessoa usuária: subagente **GPT-6 Luna, esforço high**. Alterações limitadas ao módulo de rotas e ao contrato DEV-06; agente principal revisou o diff, solicitou precisão nos retornos ORM e nas permissões documentadas, e aprovou a versão corrigida.
- A comparação de OpenAPI contra `aba1fe4` preservou schemas, parâmetros, obrigatoriedade, respostas e segurança dos endpoints; a ordem dos parâmetros foi normalizada apenas para a comparação. Inspeção das assinaturas confirmou nove handlers com retorno explícito e sem `Depends` como default. Verificação local em `work/check-dev06-openapi.py`, fora do versionamento.
- Revalidação após as correções: `.venv/Scripts/python.exe -m pytest -q --junitxml=../work/dev06-review-fixes-20261024-junit.xml` com o mesmo PostgreSQL descartável → **252 aprovados, nenhum ignorado**, em 22,03 s; um aviso Starlette/httpx. Compileall aprovado; pip check sem incompatibilidades.
- Após a revalidação, apenas `alembic_version` vazia permaneceu no banco. O cluster foi encerrado novamente. Nenhum banco operacional existente foi utilizado.

## Resultado e limites

A revisão nos dois eixos, a correção dos três achados e a execução integral dos testes PostgreSQL foram concluídas. Não foram encontrados novos bloqueadores na revisão das correções. O recorte backend DEV-06 está revisado e validado pelos cenários descritos, sem declarar conclusão de WEB-05 inteiro ou validação de produção/Gold. A execução local continua em Python 3.11.9; Python 3.12 é o alvo do Docker/CI.

O PRD permanece `Em validação`. Trello não sincronizado: leitura do quadro oficial retornou recurso não encontrado ou sem acesso. O checklist fornecido na conversa foi suficiente para a revisão. A alteração local de `frontend/package-lock.json` foi preservada.
