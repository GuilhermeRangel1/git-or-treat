# HNLU — revisão dos 24 casos de negócio — 2026-11-07

## Escopo e método

Foram submetidos 23 dos 24 casos da fixture `gold_p0_case_review.json` ao endpoint público autenticado, com Gemini em modo de interpretação e Gold v2 ativa. O `CASE-16` foi omitido porque sua expectativa depende de decisão de negócio ainda pendente. Os perfis de teste foram escolhidos conforme a persona. Os casos `CASE-09` a `CASE-12` e `CASE-18` não tinham métricas Gold permitidas para os perfis de atendimento/perdas; portanto, esses casos não medem a capacidade semântica daqueles domínios.

Resultados, estados, filtros e planos foram examinados sem incluir no relatório perguntas/respostas Gold ou valores agregados exatos. Para `CASE-02`, `CASE-20` e `CASE-21`, a consulta SQL independente ao mesmo lote confirmou os resultados numéricos. `CASE-02` exigiu repetição por erro recuperável do provedor; outra chamada, idêntica, respondeu corretamente. Uma comparação diagnóstica com o modo determinístico mostrou regressão Gemini em `CASE-19` e uma agregação incorreta em `CASE-08`. Essa comparação é evidência de caso, não benchmark estatístico: as tentativas repetidas, os perfis e as capacidades variam.

Publicação: `gold-csv-v2`, lote `GOLD_20261103T173853Z_76c37784`, publication ID `5cff9e92-c1e8-4b52-9cb8-787636129ecd`, fingerprint `d1e9d3cb4455895155c09da82865807f5f83a608f832246be91e08063d158856`. O teste usou a publicação local e consulta somente leitura. Sem grant novo.

## Resultados por caso

| Caso | Perfil | Observação do fluxo real | Classificação |
| --- | --- | --- | --- |
| CASE-01 | Diretoria | Pediu esclarecer janela aprovada; não montou a consolidação anual por classe esperada. | Extração temporal/capacidade de agregação em janela. |
| CASE-02 | Comercial | Respondeu o município de maior faturamento em maio/2025; plano de ranking e referência SQL coincidiram. Uma tentativa intermediária falhou recuperavelmente. | Sucesso reconciliado, com instabilidade transitória. |
| CASE-03 | Comercial | Pediu uma única competência para o ranking anual. | Agregação anual e ranking top-N ainda não suportados. |
| CASE-04 | Diretoria | Pediu janela aprovada para identificar máximo mensal e participação no ano. | Máximo de série/participação não representado no plano. |
| CASE-05 | Diretoria | Ocorreu erro recuperável; a repetição pediu esclarecimento. A solicitação combina variação em reais e percentual. | Operação derivada composta; pode ficar fora da fatia inicial conforme decisão da pessoa usuária. |
| CASE-06 | Diretoria | Pediu janela aprovada para uma análise de receita composta. | Análise composta/decomposição fora da fatia inicial. |
| CASE-07 | Comercial | Pediu uma competência única para comparar quedas entre períodos. | Ranking de mudança entre janelas ausente. |
| CASE-08 | Comercial | Gemini pediu janela aprovada. No modo determinístico, o plano gerou grupos mensais e a síntese escolheu o maior grupo mensal, em vez de agregar cada grupo GD no intervalo solicitado. | Bug reproduzido de granularidade/agregação; prioridade alta. |
| CASE-09 | Perdas | Perfil não expõe métricas Gold. | Bloqueio de autorização/catálogo; NLU não avaliada. |
| CASE-10 | Atendimento | Perfil não expõe métricas Gold. | Bloqueio de autorização/catálogo; NLU não avaliada. |
| CASE-11 | Atendimento | Perfil não expõe métricas Gold. | Bloqueio de autorização/catálogo; NLU não avaliada. |
| CASE-12 | Atendimento | Perfil não expõe métricas Gold. | Bloqueio de autorização/catálogo; NLU não avaliada. |
| CASE-13 | Operação | Pediu especificar alimentador embora a pergunta citasse o identificador sintético `AL-01`. | Extração do filtro não chegou ao plano; sem validar resultado físico porque o identificador é artificial. |
| CASE-14 | Operação | Pediu janela aprovada para ranking anual de alimentadores/indicadores. | Agregação/ranking temporal ausente; distinção DEC/FEC precisa permanecer explícita. |
| CASE-15 | Operação | Pediu escolher DEC ou FEC diante de pergunta composta sobre ocorrências e atendimento. | Resposta deve delimitar capacidade e evitar inferência causal; caso composto fora da fatia inicial. |
| CASE-16 | Diretoria | Não executado. | Oráculo de negócio pendente de decisão humana. |
| CASE-17 | Diretoria | Uma resposta inválida gerou erro recuperável; a repetição pediu métrica, período e local para uma recomendação. | Capacidade de recomendação/critério de esclarecimento pendente; não há evidência suficiente de acerto. |
| CASE-18 | Perdas | Perfil não expõe métricas Gold de perdas. | Bloqueio de autorização/catálogo; recusa de ação operacional não validada nesse perfil. |
| CASE-19 | Comercial | Antes do ajuste, Gemini pediu esclarecer o filtro. O diagnóstico mostrou que `Recife` aparece como município e bairro, embora o modelo tenha identificado `geography.municipality`; o builder ignorava esse ID. Depois do ajuste, uma chamada Gemini produziu plano correto e o executor retornou evidência. Uma repetição pediu esclarecimento novamente, portanto a resposta ainda é variável. | Defeito de desambiguação do builder corrigido e reproduzido; estabilidade Gemini ainda pendente. Esta rodada não conclui nova reconciliação numérica por API. |
| CASE-20 | Comercial | Respondeu consumo residencial em Olinda em maio/2025; soma independente em kWh coincidiu. | Sucesso semântico e numérico reconciliado. |
| CASE-21 | Comercial | Follow-up preservou município/classe e respondeu consumo em maio/2026; soma independente coincidiu. | Sucesso de continuidade e resultado reconciliado. |
| CASE-22 | Comercial | Gemini pediu janela aprovada para o follow-up “Classes de consumo”; modo determinístico também não preservou a intenção contextual esperada. | Falha de continuidade/contexto. |
| CASE-23 | Comercial | Gemini pediu esclarecimento de filtro para competência futura. No modo determinístico, o esclarecimento apontou ausência de janela mensal completa. | Deficiência de diagnóstico/estado de ausência de evidência no Gemini. |
| CASE-24 | Diretoria | Pediu janela aprovada, em vez de explicar que fraude não pode ser inferida causalmente com a evidência pedida. | Falha de delimitação epistêmica e de prioridade da limitação causal. |

## Leitura e limites

- Há comprovação ponta a ponta e reconciliação numérica para três casos executáveis (`CASE-02`, `CASE-20`, `CASE-21`), mas isso não demonstra estabilidade ampla nem cobre todos os domínios.
- A rodada não autoriza comparar “precisão geral”: há casos fora da capacidade F1, perfis sem concessão Gold correspondente, casos compostos, identificador sintético, uma decisão de negócio pendente e erros transitórios do provedor.
- No fluxo observado, a geração Gemini variou numa pergunta básica (`CASE-19`): antes da correção falhou; após corrigir a desambiguação, uma chamada planejou corretamente e outra esclareceu. Ainda não há base para promover Gemini como padrão. O padrão determinístico/rollback deve permanecer.
- As métricas de atendimento e perdas precisam de decisão de acesso antes de serem testadas com esses perfis. A conversa/endpoint permitir acesso não equivale a autorização a fatos Gold. Não foram ampliadas permissões.
- Não foi feita jornada visual no portal. A página local abriu na tela de login, mas não havia arquivo de credenciais de teste disponível neste worktree para autenticar sem expor ou redefinir credencial.

## Próximas correções priorizadas a partir da evidência

1. Corrigir agregação de janela antes da síntese: agrupar os totais do intervalo por dimensão e nunca usar o maior grupo mensal como substituto (`CASE-08`).
2. Corrigir entendimento de filtros explícitos em consultas simples; adicionar regressão do caso `CASE-19` para o modo Gemini.
3. Melhorar a extração/preservação de contexto e a classificação de falta de cobertura (`CASE-13`, `CASE-22`, `CASE-23`).
4. Especificar e depois habilitar ranking anual, máximo mensal e variação entre janelas, em fatias independentes (`CASE-03`, `CASE-04`, `CASE-07`, `CASE-14`).
5. Para pedidos compostos e causais, responder com os limites suportados ou pedir esclarecimento específico; não inferir causalidade (`CASE-05`, `CASE-06`, `CASE-15`, `CASE-17`, `CASE-24`).
6. Decidir formalmente se perfis de atendimento e perdas devem receber métricas/dimensões Gold, e revisar `CASE-16`; até então, manter os testes desses casos bloqueados por escopo.
