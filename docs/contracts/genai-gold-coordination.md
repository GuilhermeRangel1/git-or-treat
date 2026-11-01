# GENAI-07 — coordenação pública Gold

## Caminho implementado

`POST /api/v1/ai/questions` seleciona explicitamente o modo configurado. No modo Gold, a dependência resolve a sessão individual e cria o engine do login restrito; `answer_gold_question` chama planejamento HTTP, avaliação de prontidão, executor PostgreSQL e síntese HTTP. O modo sintético continua pelo cliente público existente. Nenhuma falha Gold chama esse caminho sintético.

O coordenador reusa `plan_gold_question`, `should_synthesize`, `execute_gold_plan`, `GoldPublicationContext`, `GenAIRequestDeadline` e o cliente interno existente. O núcleo continua independente de tabelas físicas e drivers. As duas operações GenAI permanecem autenticadas e exigem composição externa Gold.

## Invariantes e prontidão

O mesmo plano/fingerprint, pessoa/escopo, publicação e correlação atravessam a consulta e a síntese. O prazo de 35 s iniciado pelo planejamento é consumido nas etapas seguintes; o executor limita SQL ao saldo e a 5 s. Cancelamento da coroutine não demonstra cancelamento imediato de trabalho em thread: essa prova segue pendente.

`GoldPlanningResult` conserva o vocabulário observado na publicação. `QuestionSynthesisRequest.dimension_value_coverage` é um campo opcional (default vazio) adicionado simetricamente nos contratos dos dois serviços. Seus IDs precisam estar no escopo, ser únicos e não conter UC. A síntese reaprova o plano com esse vocabulário, mantendo EvidenceGuard, fingerprint e autorização. Exemplos canônicos v1 foram atualizados; emissor e receptor devem ser implantados em conjunto, pois receptor antigo com `extra=forbid` recusará o campo novo.

A seleção de fonte não aprova qualidade. Antes do SQL quantitativo, o coordenador exige relatório `gold-readiness-v2`, da mesma publicação, lote ready/partial e todas as capacidades necessárias disponíveis. A composição padrão reutiliza `evaluate_domain_readiness` e seu observador técnico na conexão operacional do Backend; o SQL quantitativo usa exclusivamente o login analítico restrito. `GENAI_GOLD_APPROVED_CONTROLS` recebe uma lista JSON de IDs explicitamente aprovados pela equipe. Default `[]`: não transforma controle pendente em aprovado. Não usar esse parâmetro para afirmar uma aprovação que não ocorreu.

Erros de configuração/transporte/banco retornam envelopes sanitizados, com correlação. Mudança de publicação retorna 409; recusa na execução retorna 403. Ausência/esclarecimento de lookup válido passa pela síntese; falhas de transporte não geram evidência inventada.

## Prova reproduzível

Em PostgreSQL 16 descartável, `tests/test_genai_session_postgres.py` foi ampliado para incluir a rota pública real, sessão por cookie, dependências, engine restrito, executor e cliente HTTP interno. O transporte de teste inicia processos GenAI separados e chama as rotas HTTP ASGI pela fábrica `create_app`, perfil Gold e EvidenceGuard reais. Somente modelo e destino de auditoria são determinísticos; a aprovação de prontidão usada no sucesso é artificial e explícita. A prova de composição padrão sem essa aprovação retorna 503. Não há chamada ao provedor nem dado privado.

Comandos em `backend/`, com URLs exclusivas do banco descartável preparado por `scripts/prepare_test_postgres.sql`:

`python -m pytest -q -p no:cacheprovider --tb=short --show-capture=no tests/test_genai_session_postgres.py tests/test_ai_chat.py tests/test_genai_session_access.py tests/test_genai_internal_contract.py tests/test_genai_planning_metadata.py`

Resultado: 107 aprovados, um aviso preexistente Starlette/httpx. Após acrescentar o caso da composição padrão sem aprovações, o teste PostgreSQL isolado passou novamente (1 aprovado).

Em `ai-agent/`:

`python -m pytest -q -p no:cacheprovider --tb=short tests/test_core_plan_synthesis.py tests/test_internal_envelopes.py tests/test_internal_wire_vectors.py tests/test_internal_contract_examples.py`

Resultado: 239 aprovados. Ruff/compileall dos arquivos alterados e diff-check aprovados. A primeira execução dos vetores apontou o campo default novo ausente nos exemplos; os exemplos foram atualizados simetricamente e a seleção final passou. A execução assíncrona local Windows foi interrompida sem resultado, substituída pela execução na imagem descartável.

## Limites de aceite

Integração de software demonstrada com publicação artificial; não é aceite Gold real. Não houve prova privada com lote autorizado, revisão visual do portal, destino durável real de auditoria (GENAI-08), cancelamento por desconexão HTTP nem ensaio de desempenho. A fábrica externa já exige auditoria durável e recusa configuração incompleta; o destino artificial desta prova não autoriza liberação pública real.

GENAI-07 permanece em andamento. A operação pública está ligada, mas o sucesso depende de publicação/controles aprovados e composição externa operacional completa. Revisão independente encontrou e corrigiu perda de vocabulário, falta de gate de prontidão e etapas fora do deadline. Nenhum requisito oficial foi concluído por estas provas.
