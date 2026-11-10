# Auditoria das respostas da baseline MGC

## Escopo

Auditoria dos 96 turnos com estado `answered` na baseline executada em 2026-11-09 pela rota F1, usando Gemini real e a Gold v2 ativa. Foram conferidos métrica, período, filtros, agrupamento, unidade e valores quando havia oráculo numérico aplicável. A auditoria usou as expectativas por turno do fixture, e não apenas o resumo do caso.

## Resultado da auditoria e revalidação

| Resultado da revisão | Turnos |
| --- | ---: |
| Respostas conciliadas na primeira baseline | 93 |
| Divergências confirmadas na primeira baseline e depois revalidadas | 3 |
| **Turnos respondidos com resultado finalmente conciliado** | **96** |

Dos 93 conciliados na primeira rodada, 78 foram comparados por linha em consultas de um turno e uma métrica, 13 foram continuações conversacionais e 2 foram respostas DEC/FEC compostas. Em 2 respostas DEC/FEC, ambos os indicadores, o alimentador e a janela coincidiram com o cálculo ponderado independente. A resposta manteve o aviso de cobertura não certificada. As outras três respostas foram corrigidas e repetidas individualmente pela rota pública autenticada, com Gold ativa; as três reexecuções atingiram o estado e os valores esperados.

## Divergências confirmadas

| Caso | Esperado | Observado | Classificação |
| --- | --- | --- | --- |
| MGC-103 | Total histórico de chamados, sem inferir período, pela métrica `service.accumulated_attendance` | Baseline: classificou como `service.attendance` e exibiu jul/2022–jun/2026. Reexecução: `service.accumulated_attendance`, 318.871 protocolos, sem intervalo declarado | Corrigido o reconhecimento da expressão “total histórico”. Reexecução na rota em 18,1 s, estado esperado e ressalva explícita de intervalo e completude desconhecidos. Gemini real chamado uma vez; Gold executada e evidenciada. |
| MGC-169 | Comparar Recife de fevereiro para maio/2026, nessa ordem | Baseline: interpretou maio como período 1 e fevereiro como período 2, invertendo o sinal. Reexecução: fevereiro = 8.266.259 kWh; maio = 6.281.884 kWh; diferença = +1.984.375 kWh (+31,59%) | Corrigido com plano tipado para a formulação explícita de comparação entre dois meses. A rota validou cobertura, município autorizado, semântica SQL e execução Gold; reexecução em 15,8 s, estado e valores conciliados. O modelo Gemini não foi chamado para este caso. |
| MGC-203 | Recusar a pergunta anual sobre atendimento sem executar SQL, conforme o oráculo congelado | Baseline respondeu 88.212 protocolos para jan–dez/2025. Reexecução recusou com `operation_outside_f1`, sem evidência nem SQL | Corrigido o limite: atendimento na F1 permanece mensal. Reexecução na rota em 0,55 s, estado esperado; guarda executada antes de chamar o modelo. |

## Referências corrigidas durante a auditoria

MGC-008 e MGC-081–089 tinham SQL de referência usando `COUNT(DISTINCT id_uc)`, que mede UCs, enquanto os casos pedem protocolos e a métrica define `protocolo`. A consulta independente foi corrigida para contar protocolos distintos. Em leitura da Gold ativa, os valores de jun/2026, jan–jun/2026, out/2025, mar/2024 e ago/2023 foram conferidos diretamente. As respostas observadas nesses casos coincidem com os valores corretos.

MGC-080 tinha valor bruto 0,625 e evidência F1 de 0,62. O executor usa arredondamento `ROUND_HALF_EVEN`, então 0,62 é o arredondamento previsto pela implementação. Esse caso foi contado como conciliado, sem alterar o código de apresentação.

## Reexecução focal de filtros e razões na rota

Depois da auditoria inicial, sete consultas que cobrem bairro, consumo médio por UC, ticket médio, filtros de classe/bandeira e denominador zero foram repetidas na rota autenticada, com a Gold ativa. Métrica, filtros, unidade e número foram comparados automaticamente com os gabaritos SQL independentes:

| Caso | Resultado observado | Gabarito independente | Estado |
| --- | --- | --- | --- |
| MGC-025 | 202.341 kWh, OLINDA / CASA CAIADA | 202.341 kWh | Conciliado |
| MGC-033 | 880 kWh, ITAPISSUMA / CENTRO / RURAL | 880 kWh | Conciliado após corrigir o enunciado |
| MGC-035 | 413,95 kWh/UC, IGARASSU / bandeira VERDE | 413,954802; 512.890 / 1.239 | Conciliado |
| MGC-039 | 211,43 kWh/UC, JABOATÃO / RESIDENCIAL | 211,429190; 1.270.478 / 6.009 | Conciliado |
| MGC-041 | Resultado indisponível por denominador zero | `NULL`; numerador `NULL`; denominador 0 | Estado e limite conciliados |
| MGC-045 | R$ 4.971,32/UC, IPOJUCA / INDUSTRIAL | 4.971,318947; R$ 94.455,06 / 19 | Conciliado |
| MGC-051 | R$ 395,65/UC, ITAPISSUMA / RURAL | 395,648; R$ 1.978,24 / 5 | Conciliado |
| MGC-031 | 152.613 kWh, CAMARAGIBE / ALDEIA DOS CAMARÁS | 152.613 kWh | Conciliado |
| MGC-178 | 427,12 kWh/UC, RECIFE | 427,120857 | Conciliado |
| MGC-179 | R$ 246,65/UC faturada, RECIFE | R$ 246,645621 | Conciliado |
| MGC-180 | R$ 0,7583/kWh, OLINDA | R$ 0,758340842/kWh | Conciliado |

A revisão encontrou um defeito no fixture: a versão da pergunta de MGC-033 não dizia “classe rural”, mas o filtro e o SQL independente exigiam RURAL. O Assistente respondeu corretamente ao texto original, retornando 185.626 kWh para todo o bairro. Corrigimos a formulação para explicitar a classe e repetimos pela rota; o plano tipado aplicou município, bairro e classe e retornou 880 kWh. Para isso, o contrato F1 passou a admitir até três filtros explícitos e cobertos. Uma tentativa Gemini anterior para a formulação ajustada retornou resposta inválida; o plano tipado validado resolveu o caso sem nova chamada Gemini.

A primeira captura focal foi `%TEMP%/mgc-f1-neighborhood-ratios-fixed-2026-11-09.json`; MGC-033 foi repetido já com o enunciado corrigido em `%TEMP%/mgc-f1-mgc033-typed-2026-11-09.json`. Os sinônimos adicionais foram avaliados em `%TEMP%/mgc-f1-synonym-neighborhood-route-2026-11-09.json`. Os onze resultados foram comparados automaticamente ao fixture atual, aos filtros esperados e aos SQLs independentes e passaram.

## Revalidação focal de GD, cadastro e estados de limite

As seguintes respostas adicionais foram repetidas na rota autenticada com a Gold ativa, e confrontadas com os gabaritos independentes:

| Caso | Evidência da rota | Resultado da conferência |
| --- | --- | --- |
| MGC-139 / 141 / 177 | 328 UCs com GD em Olinda; 96 em Ipojuca; 304 em Paulista | Métrica e município corretos; contagens iguais ao SQL independente |
| MGC-174 | Contagem de UCs com GD agrupada em 14 municípios | Todas as 14 linhas conciliadas; corrigida a frase-resumo que antes repetia o primeiro grupo como se fosse total |
| MGC-192, turno 1 | 1.420 UCs com GD em Recife | Valor conciliado |
| MGC-192, turno 2 | 1.254 UCs com queda elegível acima de 30% em Recife | Continuação herdou somente Recife e o filtro GD; valor conciliado com SQL independente |
| MGC-210 | Recusa para “DEC e FEC por alimentador” sem alimentador nomeado | `operation_outside_f1`, sem evidência nem SQL, conforme limite do contrato |
| MGC-217 / 219 / 220 | 45.000 UCs no cadastro; divisão por cinco classes; 38.336 residenciais | Totais/linhas conciliados; cadastro tratado como retrato do lote |
| MGC-223 / 225 / 226 | 808, 42.652 e 1.023 UCs por prioridade | Valores conciliados; prioridade descrita como triagem, sem inferir inspeção ou irregularidade |

Capturas: `%TEMP%/mgc-f1-gd-cadastro-controls-route-2026-11-09.json`, `%TEMP%/mgc-f1-gd-group-dec-refusal-fixed-2026-11-09.json`, `%TEMP%/mgc-f1-mgc174-presentation-fixed-2026-11-09.json` e `%TEMP%/mgc-f1-mgc192-gd-continuation-fixed-2026-11-09.json`. A suíte focada de contexto, observação, semântica, evidência, apresentação e fixture passou: **254 testes**.

## Reexecução focal de faturamento e razões

Foram repetidos os dez casos-alvo de receita com filtros de município, subgrupo, bandeira, classe e GD; ticket médio; preço observado; e a continuação de faturamento em Recife (MGC-013, 016, 017, 019, 021, 023, 043, 049, 055 e 057). Os dez estados foram `answered`. Métrica, períodos, filtros e valores apresentados conferem com os gabaritos independentes, respeitando o arredondamento do catálogo; na continuação, o município Recife e o período junho/2026 foram preservados. A captura foi `%TEMP%/mgc-f1-triage-revenue-2026-11-09.json`; foram 11 turnos HTTP incluindo o turno de contexto de MGC-013. Telemetria correlacionou três chamadas Gemini, modelo `gemini-3.5-flash-lite`, prompt `text-to-sql-f1-38`; custo USD não calculado.

## Reexecução focal de agrupamentos e rankings mensais

MGC-160, 161, 165, 167 e 172 foram repetidos na rota após implementar plano tipado de comparação agrupada/ranking. Os cinco foram respondidos e reconciliados, linha a linha, com os totais e diferenças da referência SQL independente. MGC-160 classificou receita por município; MGC-161 receita por classe; MGC-165 variação de receita por classe; MGC-167 consumo por município; MGC-172 consumo por classe em Olinda. O par mensal declarado foi preservado, o desempate é determinístico e os percentuais usam o primeiro mês como base do segundo. Nenhuma linha do holdout foi consultada. Captura em `%TEMP%/mgc-f1-triage-rankings-final-2026-11-09.json`; esses planos foram locais e não chamaram Gemini.

Na Gold, todas as diferenças ranqueadas por “maior aumento” em MGC-160 e MGC-167 foram negativas. A resposta informa que não houve aumento no intervalo, em vez de rotular as maiores diferenças negativas como aumentos. MGC-165 também teve delta máximo negativo, e isso fica explícito. A mensagem de MGC-161/172 apresenta a comparação por grupo sem atribuir causalidade.

## Reexecução focal de métricas acumuladas de atendimento

MGC-099–108 e MGC-110, 112, 114, 116 e 118 foram verificados na rota Gold e reconciliados com os oráculos SQL: 318.871 protocolos acumulados e nota média acumulada de 4,04. As respostas deixam claro que a fonte não informa intervalo nem completude histórica. Foram 14 respostas `answered`, todas dentro do arredondamento do catálogo, captura `%TEMP%/mgc-f1-accumulated-service-fixes-2026-11-09.json`.

## Limites desta auditoria

- Ela pontua os 96 turnos respondidos. Os turnos `unsupported`, `invalid_response`, `needs_clarification`, os erros de transporte e a continuação não executada permanecem nas contagens próprias da baseline e são tratados em outros itens do todo.
- A captura da baseline não persiste SQL gerado. A prova de execução vem da evidência F1 assinada e a reconciliação numérica usa consultas de referência independentes.
- Uma tentativa intermediária de MGC-103 retornou HTTP 502; a repetição seguinte foi válida e passou. A captura final das três reexecuções está em `%TEMP%/mgc-f1-audit-fixes-2026-11-09.json`.
- As reexecuções focais validam os três defeitos específicos; não alteram a pontuação de primeira resposta da baseline nem reclassificam os demais estados da rodada.
- A captura não persiste o SQL literal. Para MGC-169, a consulta observada foi formada pelo candidato tipado local e admitida pelo revisor SQL; a evidência Gold contém períodos, filtro e valores usados na conciliação.
- Custo em USD permanece não calculado. A captura registra tokens da chamada Gemini, mas não foi aplicada uma tabela de preços verificada.
- O aceite visual de gráficos, tabela, PNG e CSV continua separado para a etapa posterior.

## Triagem dos estados não respondidos na baseline

Esta triagem compara o estado observado em cada turno com o estado previsto no fixture. Ela identifica onde investigar, mas ainda não substitui a revisão individual de intenção, prontidão e evidência nem reconta a baseline após as correções focais.

| Estado observado | Turnos | Com expectativa de resposta/continuação | Com expectativa de recusa, bloqueio ou esclarecimento |
| --- | ---: | ---: | ---: |
| `unsupported` | 54 | 38 | 16 |
| `invalid_response` | 30 | 29 | 1 |
| `needs_clarification` | 6 | 5 | 1 |
| `transport_error` | 7 | 6 | 1 |
| `not_run_missing_continuation` | 1 | 1 | 0 |

As 16 recusas compatíveis com a expectativa incluem negativas de escopo/segurança, estados bloqueados por prontidão e casos sem capacidade aprovada; cada uma ainda precisa ser confirmada com o motivo e a ausência de SQL. Os outros 79 turnos são candidatos prioritários para diagnóstico: falso bloqueio, falha de contrato do provedor, transporte, continuação ou incapacidade analítica. Não são 79 defeitos semânticos: as classes precisam ser separadas antes de pontuar. Reexecuções focais posteriores já corrigiram e reconciliaram vários casos da baseline — entre eles MGC-003, 025, 031, 033, 035, 039, 041, 045, 051, 103, 139, 141, 169, 174, 177, 178–180, 192, 203 e 217/219/220/223/225/226 — mas isso não altera a medição da primeira resposta. A enumeração é limitada às capturas focais registradas; não afirma que todos os candidatos restantes foram corrigidos.

## Diagnóstico inicial dos estados não respondidos na baseline

O cruzamento do snapshot inicial com todas as capturas focais disponíveis reduziu os casos sem repetição `answered` bem-sucedida a dois conjuntos:

| Grupo ainda aberto | Casos | Diagnóstico confirmado |
| --- | --- | --- |
| Composição de consumo/receita | MGC-011, 015, 193–195 e 201 | A observação F1 barra intencionalmente múltiplas métricas antes de gerar SQL (`multiple_metrics_outside_f1`). A rota composta existente cobre preço-volume somente quando o staging fixo está carregado. Falta uma operação composta tipada para as demais perguntas; não é falha do gabarito individual. |
| Decomposição preço-volume publicada | MGC-119–128 | A Gold ativa contém o par jul/2022–jun/2023 vs. jul/2025–jun/2026: 1.098 grupos `CALCULADA_BASE_COMUM` e 8 `SEM_BASE_COMUM`. A decomposição F1 recusa agregação que misture estados, corretamente evitando somar silenciosamente grupos sem base. Alguns filtros por classe têm apenas grupos calculados, mas nenhum dos dez casos foi confirmado pela rota nesta rodada. |
| Erros sem revalidação bem-sucedida | MGC-014, 053, 098, 181, 182, 197, 198 e 199 | MGC-014/198 registraram `RemoteProtocolError`; MGC-098/182 e MGC-199 tiveram HTTP 502; MGC-181 teve HTTP 503; MGC-197 teve HTTP 500 com corpo inválido; MGC-053 não recebeu resposta HTTP. Isso identifica transporte/servidor, não a correção semântica. |

Para o caso obrigatório MGC-015 e MGC-195, a Gold ativa não tem linhas nas janelas jul/2024–jun/2025 vs. jul/2025–jun/2026 (consulta somente leitura: zero linhas). A API local também está sem `GENAI_PRICE_VOLUME_STAGING_DIR`, e não há CSV/manifesto da staging no worktree ou no container. O seletor tipado para as formulações de ranking e impacto passou nos testes unitários, mas não foi exercitado pela rota; portanto MGC-015/195 não passam aceite ponta a ponta nesta captura. Não se deve confundir o código da rota com staging presente.

O cruzamento inicial não preservou correlation IDs nas respostas 500/502/503; o Backend foi reconstruído depois, e os logs históricos dessas requisições não estão mais disponíveis. Isso impede atribuir os erros originais ao Gemini. As reexecuções controladas posteriores, sem recontar a baseline de primeira resposta, estão registradas na seção seguinte.

## Regressões verificadas após as correções

Na execução integral do Backend, a auditoria encontrou uma regressão de precedência no reconhecedor: o termo “consumo” estava sendo tratado como pedido da medida de energia antes de identificar contagens de UCs por classe, consumo zero e perguntas de GD. A precedência foi corrigida e os testes de controles, contexto, observação, semântica e rota passaram.

A mesma execução expôs uma diferença entre a regra semântica de deltas e o contrato legado dos planos de comparação. A validação agora exige período final menos inicial para aumentos, variações e comparações agrupadas; exige período inicial menos final para quedas/reduções; comparações simples preservam a ordem explicitamente declarada. O caso de satisfação acumulada com ano explícito também verifica a recusa antes de gerar SQL, pois a publicação não certifica uma janela anual.

Após esses ajustes, a suíte integral do Backend passou: **3.692 testes passaram e 154 foram ignorados em 299,81 segundos**. Ruff nos arquivos Python alterados e `git diff --check` passaram. Essa é uma validação automatizada do código; ela não reexecuta Gemini/Gold para os casos pendentes nem modifica as contagens congeladas da baseline.

Na repetição real dos oito estados inicialmente inconclusivos, MGC-014 pediu o período ausente sem SQL, conforme esperado; MGC-053 respondeu R$ 241,85/UC faturada (gabarito 241,850076...), MGC-182 respondeu média 4,10 (gabarito 4,098466...) e MGC-181 respondeu 6.433 protocolos. A comparação de MGC-181 descobriu que seu gabarito independente usava `COUNT(DISTINCT id_uc)` e rotulava 6.005 UCs como protocolos. A referência foi corrigida para `COUNT(DISTINCT protocolo)` e uma consulta PostgreSQL independente `READ ONLY` confirmou 6.433 protocolos e 6.005 UCs em jun/2026. Os dois valores medidos representam métricas distintas; o caso pergunta chamados/protocolos. MGC-053/181/182 agora têm valor e evidência conciliados.

MGC-098 inicialmente falhou no entendimento de “avaliações” acentuado: foi classificado como contagem de atendimento. Corrigido o mapeamento para reconhecer variantes acentuadas e adicionado um plano mensal tipado de satisfação com limites UTC explícitos e competência coberta. A repetição local pela rota respondeu 4,08 pontos para nov/2023, conciliando com o SQL independente (4,084642857...), sem chamada Gemini.

MGC-197 e MGC-199 continuam com recusa por operação composta fora do F1. MGC-198 continua com HTTP 502 após duas execuções; as respostas inválidas aparecem no estágio de geração, mas a captura não preserva dados suficientes para atribuir a causa ao modelo. Essas três composições esperam resultado no fixture, mas não há ainda uma resposta composta/evidências independentes integradas na rota; ficam abertas. As reexecuções não alteram as contagens congeladas da baseline original.

## Artefatos consultados

- `CASOS_MELHORIA_GERAL_CHATBOT.json`, versão diagnóstica atual MGC-2026-11-09-v4; a captura da primeira baseline usou v3 e o holdout não foi alterado.
- `GABARITOS_GOLD_MELHORIA_GERAL_CHATBOT.json` e `REFERENCIAS_GOLD_MGC_230.sql`.
- Captura da rodada em `%TEMP%/mgc-f1-baseline-2026-11-09.json`.
- Captura focal MGC-003 pós-correção em `%TEMP%/mgc-f1-mgc003-after-fix.json`.
- Captura focal MGC-103 pós-correção em `%TEMP%/mgc-f1-mgc103-after-fix.json`.
- Captura das reexecuções focais MGC-103, MGC-169 e MGC-203 em `%TEMP%/mgc-f1-audit-fixes-2026-11-09.json`.
- Capturas focais posteriores de bairro/razões: `%TEMP%/mgc-f1-neighborhood-ratios-fixed-2026-11-09.json` e `%TEMP%/mgc-f1-mgc033-typed-2026-11-09.json`.

## Replay integral e reconciliação numérica posterior

Uma segunda captura percorreu novamente os 186 casos diagnósticos, mantendo os 44 casos holdout fora da execução. Foram programados e tentados 194 turnos pela rota autenticada do Assistente, com Gold v2 ativa, Gemini `gemini-3.5-flash-lite` e prompt `text-to-sql-f1-38`. A captura está em `%TEMP%/mgc-f1-postfix-replay-2026-11-09.json`; não persiste SQL gerado, e o custo em USD não foi calculado.

Estados desta repetição: 154 turnos `answered`, 29 `unsupported`, 2 `needs_clarification` e 9 `invalid_response`. Oito dos 154 turnos respondidos são as falas iniciais de conversas; a revisão numérica abaixo compara o último turno de cada caso com o oráculo de caso e não atribui a ele a referência da primeira fala. Entre as 9 respostas inválidas, MGC-169 e MGC-177 já tinham revalidação focal bem-sucedida documentada. MGC-209 foi corrigido depois desta captura; MGC-089, 133, 137, 170, 194 e 198 ainda precisam de resolução/revalidação. O estado agregado da captura permanece congelado e não é reescrito pelas correções focais.

Nos últimos turnos respondidos com evidência de métrica única, foram conferidas dimensões/grupos e números contra os SQLs independentes: **203 valores em linhas simples e 80 células de comparação** coincidiram após corrigir a referência de MGC-189. O único `NULL` esperado também coincidiu (MGC-041). Dois resultados DEC/FEC usam o contrato composto de continuidade e permanecem cobertos pela reconciliação independente focal descrita anteriormente. A métrica e os filtros fixos de GD foram avaliados incluindo o filtro implícito `possui_gd = Sim`. A auditoria numérica não prova, por si só, acerto de linguagem natural em todos os primeiros turnos das conversas.

MGC-189 perguntava os protocolos no segundo turno. A referência independente tinha `COUNT(DISTINCT id_uc)`, que retornava 6.005 UCs; foi corrigida para `COUNT(DISTINCT protocolo)`. Uma consulta PostgreSQL `READ ONLY` separada confirmou 6.433 protocolos e 6.005 UCs em junho/2026; a evidência observada da rota era 6.433. O fixture numérico agora usa 6.433.

Também foram corrigidos dois estados que falharam na captura integral:

- MGC-162 pedia os cinco municípios com maior queda **percentual**. A versão da captura respondeu ordenando pela diferença absoluta, sem correspondência com o gabarito que exige recusa enquanto F1 não admitir ranking percentual. Foi adicionada uma recusa determinística antes da geração. Dois testes verificam variação percentual de consumo/faturamento sem chamar o modelo; replay focal pela rota retornou `unsupported` sem evidência e com estado esperado.
- MGC-209 pedia nomes e dados pessoais dos titulares. A captura terminou em HTTP 502. Foi adicionada uma recusa determinística de pedidos explícitos de dados pessoais antes da geração; teste unitário prova zero chamadas ao gerador e replay focal pela rota retornou `unsupported`, sem evidência, conforme esperado.

A suíte integral do Backend, após essas duas regras, passou: **3.695 testes passaram e 154 foram ignorados em 377,65 segundos**. Os testes focais de observação passaram: 57; Ruff nos arquivos Python alterados passou e `git diff --check` não encontrou erros. Isso não resolve lacunas de composição nem staging. Continuam em aberto 16 casos que esperam uma composição/resposta ainda não fornecida pela rota — MGC-011, MGC-015, MGC-119–128, MGC-193–195 e MGC-201 — além do replay do caso composto MGC-199, cuja resposta foi apenas satisfação de junho em vez de protocolos e satisfação de janeiro a junho. A decomposição preço-volume para as janelas exigidas segue ausente na Gold ativa e sem staging carregada.

Replays focais após as duas recusas: `%TEMP%/mgc-162-guard-recheck-2026-11-09.json` e `%TEMP%/mgc-209-guard-recheck-2026-11-09.json`.

Na etapa seguinte, o Backend passou a reconhecer pedidos conjuntos de atendimento e satisfação antes de gerar um plano para uma única métrica. O teste de regressão de MGC-199 confirma a recusa explícita sem geração. A composição completa continua pendente. A rodada focada de contexto, observação e rota pública teve 144 testes aprovados e 2 ignorados.
