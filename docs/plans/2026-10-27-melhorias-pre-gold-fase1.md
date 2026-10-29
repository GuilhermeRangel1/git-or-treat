# Melhorias pré-Gold — Fase 1 de implementação

**Data:** 2026-10-27. **Branch:** `refactor/arquitetura-backend-frontend`.
**Base:** `53de4e6fd295c2461afec03902423d91de684bcd` (`develop`).
**Autorização:** a pessoa usuária delimitou a execução a oito IDs. A auditoria original continua preservada em [relatório arquitetural](2026-10-27-auditoria-arquitetural-backend-frontend-fase1.md); não se confunde com esta Fase 1 reduzida.
**Responsáveis e modelos:** implementação T1/T2/T3 por subagentes GPT Luna, esforço high; coordenação e revisão pelo agente principal. Documentação T4 por agente GPT Luna, esforço high; revisão final pelo agente principal.

## Decisão e limites

A [ADR-0016](../decisions/0016-priorizacao-melhorias-pre-gold.md) aprova priorizar FE-010, FE-015, FE-017, FE-018, BE-012, BE-013, BE-009 e TR-001. São melhorias com benefício imediato e baixo retrabalho em validação de contratos, acessibilidade, isolamento e transporte. Modularizações mais amplas ficam para reavaliação quando os limites e contratos Gold reais reduzirem incertezas; os demais itens também são adiados por prioridade, não por suposta dependência técnica universal da Gold.

Preservar arquitetura feature-based, endpoints, contratos públicos, cálculos, controles de segurança e distinção entre demonstração e dados Gold. Esta fase não implementa integração Gold, não homologa métricas e não altera o estado funcional de requisitos do produto. A ADR-0002 está aprovada desde 25/10/2026 com base nos comentários de concordância de Backend e Engenharia de Dados no PR #54, sem Approve formal no GitHub. Backend é o único executor SQL da Gold local e coordena planejar → executar → sintetizar; isso não autoriza adaptador, credencial ou consulta real.

## Checklist da Fase 1

- [x] **FE-010** — decoder UC valida consistência/paginação; suíte e prova manual do decoder real contra API sintética local. Cobre parte da divergência de invariantes apontada por TR-003, mas não reconcilia todos os produtores/consumidores. TR-004, o smoke produtor → decoder, segue pendente.
- [x] **FE-015** — descrição acessível do Modal aponta para elemento renderizado; teste de regressão.
- [x] **FE-017** — período UC rejeita ano 0000, associa erros aos campos e foca o primeiro erro; testes de regressão.
- [x] **FE-018** — contexto do Assistente usa pares semânticos `dt`/`dd`; teste de regressão.
- [x] **BE-012** — suporte de testes separado de `conftest.py` e módulos `test_*`; imports consumidores conferidos.
- [x] **BE-013** — overrides prévios restaurados mesmo em erro no corpo e falhas de startup/shutdown; quatro regressões com app/TestClient reais.
- [x] **BE-009** — transporte GenAI compartilhado entre clientes, com validação explícita pelo schema de cada operação e tratamento de falhas preservado.
- [x] **TR-001** — guias, PRD e índice alinhados ao estado aprovado da ADR-0002; contrato mantém como propostas as rotas/campos ainda não implementados.

### Evidências e limites dos executores

- T1 revisada pelo principal: conformidade e qualidade aprovadas. Frontend: 280 testes em 34 arquivos; após ampliar um caso, formulário 6/6; boundaries (140 arquivos), lint, formatação, build e `git diff --check` passaram. Navegador confirmou formulários/modal e contexto do Assistente; o Assistente usou fixture interceptada, e a chamada de insight recebeu 503 porque GenAI não estava iniciado/configurado. FE-010 teve prova adicional do decoder servido pelo Vite com API real de fonte sintética: busca normal, página além do fim, ausência de resultados, histórico fora da última página e rejeições de paginação inválida. TR-004 não foi comprovado.
- T2 revisada pelo principal: 404 testes backend aprovados, 4 skips PostgreSQL, 1 warning Starlette preexistente; `compileall` passou e não foram encontrados imports de `conftest`/`test_*` entre módulos de teste. Testes PostgreSQL foram ignorados por falta de `TEST_POSTGRES_URL` descartável configurado.
- T3 revisada pelo principal: 426 testes backend aprovados, 4 skips PostgreSQL e 1 warning Starlette/httpx preexistente; `compileall` e `git diff --check` passaram. 44 testes focados passaram. Ruff não estava instalado e não foi instalado.
- Os executores rodaram backend com Python 3.11.9 local; alvo CI é Python 3.12. Resultado local não substitui execução CI/container nem valida a fronteira PostgreSQL ignorada. Nenhuma integração Gold é alegada.
- Revisão conjunta do código T1/T2/T3 pelo agente principal: aprovada sem achado impeditivo. Revisão documental T4 pelo agente principal: aprovada em 27/10/2026. Evidência canônica de ambas está neste plano; `work/refactor-pre-gold/review.md` é auxiliar local.
- Trello: sincronização pendente. A leitura do quadro retornou recurso não encontrado ou sem acesso; não houve escrita.

### Verificações reproduzíveis

| Área / diretório de trabalho | Comando ou conferência | Resultado registrado |
| --- | --- | --- |
| Frontend — `frontend/` | `npm.cmd run check:boundaries` | Passou; 140 arquivos verificados. |
| Frontend — `frontend/` | `npm.cmd run lint` | Passou. |
| Frontend — `frontend/` | `npm.cmd run format:check` | Passou, inclusive após a última alteração registrada no teste do formulário UC. |
| Frontend — `frontend/` | `npm.cmd run build` | Passou (`tsc -b` e Vite). |
| Frontend — `frontend/` | `npm.cmd run build` | Reexecução final pelo agente principal no estado final: `tsc -b` e Vite passaram. |
| Frontend — `frontend/` | `npm.cmd test -- --reporter=dot --maxWorkers=2` | Uma execução anterior teve 280 aprovados em 34 arquivos antes da última ampliação. Revalidação completa posterior: 280 passaram e 1 falhou por timeout de 5 s em `OperacaoPage.test.tsx`, no caso `valida limite de caracteres Unicode do alimentador pelo parser aprovado`. O teste isolado com um worker passou em 3629 ms. Sem alteração de código, teste ou timeout, a suíte completa com um worker passou em seguida (ver linha seguinte). A diferença ainda não tem causa conclusiva. |
| Frontend — `frontend/` | `npm.cmd test -- --reporter=dot --maxWorkers=1` | 281 aprovados em 34 arquivos, 128,45 s, exit code 0. Suíte final aprovada. A execução anterior com dois workers permanece registrada como timeout observado. |
| Backend T2 — tentativa a partir da raiz | Tentativa de suíte pela raiz do repositório; o comando literal não foi preservado no relatório do executor. | Inválida: `test_database` inicia subprocesso dependente do cwd `backend/`. Não usar essa tentativa como evidência de falha de implementação. |
| Backend T2 — `backend/` | `python -m pytest tests` | 404 aprovados, 4 ignorados por PostgreSQL não configurado, 1 aviso preexistente de depreciação Starlette/httpx. |
| Backend T2 — `backend/` | `python -m compileall -q app tests` | Passou. |
| Backend T2 — `backend/` | `rg -n "from tests\.conftest\|import tests\.conftest\|from tests\.test_migrations\|import tests\.test_migrations" tests` | Nenhuma ocorrência de imports acoplados entre testes. |
| Backend T3 — `backend/` | `.\.venv\Scripts\python.exe -m pytest tests/test_genai_client.py tests/test_ai_chat.py tests/test_ai_insights.py -q` | 44 aprovados, 1 aviso preexistente Starlette/httpx. |
| Backend T3 — `backend/` | `.\.venv\Scripts\python.exe -m pytest -q` | 426 aprovados, 4 ignorados por PostgreSQL não configurado, 1 aviso preexistente Starlette/httpx. |
| Backend T3 — `backend/` | `.\.venv\Scripts\python.exe -m compileall -q app tests` | Passou. |
| Backend T3 — `backend/` | `python -m ruff check app/services/genai_client.py tests/test_genai_client.py` | Não executado: Ruff indisponível no venv; nenhuma dependência foi instalada. |
| Backend T2/T3 — `backend/` | `python -m pytest tests/test_genai_client.py tests/test_client_override_isolation.py -q` | Revalidação direcionada pelo principal: 26 aprovados, 1 aviso preexistente. |
| Backend — `backend/` | `.\.venv\Scripts\python.exe -m compileall -q app tests scripts` | Revalidação final pelo agente principal: exit code 0. |
| Revisão pelo agente principal — branch `refactor/arquitetura-backend-frontend` | Revisão do diff T1/T2/T3 contra os oito IDs | Aprovada em 27/10/2026, sem achados impeditivos. Principal confirmou contratos públicos, endpoints, cálculos, guardas, imports de suporte e jornadas descritas; revisão documental T4 também aprovada. A revisão não substitui os gates de CI nem constitui aceite humano de negócio. |
| Documentação — raiz `D:\git-or-treat` | Varredura PowerShell de links Markdown locais (`[...] (...)`) nos nove documentos T4, resolvendo cada alvo relativo com `Test-Path` | Zero links locais quebrados. O verificador de links CI documentado em `.github/workflows/quality.yml` também percorre todos os Markdown; essa execução CI não foi realizada nesta tarefa. |
| Documentação — raiz `D:\git-or-treat` | `git -c safe.directory=D:/git-or-treat diff --check` | Passou sem saída. |
| Auditoria e checklist — verificação pelo principal | Conferência da fonte restaurada, seções, IDs e checkboxes | `EndsWith` ordinal da fonte original: verdadeiro; seções A–I: 9; achados: 49; itens L: 34; selecionados: 8; adiados: 41; ausentes/duplicados: 0. |

**Veredito das verificações:** revisão do código T1/T2/T3 aprovada sem achados impeditivos; a suíte final frontend passou com um worker, sem alterar código, testes ou timeout após o timeout observado com dois workers. A causa dessa diferença de execução não foi determinada. Os resultados sustentam os oito itens de preparação conforme os limites registrados; não demonstram integração Gold, validação PostgreSQL local, execução final CI Python 3.12 ou conclusão funcional dos requisitos WEB/IA. A tentativa de suíte backend na raiz foi inválida por cwd; o comando literal não está preservado. A sincronização Trello segue pendente por falta de acesso.

## Checklist das 41 observações adiadas

Os itens abaixo permanecem no relatório integral e são **observações para reavaliar**, não 41 defeitos confirmados nem obrigações aprovadas. O adiamento reflete prioridade; alguns podem ser independentes da Gold. Marcar cada item após validar sua relevância, premissas e evidência na ocasião da retomada. FE-010 cobre parte dos invariantes de paginação associados a TR-003; a revisão transversal dos produtores e consumidores continua pendente. TR-004 é separado e descreve o smoke produtor → decoder, que também continua pendente.

### Backend — 17 IDs adiados

- [ ] BE-001 — Contratos de domínios independentes concentrados em analytics.py
- [ ] BE-002 — UCProfile duplicado
- [ ] BE-003 — analytics.py mistura suporte comum e cálculo de continuidade
- [ ] BE-004 — Serviço UC reúne jornadas de evolução independente
- [ ] BE-005 — Avaliação de cobertura UC repetida em overview e histórico
- [ ] BE-006 — Fronteiras internas dependem de dicionários auxiliares
- [ ] BE-007 — Decomposição preço-volume está dentro da orquestração Receita
- [ ] BE-008 — Validação semântica do insight está no endpoint
- [ ] BE-010 — Tradução de erros GenAI repetida
- [ ] BE-011 — Consultas operacionais e comandos no mesmo serviço
- [ ] BE-014 — Interface analítica ampla e registros pouco tipados
- [ ] BE-015 — Adaptadores sintéticos expõem listas mutáveis compartilhadas
- [ ] BE-016 — Dependências backend pouco reproduzíveis (**validar** necessidade e custo)
- [ ] BE-017 — Scaffold Gold abre sessão sem executar operação de banco (**validar** em relação às definições do banco)
- [ ] BE-018 — Docstring atribui fixture demonstrativa ao PRD/Figma (**validar** se ainda procede)
- [ ] BE-019 — Wrappers genéricos sem consumidores encontrados (**investigar** consumidores antes de remover/alterar)
- [ ] BE-020 — Mecânica de competência repetida

### Frontend — 18 IDs adiados

- [ ] FE-001 — Recursos exclusivos do Panorama estão em shared
- [ ] FE-002 — Fixture, calculadora e utilitários juntos
- [ ] FE-003 — AIInsightCard reúne narrativa, estado e drawer
- [ ] FE-004 — Mutações de Ordens coordenadas no diálogo
- [ ] FE-005 — Chaves e invalidações de Ordens espalhadas
- [ ] FE-006 — Parser do snapshot e regras de ação no mesmo módulo
- [ ] FE-007 — Regras pequenas de Ordens duplicadas
- [ ] FE-008 — Histórico UC inclui painel, erro e diálogo
- [ ] FE-009 — Tipos do histórico não vinculam seção e registro
- [ ] FE-011 — ReceitaPage mistura coordenação e contexto visual
- [ ] FE-012 — RevenueSeries mistura geometria, DOM e tabela
- [ ] FE-013 — Formatação e marcador de dimensão ausente repetidos
- [ ] FE-014 — AssistentePage mistura estado da conversa e renderização
- [ ] FE-016 — Foco e aria-invalid dependem da redação de erro em Operação
- [ ] FE-019 — Cor de série duplicada
- [ ] FE-020 — README descreve estágio anterior (**validar** conteúdo vigente ao retomar)
- [ ] FE-021 — Testes de Receita concentram responsabilidades
- [ ] FE-022 — Falha de import lazy merece investigação (**investigar** antes de tratar como defeito)

### Transversal — 6 IDs adiados

- [ ] TR-002 — Conferência do contexto respondido desigual
- [ ] TR-003 — Invariantes de paginação divergentes (**parcialmente coberto** por FE-010; alinhar e validar produtores/consumidores restantes)
- [ ] TR-004 — Falta smoke produtor → decoder (**teste integrado continua pendente**)
- [ ] TR-005 — Limite de ID de ordem excede inteiro seguro JS
- [ ] TR-006 — UI interpreta envelope bruto de conflito em dois pontos
- [ ] TR-007 — Limites de identificação UC dependem de homologação (**condicional à homologação/fonte Gold**)

## Hipóteses e oportunidades condicionais

- Reavaliar modularizações amplas quando houver contratos e limites Gold reais; isso reduz incerteza, mas não torna cada item tecnicamente bloqueado até lá.
- Validar BE-016, BE-017, BE-018, BE-019, FE-020, FE-022 e TR-007 antes de classificá-los como defeitos ou trabalho obrigatório; seus próprios itens indicam a condição de investigação/homologação.
- FE-010 corrige decoder e página além do fim, mas não altera schemas Backend nem cobre o smoke automatizado integrado TR-004.
- P-04, DE-06 e DE-08, além de catálogo, autorização individual, prazos e auditoria, continuam dependências explícitas para consulta Gold real conforme ADR-0002.

## Documentos e conclusão de escopo

ADR-0016, índice de decisões, guias Backend/GenAI, guia de integração GenAI/Gold, PRD, auditoria restaurada e este checklist registram o escopo. A ADR-0002 está aprovada, mas a integração Gold permanece não implementada. O PRD conserva todos os estados funcionais. A evidência reproduzível e a aprovação da revisão documental pelo agente principal ficam nesta seção permanente; `work/refactor-pre-gold/task-docs-report.md` e os demais arquivos `work/` são artefatos auxiliares locais.
