# P0 — diagnóstico inicial do planejamento GenAI

Data: 05/11/2026. Preparação para IA-01/02/03; nenhum aceite Gold concluído.
Referência executada nesta branch limpa: `origin/main` / `2c2c024`, com a fixture e as mudanças locais do avaliador. Perfil Gold v2, fonte gold.local; sem provedor, SQL ou publicação real.

## Amostra e resultado

40 casos: 32 controles conhecidos de `gold_language_eval.json` e oito casos autorais de demanda, em `ai-agent/tests/fixtures/gold_p0_diagnostic.json`. Resultado: 36 corresponderam às expectativas verificadas e quatro divergiram. Os controles passaram em 32/32; os casos novos, em 4/8. Isso não é taxa geral de acerto nem avaliação cega. Parte dos oráculos verifica apenas o status, portanto um esclarecimento de motivo errado pode passar; essa limitação exige revisão antes de promover o benchmark como gate.

Relatório estruturado: `ai-agent/reports/genai-p0-planning-baseline.json`. O conjunto reservado existente não foi executado. Os casos novos agora são dados de desenvolvimento. A cobertura artificial é janeiro a março de 2025; os dois casos de últimos 12 meses avaliam esclarecimento, sem provar distribuição anual ou desambiguação temporal.

## Primeiras divergências observadas

| Casos | Resultado e primeira divergência | Próxima investigação |
| --- | --- | --- |
| P0-35/36 | Interpretação/política funcional: pede escolher variação ou total mesmo quando o pedido solicita maior faturamento/top cinco no intervalo. Há também uma lacuna posterior de capacidade: o validador restringe ranking a um mês. | Interpretar intenção de total e expor indisponibilidade da operação corretamente; representar consolidação antes de ordenar. |
| P0-37 | Interpretação/planejamento: aceita a pergunta de maior mês como série comum, sem ordenação e com limite 100. Sucesso estrutural com perda da intenção. | Representar ranking por competência e exigir equivalência semântica além de plano válido. |
| P0-38 | Interpretação: pedido de distribuição entre classes recebe mensagem de geografia desconhecida. Há lacuna posterior de consolidação/participação. | Rastrear o segmento identificado como local, sem corrigir só pela frase do exemplo. |

São três famílias demonstradas nesta amostra, não as três causas mais frequentes entre usuários reais. Dois casos de ranking por intervalo, um de ranking temporal e um de distribuição não sustentam uma priorização por frequência real. Não classificar essas quatro lacunas como falhas de segurança.

## Reprodução

No diretório `ai-agent`, com dependências instaladas, executar:

```powershell
$env:GENAI_MODEL_PROVIDER='unavailable'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -c "import json; from tests.test_genai_regression import build_gold_language_report; print(json.dumps(build_gold_language_report('gold_p0_diagnostic_v1.0.json', include_checks=True), ensure_ascii=False, indent=2))"
```

Execução observada: 40 casos, 36 conformes e quatro divergentes; sem erros do avaliador. Uma inspeção auxiliar das respostas falhou ao ler `response=null`; foi corrigida e os casos restantes inspecionados. Não afeta o relatório da execução completa. No Windows desta sessão, o ASGI exigiu execução fora do sandbox por bloqueio de sockets locais.

## P0 ainda aberto

Faltam perguntas reais sanitizadas, acompanhamento com contexto, casos de autorização específicos deste conjunto, oráculos de intenção/motivo mais fortes, referência numérica independente, classificação por frequência real e avaliação reservada. SQL, dados, síntese, portal, custo e latência ponta a ponta não foram medidos. A etapa seguinte é corrigir a força dos oráculos e completar essas categorias antes de escolher uma expansão ampla do contrato. Os campos semânticos esperados usados nos casos novos não são uma decisão de formato do contrato HTTP.


## Rodada 1.1 — motivos de esclarecimento e conversas

A fixture corrente `gold_p0_diagnostic.json` contém 46 casos. A versão inicial foi preservada em `gold_p0_diagnostic_v1.0.json` para reproduzir a primeira rodada. O runner admite contexto de até três turnos no mesmo caminho `_plan`, e os 20 esclarecimentos esperados agora verificam termos relacionados ao motivo na mensagem principal, excluindo o exemplo sugerido. Essa checagem lexical é mais forte que status isolado, mas não substitui anotação semântica humana e pode precisar aceitar formulações equivalentes.

Resultado: 40/46 conformes, seis divergências, zero erros do avaliador. Os seis casos novos de conversa passaram (3 troca de competência, 2 troca curta de métrica e 1 pergunta completa nova), conferindo métrica, filtros e limites temporais. Prova do núcleo HTTP interno com contexto artificial, sem provar token de continuidade, sessão Backend ou isolamento entre usuários.

Dois falsos sucessos da avaliação inicial foram revelados, sem mudança do produto:

- `GUARD-14`: data inválida `13/2025` recebe mensagem de geografia desconhecida. Primeira falha: interpretação do calendário/entidade.
- `P0-34`: pergunta longa de distribuição anual recebe mensagem de valor desconhecido de classe. Primeira falha: interpretação do agrupamento/entidade, anterior à resolução de cobertura ou expansão da capacidade. A resposta não permite concluir como o sistema trataria o conflito temporal depois de reconhecer a intenção.

Os quatro casos anteriores continuam divergentes. Portanto 36/40 e 40/46 não medem melhora do chatbot: o conjunto e a força dos oráculos mudaram. Sob o oráculo novo, 34 dos 40 casos iniciais correspondem ao esperado, e os seis adicionais passaram.

Relatório: `ai-agent/reports/genai-p0-planning-baseline-v1.1.json`. Reprodução: usar o comando anterior com `gold_p0_diagnostic.json`. Configuração e referência de produção permanecem as mesmas da rodada inicial.

Verificações: `python -m pytest tests/test_gold_language_evaluation.py -q -p no:cacheprovider --tb=short`, no diretório `ai-agent` com as mesmas variáveis, passou em 3 testes (4,74 s); a execução direta dos 46 casos terminou sem erro. `git diff --check` passou. A inspeção das quatro respostas sintéticas confirmou a classificação das falhas, sem SQL ou provedor.

Próxima prioridade do P0: anotar métricas de falha por etapa e ampliar a prova de cobertura para 12 meses artificiais, separando explicitamente perda de intenção e operação ainda não representável. Ainda não há evidência de frequência real nem benchmark numérico ponta a ponta. P0 continua aberto.


## Reprodução após reiniciar da main limpa

A rodada 1.1 foi reexecutada em 05/11/2026 em `feat/genai-p0-impacto`, partindo de `origin/main` / `2c2c024`, sem cherry-pick dos commits da comparação municipal. O resultado permaneceu 40/46, com os mesmos seis casos divergentes. Relatório reproduzível nesta branch: `ai-agent/reports/genai-p0-planning-baseline-v1.1.json`. A regressão `python -m pytest tests/test_gold_language_evaluation.py -q -p no:cacheprovider --tb=short` passou em 3 testes; a execução da amostra limpa foi bem-sucedida sem erro do runner.


## Complemento P0 — síntese numérica e janela anual

Referência de produção: `748376c`, branch `feat/genai-baseline`. Nenhuma mudança no comportamento do chatbot nesta rodada.

- Avaliador existente `tests.gold_evaluation.evaluate_gold_case` aplicado aos 14 casos de `gold_evaluation_numeric.json`: 14/14 conformes. Cobre preservação de números calculados em Python com Decimal, evidência, ausência, acesso negado, publicação divergente e falha do provedor falso. Não executa SQL: os agregados são injetados. Arquivo: `ai-agent/reports/genai-p0-numeric-baseline.json`.
- Latências da mesma execução: p50 29,947 ms e p95 175,734 ms. Uma execução fria por caso, incluindo composição do teste; não são latências de produção nem do Gemini. Modelo falso, sem chamadas externas; custo/tokens reais não medidos.
- Experimento com competências artificiais completas de abril/2024 a março/2025: receita simples nos últimos 12 meses planeja corretamente a janela; pergunta longa de distribuição mantém a falha de classe desconhecida; ranking por classe pede uma única competência; agrupamento simples por classe planeja uma série mensal, sem comprovar consolidação do intervalo. Evidência: `ai-agent/reports/genai-p0-annual-coverage.json`. Nenhuma dessas quatro respostas comprova prontidão ou execução Gold real.

### Frequência e impacto dentro da amostra de 46

| Família | Casos divergentes | Frequência na amostra | Impacto observado |
| --- | --- | --- | --- |
| Classificação de entidade/calendário | GUARD-14, P0-34, P0-38 | 3/46 | Mensagem de esclarecimento não explica a intenção real |
| Ranking de total no intervalo | P0-35, P0-36 | 2/46 | Operação solicitada não é entregue; interpretação/política e capacidade posterior ausente |
| Ranking temporal perdido | P0-37 | 1/46 | Plano aceito sem escolher o maior mês; risco de resposta que não corresponde à pergunta |

A prioridade do ranking temporal decorre do impacto de sucesso semântico falso, não de ser a falha mais frequente. As proporções são autorais e não estimam frequência de insatisfação em produção.

### Correção do registro sobre perguntas reservadas

A afirmação anterior de que `gold_language_holdout.json` permanecia intocado estava incorreta: o comando `tests/test_gold_language_evaluation.py` inclui esse arquivo e foi executado nas verificações do avaliador. Portanto ele é regressão histórica conhecida, não reserva inédita do P0. Esta rodada não o usou para ajustar produto. É necessário obter um novo conjunto independente, separado antes das próximas correções; não reaproveitar perguntas reveladas como avaliação cega.

### Fechamento auditável do P0

| Critério | Estado |
| --- | --- |
| Conjunto reproduzível e baseline de planejamento | Disponível: 46 casos, 40 conformes e seis divergentes |
| Classificação e justificativa da primeira correção | Disponível na amostra; revisão humana da prioridade ainda necessária |
| Baseline de síntese numérica | Disponível com 14 agregados artificiais; sem consulta SQL |
| Frequência e impacto reais | Pendente: exemplos reais além dos dois pedidos fornecidos e amostragem representativa |
| Execução/números com referência independente do SQL | Pendente: exercício do executor no mesmo universo; agregado injetado não substitui essa prova |
| Clareza, utilidade e naturalidade | Pendente: avaliação humana, incluindo síntese de provedor real |
| Latência/custo de produção | Pendente: configuração e provedor de avaliação autorizados; medição local não substitui |
| Reserva independente | Pendente: criar nova reserva não exposta à implementação |

P0 permanece aberto. Foi solicitada à pessoa usuária uma amostra adicional de perguntas reais sanitizadas; a ausência dessa resposta não autoriza inventar frequência de uso. A cobertura anual agora foi investigada e deixa de ser dependência da classificação dessas falhas.


## Perguntas reais fornecidas pela pessoa usuária

Foram fornecidos dois exemplos, preservados em `ai-agent/tests/fixtures/gold_p0_user_reported.json`, e uma avaliação qualitativa de inflexibilidade generalizada fora das perguntas conhecidas. Esse relato não tem denominador e não permite declarar uma taxa de falha de todas as perguntas não avaliadas. A pessoa confirmou que “setores”, no segundo exemplo, significa classes de consumo; isso não cria um alias global para qualquer conversa.

A avaliação por `build_gold_language_report('gold_p0_user_reported.json', include_checks=True)` passou em 4/7 casos. Cobertura artificial completa: janeiro/2024 a maio/2025, sem SQL ou provedor. Quatro controles explícitos geram os planos esperados; as duas perguntas originais recebem esclarecimentos com motivos inadequados, e a continuação após confirmar classes não chega ao plano esperado. Arquivos de evidência: `genai-p0-user-reported.json` (respostas e recortes do experimento) e `genai-p0-user-reported-evaluation.json` (checks), em `ai-agent/reports`.

- REAL-01: “Qual foi o municipio com maio faturamento de maio de 2025?” é tratado como intervalo incompleto. O comportamento aceitável anotado é confirmar o possível erro maio/maior, sem exigir dois extremos que não foram solicitados. Controle com “maior faturamento em maio de 2025” planeja município, ordem descendente e limite um.
- REAL-02: “Quanto foi o faturamento total de 2024 em janeiro, dividido por setores?” para no período. O comportamento aceitável é reconhecer a competência e esclarecer a dimensão. O controle “janeiro de 2024, por classe de consumo” planeja o agrupamento.
- REAL-02C: após a confirmação “Classes de consumo” em contexto artificial, a continuação ainda não produz o plano esperado. Primeira divergência observada: interpretação/retomada de intenção; não foi executado o plano ou consultado banco.

O helper HTTP agora admite competências artificiais por caso e o avaliador reutiliza esse parâmetro. Não foi modificada interpretação de produção para fazer os exemplos passarem. Os três testes de regressão do avaliador passaram em 4,75 s. Os novos casos entram no conjunto de desenvolvimento, não na reserva inédita. Os dois exemplos são evidência real relatada, mas ainda não representam frequência de produção.


## Rastreio do fluxo para o P0

Fluxo quantitativo: pergunta e contexto → endpoint público Backend (`api/v1/endpoints/ai.py`) → coordenação (`services/genai_coordination.py`) com sessão, publicação e cobertura → cliente interno → `QuestionOrchestrator.plan` → `QuestionAnalysisPlanner` → `QuestionInterpreter`/`ReadPlanBuilder`/`ReadPlanValidator` → admissão Backend e `genai_executor` → SQL Gold somente leitura → evidência → `QuestionOrchestrator.synthesize`/`EvidenceGuard` → seleção de observações e composição → auditoria e resposta pública.

O plano contém IDs lógicos e recorte, não SQL. A evidência retorna valores, unidades, períodos, filtros, dimensões e publicação. O perfil não dá ao modelo autoridade para alterar escopo.

A recuperação em `language_recovery.py` usa regras e similaridade lexical para confirmação. A busca documental (`documentation.py`, `DocumentationResponder`) pode recorrer a `selector.select(question, chunks)` quando o roteamento lexical não resolve a seleção; essa seleção tem schema de referência/suficiência e não propõe plano quantitativo. Portanto não há uma intenção quantitativa semântica atualmente descartada pelo planner: o caminho de interpretação quantitativa com modelo ainda precisa ser avaliado/implementado. Os casos longos relatados ajudam a justificar essa investigação, sem comprovar que ela supera uma correção delimitada.

Chat e insights usam entradas diferentes: chat interpreta pergunta/contexto e busca evidência; `agent/insights.py` recebe contexto estruturado de tela, reautoriza os IDs necessários e gera hipóteses sobre indicadores já fornecidos. A qualidade do interpretador do chat não é demonstrada pelo sucesso de um insight. O modelo de síntese Gold seleciona IDs de observações; o texto numérico é composto pelo núcleo. Nenhuma dessas descrições altera a arquitetura ou o escopo do PRD.


## Prova SQL independente — PostgreSQL 16

Em 05/11/2026, no código `748376c` mais os ajustes locais do avaliador, o comando `python -m pytest tests/test_genai_session_postgres.py::test_session_selects_reader_and_database_denies_prohibited_access -q -p no:cacheprovider --tb=short`, executado em `backend`, passou em 205,42 s. Dependências: requirements Backend na venv de validação; PostgreSQL 16 temporário com autenticação por senha, usuário e bancos de teste preparados pelo script `backend/scripts/prepare_test_postgres.sql`, variáveis `TEST_POSTGRES_URL` e `TEST_GOLD_READER_ADMIN_URL` apontando apenas para bancos descartáveis. Comando de preparação: `Get-Content backend/scripts/prepare_test_postgres.sql -Raw | docker exec -i <container-descartavel> psql -U <admin-sintetico> -d v_energy_test`.

O teste existente confere a saída do executor contra `SELECT sum(receita_total_reais) FROM gold_v2.diagnostico_receita WHERE competencia = :month AND municipio = :city`, com referência sintética igual a 12,0. Esse controle não usa o compilador do plano para construir a consulta de referência. Também percorre pergunta pública autenticada, coordenação, SQL pelo leitor restrito, GenAI HTTP em subprocesso, evidência e auditoria; confere valores e percentuais sintéticos, acesso indevido, ranking, zero, ausência e nulo. Trata-se de um teste integrado com várias assertions, não de 46 consultas SQL do corpus inicial.

Resultado estruturado: `ai-agent/reports/genai-p0-postgres-baseline.json`. O container temporário foi parado e removido após o teste. A prontidão é controlada e o modelo é falso; não é prova de publicação real, Gemini ou portal. A dependência anterior “exercício do executor no mesmo universo com controle independente” foi atendida para essa fatia sintética. Isso não constitui certificado numérico para as operações que continuam ausentes.

### Estado atualizado do diagnóstico

Amostra de planejamento: 46 casos de desenvolvimento, mais sete casos dirigidos pelos relatos reais (com controles), sem misturar denominadores. Síntese numérica: 14/14; execução PostgreSQL: 1 teste integrado aprovado. As causas por etapa e o impacto já justificam investigar interpretação/retomada e ranking temporal. A contagem de incidentes refere-se aos conjuntos autorais; a alegação de falha generalizada relatada não foi convertida em taxa de produção.

Ainda faltam reserva inédita independente e revisão humana da utilidade das respostas medidas. O escopo de métricas reais de modelo/portal depende de ambiente de avaliação configurado; custo e tokens com modelo falso não podem ser reportados como números reais. P0 continua aberto enquanto essas condições permanecerem declaradas no roteiro.


## Pacote para revisão humana baseado no case

O PDF fornecido foi lido localmente (10 páginas) via pypdf 6.21.4 instalado apenas na venv de validação. Não foi copiado para o repositório. Foram elaborados e executados 24 cenários de diretoria, comercial, atendimento, operação, perdas, causalidade e continuidade, usando cobertura artificial de julho/2022 a junho/2026. A aplicação produziu 18 esclarecimentos e seis planos; esses números não são acurácia.

Artefatos: `gold_p0_case_review.json` em fixtures, `genai-p0-case-review.json` em reports e `2026-11-05-genai-p0-revisao-humana.md` nesta pasta. Reprodução em `ai-agent`: `python -m tests.p0_case_review`, com `GENAI_MODEL_PROVIDER=unavailable`, dependências do agente e autorização para sockets locais se o sandbox Windows os bloquear. O runner foi executado com sucesso nos 24 casos; não consulta SQL ou provedor. A avaliação humana está pendente e será solicitada no chat.

Achados para revisão: CASE-05 recusa percentual mesmo em uma comparação que pede reais e variação; CASE-08 planeja grupos mensais para um pedido de totais no intervalo; CASE-18 pede indicador em vez de comunicar o limite somente leitura (nenhuma alteração foi executada). CASE-23 pede outro período diante de cobertura ausente, comportamento potencialmente adequado. Uma mensagem inadequada não é, por si só, violação de autorização.


## Avaliação humana recebida em 05/11/2026

A pessoa usuária avaliou os 24 retornos apresentados no chat. Registro estruturado: `ai-agent/reports/genai-p0-human-review.json`, vinculado à fixture e ao pacote de revisão. A avaliação é de mensagens e planos resumidos, sem resposta numérica final.

Critérios de negócio confirmados: entregar valores/tabelas e rankings quando a análise for válida; resolver comparações e continuidade sem exigir frase pronta; permitir resposta parcial de perguntas compostas e explicitar a parte sem evidência; informar claramente somente leitura; admitir incapacidade de inferir causalidade ou fraude. CASE-09 aceita esclarecimento, sem definir ainda seus campos; CASE-16 permanece decisão de negócio aberta; CASE-23 é aceito com melhoria adiada. CASE-08 foi considerado ideal no formato apresentado, mas ainda requer prova de consolidação do período no executor. CASE-19 não torna soma anual, máximo mensal e maior município operações equivalentes: avaliar as paráfrases segundo a intenção correta.

A pendência de avaliação humana do pacote foi atendida; persistem o caso de negócio 16 e a ausência de reserva inédita independente. Resultados reais de Gold/Gemini e qualidade numérica não são aprovados por esta avaliação. As sugestões de prioridade anteriores ao feedback deverão ser revisitadas com os critérios de negócio agora explícitos.
