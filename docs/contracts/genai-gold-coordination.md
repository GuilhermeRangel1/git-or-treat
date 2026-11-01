# GENAI-07 — coordenação pública Gold

## Caminho implementado

`POST /api/v1/ai/questions` seleciona explicitamente o modo configurado. No modo Gold, a dependência resolve a sessão individual e cria o engine do login restrito; `answer_gold_question` chama planejamento HTTP, avaliação de prontidão, executor PostgreSQL e síntese HTTP. O modo sintético continua pelo cliente público existente. Nenhuma falha Gold chama esse caminho sintético.

O coordenador reusa `plan_gold_question`, `should_synthesize`, `execute_gold_plan`, `GoldPublicationContext`, `GenAIRequestDeadline` e o cliente interno existente. O núcleo continua independente de tabelas físicas e drivers. As duas operações GenAI permanecem autenticadas e exigem composição externa Gold.

## Invariantes e prontidão

O mesmo plano/fingerprint, pessoa/escopo, publicação e correlação atravessam a consulta e a síntese. O prazo de 35 s iniciado pelo planejamento é consumido nas etapas seguintes; o executor limita SQL ao saldo e a 5 s. Cancelamento da coroutine não demonstra cancelamento imediato de trabalho em thread: essa prova segue pendente.

`GoldPlanningResult` conserva o vocabulário observado na publicação. `QuestionSynthesisRequest.dimension_value_coverage` é um campo opcional (default vazio) adicionado simetricamente nos contratos dos dois serviços. Seus IDs precisam estar no escopo, ser únicos e não conter UC. A síntese reaprova o plano com esse vocabulário, mantendo EvidenceGuard, fingerprint e autorização. Exemplos canônicos v1 foram atualizados; emissor e receptor devem ser implantados em conjunto, pois receptor antigo com `extra=forbid` recusará o campo novo.

A seleção de fonte não aprova qualidade. Antes do SQL quantitativo, o coordenador exige relatório `gold-readiness-v2`, da mesma publicação, lote ready/partial e todas as capacidades necessárias disponíveis. A composição padrão reutiliza `evaluate_domain_readiness` e seu observador técnico na conexão operacional do Backend; o SQL quantitativo usa exclusivamente o login analítico restrito. `GENAI_GOLD_APPROVED_CONTROLS` recebe uma lista JSON de IDs explicitamente aprovados pela equipe. Default `[]`: não transforma controle pendente em aprovado. Não usar esse parâmetro para afirmar uma aprovação que não ocorreu.

A proveniência da evidência inclui `quality`: versão da prontidão, lote, estado e capacidades exigidas pelo plano que o gate confirmou. O Backend valida o lote antes de executar e o `EvidenceGuard` rejeita qualidade ausente, de outro lote ou anexada a uma fonte sintética. Esse snapshot registra a decisão do gate; não declara que os controles ou dados foram aprovados por uma revisão humana.

Erros de configuração/transporte/banco retornam envelopes sanitizados, com correlação. Mudança de publicação retorna 409; recusa na execução retorna 403. Ausência/esclarecimento de lookup válido passa pela síntese; falhas de transporte não geram evidência inventada.

## Prova reproduzível

Em PostgreSQL 16 descartável, `tests/test_genai_session_postgres.py` exercita `app.main:app` do Backend com suas rotas, middleware de correlação, login por sessão e composição de dependências. O cliente chama a rota pública; o transporte de teste inicia processos GenAI separados e chama as rotas internas pela fábrica `create_app`, perfil Gold e `EvidenceGuard` reais. O executor e o leitor PostgreSQL não são substituídos por mocks. A base e as linhas são artificiais; o teste reconcilia a receita **R$ 12,00**, competência `2001-01`, unidade e filtro `Lumenia` na evidência que chega à síntese. Verifica o perfil lógico, versões do catálogo/dicionário/schema, lote e correlação compartilhados e que não há callback à rota pública.

O modelo, o destino de auditoria e o gate de prontidão aprovado para o caso de sucesso são controlados e artificiais; não há chamada a provedor nem dado privado. Relatórios com lote divergente ou capacidade ausente retornam 503 antes do SQL quantitativo e da síntese. O gate padrão, sem aprovação configurada, também falha fechado. A ausência de competência retorna esclarecimento; falha de transporte não ativa a demonstração. A aprovação controlada torna o caminho testável, não constitui aprovação de controles reais.

Comandos em `backend/`, com URLs exclusivas do banco descartável preparado por `scripts/prepare_test_postgres.sql`:

`python -m pytest -q -p no:cacheprovider --tb=short --show-capture=no tests/test_genai_session_postgres.py tests/test_ai_chat.py tests/test_genai_session_access.py tests/test_genai_internal_contract.py tests/test_genai_planning_metadata.py`

Resultado: 107 aprovados, um aviso preexistente Starlette/httpx. O teste PostgreSQL isolado, executado depois pela aplicação ASGI de produção, também passou (1 aprovado, mesmo aviso).

Em `ai-agent/`:

`python -m pytest -q -p no:cacheprovider --tb=short tests/test_core_plan_synthesis.py tests/test_evidence_guard.py tests/test_internal_envelopes.py tests/test_internal_wire_vectors.py tests/test_internal_contract_examples.py`

Resultado: 263 aprovados, incluindo o `EvidenceGuard`, evidência de lote/qualidade e os vetores de contrato.

`python -m pytest -q -p no:cacheprovider --tb=short tests/test_external_source_composition.py tests/test_import_boundaries.py` — 17 aprovados.

`python -m pytest -q -p no:cacheprovider --tb=short tests/test_execution_limits.py` — 10 aprovados.

`python -m pytest -q -p no:cacheprovider --tb=short tests/test_model_router_flow.py` — 28 aprovados.

No Backend, `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_deadline.py` — 15 aprovados, um aviso preexistente Starlette/httpx. Ruff, compilação dos arquivos Python alterados e `git diff --check` passaram. A primeira execução dos vetores apontou exemplos sem o novo campo de qualidade; os exemplos foram atualizados simetricamente e a seleção final passou. A execução assíncrona local Windows foi interrompida sem resultado, substituída pela execução na imagem descartável.

## Limites de aceite

Integração de software demonstrada com publicação e dados artificiais; não é aceite Gold real. Não houve prova privada com lote autorizado, revisão visual do portal, destino durável real de auditoria (GENAI-08), cancelamento por desconexão HTTP nem ensaio de desempenho. A fábrica externa já exige auditoria durável e recusa configuração incompleta; o destino artificial desta prova não autoriza liberação pública real.

GENAI-07 permanece em andamento. A operação pública está ligada, mas o sucesso depende de publicação/controles aprovados e composição externa operacional completa. Revisão independente encontrou e corrigiu perda de vocabulário, falta de gate de prontidão e etapas fora do deadline. Nenhum requisito oficial foi concluído por estas provas.

## Consolidação após a integração dos PRs

A pendência de destino durável e propagação de escopo/correlação foi comprovada pelos GENAI-08/09 e reconferida na branch de consolidação. O fluxo público com PostgreSQL, processos GenAI e ingresso durável está em `tests/test_genai_session_postgres.py`; falha de confirmação impede resposta quantitativa. A amostra Gold e a referência vista no portal constam em [primeira pergunta](genai-first-question.md). [Matriz da consolidação](genai-consolidation.md): GENAI-07 com todos os itens técnicos comprovados para a primeira fatia; as limitações históricas acima não representam mais falta de auditoria integrada. Requisitos oficiais IA e expansão de domínios mantêm os estados do PRD.
