# WEB-10 — evidência integrada da etapa 5

**Data:** 01/11/2026
**Estado do requisito:** Em validação
**Escopo comprovado:** banco PostgreSQL descartável, API FastAPI real e portal Vite no navegador, com contas artificiais e chamadas HTTP sem interceptação.

## Atualização vigente — 02/11/2026 — Gold v2 e provedor real

WEB-10 permanece **Em validação**. Esta rodada acrescenta evidência à validação de 01/11; as afirmações antigas de ausência de lote/provedor descrevem aquele ambiente, não o atual. Base revisada: `feat/web10-perfis` em `92f80b4`, com a correção de autorização descrita abaixo; alterações encaminhadas ao [PR #101](https://github.com/GuilhermeRangel1/git-or-treat/pull/101), sem merge.

### Ambiente privado

- Snapshot privado da publicação Gold v2 autorizada, restaurado em `v_energy_web10_validation_20261102`, no PostgreSQL 16 local existente. A identidade da publicação foi preservada; o banco original e seus serviços não foram migrados nem substituídos. As migrações da branch foram aplicadas somente na cópia, até `20261102_cadastro`.
- Composição `web10-validation`: Backend em `127.0.0.1:8012`, portal em `http://localhost:5181` e GenAI externa Gold na rede privada. O override local não inicia outro DB/loader. Configurações e chave estão apenas em arquivos ignorados, com tokens de serviço/auditoria distintos e correspondentes entre os serviços. O leitor é `venergy_genai_reader`; a GenAI não recebe DSN de banco.
- `GENAI_AUDIT_DATABASE_URL` é configuração do CLI administrativo de retenção, não do ingresso de eventos da API. Não foi criada credencial administrativa adicional para a prova: a escrita/leitura de confirmação da trilha pela aplicação passou no runtime.
- O Gemini aceitou a chave. O modelo principal configurado apresentou 503 `UNAVAILABLE` e, no diagnóstico neutro posterior, 429 `RESOURCE_EXHAUSTED`. A lista de modelos da conta incluía `gemini-3.5-flash-lite`, que passou no teste neutro. O modelo foi alterado apenas no `.env` local dessa composição; a rodada final de Receita usou o Flash-Lite real, sem mock.

### Jornadas e autorização

Chromium real fez login dos cinco perfis pela interface, sem interceptar sessão ou API. Rotas iniciais: Admin/Comercial → Panorama; Operação → Operação; Atendimento → UC 360; Perdas → Inspeções. Menus observados corresponderam à matriz; todos abriram o Assistente. Navegação cruzada Comercial → UC 360 e Operação → Receita mostrou acesso negado.

Matriz HTTP final: 35 combinações, com login real e expectativas explícitas para cada status:

| Perfil | Panorama | Receita | Opções Operação | UCs | Fila | Ordens | Filtros compartilhados |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Admin | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| Comercial | 200 | 200 | 403 | 403 | 403 | 403 | 200 |
| Operação | 403 | 403 | 200 | 403 | 403 | 403 | 403 |
| Atendimento | 403 | 403 | 403 | 200 | 403 | 403 | 200 |
| Perdas | 403 | 403 | 403 | 403 | 200 | 200 | 200 |

Os endpoints foram `/panorama`, `/revenue`, `/operations/options`, `/ucs?limit=1`, `/inspections/queue`, `/inspections/orders` e `/analytics/options`. Logout retornou 204 para os cinco perfis e a chamada protegida seguinte retornou 401. Atendimento/Perdas receberam `needs_clarification` com lista de limitações antes da consulta ao modelo. Perguntas cruzadas Comercial → DEC e Operação → Receita não retornaram números; a prova de negação antes de SQL continua coberta também pela regressão versionada anterior.

A rodada encontrou e corrigiu um defeito: Receita ainda exigia `orders:read` através de um guard legado, bloqueando Comercial na Gold. Receita agora usa sua permissão `revenue:read`. As opções compartilhadas usam identidade de plataforma e uma das permissões dos consumidores reais (`revenue:read`, `ucs:read`, `inspections:read`) em ambas as fontes, antes de abrir o repositório. Operação conserva seu catálogo específico. A matriz acima foi repetida após a correção; nenhum grant de banco foi ampliado.

### Respostas Admin, controle independente e auditoria

- Receita: pergunta enviada pelo campo do portal, “Qual foi a receita faturada em Recife em junho de 2026?”. HTTP 200 `answered`, indicador `billing.revenue`, unidade `R$`, período `2026-06-01 a 2026-06-30` e filtro municipal correto. O valor da resposta coincide exatamente, a centavos, com o SQL independente abaixo. A referência `batch_reference` é igual à publicação capturada na conexão de conferência. Correlação `736c1a4a325648ba9e472b13d7898803`; referência de auditoria persistida `5ffeafad533d4175858c57a222d6ef2a`, com estágio de modelo concluído. Não se copiam linhas de origem nem cadastro pessoal para este relatório.
- DEC e FEC: perguntas mensais do alimentador `ALM-JAB-015` em junho/2026 enviadas pelo portal. Ambas retornaram HTTP 503, `service_unavailable`, `retryable=false`, com explicação de cobertura insuficiente. Correlações `3e74529434b949ddb3f9ba0efe82f3c6` (DEC) e `8d7bfd3224a345f094b57813cf999545` (FEC); trilhas persistidas foram conferidas por essas correlações, sem estágio de modelo. O envelope de erro não expõe `audit_reference`; não se inventa essa referência.
- O SQL independente encontra linhas de DEC/FEC e confere as razões contra numerador/denominador, mas isso não certifica o mês nem transforma o bloqueio em resposta reconciliada. Todos os recortes de ocorrências dessa publicação continuam `NAO_CERTIFICADA`. Permanece pendente a resposta de Continuidade com cobertura autorizada; não se alterou o selo para passar no teste.
- Reinvestigação da pendência em 02/11: conferidos diretamente o `manifest.json` e o CSV `cobertura_dominios` do diretório configurado em `GOLD_CSV_V2_HOST_DIR`. O manifesto continua no lote `GOLD_20261031T020143Z_fd69c375`; o CSV tem 5.904 linhas de ocorrências `NAO_CERTIFICADA`, contra 48 linhas fechadas de consumo e 48 de faturamento. O [notebook produtor da declaração](../../data-engineering/notebook/Cobertura_Declaracao.ipynb) contém somente os pares consumo/leituras e faturamento/faturas em `DOMINIOS`; não produz declaração de ocorrências. O [contrato de cobertura](../contracts/gold-cobertura-v1.md) exige evidência vinculada à origem e não propaga automaticamente uma declaração global para alimentadores. Não foi localizada declaração aplicável a junho/2026 e ao alimentador consultado. Para retomar: reconciliar a extração de ocorrências com sua origem, publicar declaração válida para o período/recorte, exportar/carregar o pacote correspondente e repetir as perguntas Admin com SQL independente na nova publicação. Acrescentar o domínio à lista ou editar o CSV/banco como `FECHADO` sem essa evidência não encerra o aceite.
- Leitor real: `has_schema_privilege` e `has_any_column_privilege` confirmaram ausência de acesso a `gold_cadastro.cadastro_titular_uc`; também não lê `public.auth_users` nem tem TEMP. O catálogo/contexto quantitativo GenAI não inclui a projeção pessoal. A referência numérica recebida continha somente indicador, período, município, valor agregado e proveniência.
- A [evidência do run limpo](../../data-engineering/evidencias/workflow/run-limpo-250327107715287.md) registra 64 verificações sem falhas no mesmo lote, incluindo ocorrências e DEC/FEC. `Silver_to_gold.ipynb` implementa fórmulas e controles de duração, frequência, denominador e reconciliação. Portanto, a pendência não significa ausência das medidas nem erro de cálculo: é a falta da declaração de cobertura no pacote consultado pela aplicação, que não pode ser inferida apenas dessas verificações.

Consultas de controle em transação `READ ONLY`, na mesma cópia/publicação, com parâmetros vinculados:

```sql
SELECT sum(receita_total_reais)
FROM gold_v2.diagnostico_receita
WHERE competencia = :competencia AND municipio = :municipio;

SELECT "DEC", "FEC", total_ucs_alimentador,
       duracao_total_interrupcoes_horas, frequencia_total_interrupcoes
FROM gold_v2.indicadores_dec_fec
WHERE competencia = :competencia AND id_alimentador = :alimentador;

SELECT dominio, estado_cobertura, count(*)
FROM gold_v2.cobertura_dominios
GROUP BY dominio, estado_cobertura;
```

### Comandos, verificações e limites

- `docker compose --env-file .env.gold-v2 -p web10-validation -f docker-compose.yml -f docker-compose.gold-v2.yml -f work/web10-validation/compose.override.yml build backend ai-agent frontend`: passou. `up -d --no-deps ai-agent backend frontend`: passou. Override e DSNs privados ficam em `work/`, ignorados.
- `alembic upgrade head`, executado no serviço Backend com a credencial de carga apontada somente à cópia: passou. Não foi repetida a ingestão do lote.
- `docker exec web10-validation-backend-1 python scripts/check_genai_runtime.py`: configuração, banco, leitor, publicação, catálogo, auditoria e GenAI `ready`; geração `configured`.
- Em `backend/`, fonte sintética/session e CORS das fixtures: `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_profile_access.py tests/test_platform_profiles.py tests/test_platform_authorization.py tests/test_profile_provisioning.py tests/test_genai_session_access.py tests/test_analytics_kpis_revenue.py tests/test_gold_http.py tests/test_analytics_query_parameters.py tests/test_security_regressions.py` → **141 passaram, 1 aviso preexistente Starlette/httpx, 14,40 s**. A primeira tentativa com CORS exclusivo da porta 5181 falhou em logins das fixtures (403); repetir com as origens 5173 esperadas resolveu essa contaminação de configuração, sem mudar o código de login.
- Roteiros privados executados: `python work/web10-validation/finalize_validation.py` (matriz HTTP, SQL e privilégios), `node work/web10-validation/validate_browser.mjs` (login, menu, chat real e navegação negada) e `python work/web10-validation/check_reconciliation.py` (igualdade do número/contexto/publicação, referência persistida e bloqueio de Continuidade sem modelo). Capturas em `work/web10-validation/admin-revenue.png`, `admin-dec.png` e `admin-fec.png`; artefatos privados ignorados pelo Git. Os testes de autorização versionados reproduzem a regressão com dados artificiais; os roteiros privados exigem a publicação e configuração locais autorizadas.
- Esta rodada não repete o ciclo de ordens nem todos os cenários de inatividade/expiração/downgrade no navegador; essas provas anteriores e os testes automatizados ficam distinguidos nas seções históricas. Não é aceite integral de IA ou Dados.
- Decisão vigente: **manter WEB-10 Em validação**, com Receita real comprovada e Continuidade ainda pendente por cobertura da fonte. Sem merge enquanto esse limite permanecer.
- Encerramento: as cinco contas temporárias e suas sessões foram removidas da cópia; o arquivo de credenciais temporárias foi apagado. Os três serviços `web10-validation` foram parados. O snapshot privado e as capturas permanecem locais para conferência; chave/configuração ignoradas preservadas e composição original `dev131-gold` mantida ativa.

## Ambiente e isolamento — rodada histórica de 01/11

- Container PostgreSQL 16 já autorizado: `web10-profiles-task1-test`, bind local `127.0.0.1:55444`.
- Banco da jornada no browser: `grid360_web10_task5_test`, criado vazio com owner `web10_migrator` não-superuser. Recebeu a migração atual e cinco contas artificiais; contém apenas dados sintéticos da demonstração e ordens criadas no fluxo desta validação.
- Banco da prova automatizada: `grid360_web10_task5_provision_test`, também criado vazio com o mesmo owner. A fixture migrou e reverteu as tabelas ao final; permaneceu vazio.
- API local: `127.0.0.1:8000`, `ORDERS_AUTH_MODE=session`, `ANALYTICS_SOURCE=synthetic`; health respondeu `online` e `database=connected`.
- Portal local: `127.0.0.1:5173`. O navegador carregou o portal e fez chamadas reais à API pelo proxy local. Nenhuma resposta foi interceptada nem substituída por mock.
- Credenciais artificiais ficam somente em `work/web10-execution/task5-credentials.txt` (ignorado pelo Git). Nenhuma senha ou cookie consta neste relatório.
- O portal permanece ativo (Vite PID `21616`; API PID `1816`) e o container de PostgreSQL permanece ativo para inspeção local. Nenhum banco local preexistente foi migrado ou alterado.

## Prova PostgreSQL de provisionamento

Arquivo: `backend/tests/test_platform_profiles_postgres.py`.

Antes de migrar, o teste exige driver `postgresql+psycopg`, nome com sufixo `_test`, `current_database()` igual ao alvo da URL, papel atual sem `SUPERUSER` e schemas públicos sem tabelas/views. Em seguida, usa o helper de migração do repositório, cria uma conta sentinela não selecionada, executa `bootstrap_local_auth.py` e confirma os cinco perfis e a preservação do hash, JSON legado, estado ativo e perfil nulo da sentinela. O texto capturado do bootstrap não contém senha; os cinco segredos são gravados somente em arquivo temporário privado.

Comando executado em `backend/`:

```powershell
$env:ANALYTICS_SOURCE = 'synthetic'
$env:ORDERS_AUTH_MODE = 'session'
$env:TEST_PLATFORM_PROFILES_POSTGRES_URL = '<DSN privado do banco *_test>'
.\.venv\Scripts\python.exe -m pytest tests/test_platform_profiles_postgres.py -q -p no:cacheprovider --tb=short --basetemp=.pytest-tmp-web10-task5-pg-guard
```

Resultado observado: **1 passed**, 1 aviso conhecido de depreciação Starlette/httpx, 3,67 s. O primeiro nome de banco usado para a jornada já continha a migração e foi recusado pelo guard; a prova foi repetida no banco novo e vazio `grid360_web10_task5_provision_test`.

## Jornadas por perfil no navegador e HTTP

As rotas e os recursos foram percorridos no navegador real conectado à API local. As verificações HTTP adicionais usaram `fetch` na página, preservando o cookie de sessão e sem interceptar chamadas.

| Perfil | Entrada, tela e menu verificados | HTTP permitido | HTTP negado |
| --- | --- | --- | --- |
| Comercial | Login → Panorama → Receita; menu mostrou Panorama, Receita e Assistente. URL direta `/uc-360/TEST-01` exibiu acesso negado e apontou a área inicial comercial. | `/panorama` 200; `/revenue` 200 | `/ucs`, `/inspections/queue`, `/operations/options` 403 |
| Atendimento | Login → UC 360; busca por `UC-1001`; detalhe exibiu cadastro sintético, comparação, faturamento, medição, apoio ao atendimento e históricos. Reload preservou o detalhe e o menu UC 360/Assistente. | `/ucs?limit=1` 200 | `/panorama`, `/revenue`, `/inspections/queue`, `/operations/options` 403 |
| Perdas | Login → fila sintética → detalhe de suspeita; menu mostrou Inspeções, Ordens e Assistente. URL direta `/operacao` exibiu acesso negado; reload manteve a negação e a sessão. | `/inspections/queue` e `/inspections/orders/search` 200 | `/panorama`, `/ucs?limit=1`, `/operations/options` 403 |
| Operação | Login → indicadores internos → detalhe do alimentador `AL-01`; detalhe apresentou série DEC/FEC e ocorrências sintéticas. Reload preservou o detalhe e o menu Operação/Assistente. | `/operations/summary?periodo=2025-01`, `/operations/continuity?periodo=2025-01` e `/operations/feeders/AL-01?...` 200 | `/panorama`, `/revenue`, `/ucs?limit=1`, `/inspections/queue` 403 |
| Admin | Login → menu com a união das sete áreas; UI carregou Panorama, Receita, UC `UC-1001`, fila, Ordens e detalhe de alimentador com ocorrências. | Panorama, Receita, UC, fila, busca de ordens, resumo de Operação e detalhe do alimentador 200 | Nenhuma negação entre os sete recursos testados |

As contas foram alternadas usando logout da UI; login também foi feito para cada perfil. Reload foi conferido em Atendimento, Perdas e Operação. Cada página e resposta analítica exibiu os avisos de origem sintética pertinentes; esses dados não constituem diagnóstico ou reconciliação Gold.

## Ciclo de ordens — Perdas

Na conta `losses`, o browser criou duas ordens para UCs artificiais diferentes a partir da fila. A primeira percorreu `Pendente → Em andamento → Concluída` e aceitou um resultado escrito no formulário; a UI exibiu o estado final, resultado e histórico de atualização. A segunda foi cancelada pelo diálogo, com motivo sintético; a UI confirmou `Cancelada`. O backend confirmou as gravações. Nenhuma consulta à Gold foi executada pela fila ou ordens.

## Assistente e limites de fonte

Os cinco perfis têm `ai:ask` na sessão e o endpoint de perguntas foi chamado em contexto real para Comercial, Atendimento, Perdas, Operação e Admin. Todas as chamadas responderam HTTP **503 `service_unavailable`** com mensagem pública de indisponibilidade do serviço de resposta. Não foi conectado um provedor GenAI para esta execução, e nenhuma resposta numérica foi fabricada.

O Admin também consultou as rotas analíticas de receita e continuidade, que responderam 200 e exibiram fonte `synthetic`. Isso não equivale a uma resposta do Assistente nem à reconciliação de duas respostas com um lote Gold autorizado. Atendimento e Perdas não puderam exibir a limitação `needs_clarification` no navegador porque a resposta do serviço de IA indisponível ocorreu antes; a ausência de grants desses perfis e o retorno de `needs_clarification` antes de leitor/modelo permanecem cobertos pelo teste PostgreSQL da etapa 4 (`test_genai_session_postgres.py`, 15 testes aprovados no relatório anterior), não por uma resposta ao vivo nesta sessão.

## Sessão, remoção e downgrade

- **Usuário inativo:** após login de Operação, `is_active` foi temporariamente alterado para `false` somente no DB UI artificial. `GET /api/v1/panorama` respondeu 401; reload enviou a UI à tela de login. `is_active` foi restaurado.
- **Perfil removido:** após login de Atendimento, `profile` foi temporariamente limpo. `GET /api/v1/ucs?limit=1` respondeu 403; `GET /api/v1/auth/session` preservou a sessão com `profile: null` e permissões vazias; reload em `/uc-360` exibiu “Acesso ainda não provisionado”. O perfil customer_service foi restaurado.
- **Downgrade Admin → Operação:** mantendo o mesmo cookie, alteração do perfil no DB foi observada por `/api/v1/auth/session` como `operations`, e `/api/v1/revenue` respondeu 403. Reload reduziu o menu a Operação/Assistente e negou a rota `/uc-360`. Perfil admin foi restaurado e menu completo reapareceu no reload.
- **Expiração:** o `expires_at` da sessão sintética Comercial foi temporariamente movido para o passado. Uma rota protegida respondeu 401 e reload foi para `/login`. O horário original foi restaurado antes da limpeza da sessão.
- **Logout/revogação:** logout pela UI retornou à tela de login; uma rota protegida respondeu 401. Outra sessão criada no contexto do browser foi revogada por `POST /api/v1/auth/logout` (204) e a rota protegida seguinte respondeu 401.
- **Troca de conta com requisição em voo:** não controlada como requisição ao vivo nesta etapa. A comprovação executável do frontend está em `frontend/src/features/assistente/AssistenteSession.test.tsx` (`aborta pergunta e descarta conversa quando o mesmo usuario perde o perfil admin`) e `descarta conversa e contexto anteriores ao confirmar outra identidade`; `frontend/src/shared/auth/AuthProvider.test.tsx` também cobre limpeza de cache na troca de identidade/perfil. A etapa 3 reportou a suíte completa do frontend com 373 testes aprovados.
- Após cada cenário, o estado de negócio foi restaurado. O estado final observado no DB UI: os cinco perfis originais restaurados, todas as contas ativas e nenhuma sessão de teste restante (`profiles_ok=True active_ok=True has_sessions=False`).

## Clarificação Gold ao vivo para Atendimento/Perdas

Subi temporariamente uma segunda API em `127.0.0.1:8002` com `ANALYTICS_SOURCE=gold`, conectada apenas ao banco operacional descartável da UI. Não configurei `GENAI_GOLD_DATABASE_URL`, não havia lote Gold e não inicializei leitor nem modelo. A página do portal autenticou Atendimento e Perdas nessa API e chamou `POST /api/v1/ai/questions` sem interceptação:

| Perfil | Login | Resposta HTTP | Estado | Limitação |
| --- | ---: | ---: | --- | --- |
| Atendimento | 200 | 200 | `needs_clarification` | “Ainda não há consultas disponíveis para esta área.” |
| Perdas | 200 | 200 | `needs_clarification` | “Ainda não há consultas disponíveis para esta área.” |

Essas respostas demonstram negação por capacidade ausente antes de qualquer conexão ao leitor Gold/modelo. A API temporária em 8002 foi encerrada ao final; API 8000 permaneceu `ANALYTICS_SOURCE=synthetic`, e health respondeu `database=connected`.
- Não foi capturada uma imagem sanitizada persistida: a ferramenta de screenshot recusou gravar em `docs/plans/` por limite de diretório do serviço de browser; a tentativa sem caminho não concluiu e foi encerrada. A observação visual/semântica foi registrada pelos snapshots de acessibilidade e estados visíveis descritos acima.

## Verificações e situação dos critérios

- `alembic upgrade head` no banco novo da UI: passou; revisões atuais aplicadas.
- `bootstrap_local_auth.py` no banco novo: criou as cinco contas artificiais; nenhuma conta de banco preexistente foi alvo.
- `python -m pytest tests/test_platform_profiles_postgres.py ...`: 1 passou no PostgreSQL descartável com os guards de isolamento.
- `GET /api/v1/health`: `database=connected`.
- Browser real + API real: logins dos cinco perfis, menus e grupos de recursos permitidos/negados exercitados; ciclo de ordens concluído no banco operacional descartável.
- Histórico do gate: uma tentativa inicial foi interrompida na etapa integrada; depois, a primeira suíte completa executada da raiz teve falhas de fixtures antigas que não autenticavam as chamadas. As fixtures foram corrigidas para criar sessão/perfil e usar cookie/Origin reais. O resultado final aprovado está registrado abaixo; a tentativa inicial é histórica e não é o resultado vigente.
- Atendimento/Perdas produziram ao vivo o envelope de clarificação acima no modo Gold sem leitor. Perguntas dos cinco perfis em modo sintético continuaram 503 porque o serviço de resposta real não estava configurado; não foi usado modelo mock nesta integração.
- Gate completo Backend em `backend/`, com `ANALYTICS_SOURCE=synthetic`, `ORDERS_AUTH_MODE=session`, sem URLs PostgreSQL opcionais: `python -m pytest tests -q --basetemp=..\.pytest-tmp-web10-full-final`: **901 passed, 102 skipped, 1 warning em 561,66 s**. Os skips incluem integrações PostgreSQL opt-in. As provas PostgreSQL específicas de WEB-10 para migração, provisionamento e acesso foram executadas separadamente e estão nos relatórios das tarefas 1, 2, 4 e 5; não se atribui cobertura desses 102 skips a essas provas dirigidas. `python -m compileall -q app tests scripts` e `git diff --check` passaram. Ruff não estava instalado.
- Reconciliação de duas respostas Admin de domínios distintos com lote Gold autorizado: **não realizada**; não havia lote Gold autorizado nem serviço de resposta real.

**Decisão de aceite:** manter WEB-10 `Em validação`. O gate completo do Backend passou com 102 testes pulados, incluindo integrações PostgreSQL opt-in; esses skips não são considerados cobertos pela validação dirigida. As provas PostgreSQL específicas de WEB-10 para migração, provisão e acesso foram executadas separadamente, conforme os relatórios das tarefas. Permanecem pendentes respostas conversacionais Admin e reconciliação de duas respostas com lote Gold autorizado; nenhum lote/provedor estava disponível. A troca de conta com chamada em voo foi coberta por testes automatizados, não ao vivo. Não foi possível salvar uma captura sanitizada pelo serviço de browser; snapshots de página e estados visíveis foram observados diretamente. A UI das ordens, menus, autorização HTTP, inativação, revogação, expiração, remoção de perfil, downgrade e clarificação vazia de Atendimento/Perdas foram comprovados no banco e API descartáveis.
