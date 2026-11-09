# TODO — Melhoria Geral do Chatbot V-Energy

A avaliação usa **230 casos novos** para medir a precisão, a flexibilidade e a capacidade analítica do Text-to-SQL. O ciclo é medir a versão atual com Gemini e Gold reais, identificar falhas, corrigir capacidades e medir novamente.

## 1. Montar a bateria de 230 casos

- [x] Revisar e congelar como especificação as perguntas, intenções e oráculos da amostra diagnóstica MGC-001–MGC-015. MGC-006 foi alinhado ao F1 v12 para um alimentador explícito e janela completa; a referência independente foi calculada. A primeira execução admin detectou esclarecimento incorreto. Depois da correção, a rota pública respondeu DEC e FEC agregados para jan–jun/2026 e conciliou com o cálculo independente, mantendo aviso de cobertura não certificada. MGC-015 foi definido como comparação limitada nas duas janelas anuais completas: informar o ranking e as variações por classe, além de declarar que não há decomposição preço-volume para esse par. Isso fecha o oráculo diagnóstico; uma alegação causal continua fora do aceite.
- [x] Calcular referências SQL independentes para os 15 casos no snapshot Gold ativo e registrar consulta, resultados e limites em [GABARITOS_REFERENCIA_MELHORIA_GERAL_CHATBOT.md](GABARITOS_REFERENCIA_MELHORIA_GERAL_CHATBOT.md) e [REFERENCIAS_SQL_MELHORIA_GERAL_CHATBOT.sql](REFERENCIAS_SQL_MELHORIA_GERAL_CHATBOT.sql). As instruções são reproduzíveis e foram executadas somente em leitura.
- [x] Criar a matriz das métricas e operações observadas em [MATRIZ_COBERTURA_MELHORIA_GERAL_CHATBOT.md](MATRIZ_COBERTURA_MELHORIA_GERAL_CHATBOT.md), separando contrato do catálogo, prontidão por lote e prova pela interface.
- [x] Gerar a bateria com **230 perguntas únicas** e a distribuição revisada das seis categorias em [CASOS_MELHORIA_GERAL_CHATBOT.json](CASOS_MELHORIA_GERAL_CHATBOT.json). O arquivo reaproveita somente a amostra nova aprovada; os 596 casos antigos não foram importados.
- [x] Alinhar os 230 registros ao catálogo Gold v2. Os casos MGC-211–220 cobrem dez consultas de cadastro por classe; MGC-221–230 cobrem dez consultas da fila por prioridade, incluindo a categoria zero. Assim, as 17 métricas do catálogo têm ao menos dez casos individuais. O teste estrutural confere o fixture; não certifica resposta do Gemini nem prontidão por usuário.
- [x] Habilitar localmente C05–C07 com o mínimo grant para `id_uc` e `prioridade_inspecao` na fila. A rota foi exercitada como admin contra a Gold ativa; isso não altera as políticas do perfil nem dá acesso a outras colunas.
- [x] Cobrir pela rota Gold as capacidades analíticas associadas aos controles liberados C05–C09. C05–C07 agora integram os 170 casos individuais como dez perguntas por métrica; as consultas CTL-001–004 ligam quatro casos MGC a Gemini real e SQL independente. C08/C09 já tinham perguntas e casos individuais na bateria (MGC-004/005); CTL-005/006 ligam os testes de rota a esses casos. As seis consultas passaram na rota autenticada e foram reconciliadas com SQL independente; C07 confirmou zero válido. Houve um 502 transitório do provedor em CTL-003, que passou na repetição.
- [x] Restaurar a configuração local `GENAI_GOLD_APPROVED_CONTROLS` do ambiente de demonstração Gold, incluindo C01–C15, sem alterar políticas de autorização. Readiness identificou as capacidades utilizáveis e as limitações restantes, registradas na matriz. A lista aprovada não substitui os resultados de controle nem certifica cobertura.

| Controles liberados/configurados | Relação com perguntas da bateria |
| --- | --- |
| C01–C04 | Regras de consistência e integridade que protegem consultas de consumo e faturamento. Esses controles não são métricas perguntáveis por si; os domínios correspondentes já aparecem nos casos MGC, cuja linha de base Gemini ainda está pendente. |
| C05 | UCs por classe de consumo. Dez casos individuais MGC-211–220; CTL-001/002 passaram na rota Gemini/Gold com SQL independente. |
| C06–C07 | UCs por prioridade da fila e categoria `ALTA - CONSUMO ZERO`. Dez casos individuais MGC-221–230; CTL-003/004 passaram na rota Gemini/Gold com SQL independente. |
| C08–C09 | Cadastro de GD e queda elegível acima de 30%. Já tinham perguntas individuais na bateria (MGC-004/005); CTL-005/006 passaram novamente na rota Gemini/Gold com SQL independente. |
| C10–C13 | Controles de população/nulos, continuidade, reconciliação e normalização das fontes. As métricas relacionadas têm casos MGC; não se deve interpretar a aprovação local do controle como validação da resposta Gemini. A linha de base ampla segue pendente. |
| C14–C15 | Prontidão/cobertura de atendimento. Atendimento mensal e satisfação já têm casos MGC; a linha de base Gemini dessas perguntas segue pendente. |
- [x] Carregar a Gold v2 local com os CSVs e manifesto disponíveis. O compose já monta a entrada e o lote ativo é `GOLD_20261103T173853Z_76c37784`; portanto, não falta montar `/gold-input`.
- [x] Auditar a disponibilidade de decomposição para MGC-015. A tabela ativa tem zero linhas para jul/2024–jun/2025 vs. jul/2025–jun/2026; suas 1.106 linhas usam jul/2022–jun/2023 vs. jul/2025–jun/2026. MGC-015 ficou congelável como comparação observada, com disclosure obrigatório da decomposição indisponível e sem atribuição causal. O efeito preço-volume continua pendente como capacidade separada; não foram inventadas linhas nem reutilizados atributos cadastrais atuais.
- [x] Auditar estrutura e diversidade dos 230 registros: IDs e perguntas únicos, distribuição 170/20/10/10/10/10, filtros variados e 198 famílias semânticas. Nenhuma família foi dividida entre diagnóstico e holdout.
- [x] Revisar semanticamente os 230 enunciados e transições contra o contrato F1 v12 e o catálogo Gold v2. Além das correções anteriores, MGC-211–230 variam classes e prioridades existentes na Gold, sem inventar categorias. Ver [revisão semântica](REVISAO_SEMANTICA_MELHORIA_GERAL_CHATBOT.md).
- [x] Congelar a bateria e o split por família para a linha de base. Revisão semântica, auditoria Gold e gabaritos independentes dos 219 casos com SQL concluídos no snapshot identificado. O split mantém 186 casos diagnósticos e 44 reservados, sem separar famílias semânticas. Os 11 casos sem SQL têm oráculo de estado; isso não equivale à aprovação do chatbot.

| Categoria | Casos | Cobertura |
| --- | ---: | --- |
| Cobertura individual das métricas | 170 | Dez casos por cada uma das 17 métricas do catálogo Gold v2. Inclui C05/C06/C07 em dez consultas próprias cada para cobrir classe cadastral, fila e prioridades; C08/C09 seguem nos casos GD já existentes. Variar operações e filtros dentro do que catálogo, dados e controles admitem. Usar faturamento simples como controle positivo. |
| Rankings, agrupamentos e comparações | 20 | A Gold foi varrida nos grãos mensais por município e município/classe: nenhum empate exato nesses recortes; também não houve base zero nas janelas anuais de MGC-015. MGC-041 cobre denominador zero real. Não fabricar exemplos. |
| Linguagem coloquial e sinônimos | 10 | Abreviações, perguntas indiretas e expressões usuais no portal. |
| Continuidade conversacional | 10 | Manter, trocar ou remover filtros, períodos e métricas entre mensagens. |
| Perguntas compostas e complexas | 10 | Combinar métricas, janelas e recortes. Incluir o caso obrigatório de consumo e receita. |
| Ambiguidades, limites e segurança | 10 | Avaliar respostas, esclarecimentos, falta de cobertura e recusas por escopo ou acesso. |
| **Total** | **230** | |

- [x] Revisar semanticamente cada caso, inclusive filtros, intenção, métrica, unidade, operação, estado e proibição de SQL. Revisão numérica independente concluída em seguida; não implica aprovação do Gemini.
- [x] Fazer auditoria dirigida de bordas no snapshot ativo: 48 competências e 7.600 linhas em `diagnostico_receita`; oito grupos município/classe/mês com zero UCs com leitura, nenhum empate mensal por município ou município/classe (consumo/receita), nenhum empate nas 14 variações anuais municipais de consumo e nenhuma base zero por município/classe nas janelas de MGC-015. MGC-041 agora cobre uma linha real de IGARASSU/PODER PUBLICO/2023-06 com zero leitores e consumo NULL. O resultado está limitado a esses grãos e períodos; não se generaliza a todo o catálogo.
- [x] Executar consultas independentes para todos os casos numéricos e conferir as 257 saídas caso/métrica/período: 2.001 linhas, nenhum resultado vazio e um NULL esperado em MGC-041. As 20 referências novas de cadastro/fila usam agregações e filtros independentes no snapshot. A execução foi READ ONLY.
- [x] Congelar a divisão por família, estratificada nas seis categorias: 186 casos diagnósticos e 44 reservados. Paráfrases e consultas equivalentes permanecem no mesmo split; o holdout não deve ser usado em ajustes.
- [x] Congelar a divisão depois de concluir os gabaritos independentes. MGC-015 é comparação observada com aviso explícito de que a decomposição preço-volume para as janelas pedidas não está disponível. O holdout de 44 casos continua reservado e não deve ser usado para ajuste.

## 2. Medir o estado atual do chatbot

- [x] Fazer verificações ponta a ponta da rota autenticada Gemini/Gold v2 para os seis cenários CTL-001–006 ligados aos casos MGC da bateria, incluindo classe residencial e a categoria de consumo zero ausente da Gold. Os resultados foram conciliados com SQL independente. Isso prova esses cenários de rota, não a linha de base completa MGC.
- [x] Fazer uma verificação ponta a ponta no Assistente com Gemini e Gold v2: “Qual foi o consumo medido em Recife em junho de 2026?”. A rota retornou 5.353.512,00 kWh para RECIFE, com tabela/evidência e a ressalva de que consumo medido não é energia faturada. É uma prova pontual de jornada, não a linha de base dos 230 casos.
- [x] Reproduzir e corrigir a falha de MGC-006 pela rota pública autenticada como admin. A causa era depender da geração livre para uma interpretação de par DEC/FEC e janela explícita. A rota agora deriva planos tipados estritos para pedidos conjuntos e individuais de DEC/FEC, somente para janela mensal explícita e coberta e alimentador presente no catálogo; cada consulta continua passando pela revisão semântica, prontidão, escopo, compilação e execução Gold. As chamadas reais responderam DEC 0,5385047281 h/UC e FEC 0,2996453901 interrupções/UC para jan–jun/2026 em ALM-ABR-001, conciliando com a referência independente e preservando o aviso de cobertura observada não certificada. Nenhuma consulta foi executada sem prontidão/autorização.
- [x] Preparar o executor de captura da baseline em `backend/scripts/run_mgc_f1_baseline.py`. Ele percorre apenas o split diagnóstico pela rota pública F1, mantém continuidade entre turnos, registra status, evidência, gabarito independente, correlação e latência; não grava SQL gerado nem tokens de continuação e não repete falhas automaticamente. O holdout não pode ser selecionado por esse executor. A revisão humana continua necessária para intenção e resultado; o executor correlaciona tokens/modelo/prompt pela telemetria Docker; custo em USD permanece nulo até aplicar uma tabela de preços confirmada. Testes offline cobrem seleção dos 186 casos, continuidade, redação dos tokens e estados esperados.
- [ ] Executar os casos de diagnóstico com Gemini e Gold reais pela rota usada pelo portal, antes das correções. A chave Gemini está configurada no runtime local, mas a rodada ampla ainda não foi executada nesta branch.
- [ ] Conferir intenção, métrica, filtros, períodos, validade e execução do SQL, valores retornados e clareza da resposta.
- [ ] Classificar as falhas conforme a seção 6 e consolidar os resultados por métrica e operação, com latência e custo.

## 3. Corrigir as capacidades que falharem

- [ ] Ajustar as definições das métricas, a interpretação da linguagem e o contexto conversacional conforme os erros observados.
- [ ] Corrigir geração e validação de SQL e implementar as operações analíticas reutilizáveis que estiverem faltando.
- [ ] Evoluir as consultas compostas para combinar métricas com períodos e recortes compatíveis.
- [ ] Reexecutar os casos afetados e verificar se as correções funcionam com outras formulações da mesma intenção.

## 4. Validar e melhorar a experiência no portal

- [ ] Conferir se a escolha automática do gráfico é adequada e se a tabela preserva o detalhamento necessário.
- [ ] Conferir se o PNG representa o gráfico exibido e se o CSV preserva valores, unidades e recortes da tabela.
- [ ] Aprimorar a apresentação das análises complexas, deixando claros os períodos comparados, os resultados por grupo e os limites da interpretação.

## 5. Homologar a melhoria

- [ ] Executar os casos de diagnóstico pela rota Gemini e comparar os resultados com a primeira rodada usando os mesmos critérios. A linha de base ainda não foi rodada.
- [ ] Rodar as perguntas inéditas reservadas e medir a capacidade de generalização.
- [ ] Confirmar o caso obrigatório no portal e registrar as capacidades comprovadas, as evidências e as limitações restantes.

### Caso obrigatório de aceite

> Quais municípios apresentaram a maior queda no consumo de energia nos últimos 12 meses e como essa redução impactou a Receita faturada, considerando as diferentes classes de consumo?

- [ ] Comparar os 12 meses mais recentes com cobertura completa na Gold com os 12 meses anteriores e informar as duas janelas.
- [ ] Ordenar os municípios pela maior queda absoluta em kWh e mostrar também a variação percentual. Explicar a ausência de percentual quando a base for zero.
- [ ] Detalhar a variação do consumo e da receita faturada por classe nos municípios selecionados, usando as mesmas janelas.
- [ ] Quantificar o efeito de volume quando houver decomposição válida para aquele recorte. Quando a Gold sustentar apenas uma comparação, apresentar as variações observadas e explicitar o limite da análise.
- [ ] Conferir ranking, recortes e valores com gabaritos independentes na Gold. Validar gráfico, tabela, PNG e CSV no portal.

## 6. Garantir a qualidade e a confiabilidade da avaliação

Os critérios desta seção valem desde a primeira rodada.

### Critérios propostos antes da linha de base

- Considerar elegível apenas pergunta com intenção/referência definida e fonte liberada. Falha Gemini, timeout e indisponibilidade entram em contagens próprias, sem virar acerto nem erro semântico.
- Para perguntas respondidas: exigir métrica, unidade, períodos, filtros e agrupamentos corretos; exigir valores dentro do arredondamento do catálogo Gold v2 (contagens inteiras; moeda, kWh e DEC/FEC em 2 casas; preço observado em 4; satisfação em 2).
- Em perguntas legítimas com prontidão aprovada, buscar ao menos **95% de acerto semântico na primeira resposta** e no máximo **5% de recusas indevidas**. Reportar os resultados geral e por métrica; não ocultar denominadores.
- Exigir **zero SQL** nas recusas por domínio, segurança, acesso negado e esclarecimentos sem contexto. Exigir estado correto para falta de cobertura, indisponibilidade e ausência de capacidade.
- Exigir que perguntas compostas passem em todas as etapas e evidências. Para o caso obrigatório, não inventar decomposição: comparar e detalhar o que a Gold sustenta e explicitar qualquer etapa não disponível.
- No holdout, exigir não regressão em relação aos mesmos critérios da linha de base; manter o resultado separado dos casos usados para correção.

Esses limites são uma proposta de aceite, fixada antes da linha de base. A chave do Gemini está configurada no runtime local e uma consulta ponta a ponta já foi confirmada. A amostra e os oráculos estão congelados; a linha de base diagnóstica ainda não foi executada.

- [x] Construir a matriz inicial relacionando as 15 métricas às operações e condições do catálogo/código. Ampliar a rastreabilidade para cobrir cada pergunta da bateria antes da rodada inicial.
- [x] Verificar a cobertura representada na matriz: métricas individuais, filtros e dimensões disponíveis, agrupamentos, comparações, fórmulas, continuidade, perguntas compostas e estados de limite/segurança. A revisão encontrou o ranking percentual de MGC-162 fora do contrato; ele agora é um caso negativo esperado sem SQL. A matriz de presença não garante cobertura exaustiva nem capacidade pronta.
- [x] Propor antes da rodada inicial critérios de aprovação, tolerâncias baseadas no catálogo e tratamento de falhas do provedor, acima. Revisar a proposta e congelá-la junto com a amostra.
- [x] Completar os gabaritos independentes e reproduzíveis dos 219 casos numéricos, com valores, fontes, recortes e snapshot explícitos. As 257 consultas caso/métrica/período produziram 2.001 linhas em transação PostgreSQL `READ ONLY`; não houve resultado vazio. O único NULL numérico é o caso de denominador zero MGC-041. Os 11 casos de recusa/limite têm estados esperados sem SQL. Ver [gabaritos completos](GABARITOS_GOLD_MELHORIA_GERAL_CHATBOT.json), [SQL reproduzível](REFERENCIAS_GOLD_MGC_230.sql) e [gerador do relatório](../../backend/scripts/build_mgc_gold_reference_report.py).
- [ ] Classificar cada falha por camada: interpretação de linguagem (NLU), camada semântica, planejamento, SQL, execução, resultado ou apresentação. Identificar separadamente as limitações dos dados e as indisponibilidades do provedor.
- [ ] Repetir perguntas críticas em execuções independentes para medir a estabilidade do Gemini. Registrar as repetições como execuções adicionais dos mesmos casos e manter a pontuação da primeira resposta separada.
- [ ] Registrar as versões do modelo, dos prompts, do catálogo semântico e do snapshot Gold em cada rodada. Se o snapshot mudar, recalcular os gabaritos para o recorte avaliado e registrar a mudança na comparação.
- [ ] Medir separadamente a precisão geral, a precisão por métrica, a taxa de acerto na primeira resposta, a estabilidade e a generalização nos casos reservados.
- [ ] Validar cada etapa das perguntas compostas com evidência própria. Aprovar o caso somente quando todas as etapas obrigatórias passarem.

**Critério de sucesso.** Demonstrar, dentro dos 230 casos novos, que as correções melhoraram capacidades reutilizáveis do chatbot. Confirmar o ganho nas perguntas inéditas reservadas, preservar os comportamentos aprovados na rodada inicial e exigir zero execução de consultas não autorizadas.

### Manifesto congelado para a linha de base

- Fixture: `CASOS_MELHORIA_GERAL_CHATBOT.json`, versão `MGC-2026-11-09-v3`; 230 casos com split por família semântica (186 diagnóstico / 44 holdout), incluindo dez casos individuais por cada métrica Gold v2. Hashes e snapshot no [manifesto](MANIFESTO_MGC_2026-11-09.md).
- Gold pretendida: lote `GOLD_20261103T173853Z_76c37784`; fingerprint `d1e9d3cb4455895155c09da82865807f5f83a608f832246be91e08063d158856`.
- Contrato da aplicação: F1 v12 nesta branch; registrar hash do commit antes da rodada.
- Gemini: registrar provedor, nome exato do modelo e versão configurados/retornados, hash do prompt e parâmetros efetivos. Não copiar a chave para os artefatos.
- Execução: registrar por caso ID, split, readiness/controles, horário, latência, custo, SQL admitido (ou confirmação de ausência), classe do resultado e evidência apresentada. Não registrar segredos nem dados pessoais.
- Estado: **230 casos e seus oráculos congelados; baseline Gemini completo ainda não executado**. A linha de base deve começar pelos 186 casos diagnósticos; os 44 casos holdout ficam reservados até concluir correções e definir a promoção. Os seis CTL são evidência de integração já executada, vinculada aos casos da bateria, e não substituem a baseline. MGC-015 tem comparação reproduzível com disclosure; a Gold não sustenta causalidade preço-volume nessas janelas. MGC-006 passou pela rota admin com referência conciliada e aviso de cobertura não certificada.
