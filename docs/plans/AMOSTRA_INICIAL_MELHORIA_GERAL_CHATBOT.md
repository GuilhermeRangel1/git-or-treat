# Amostra inicial — Melhoria Geral do Chatbot V-Energy

Esta amostra contém 15 perguntas novas e está congelada como especificação da rodada diagnóstica. Congelar enunciados e oráculos não declara todas as capacidades prontas: prontidão, cobertura e suporte são estados avaliados em cada execução. As referências numéricas da Gold ativa e os limites conhecidos estão em [GABARITOS_REFERENCIA_MELHORIA_GERAL_CHATBOT.md](GABARITOS_REFERENCIA_MELHORIA_GERAL_CHATBOT.md), com SQL reproduzível em [REFERENCIAS_SQL_MELHORIA_GERAL_CHATBOT.sql](REFERENCIAS_SQL_MELHORIA_GERAL_CHATBOT.sql). A matriz de capacidades está em [MATRIZ_COBERTURA_MELHORIA_GERAL_CHATBOT.md](MATRIZ_COBERTURA_MELHORIA_GERAL_CHATBOT.md).

Os 15 casos também estão incorporados como a abertura do rascunho de [230 casos estruturados](CASOS_MELHORIA_GERAL_CHATBOT.json). A bateria de 230 casos foi revisada semanticamente e congelada para a linha de base; a avaliação Gemini completa ainda está pendente.

As categorias se sobrepõem. Uma pergunta composta também avalia métrica, linguagem e apresentação. Os casos devem percorrer Gemini, rota F1, readiness, SQL somente leitura, evidência e resposta que o portal exibe.

## Casos

### MGC-001 — Receita mensal, controle positivo

**Categoria:** métrica individual.
**Pergunta:** “Qual foi o faturamento total de Recife em junho de 2026?”
**Esperado:** total de `billing.revenue` em R$, município Recife, competência 2026-06.
**Gabarito:** `SUM(receita_total_reais)` na fonte Gold autorizada, filtrado pelo município e competência iguais. Comparar valor e unidade.
**Apresentação:** resposta direta e tabela ou cartão coerente com evidência.

### MGC-002 — Consumo por classe

**Categoria:** métrica individual, agrupamento.
**Pergunta:** “Quanto foi o consumo medido em cada classe de Recife em junho de 2026?”
**Esperado:** `energy.consumption`, em kWh, agrupado por classe, mantendo município e competência.
**Gabarito:** somar `consumo_total_kwh` por classe na população autorizada. Conferir que os grupos e o total correspondem ao mesmo recorte.
**Apresentação:** tabela por classe e gráfico categórico quando a evidência permitir.

### MGC-003 — Consumo médio por UC com leitura

**Categoria:** métrica individual, fórmula.
**Pergunta:** “Em média, quantos kWh cada UC com leitura consumiu em Recife em junho de 2026?”
**Esperado:** `energy.average_consumption_per_uc`, em kWh/UC com leitura.
**Gabarito:** `SUM(consumo_total_kwh) / SUM(qtd_ucs_com_leitura)` no grão mensal comparável. Não usar média simples das médias por grupo. Denominador zero deve produzir estado definido pelo contrato, sem divisão inválida.

### MGC-004 — UCs com GD cadastrada

**Categoria:** métrica individual, limite temporal.
**Pergunta:** “Quantas UCs estão cadastradas com GD?”
**Esperado:** contagem distinta de `id_uc` com `possui_gd = Sim` no lote consultado. A resposta deve descrever o resultado como retrato cadastral do lote, sem inferir vigência, geração ou injeção.
**Gabarito:** contagem distinta independente na população validada pelo readiness.
**Apresentação:** quantidade em UCs, sem período inventado.

### MGC-005 — Queda elegível em UCs com GD

**Categoria:** métrica individual, elegibilidade.
**Pergunta:** “Quantas UCs com GD tiveram queda de consumo maior que 30%?”
**Esperado:** `energy.gd_consumption_drop`; aplicar flag estritamente abaixo de −30%, GD cadastrada e pelo menos seis meses lidos em cada janela fixa.
**Gabarito:** consulta independente na Gold aplicando elegibilidade, janelas jul/2022–jun/2023 e jul/2025–jun/2026 e os dois mínimos de leitura. Não descrever a queda como causada pela GD.
**Apresentação:** total elegível e nota que explique as janelas fixas.

### MGC-006 — DEC/FEC de um alimentador em várias competências

**Categoria:** métrica individual, agregação e cobertura.
**Pergunta:** “Como ficaram o DEC e o FEC do alimentador ALM-ABR-001 de janeiro a junho de 2026?”
**Esperado:** avaliar prontidão para as seis competências do alimentador explícito. A rota F1 executa duas operações tipadas independentes, uma para DEC e outra para FEC, ambas sem agrupamento e sob o mesmo escopo e publicação Gold. Cada cálculo exige competências completas, denominador positivo constante e numerador válido; soma os numeradores e conta o denominador uma vez. O resultado permanece observado não certificado conforme a ADR-0024. Se prontidão negar ou o perfil não tiver autorização, não executar SQL.
**Gabarito:** cálculo independente restrito a ALM-ABR-001 pela regra acima. Nunca somar nem tirar média simples dos índices publicados. Em 09/11, a primeira execução admin confirmou a falha: pediu escolha entre DEC/FEC. Após a correção, a mesma pergunta passou pela rota pública `/api/v1/ai/sql-analyses` usando admin e a Gold ativa `GOLD_20261103T173853Z_76c37784`: DEC **0,5385047281 h/UC** e FEC **0,2996453901 interrupções/UC**, conciliados com a referência independente. As duas evidências mantiveram o aviso “Valores observados; cobertura do alimentador não certificada.”

### MGC-007 — Satisfação mensal

**Categoria:** métrica individual, fórmula e cobertura.
**Pergunta:** “Qual foi a nota média de satisfação dos atendimentos em junho de 2026?”
**Esperado:** `service.satisfaction`, média por protocolo aberto no mês. Ignorar notas nulas e preservar nota zero válida. Exigir cobertura mensal fechada e controle de prontidão.
**Gabarito:** média independente das notas válidas por protocolo dentro dos limites UTC do mês. Conferir precisão de apresentação.

### MGC-008 — Atendimento em linguagem simples

**Categoria:** métrica individual, linguagem coloquial.
**Pergunta:** “Quantos atendimentos foram abertos em junho de 2026?”
**Esperado:** contagem de protocolos abertos em junho, com competência e fuso horário conforme o contrato de `service.attendance`.
**Gabarito:** contagem independente de protocolos no intervalo UTC correspondente. Não contar tratativas repetidas como protocolos distintos quando a regra do catálogo exigir unicidade.

### MGC-009 — Preço médio observado

**Categoria:** métrica derivada, distinção semântica.
**Pergunta:** “Qual foi o preço médio observado por kWh faturado em Recife em junho de 2026?”
**Esperado:** `billing.effective_tariff`, com base conjunta elegível e valor em R$/kWh. Identificar como preço observado, sem chamá-lo de tarifa homologada ou regulada.
**Gabarito:** fórmula versionada no catálogo Gold para preço observado e mesmo recorte. Conferir numerador, denominador e critérios de elegibilidade contra cálculo independente.

### MGC-010 — Ranking por queda de consumo

**Categoria:** ranking, comparação temporal.
**Pergunta:** “Quais municípios tiveram as maiores quedas de consumo entre julho de 2024 e junho de 2025 e julho de 2025 e junho de 2026?”
**Esperado:** totais para as duas janelas, diferença em kWh e ranking decrescente pela maior queda absoluta. Mostrar percentual somente quando a base de referência for positiva.
**Gabarito:** agregações independentes por município nas mesmas janelas, com população comparável, diferença `período 2 − período 1` e percentual calculado sobre período 1. Definir desempate determinístico por município.

### MGC-011 — Comparação de consumo e receita por classe

**Categoria:** comparação, agrupamento composto.
**Pergunta:** “Compare consumo e receita faturada por classe entre julho de 2024 a junho de 2025 e julho de 2025 a junho de 2026.”
**Esperado:** apresentar cada métrica com unidade própria, os valores dos dois períodos e suas variações por classe. Só responder às duas métricas se cada origem, grão, recorte e população estiverem autorizados e conciliados. Não juntar fatos crus nem inferir causalidade.
**Gabarito:** uma referência independente para consumo e outra para receita, ambas agrupadas por classe e usando as mesmas janelas. Aprovar somente se os dois conjuntos estiverem completos e reconciliados.

### MGC-012 — Continuidade com troca de localidade

**Categoria:** linguagem coloquial, contexto conversacional.
**Turno 1:** “Me mostra o faturamento de Recife em junho de 2026.”
**Turno 2:** “E em Olinda?”
**Esperado:** no segundo turno, manter métrica e competência e substituir somente o município por Olinda.
**Gabarito:** comparar a interpretação do segundo turno com `billing.revenue`, junho/2026, Olinda. Conferir que Recife não permaneceu como filtro e que a primeira resposta continua vinculada ao seu próprio recorte.

### MGC-013 — Continuidade com mudança de métrica

**Categoria:** linguagem coloquial, contexto conversacional.
**Turno 1:** “Qual foi o consumo de Recife em junho de 2026?”
**Turno 2:** “E o faturamento no mesmo período?”
**Esperado:** manter município e competência, trocar a métrica para `billing.revenue` e sua unidade para R$.
**Gabarito:** validar o plano, a SQL e o resultado do segundo turno independentemente. Nenhum valor de consumo deve ser reutilizado como faturamento.

### MGC-014 — Ambiguidade legítima

**Categoria:** esclarecimento e contexto.
**Pergunta isolada:** “Qual foi o consumo?”
**Esperado:** pedir o recorte necessário, como competência ou localidade, conforme o contrato de esclarecimento. Não executar SQL nem assumir um contexto que não existe.
**Gabarito:** estado de esclarecimento, campos ausentes explicitados e zero execução SQL. Repetir como acompanhamento de uma consulta anterior em uma execução separada para conferir se o contexto inequívoco é herdado.

### MGC-015 — Caso composto obrigatório

**Categoria:** pergunta composta e complexa, caso obrigatório de aceite.
**Pergunta:** “Quais municípios apresentaram a maior queda no consumo de energia nos últimos 12 meses e como essa redução impactou a Receita faturada, considerando as diferentes classes de consumo?”
**Esperado:** usar as janelas anuais completas mais recentes existentes na Gold (neste snapshot, jul/2025–jun/2026 contra jul/2024–jun/2025), informá-las, ordenar municípios pela queda absoluta em kWh e mostrar a variação percentual quando a base for positiva. Destacar os três maiores recuos e detalhar consumo e receita por classe nesses municípios. A Gold não publica decomposição preço-volume para esse par; comparar as variações observadas, dizer que a decomposição não está disponível e não atribuir causalidade.
**Gabarito:** referências independentes para cada janela, município, métrica e classe. Conferir população, filtros, ordenação, valores, evidência e texto. O caso só passa quando todas as etapas obrigatórias passam. Se o produto não suportar uma etapa, registrar a falha da capacidade no baseline em vez de aceitar resposta parcial como completa.
**Apresentação:** ranking visual e tabela completa por município/classe. Conferir PNG e CSV com os mesmos dados e notas de alcance.

## Protocolo da rodada de amostra

- [x] Revisar e congelar estes 15 enunciados, intenções e gabaritos para a rodada diagnóstica.
- [x] Registrar snapshot Gold e publicar referências SQL independentes reproduzíveis. O lote é `GOLD_20261103T173853Z_76c37784`.
- [ ] Registrar, por execução, versões do modelo/prompt/catálogo, prontidão da capacidade e período, além de horário, latência e custo. Uma consulta de consumo foi confirmada pela tela; readiness geral para `2026-06` ficou `partial`.
- [ ] Executar a linha de base destes 15 casos pela rota F1 do portal e classificar cada resultado como aceito, esclarecido, bloqueado por readiness ou indisponível. A verificação pontual de consumo não é baseline.
- [ ] Repetir apenas os casos críticos definidos antes da rodada e manter estabilidade separada da pontuação da primeira resposta.

A amostra inicial de 15 está congelada. A bateria completa de 230 casos também foi revisada semanticamente e congelada, com 170 perguntas individuais cobrindo as 17 métricas do catálogo (ao menos dez por métrica) e divisão de 186 diagnósticos / 44 holdout, sem separar perguntas da mesma família. A baseline Gemini completa ainda não foi executada; ver [revisão semântica](REVISAO_SEMANTICA_MELHORIA_GERAL_CHATBOT.md) e [fixture](CASOS_MELHORIA_GERAL_CHATBOT.json). MGC-006 foi reconciliado pela rota pública com perfil admin, preservando o aviso de cobertura observada não certificada. MGC-015 foi especificado para comparação limitada nas janelas completas 2024-07..2025-06 e 2025-07..2026-06; sua resposta deve explicitar que não há decomposição preço-volume para esse par. Os gabaritos independentes e o holdout da bateria de 230 estão congelados para o snapshot Gold identificado; não confundir isso com aprovação do chatbot, que depende da baseline Gemini ainda pendente. Recalcular as referências se a publicação mudar.
