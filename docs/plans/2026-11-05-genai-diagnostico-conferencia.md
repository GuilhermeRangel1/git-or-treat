# Conferência do fechamento do diagnóstico GenAI

05/11/2026. Branch `feat/genai-diagnostico-final`, criada de `origin/develop` (`0511232`). Alterações da P1 preservadas no worktree `genai-p0-impacto`.

## Resultado reproduzido nesta branch

Em `ai-agent`, execução de `build_gold_language_report(nome, include_checks=True)` para as fixtures:

- `gold_p0_diagnostic.json`: 46 casos, 40 conformes, seis divergentes.
- `gold_p0_user_reported.json`: sete casos, quatro conformes, três divergentes.

Relatório: `ai-agent/reports/genai-diagnostic-recheck.json`. Execução terminou com código zero; esse código indica término do runner, não ausência de falhas do chatbot. As nove divergências continuam abertas para correção de produto. Não somar os denominadores nem interpretar conformidade do diagnóstico como qualidade numérica.

## Pendências que precisam de tratamento explícito

| Pendência | Evidência atual | Estado |
| --- | --- | --- |
| Fluxo, interpretação e recuperação existentes | Diagnóstico, seção Rastreio do fluxo | Inspecionado; falta sincronizar checkboxes detalhados |
| Falhas e baseline | Reexecução acima e consolidação | Reproduzidos |
| Revisão humana dos 24 casos | Relatório e avaliação fornecida pela pessoa usuária | Recebida; não avalia números finais |
| Referência SQL independente | Prova PostgreSQL registrada em 205,42 s | Disponível para fatia sintética; não cobre corpus inteiro |
| Reserva independente | Reserva autoral de 12 perguntas | Independência não demonstrada; mantida sem execução |
| Tokens, custo e latência de produção | Ausentes no baseline determinístico | Pendente; probe P1 não substitui produção |
| Experiência integrada Gold/portal | Sem nova prova nesta branch | Pendente |
| CASE-16 | Regra de negócio não decidida | Pendente |

## Correção do relato de andamento

O P0 foi encerrado anteriormente como diagnóstico inicial pelos cinco critérios de saída. Não existe evidência de conclusão de todos os checkboxes detalhados. Também foi impreciso afirmar no chat que esses checkboxes necessariamente exigem alterações no chatbot: primeiro é preciso conferir evidências, instrumentação e validações. A reserva não deve ser executada para preencher uma caixa; sua independência não pode ser criada por uma declaração do mesmo autor.

Esta conferência não conclui o P0 ampliado. Próximo trabalho: reconciliar cada item da seção 1 do TODO com as evidências, implementar lacunas do avaliador demonstradas nessa conferência e registrar os gates externos ainda não executados. Corrigir as falhas de interpretação e ampliar operações são entregas de produto rastreadas na P1.

## Auditoria item a item — seções 1.1 e 1.2

Esta é uma entrega de diagnóstico/preparação, ligada a IA-01/02/03/05/06/07/08 e ENT-01. Não altera o estado de aceite desses requisitos nem demonstra correção do chatbot.

### 1.1 — Estado do projeto

| Item | Resultado da conferência | Evidência |
| --- | --- | --- |
| IA-01 a IA-08 e ENT-01 | Revisados: português e números reconciliados; vocabulário e ambiguidade; fundamento reproduzível; insight; acesso portal; somente leitura; contexto; avaliação automática; decomposição da receita com incerteza. IA-01/02/03/06 e ENT-01 pendentes; IA-04/05 em validação; IA-07/08 concluídos no PRD | PRD, tabelas de requisitos IA e entrega. Revisar requisito não significa aprová-lo |
| Portal até exibição | Caminho estático identificado; jornada visual atual ainda não executada | `frontend/src/features/assistente/api.ts:askAIQuestion` → Backend `/ai/questions` ou `/ai/conversations/{id}/questions` → coordenação → GenAI → retorno decodificado → `AssistentePage.tsx` usa answer/message e MessageCard. Evidência histórica de navegador no contrato de follow-up não substitui nova prova |
| Interpretador e chamadores | Identificados | `composition.py:compose_core` injeta `QuestionInterpreter` em `QuestionAnalysisPlanner`; `planner.py` chama `interpret` com pergunta, contexto e intenção temporal pendente |
| Acionamento semântico existente | Identificado | `DocumentationResponder`: correspondência lexical exata evita modelo; demais casos podem chamar `selector.select`, após filtro de corpus/escopo. Recuperação quantitativa em `language_recovery.py` usa regras/similaridade para confirmação |
| Papel Gemini/compositor | Identificado | `GeminiModelAdapter.generate` usa schema de seleção em `generation/selection.py`; Gold escolhe observações, núcleo valida evidência e compõe números. Documentação escolhe referência/suficiência e retorna texto literal. Insight recebe contexto estruturado |
| Branch, commit, alterações | Conferidos | `feat/genai-diagnostico-final`, base `0511232`, P1 em outro worktree. `git status --short --branch` registra arquivos de diagnóstico locais; não há commit desta entrega |
| Contratos, decisões e aceite | Revisados no recorte afetado | Guia GenAI; contratos de execução, busca documental e follow-up; ADR-0002 (executor Backend), ADR-0018 (âncora na cobertura), ADR-0024 (DEC/FEC observado com ressalva). Notas de preparação antigas não substituem os parágrafos vigentes do guia |
| Recuperação implementada/utilizada | Confirmada | Composição existente e rastreio acima; seletor documental não propõe plano quantitativo |
| Intenção semântica até planner | Verificado como caminho ausente nesta base | Não existe proponente quantitativo em `compose_core`; planner recebe intenção determinística e a passa a `plan_builder.build` e `_approve`. Não há proposta semântica a perder filtros nesta branch. Avaliar/implementar esse caminho pertence à P1; este item diagnóstico está respondido |
| Fluxo com contratos/decisões | Registrado | Diagnóstico anterior, seção Rastreio do fluxo; composição, planner, coordenador Backend, executor, evidência, síntese, auditoria, consumidor acima |
| Chat versus insights | Confirmado | Chat interpreta pergunta/contexto; `ScreenInsightOrchestrator` recebe indicadores/recorte estruturados e gera hipótese sob a mesma política. Insight correto não valida compreensão do chat |

### 1.2 — Cobertura das perguntas

Os IDs abaixo referem-se às fixtures em `ai-agent/tests/fixtures/`. Presença de um cenário não indica que o produto o resolveu. Não misturar os denominadores.

| Item | Casos conferidos |
| --- | --- |
| Perguntas reais ruins | `gold_p0_user_reported`: REAL-01, REAL-02 e confirmação REAL-02C fornecidos pela pessoa usuária |
| Controles simples | `gold_p0_diagnostic`: REV-01, ENE-01; `user_reported`: REAL-01A/B, REAL-02A/B |
| Paráfrases sem aliases da métrica | Nova fixture `gold_p0_noncanonical`: NONCAN-01/02. Conferência programática dos aliases reais de billing.revenue, normalizados sem acentos/capitalização: nenhum está contido nas perguntas |
| Coloquial, longa, erro natural | REV-03, P0-34/P0-38, GUARD-01 e REAL-01 |
| Período explícito/relativo | REV-01, P0-33 e CASE-01/11 |
| Filtros, agrupamentos, ranking | REV-04, RANK-03, P0-35/36/38 |
| Mais de uma métrica | GUARD-08, P0-39, CASE-12/14 |
| Análise complexa | CASE-01/06/15/17; P0-38 |
| Acompanhamento | P0-41 a P0-46, REAL-02C, CASE-21/22; contexto está na fixture, não apenas no texto da pergunta |
| Ambiguidade genuína | GUARD-02/03/06, P0-40; CASE-09 aceita esclarecimento conforme revisão humana |
| Compreensível, não suportada | P0-35/36/37/38; CASE-03/04/06. A falta de capacidade não pode virar alegação de falta de autorização |
| Sem dados/cobertura | P0-33 tem janela maior que os três meses artificiais; CASE-23 pede janeiro/2027 além da cobertura. A ausência de linha SQL é coberta separadamente pela prova integrada, não por essas perguntas de planejamento |
| Causalidade/hipótese | CASE-15 e CASE-24; expectativa humana exige admitir limite causal |
| Sanitização | Fixtures contêm perguntas autorais, municípios e identificador artificial AL-01; nenhum PDF, chave, cadastro de pessoa ou linha bruta foi acrescentado. Relatos foram transcritos sem dados pessoais |

A amostra inicial de 46 continua congelada como baseline histórico; o suplemento de duas paráfrases não a reescreve. Os 24 casos de revisão humana e os sete relatos/controles têm escopos próprios. Reserva de 12 perguntas continua sem execução; não é apresentada como independente.

### Lacuna demonstrada e verificações novas

- NONCAN-01: soma em reais das faturas emitidas por município/mês. Intenção anotada: billing.revenue, Recife, março/2025, sem agrupamento.
- NONCAN-02: soma do valor total das faturas por classe em março/2025. Intenção anotada: billing.revenue e agrupamento por classe.
- Resultado: 0/2 conformes, ambos `needs_clarification`; não há plano/número calculado. Relatório `ai-agent/reports/genai-p0-noncanonical.json`.
- Reprodução em `ai-agent`: `build_gold_language_report('gold_p0_noncanonical.json', include_checks=True)` pelo avaliador existente. O novo nome foi incluído explicitamente na whitelist; a reserva continua excluída.
- `python -m pytest tests/test_gold_language_evaluation.py -q -p no:cacheprovider --tb=short`: três passaram em 5,00 s, incluindo detecção de filtro perdido em plano com status válido.
- `python -m ruff check tests/test_genai_regression.py`: passou.

A seção 1.2 está conferida. Na seção 1.1 permanece aberta a prova de uma pergunta exibida no portal atual, além do rastreio estático já concluído. Seção 1.3 e formato mínimo dos oráculos ainda precisam de conferência detalhada; P0 completo continua aberto. As falhas de produto encontradas permanecem na fila de correções, sem trocar seu resultado esperado para fazê-las passar.

## Rodada de fortalecimento dos oráculos

Conferidos 55 casos de planejamento, dos quais 33 esperam plano. A fotografia `genai-p0-oracle-audit.json` detectou quatro expectativas sem janela e nove sem filtros. Foram completadas a janela janeiro–março/2025 de P0-35/36/37/38 e a ausência explícita de filtros nos casos pertinentes. As perguntas e o comportamento de produção não foram alterados. Versões das fixtures receberam sufixo `-oracle-audit-1`.

Reexecução: 40/46, 4/7 e 0/2 conformes; relatório `genai-p0-oracles-recheck.json`. Os quatro casos de operações ainda ausentes continuam divergentes. Nenhuma referência numérica SQL foi inventada; 1.3 e a conferência de ordenação/limite/agregação ainda não estão concluídas. A fotografia de presença de campos não é validação semântica completa.

## Rodada — jornada visual e estado dos itens solicitados

A stack da branch foi compilada com `docker compose --env-file ../docker-gold-inicializacao/.env up --build -d`, preservando o volume existente. Build das três imagens concluído; banco e GenAI saudáveis no último resultado observado, loader iniciado e coordenação de subida ainda aguardando. Isso não demonstra portal pronto ou resposta exibida.

O Computer Use foi interrompido pela política da ferramenta: Firefox não suporta a aplicação da política de URLs neste ambiente. Não foi aberta nem enviada uma pergunta no portal nesta tentativa. O checkbox visual permanece aberto; desbloqueio: disponibilizar um navegador suportado pela ferramenta e validar a jornada nele. Não substituir prova visual por resposta HTTP.

### Formato mínimo — estado conferido

| Item | Estado e evidência |
| --- | --- |
| Pergunta original e contexto | Atendido para os conjuntos de desenvolvimento: fixtures registram perguntas e contextos quando relevantes; contextos vazios não significam histórico oculto |
| Intenção esperada | Parcial: expected e expected_business_intent em parte dos casos; falta uniformizar cada caso |
| Métrica/dimensões/filtros/período/agregação/ordenação | Parcial: janelas/filtros completados; agregação/ordem/limite ainda em auditoria |
| Resultado esperado | Parcial: status anotado nas fixtures; taxonomia não distingue em todos os casos capacidade ausente, ambiguidade e falta de dados |
| Referência quantitativa independente | Parcial: 14 agregados artificiais e uma prova SQL integrada; não há referência independente para toda pergunta quantitativa |
| Primeira divergência e evidência | Parcial: diagnóstico classifica famílias/casos divergentes; falta registro uniforme por caso e por fronteira |
| Desenvolvimento/reserva separados | Atendido: gold_p0_reserved.json permanece separado e sem execução; reserva autoral, sem alegação de independência |

### Medição 1.3 — estado conferido

| Item | Estado e evidência |
| --- | --- |
| Intenção correta | Parcial: checagens de plano e revisão humana; sem medida separada de intenção para todos os casos |
| Parâmetros corretos | Parcial: verificações de janela/filtros/métrica e demais campos presentes nos oráculos; faltam slots ainda não uniformizados |
| Plano representa intenção | Parcial: 40/46, 4/7 e 0/2 conforme os oráculos; campos de capacidade ausente são critérios de negócio, não contrato aprovado |
| Consulta executada corretamente | Parcial: um teste PostgreSQL integrado registrado; corpus de planejamento não executa SQL |
| Números reconciliados | Parcial: 14/14 artificiais e controle SQL independente de uma fatia; sem cobertura de todo corpus |
| Recusas indevidas | Parcial: contagem de plano esperado que recebeu esclarecimento é 3/46, 1/7 e 2/2; não equivale a recusa de segurança nem comprova que toda capacidade já existe |
| Esclarecimento necessário | Parcial: oráculos anotados e avaliação humana; falta classificar individualmente causas e suporte real |
| Clareza/utilidade/naturalidade | Parcial: 24 mensagens/planos avaliados pela pessoa usuária, sem nova resposta final numérica nem avaliação global de naturalidade |
| Latência/chamadas/tokens/custo/erros | Parcial: síntese artificial p50 29,947 ms e p95 175,734 ms; não são produção. Modelo falso sem custo/tokens reais. Probe de P1 é externo a esta branch e não fecha medição P0 |
| Regressões | Parcial: reexecução mantém 40/46 e 4/7; não comprova ausência de regressão em números/SQL/portal |

Contagens de esclarecimentos reproduzidas em `ai-agent/reports/genai-p0-clarification-counts.json`. Próximo trabalho interno: uniformizar intenção/resultado/primeira divergência nos casos e concluir slots; jornada visual exige navegador suportado. P0 permanece aberto.

## Execução das medições — runner P0

`python -m tests.p0_measurements` executado nesta branch. Resultado: 40/46, 4/7 e 0/2 no planejamento; 14/14 na síntese numérica artificial. Ruff aprovado. O relatório registra oráculos, resultado observado, mensagem, checks por slot, p50/p95 local e fronteira observável da divergência. Não usa modelo externo, SQL ou reserva. Tokens/custo ausentes são null, não zero inventado.

A conformidade por campo agora é reproduzível; não se promete precisão do interpretador isolado. Falhas de agregação/ranking continuam expostas e não são removidas do denominador. A saída de planejamento não basta para atribuir primeira causa interna; o relatório explicita essa limitação. Runner retorna falha para erro do avaliador ou falha numérica; falhas conhecidas de planejamento continuam no relatório diagnóstico.

A subida Docker terminou com loader concluído, Backend saudável e frontend iniciado. A jornada visual não foi executada porque Computer Use interrompeu o controle por falta de suporte à política de URLs no Firefox. Esse impedimento não afeta a execução dos testes HTTP artificiais.

## Consolidação na P1 — interpretação, esclarecimentos, regressão e provedor

Branch ativa `feat/genai-interpretacao`, worktree `work/genai-p0-impacto`. O diagnóstico foi copiado da branch `feat/genai-diagnostico-final` preservando o proponente/shadow P1. Diferença relevante: avaliador, duas perguntas sem aliases, oráculos de janela/filtros, runner e relatórios. A branch de diagnóstico não trouxe mudança ao comportamento produtivo. Mudanças desta rodada continuam locais.

### Medições executadas

- Captura de `QuestionAnalysisPlanner.plan` no mesmo fluxo HTTP: status/métrica/agrupamento anotados concordam em 43/46, 6/7 e 0/2 casos. `interpretation` e `intent_checks` ficam por caso; campos não anotados não são contados como acertos. Essa medida limitada não comprova intenção analítica inteira, janela resolvida ou operação que o contrato ainda não representa.
- Plano inteiro conforme campos anotados: 40/46, 4/7 e 0/2. Primeira fronteira observável é interpretação selecionada quando seus campos checados divergem; nos demais erros, planejamento HTTP. Causa interna não é inferida somente do status.
- Controles de capacidades existentes: esclarecimentos indevidos 0/22, 1/5 e 2/2. P0-35/36/37/38 ficam separados como capacidades ausentes. Não são taxas de bloqueio de segurança.
- Esclarecimentos esperados: status correto 20/20 e 2/2; motivo compatível 18/20 e 0/2. O conjunto de duas paráfrases não espera esclarecimento.
- Comparação com baseline `genai-diagnostic-recheck.json`: zero regressões novas em 53 casos comparáveis; as duas paráfrases novas não têm baseline anterior.
- Revisão textual do agente nas 18 mensagens existentes: `genai-p0-language-review.json` registra clareza, utilidade, naturalidade e motivo por caso. O artefato identifica autoria do agente e aponta separadamente para a revisão humana de 24 cenários. Seis planos sem texto final não recebem nota fictícia de resposta numérica. Predominam motivos inadequados, linguagem genérica e alternativas que não preservam a análise; CASE-17 tem exemplo pouco natural.
- Provedor: `python -m tests.semantic_provider_probe` executou sete solicitações Gemini com uma tentativa configurada. Quatro propostas validadas pelo contrato e três ServerError/503; nenhuma taxa de acerto semântico é inferida desses quatro contratos. Total de tokens retornados nas quatro chamadas com metadados: 18.456. Uso das falhas permanece desconhecido. p50 1.418,87 ms e p95 16.002,42 ms para esta amostra. Custo permanece null com motivo `pricing_not_configured`; não é zero. Arquivo de perguntas lido explicitamente em UTF-8.
- Síntese artificial reexecutada: 14/14. `python -m pytest tests/test_gold_language_evaluation.py tests/test_interpretation_shadow.py -q -p no:cacheprovider --tb=short`: seis passaram em 7,02 s. Ruff dos arquivos de medição, probe e proponente passou após correção de captura das variáveis do loop.

### Prova SQL em repetição

Primeira tentativa Windows interrompida sem resultado; não conta como aprovação. A primeira tentativa Linux detectou objetos deixados no banco descartável e falhou antes da prova. Somente o container sem volume `genai-diagnostic-postgres` foi recriado; o banco do portal foi preservado. Nova prova Linux em banco limpo em andamento; o resultado deve ser registrado depois de terminar. A aprovação histórica permanece descrita com sua data/alcance e não é apresentada como resultado desta execução.

## Resultado final da repetição SQL

A execução Linux limpa terminou com **1 teste integrado aprovado em 145,96 s** (145,164 s no testcase JUnit), mais um aviso preexistente Starlette/httpx. O teste percorreu sessão autenticada, planejamento HTTP GenAI, executor PostgreSQL com leitor restrito, referência SQL independente, síntese e auditoria. Inclui controles de proibição, prazo, ausência/nulo/zero, falhas e rotação no banco artificial. Esse conjunto de assertions continua sendo um teste integrado, não 55 consultas numéricas reais.

Evidência estruturada: `ai-agent/reports/genai-p0-sql-recheck.json`; JUnit privado: `work/p0-sql-linux-result.xml`. O container `genai-diagnostic-postgres`, sem volume, foi parado e removido; a consulta posterior por nome retornou vazia. Nenhuma remoção do banco do portal foi feita.

Os itens SQL e reconciliação da seção 1.3 foram marcados com esse alcance. A medição dos demais itens tem evidências limitadas e identificadas na rodada acima: intenção em campos anotados, corpus controlado, mensagens/planos de revisão humana e 18 esclarecimentos, sete chamadas experimentais Gemini. Não é aceite de qualidade global nem conclusão de todos os requisitos do P0: jornada visual e referência independente por pergunta quantitativa continuam pendentes.
