> **TODO 2 — roteiro principal de execução.**
> Branch atual: `feat/genai-interpretacao`; worktree `work/genai-p0-impacto`.
> Diagnóstico e preparação P1 reunidos nesta branch a pedido da pessoa usuária. Os TODOs permanecem locais, fora dos commits/push.
> O PRD é a fonte de verdade; cada conclusão exige o alcance e a evidência descritos nas rodadas abaixo.

# TODO --- Evolução do GenAI com foco em impacto

**Versão:** 2.1 --- execução por falhas demonstradas e entregas verificáveis\
**Data:** 05/11/2026\
**Repositório:** `GuilhermeRangel1/git-or-treat`\
**Branch de trabalho:** `feat/genai-interpretacao`\
**Base desta branch:** `origin/develop` / `0511232`; checkpoint P1 `c1911d1`

## Objetivo

Melhorar de forma perceptível a capacidade do chatbot de compreender
perguntas naturais, planejar análises úteis e explicar resultados com
clareza, sem comprometer segurança, autorização ou confiabilidade
numérica.

**Estratégia principal: medir uma falha → localizar sua primeira divergência → escolher a menor correção completa → demonstrar antes/depois → repetir.**

A interpretação semântica é uma alternativa a avaliar quando a falha demonstrar necessidade. Não é uma etapa obrigatória antes de corrigir calendário, reconhecimento de entidades, capacidade do plano, SQL ou apresentação.

Este plano substitui a abordagem de tentar evoluir todas as partes do
GenAI simultaneamente. A prioridade é trabalhar primeiro no que tem
maior potencial de melhorar a experiência real do usuário.

> **Regra de escopo:** não implementar uma capacidade apenas porque ela
> parece interessante. Primeiro demonstrar, com perguntas e traces, qual
> limitação ela resolve.

### Regras operacionais da versão 2.1

- Trabalhar em uma família de falhas por entrega, com pergunta original, intenção esperada, primeira divergência e caso de regressão.
- Limitar o diagnóstico inicial à amostra de 30–50 perguntas e a uma rodada dirigida da família escolhida. Os 46 casos atuais já atendem ao tamanho; não ampliar o conjunto só para adiar a correção.
- Reabrir investigação quando faltar referência numérica, a causa continuar incerta ou surgirem falhas novas. Registrar o motivo e a pergunta que a investigação precisa resolver.
- Definir critérios de sucesso antes da implementação; executar o mesmo conjunto antes/depois e acrescentar paráfrases ou casos de borda que não repitam a frase original.
- Encerrar cada entrega com comportamento observável corrigido no consumidor afetado. Para uma nova análise, verificar intenção, plano, execução, evidência e resposta; um esclarecimento melhor, sozinho, não conclui a capacidade analítica.
- Registrar a natureza da prova: planejamento, integração sintética ou Gold real/portal. Testes artificiais não encerram aceite de produto.
- A contagem de checkboxes é acompanhamento operacional. Relatar melhoria pelo comportamento corrigido, erros restantes e evidência reproduzível.

### Próxima entrega selecionada pelo diagnóstico

Priorizar o ranking temporal de faturamento (`P0-37`): “qual mês teve o maior faturamento entre janeiro e março de 2025?”. Hoje a pergunta é aceita como série mensal sem selecionar o maior mês. É um erro semântico silencioso demonstrado e a correção não depende de provar primeiro um fallback LLM.

- [ ] Fixar o caso atual e a intenção de escolher uma competência, distinguindo maior mês de maior classe/município no intervalo.
- [ ] Conferir contrato e consumidores e delimitar a operação mínima de ranking temporal.
- [ ] Implementar interpretação, plano, validação independente, execução ordenada antes do limite e apresentação da competência vencedora.
- [ ] Definir desempate, ausência de dados e cobertura antes de calcular o ranking.
- [ ] Comparar com uma referência independente sobre valores sintéticos controlados, incluindo empates, zero e lacunas.
- [ ] Validar paráfrases e regressões dos demais rankings e séries mensais.
- [ ] Registrar antes/depois, critérios aprovados e limites da integração, mantendo Gold real/portal pendentes sem prova.

Critério de sucesso desta entrega: devolver o mês e o faturamento corretos no intervalo solicitado, coincidentes com referência independente, preservando período, filtros, autorização e evidência. Se a capacidade ainda estiver ausente durante o desenvolvimento, o sistema deve reconhecê-la explicitamente, sem apresentar uma série como se respondesse ao máximo. Esse estado intermediário não conclui a entrega.

Em seguida, priorizar a distribuição por classe e os rankings sobre totais consolidados conforme a evidência já reunida. Os esclarecimentos incorretos de calendário/classe continuam registrados como correções delimitadas; a fila pode ser reordenada com justificativa de impacto ou dependência. Não há evidência de frequência real para declarar uma prioridade universal.

### Como ler as prioridades

-   **P0 --- Diagnóstico suficiente para decidir:** reproduzir e classificar a falha da entrega antes de alterá-la. O diagnóstico global pode continuar aberto enquanto uma família já compreendida é corrigida.
-   **P1 --- Maior retorno:** melhorias com impacto direto na
    compreensão e na capacidade de responder.
-   **P2 --- Evolução seguinte:** ampliar a cobertura depois de
    comprovar a primeira melhoria.
-   **Contínuo --- Qualidade e segurança:** controles que acompanham
    todas as entregas.

Os itens marcados `[x]` nesta versão foram executados e registrados nesta branch. Planos e testes anteriores não foram importados como estados concluídos.

------------------------------------------------------------------------

# 0. Princípios que não devem ser negociados

-   [ ] Preservar o Backend como executor exclusivo das consultas SQL da
    Gold.
-   [ ] Manter SQL parametrizado, papel de leitura restrito, autorização
    e validação independente dos planos.
-   [ ] Tratar o LLM como proponente de interpretação e planejamento,
    nunca como autoridade de acesso ou execução.
-   [ ] Não permitir SQL arbitrário gerado pelo modelo como fallback.
-   [ ] Manter números, unidades, agregações e cálculos vinculados a
    evidências verificáveis.
-   [ ] Separar fatos observados, hipóteses e afirmações causais.
-   [ ] Não remover controles de segurança sem reproduzir o problema,
    documentar o risco e adicionar testes.
-   [ ] Não confundir pergunta não suportada com pergunta não
    autorizada.
-   [ ] Não adotar arquitetura multiagente, novos frameworks ou novos
    serviços sem necessidade demonstrada.
-   [ ] Não reescrever componentes inteiros antes de medir a falha que
    justifica a mudança.
-   [ ] Toda mudança deve ter teste de regressão e evidência de
    validação.
-   [ ] Toda nova capacidade deve funcionar de ponta a ponta, não apenas
    no interpretador ou no planner.

## Classificação obrigatória das falhas

Ao investigar uma pergunta, identificar a primeira etapa em que o
resultado diverge do esperado:

-   [ ] **Interpretação / NLU:** a intenção, métrica, dimensão, período
    ou filtro não foi compreendido.
-   [ ] **Planejamento / capacidade:** a intenção foi compreendida, mas
    não pode ser representada pelo contrato ou pelas operações
    existentes.
-   [ ] **Dados / cobertura:** a operação é válida, mas faltam dados ou
    cobertura na Gold.
-   [ ] **Execução / integração:** o plano é válido, mas Backend, SQL,
    API, cache ou portal falhou.
-   [ ] **Síntese / apresentação:** as evidências estão corretas, mas a
    resposta não explica ou não responde adequadamente.
-   [ ] **Segurança / autorização:** a solicitação não pode ser
    executada por uma restrição real de acesso ou segurança.
-   [ ] **Política funcional / UX:** uma regra de interpretação, formato
    ou tratamento de capacidade bloqueia uma pergunta legítima.

Não classificar toda recusa como problema de guardrail nem toda resposta
ruim como problema de prompt.

------------------------------------------------------------------------

# 1. P0 --- Diagnóstico rápido e baseline reproduzível

**Estado: diagnóstico inicial consolidado; fechamento detalhado P0 em andamento.** Os cinco critérios de saída têm evidências no relatório de consolidação. As pendências históricas abaixo refletem etapas anteriores; os gates de produto, benchmark independente e medições indisponíveis não foram aprovados por este fechamento. Itens detalhados sem evidência continuam abertos para as próximas entregas, sem invalidar o alcance declarado do diagnóstico inicial.

**Objetivo:** descobrir quais problemas realmente mais prejudicam o
chatbot antes de começar uma refatoração.

## 1.1. Confirmar o estado do projeto

-   [x] Revisar os critérios IA-01 a IA-08 e ENT-01 do PRD.
-   [ ] Rastrear uma pergunta do portal até a resposta exibida. Rastreio estático concluído; jornada visual atual pendente.
-   [x] Identificar o interpretador determinístico e seus chamadores.
-   [x] Identificar quando a recuperação/interpretação semântica
    existente é acionada.
-   [x] Identificar o que o Gemini gera e o que o compositor monta
    deterministicamente.
-   [x] Confirmar branch, commit, working tree e alterações pendentes.
-   [x] Revisar contratos, ADRs e critérios de aceite vigentes.
-   [x] Confirmar quais partes da recuperação semântica já estão
    implementadas e efetivamente utilizadas.
-   [x] Verificar se a intenção semântica consegue chegar ao planner sem
    perda de filtros, período ou contexto.
-   [x] Desenhar o fluxo atual com entradas, saídas, contratos e pontos
    de decisão.
-   [x] Mapear diferenças entre o fluxo de chat e o fluxo de insights.

## 1.2. Criar um conjunto inicial de perguntas

Começar com uma amostra manejável de **30--50 perguntas**. Depois
ampliar para 50--100, conforme os primeiros resultados.

-   [x] Reunir perguntas reais que falharam, foram recusadas ou
    produziram respostas pouco úteis.
-   [x] Incluir perguntas simples que já funcionam, para detectar
    regressões.
-   [x] Criar paráfrases sem repetir os aliases e expressões do
    catálogo.
-   [x] Incluir linguagem coloquial, perguntas longas e erros naturais
    de escrita.
-   [x] Incluir perguntas com períodos explícitos e relativos.
-   [x] Incluir filtros, agrupamentos e rankings.
-   [x] Incluir perguntas com mais de uma métrica.
-   [x] Incluir perguntas analíticas complexas.
-   [x] Incluir acompanhamentos como "e no ano anterior?", "agora só
    Recife" e "quais foram os cinco maiores?".
-   [x] Incluir perguntas genuinamente ambíguas, que devem gerar
    esclarecimento.
-   [x] Incluir perguntas compreensíveis, mas ainda não suportadas.
-   [x] Incluir cenários sem dados ou sem cobertura temporal.
-   [x] Incluir perguntas que pedem explicações causais, para testar a
    distinção entre fato e hipótese.
-   [x] Sanitizar os exemplos e não incluir dados pessoais ou
    credenciais.


Evidências por checkbox: [conferência do diagnóstico](2026-11-05-genai-diagnostico-conferencia.md). O item de intenção semântica foi respondido como caminho quantitativo ausente na base atual; não declara integração de fallback. A seção 1.2 registra cobertura de perguntas, não aprovação das respostas.

### Formato mínimo de cada caso de teste

-   [x] Registrar pergunta original e contexto conversacional relevante.
-   [ ] Registrar intenção esperada.
-   [ ] Registrar métrica, dimensões, filtros, período, agregação e
    ordenação esperados.
-   [ ] Registrar resultado esperado: resposta, esclarecimento,
    capacidade não suportada, ausência de evidência ou não autorizado.
-   [ ] Para perguntas quantitativas, registrar uma consulta ou cálculo
    independente como referência.
-   [ ] Registrar a primeira etapa em que o sistema falhou e a evidência
    que demonstra isso.
-   [x] Separar perguntas de desenvolvimento de um conjunto reservado de
    perguntas inéditas.

## 1.3. Medir o comportamento atual

-   [x] Medir se a intenção foi compreendida corretamente. Captura da interpretação selecionada pelo planner: status/métrica/agrupamento quando anotados, 43/46, 6/7 e 0/2; não significa intenção inteira correta nem cobre operações não representáveis.
-   [x] Medir se os parâmetros extraídos estão corretos. Medido na saída HTTP para os campos anotados; cobertura por campo no relatório, sem atribuir acerto ao interpretador isolado.
-   [x] Medir se o plano representa a intenção. Comparação reproduzível com os oráculos de negócio dos três conjuntos; operações ausentes continuam divergentes.
-   [x] Medir se a consulta foi executada corretamente. Nova prova Linux/PostgreSQL 16: 1 teste integrado aprovado em 145,96 s, com acesso restrito, coordenação e auditoria; dados artificiais, não todo corpus.
-   [x] Medir se os números coincidem com a referência independente. Controle SQL independente na prova integrada e 14/14 casos de síntese artificial. Não há referência numérica real para todas as 55 perguntas.
-   [x] Medir quantas perguntas suportadas são recusadas indevidamente. Esclarecimentos indevidos nos controles de capacidade: 0/22, 1/5 e 2/2. Pedidos de operações ausentes separados; sem equiparar esclarecimento a recusa de segurança.
-   [x] Medir se os pedidos de esclarecimento são realmente necessários. Nos oráculos anotados: 20/20 e 2/2 com status esperado; motivo correto 18/20 e 0/2. Ver casos e limitações no relatório.
-   [x] Avaliar clareza, utilidade e naturalidade das respostas. Revisão qualitativa do agente das 18 mensagens existentes e revisão humana anterior de 24 cenários, identificadas separadamente. Seis planos sem texto final não foram avaliados como resposta numérica.
-   [x] Registrar latência, chamadas ao modelo, tokens, custo e erros do
    provedor, quando disponíveis. Rodada real de sete solicitações Gemini: quatro propostas válidas, três erros 503, 18.456 tokens retornados nas quatro chamadas com uso disponível. Custo nulo por preço não configurado; não presumir uso zero nas falhas.
-   [x] Registrar regressões em perguntas que já funcionavam. Zero novas divergências nos 53 casos comparáveis ao baseline; duas paráfrases novas ficam fora da comparação. Não constitui regressão SQL/portal completa.

### Critério de saída do P0

-   [x] Existe um conjunto de perguntas reproduzível.
-   [x] As falhas estão classificadas por etapa, não apenas por sintoma.
-   [x] As três maiores causas de insatisfação estão identificadas por
    frequência e impacto na amostra avaliada, sem extrapolar para produção.
-   [x] Existe uma linha de base para comparar as melhorias.
-   [x] A equipe consegue demonstrar por que a primeira mudança foi
    escolhida.

**Não iniciar uma grande refatoração sem evidência da sua necessidade. Uma correção delimitada pode avançar com diagnóstico suficiente da família afetada, mesmo com o P0 global aberto.**

------------------------------------------------------------------------

# 2. P1 --- Melhorar a compreensão semântica

**Objetivo:** permitir que o sistema compreenda a intenção mesmo quando
o usuário não utiliza exatamente os termos e formatos esperados pelo
catálogo.

Esta é uma das frentes com maior potencial de retorno perceptível.

## 2.1. Investigar o que já existe

-   [ ] Inspecionar a recuperação semântica e o interpretador existentes
    antes de criar outro mecanismo.
-   [ ] Verificar quando o caminho semântico é acionado e quando não é.
-   [ ] Conferir quais metadados do catálogo chegam ao modelo.
-   [ ] Conferir se as descrições incluem significado, unidade,
    agregação e restrições das métricas.
-   [ ] Conferir se dimensões, filtros e períodos são enviados com
    contexto suficiente.
-   [ ] Identificar se a saída semântica é descartada, reduzida ou
    sobrescrita por regras posteriores.
-   [ ] Comparar a intenção proposta pelo mecanismo semântico com a
    interpretação determinística.
-   [ ] Identificar se as falhas vêm da ausência de interpretação, da
    qualidade do contexto ou da integração com o planner.

## 2.2. Definir uma representação estruturada de intenção

-   [ ] Definir um objeto interno tipado para representar a intenção do
    usuário, separado do plano executável.
-   [ ] Representar tipo de pergunta, métricas, dimensões, filtros,
    período, agregação, comparação, ordenação e limite.
-   [ ] Representar campos ausentes e ambiguidades explicitamente.
-   [ ] Permitir que a interpretação solicite esclarecimento quando
    faltar informação essencial.
-   [ ] Usar somente IDs e operações existentes no catálogo.
-   [ ] Rejeitar campos extras, IDs inexistentes e tipos inválidos.
-   [ ] Não permitir que o modelo escolha tabelas físicas, permissões ou
    SQL.
-   [ ] Não tratar a confiança declarada pelo modelo como garantia de
    correção.

## 2.3. Testar primeiro em shadow mode

-   [ ] Executar a interpretação semântica em paralelo ao caminho atual,
    sem alterar a resposta enviada ao usuário.
-   [ ] Comparar a interpretação semântica com a determinística e com o
    rótulo esperado.
-   [ ] Registrar divergências e identificar qual interpretação estava
    correta.
-   [ ] Testar perguntas inéditas, paráfrases e perguntas longas.
-   [ ] Medir precisão, latência, custo e frequência de ambiguidades.
-   [ ] Verificar se o modelo inventa métricas, dimensões, períodos ou
    operações.
-   [ ] Verificar se o contexto fornecido é suficiente e está limitado
    ao necessário.
-   [ ] Testar prompt injection em pergunta, histórico, catálogo e
    evidências.
-   [ ] Documentar os casos em que o caminho semântico melhora, piora ou
    não altera o resultado.

## 2.4. Promover para fallback controlado

Somente depois de demonstrar melhora no shadow mode:

-   [ ] Manter o caminho determinístico para perguntas simples e
    inequívocas.
-   [ ] Acionar interpretação semântica quando o caminho determinístico
    falhar, ficar ambíguo ou não cobrir a formulação.
-   [ ] Validar a intenção proposta antes de encaminhá-la ao planner.
-   [ ] Pedir esclarecimento quando houver ambiguidade relevante.
-   [ ] Diferenciar intenção compreendida, capacidade não suportada e
    falta de dados.
-   [ ] Manter feature flag e possibilidade de rollback.
-   [ ] Comparar o comportamento novo com o baseline em perguntas
    inéditas.

### Critério de saída do P1

-   [ ] Paráfrases inéditas são interpretadas corretamente com melhora
    comprovada sobre o baseline.
-   [ ] Perguntas ambíguas geram esclarecimentos úteis.
-   [ ] IDs e operações inventados pelo modelo são rejeitados.
-   [ ] O interpretador semântico não amplia permissões nem contorna
    validações.
-   [ ] O custo e a latência estão dentro do orçamento definido.
-   [ ] O caminho determinístico continua funcionando sem regressões
    relevantes.

------------------------------------------------------------------------

# 3. P1 --- Entregar uma análise completa de ponta a ponta

**Objetivo:** provar que uma pergunta natural pode ser compreendida,
planejada, executada e respondida corretamente em um caso analítico de
valor real.

Em vez de ampliar muitos contratos ao mesmo tempo, escolher **uma
primeira capacidade vertical** com base no diagnóstico do P0.

Candidata já discutida: comparação de receita entre períodos por
município. Confirmar se é a melhor prioridade após avaliar as perguntas
reais.

## 3.1. Escolher a primeira capacidade

-   [ ] Selecionar a pergunta ou família de perguntas com maior impacto
    e viabilidade na Gold.
-   [ ] Confirmar que os dados e períodos necessários existem.
-   [ ] Definir exatamente a semântica da operação.
-   [ ] Definir o resultado esperado e uma referência independente.
-   [ ] Registrar o que fica fora do escopo da primeira entrega.

## 3.2. Implementar o fluxo completo

-   [ ] Interpretar a pergunta em linguagem natural.
-   [ ] Converter a intenção em plano lógico aprovado.
-   [ ] Validar catálogo, parâmetros, permissões e limites.
-   [ ] Executar exclusivamente pelo Backend.
-   [ ] Calcular diferenças absolutas e percentuais de forma
    determinística.
-   [ ] Definir comportamento para nulos, ausência de registros e
    denominador zero.
-   [ ] Aplicar agrupamento e ordenação sobre a granularidade correta.
-   [ ] Validar as evidências e preservar a proveniência.
-   [ ] Apresentar a resposta pelo portal com período, unidade e filtros
    utilizados.
-   [ ] Reconciliar os resultados com consulta independente na Gold.

## 3.3. Validar a capacidade

-   [ ] Testar a formulação original.
-   [ ] Testar pelo menos cinco paráfrases diferentes.
-   [ ] Testar períodos sem cobertura.
-   [ ] Testar empate, nulo, zero e denominador zero.
-   [ ] Testar pedido ambíguo e pedido fora da capacidade.
-   [ ] Testar usuário sem autorização.
-   [ ] Testar acompanhamento conversacional relacionado à análise.
-   [ ] Registrar resultado antes/depois.

### Critério de saída do P1

-   [ ] A capacidade funciona desde a pergunta no portal até a resposta
    final.
-   [ ] Os valores coincidem com a referência independente.
-   [ ] As paráfrases são compreendidas sem depender de uma frase fixa.
-   [ ] A execução continua autorizada, parametrizada e rastreável.
-   [ ] As limitações são explicadas sem inventar resultados.

------------------------------------------------------------------------

# 4. P1/P2 --- Melhorar a síntese e a experiência conversacional

**Objetivo:** fazer o Gemini participar de maneira mais útil da
explicação, sem transferir a ele a autoridade sobre os fatos numéricos.

## 4.1. Separar fatos de narrativa

-   [ ] Identificar quais partes da resposta são montadas
    deterministicamente.
-   [ ] Definir quais partes podem ser elaboradas pelo Gemini.
-   [ ] Manter valores, unidades, cálculos, filtros e períodos sob
    controle do Backend.
-   [ ] Fornecer ao modelo evidências identificáveis e contexto
    suficiente.
-   [ ] Exigir que afirmações quantitativas estejam vinculadas a
    evidências ou cálculos.
-   [ ] Impedir que a narrativa acrescente números ou fatos não
    presentes nas evidências.
-   [ ] Tratar evidências contraditórias ou insuficientes
    explicitamente.

## 4.2. Melhorar a resposta ao usuário

-   [ ] Começar com uma conclusão direta que responda à pergunta.
-   [ ] Explicar os principais resultados e diferenças relevantes.
-   [ ] Apresentar período, filtros, unidade e critério de ordenação.
-   [ ] Explicar limitações importantes sem excesso de mensagens
    genéricas.
-   [ ] Diferenciar observação, hipótese e causalidade comprovada.
-   [ ] Ajustar o nível de detalhe à complexidade da pergunta.
-   [ ] Oferecer próximos recortes úteis quando fizer sentido.
-   [ ] Melhorar mensagens de capacidade não suportada e ausência de
    evidência.
-   [ ] Testar respostas curtas, analíticas e conversacionais.
-   [ ] Verificar legibilidade de tabelas, números e percentuais no
    portal.

### Critério de saída

-   [ ] As respostas são mais claras e naturais que o baseline.
-   [ ] Todos os números podem ser rastreados até evidências.
-   [ ] O Gemini não inventa dados nem causalidade.
-   [ ] O usuário entende o que foi analisado, em qual período e com
    quais limitações.

------------------------------------------------------------------------

# 5. P2 --- Ampliar o planejamento analítico conforme a demanda

**Objetivo:** aumentar o conjunto de análises possíveis sem transformar
o planner em um mecanismo genérico e difícil de validar.

Só ampliar o contrato quando o benchmark mostrar que perguntas
importantes são compreendidas, mas não podem ser representadas.

## 5.1. Capacidades candidatas

-   [ ] Comparação entre períodos por município ou classe.
-   [ ] Ranking por total consolidado no período.
-   [ ] Ranking por maior crescimento ou queda absoluta.
-   [ ] Ranking por variação percentual.
-   [ ] Distribuição de faturamento por classe em um intervalo.
-   [ ] Múltiplas métricas na mesma pergunta.
-   [ ] Filtros numéricos, exclusões e condições sobre agregações,
    quando necessários.
-   [ ] Decomposição em subconsultas quando uma única operação não for
    suficiente.
-   [ ] Cálculos derivados entre resultados.
-   [ ] Explicações e análises exploratórias fundamentadas.

## 5.2. Regras para ampliar contratos

-   [ ] Implementar uma capacidade por vez.
-   [ ] Atualizar schemas, catálogo, validadores, executor, evidências e
    apresentação em conjunto.
-   [ ] Versionar contratos e verificar consumidores.
-   [ ] Definir operações de composição explicitamente permitidas.
-   [ ] Garantir que subplanos compartilhem publicação, escopo e filtros
    compatíveis.
-   [ ] Impor limites globais de consultas, linhas, bytes, tempo e
    custo.
-   [ ] Preservar proveniência dos cálculos derivados.
-   [ ] Definir comportamento para falha parcial.
-   [ ] Validar unidades, granularidade, agregação e universo antes de
    comparar métricas.
-   [ ] Diferenciar ranking por total, maior valor mensal e maior
    variação.
-   [ ] Não implementar junções livres ou SQL arbitrário como atalho.
-   [ ] Não introduzir um sistema multiagente sem uma necessidade
    comprovada.

### Critério de saída

-   [ ] Cada nova capacidade possui pergunta de referência, teste de
    regressão e validação independente.
-   [ ] O plano é validado integralmente antes da execução.
-   [ ] Resultados compostos são comparáveis e rastreáveis.
-   [ ] A ampliação não provoca regressões nas capacidades existentes.

------------------------------------------------------------------------

# 6. Contínuo --- Revisar guardrails sem enfraquecer segurança

**Objetivo:** identificar se alguma regra está bloqueando perguntas
legítimas, sem presumir que os guardrails sejam a causa principal.

## 6.1. Inventariar e classificar controles

-   [ ] Listar controles de autenticação, autorização, SQL, evidência,
    interpretação e formato de saída.
-   [ ] Classificar cada controle como segurança, capacidade,
    interpretação ou UX.
-   [ ] Registrar qual problema cada controle pretende resolver.
-   [ ] Identificar em qual etapa o controle atua.
-   [ ] Localizar regras duplicadas ou filtros lexicais que possam gerar
    falsos positivos.
-   [ ] Reproduzir cada bloqueio suspeito com uma pergunta legítima.
-   [ ] Diferenciar `unsupported_capability`, `no_evidence`,
    `ambiguous`, `unauthorized` e `provider_unavailable`.

## 6.2. Ajustar somente com evidência

-   [ ] Corrigir falsos positivos funcionais demonstrados.
-   [ ] Manter bloqueios reais de autorização e segurança.
-   [ ] Garantir que a segurança seja aplicada no Backend, não apenas no
    prompt.
-   [ ] Testar tentativas de ampliar escopo, ignorar permissões ou
    injetar instruções.
-   [ ] Comparar recusas indevidas antes/depois.
-   [ ] Registrar risco, justificativa, teste e possibilidade de
    rollback para cada alteração.

**Princípio:** fail closed para segurança; fail helpful para capacidades
não suportadas.

### Critério de saída

-   [ ] Perguntas legítimas deixam de ser bloqueadas por regras
    funcionais indevidas.
-   [ ] Perguntas não autorizadas continuam bloqueadas.
-   [ ] Não há aumento de execução indevida ou perda de proveniência.

------------------------------------------------------------------------

# 7. P2 --- Continuidade conversacional

-   [ ] Conferir herança de métrica, período e filtros.
-   [ ] Testar acompanhamentos temporais e mudanças de agrupamento.
-   [ ] Testar correções explícitas de recorte.
-   [ ] Testar mudança completa de assunto.
-   [ ] Garantir que correções curtas alterem apenas a dimensão
    indicada.
-   [ ] Garantir que perguntas novas não herdem filtros indevidos.
-   [ ] Revalidar autorização, catálogo e publicação em cada
    continuação.
-   [ ] Não reutilizar números antigos como se fossem dados atuais.
-   [ ] Testar expiração e adulteração de tokens de continuidade.
-   [ ] Testar retomada após falha de provedor.

### Critério de saída

-   [ ] O contexto melhora a conversa sem carregar filtros indevidos,
    ampliar permissões ou reutilizar dados desatualizados.

------------------------------------------------------------------------

# 8. P0/P1 --- Observabilidade mínima para todas as entregas

A observabilidade não deve virar um projeto paralelo. Implementar
primeiro os sinais necessários para diagnosticar e comparar as mudanças.

-   [ ] Correlacionar portal, Backend e GenAI por identificador de
    requisição.
-   [ ] Registrar a estratégia de interpretação selecionada.
-   [ ] Registrar a etapa e o motivo de esclarecimento, recusa ou falha.
-   [ ] Registrar divergência entre interpretação determinística e
    semântica.
-   [ ] Registrar a capacidade e a versão do plano selecionado.
-   [ ] Registrar versão do modelo, prompt e configuração relevante, sem
    segredos.
-   [ ] Registrar duração por etapa: interpretação, planejamento,
    validação, execução e síntese.
-   [ ] Registrar publicação, versão do catálogo e quantidade de
    evidências.
-   [ ] Registrar chamadas ao modelo, tentativas, tokens e custo quando
    disponíveis.
-   [ ] Sanitizar logs e impedir exposição de credenciais, dados
    privados ou SQL sensível.
-   [ ] Produzir um relatório simples com frequência e origem das
    falhas.

### Critério de saída

-   [ ] Uma pergunta problemática pode ser reconstruída por trace e
    classificada sem depender de suposição.
-   [ ] Os logs são úteis e respeitam privacidade e segurança.

------------------------------------------------------------------------

# 9. Critérios de qualidade e promoção

Definir limites quantitativos depois de obter o baseline. Não escolher
metas depois de ver os resultados.

## Métricas mínimas

-   [ ] Precisão de interpretação por categoria.
-   [ ] Precisão dos parâmetros extraídos.
-   [ ] Validade dos planos.
-   [ ] Percentual de perguntas suportadas respondidas corretamente.
-   [ ] Taxa de falsas recusas.
-   [ ] Precisão dos pedidos de esclarecimento.
-   [ ] Fundamentação das afirmações quantitativas.
-   [ ] Qualidade humana: clareza, utilidade e naturalidade.
-   [ ] Latência p50/p95.
-   [ ] Custo e consumo de tokens por pergunta.
-   [ ] Taxa de regressão em perguntas previamente suportadas.
-   [ ] Execuções não autorizadas --- meta obrigatória: zero.

## Gate antes de ativar uma mudança para usuários

-   [ ] Testes unitários, de contrato e integração aprovados.
-   [ ] Perguntas de referência aprovadas.
-   [ ] Conjunto reservado de perguntas inéditas aprovado.
-   [ ] Reconciliação numérica independente aprovada.
-   [ ] Testes de autorização e segurança aprovados.
-   [ ] Custo e latência dentro do orçamento.
-   [ ] Revisão humana da experiência aprovada.
-   [ ] Feature flag, rollout gradual e rollback disponíveis.
-   [ ] Limitações conhecidas documentadas.

------------------------------------------------------------------------

# 10. Sequência recomendada de PRs

Os números abaixo identificam tipos de entrega; não impõem uma fila serial. Escolha o próximo PR pela falha demonstrada e pelas dependências. PR 2 depende da evidência de PR 1; PR 3 e PR 5 podem avançar com diagnóstico suficiente da família, sem esperar interpretação semântica. PR 4 exige evidência correta disponível para explicar. PR 6 promove somente o escopo efetivamente validado.

## PR 0 --- Baseline e diagnóstico

-   [ ] Completar conjunto inicial de perguntas.
-   [ ] Registrar traces das perguntas representativas.
-   [ ] Classificar falhas e medir baseline.
-   [ ] Publicar relatório das maiores causas de insatisfação.

**Entrega:** sabemos onde o chatbot falha e qual problema deve ser
atacado primeiro.

## PR 1 --- Interpretação semântica em shadow mode

-   [ ] Inspecionar e reutilizar o mecanismo semântico já existente, se
    adequado.
-   [ ] Definir ou revisar a estrutura tipada de intenção.
-   [ ] Executar interpretação semântica em paralelo ao fluxo atual.
-   [ ] Comparar resultados com o conjunto de avaliação.
-   [ ] Medir qualidade, latência e custo.

**Entrega:** evidência de que a interpretação semântica melhora a
compreensão antes de influenciar a execução.

## PR 2 --- Fallback semântico controlado

-   [ ] Definir regras de roteamento entre caminho determinístico e
    semântico.
-   [ ] Validar a intenção antes do planner.
-   [ ] Tratar ambiguidades e capacidades não suportadas.
-   [ ] Ativar com feature flag e rollback.

**Entrega:** perguntas novas e paráfrases passam a ser compreendidas
melhor sem abrir mão dos controles.

## PR 3 --- Primeira análise ponta a ponta

-   [ ] Selecionar a capacidade de maior impacto e viabilidade na Gold.
-   [ ] Implementar intenção, plano, validação, execução, cálculo e
    resposta.
-   [ ] Reconciliar com consulta independente.
-   [ ] Testar formulações inéditas e casos de borda.

**Entrega:** uma análise de valor real funciona do início ao fim.

## PR 4 --- Síntese generativa fundamentada

-   [ ] Separar fatos calculados de narrativa.
-   [ ] Permitir explicação contextualizada pelo Gemini.
-   [ ] Validar referências e afirmações quantitativas.
-   [ ] Comparar respostas antes/depois com avaliação humana.

**Entrega:** respostas mais naturais sem perder precisão.

## PR 5 --- Próxima capacidade analítica

-   [ ] Escolher a próxima lacuna com base no benchmark.
-   [ ] Atualizar contratos e executor somente para essa capacidade.
-   [ ] Adicionar testes de regressão e referência independente.

**Entrega:** ampliação incremental e comprovada do que o agente consegue
analisar.

## PR 6 --- Estabilização e promoção

-   [ ] Executar a avaliação completa.
-   [ ] Confirmar segurança, qualidade, custo e latência.
-   [ ] Documentar resultados antes/depois.
-   [ ] Fazer rollout gradual e monitorar.

**Entrega:** versão evoluída, validada e reversível.

------------------------------------------------------------------------

# 11. Definition of Done por tarefa ou PR

-   [ ] O problema original está descrito com exemplo reproduzível.
-   [ ] A categoria da falha está identificada.
-   [ ] O comportamento esperado está documentado.
-   [ ] Existe teste de regressão para o caso original.
-   [ ] Existe pelo menos uma paráfrase ou caso de borda relevante.
-   [ ] Contratos e consumidores afetados foram revisados.
-   [ ] Controles de segurança continuam válidos.
-   [ ] Resultados numéricos foram reconciliados, quando aplicável.
-   [ ] Logs e métricas necessários estão disponíveis e sanitizados.
-   [ ] Testes foram executados e os resultados registrados.
-   [ ] Documentação e PRD foram atualizados com evidência.
-   [ ] Limitações restantes e plano de rollback estão registrados.

------------------------------------------------------------------------

# 12. O que não fazer nesta rodada

-   [ ] Não reescrever o interpretador inteiro antes de avaliar o
    mecanismo semântico existente.
-   [ ] Não criar um segundo interpretador sem entender o primeiro.
-   [ ] Não expandir o contrato para todas as operações imagináveis.
-   [ ] Não implementar múltiplas métricas e subplanos antes de uma
    primeira capacidade ponta a ponta.
-   [ ] Não transformar o projeto em multiagente por moda.
-   [ ] Não remover guardrails de segurança para aumentar a taxa de
    respostas.
-   [ ] Não tentar resolver toda a experiência com prompts maiores.
-   [ ] Não avaliar o chatbot apenas com perguntas conhecidas pelo
    desenvolvedor.
-   [ ] Não considerar sucesso o aumento de respostas se a precisão
    numérica ou a segurança piorarem.
-   [ ] Não iniciar várias frentes grandes em paralelo sem dependências
    e critérios de aceite claros.

------------------------------------------------------------------------

# 13. Resultado esperado

Ao final da evolução, o GenAI deve:

-   [ ] Compreender paráfrases e perguntas naturais inéditas dentro do
    domínio coberto.
-   [ ] Reconhecer quando uma pergunta é ambígua e solicitar
    esclarecimento útil.
-   [ ] Distinguir capacidade não suportada de ausência de dados e falta
    de autorização.
-   [ ] Planejar operações analíticas autorizadas com base na intenção
    do usuário.
-   [ ] Decompor análises em etapas quando houver capacidade
    implementada para isso.
-   [ ] Executar consultas exclusivamente pelo Backend.
-   [ ] Produzir cálculos verificáveis e respostas fundamentadas.
-   [ ] Explicar resultados com naturalidade, contexto e limitações.
-   [ ] Preservar segurança, proveniência, desempenho e custo aceitável.
-   [ ] Demonstrar melhora por comparação com baseline e perguntas
    inéditas.

## Princípio final

**Flexibilidade para compreender, planejar e explicar. Rigor para
autorizar, executar e comprovar.**

O objetivo não é fazer o agente responder qualquer coisa. É fazer com
que ele consiga responder muito mais perguntas legítimas, de maneira
útil e confiável, dentro das capacidades reais dos dados e do sistema.



## Execução do TODO 2 nesta branch

Esta branch foi criada limpa a partir de `origin/main`. Nenhuma implementação ou estado de conclusão da comparação municipal foi carregado. A amostra P0 de 46 casos foi executada nesta base: 40 conformes e seis divergentes. As quatro skills GenAI foram mantidas a pedido da pessoa usuária. Os TODOs continuam locais e fora de commits.


### Avanço P0 — síntese e cobertura anual

- [x] Executar o avaliador de síntese numérica existente: 14/14 casos com agregados artificiais.
- [x] Medir duração da execução sintética e declarar seu alcance, sem atribuir custo/latência de produção.
- [x] Investigar quatro perguntas com 12 competências artificiais completas, separando cobertura, interpretação e capacidade.
- [x] Quantificar as três famílias divergentes dentro da amostra e justificar a prioridade pelo impacto.
- [x] Auditar critérios de saída e corrigir a informação de que o holdout antigo estaria intocado.

P0 não concluído: dependências e estados específicos constam no relatório de diagnóstico. O holdout antigo foi executado na regressão do avaliador e não pode ser apresentado como reserva inédita. Perguntas reais adicionais foram solicitadas; não inferir aprovação ou dados a partir do tempo sem resposta.


### P0 — incorporação dos relatos reais

- [x] Registrar dois exemplos de falha relatados pela pessoa usuária, sem dados pessoais.
- [x] Confirmar o significado de “setores” no exemplo e preservar a confirmação no caso conversacional.
- [x] Avaliar dois originais, quatro controles e uma continuação com cobertura artificial suficiente: 4/7 conformes, três divergentes.

Evidências no relatório de diagnóstico e em `gold_p0_user_reported.json`. O relato indica inflexibilidade, mas não traz denominador para frequência real. A tarefa de obter exemplos iniciais foi atendida; representatividade e avaliação de SQL/provedor/experiência continuam abertas. Nenhum desses sete casos é reserva inédita.


### P0 — rastreio de composição

Fluxo quantitativo, papel do modelo, recuperação lexical e diferenças chat/insights documentados no diagnóstico com os símbolos reais. Essa inspeção não aprova um fallback semântico novo. Integração PostgreSQL descartável concluída: 1 teste passou em 205,42 s, com controle SQL independente; consultar o diagnóstico para alcance e limites.


### P0 — execução SQL comprovada

- [x] Executar a integração autenticada existente em PostgreSQL 16 descartável com papel restrito, controle SQL independente e auditoria: 1 passou em 205,42 s.
- [x] Registrar valores de referência e limites da prova sintética e remover o container temporário.

A prova vale para os cenários do teste integrado; não encerra aceite Gold real ou portal e não valida operações ainda ausentes. P0 permanece aberto pelas pendências explícitas do diagnóstico (reserva inédita e avaliação humana/ambiente real).


### P0 — revisão humana baseada no case

- [x] Ler o case fornecido e preparar 24 perguntas autorais plausíveis para seus públicos, com intenção esperada e contexto quando aplicável.
- [x] Executar os 24 casos pelo planejamento interno e preparar as mensagens e planos para revisão humana no chat.
- [x] Receber e registrar a avaliação humana dos retornos apresentados (24 avaliados; CASE-16 sem decisão de negócio).

18 esclarecimentos e seis planos, sem taxa de acerto presumida. Artefato local de revisão: `2026-11-05-genai-p0-revisao-humana.md`. Os exemplos executados são desenvolvimento/revisão, não reserva inédita. O TODO continua local.


### P0 — critérios de negócio confirmados

Avaliação humana registrada na fixture, no pacote de revisão e em `genai-p0-human-review.json`. Valores/tabelas, resolução de análises válidas, resposta parcial, continuidade e limites claros passam a orientar os critérios das próximas entregas. CASE-16 permanece pendente da lógica de negócio. A avaliação não comprova números reais nem encerra automaticamente o P0; a reserva inédita independente continua pendente.


### Conferência dos critérios de saída após revisão humana

Os critérios de conjunto reproduzível, classificação por etapa e linha de base foram sincronizados com as evidências já registradas. Faltam consolidar as causas/prioridades com a avaliação humana recebida, registrar a primeira entrega escolhida à luz desse retorno e separar uma reserva inédita para avaliação futura. A decisão de negócio do CASE-16 continua própria desse caso e não bloqueia todas as demais correções. Prova Gold/Gemini/portal real continua como gate posterior de integração e qualidade, sem ser confundida com aprovação do diagnóstico inicial.


## Consolidação aprovada — 05/11/2026

A pessoa usuária concordou com os grupos de critérios e com o significado de interpretação. Evidências e prioridade consolidadas em [consolidação P0](2026-11-05-genai-p0-consolidacao.md).

- [x] Consolidar avaliações humanas, causas e critérios de aceite sem confundir aprovação de plano com correção numérica.
- [x] Separar 12 perguntas novas não executadas para avaliação futura; reserva autoral, sem alegar autoria independente ou teste cego.
- [x] Registrar baseline, limitações e justificativa da primeira entrega após a avaliação humana.

A prioridade inicial de implementar isoladamente o ranking temporal foi revista: a próxima entrega avalia interpretação quantitativa em shadow mode para faturamento/tempo/agrupamento/ranking; o máximo mensal permanece na regressão e na expansão analítica. A promoção ao fluxo executável depende dos resultados. O diagnóstico inicial está consolidado; gates de produto e avaliação independente permanecem próprios das próximas entregas. A contagem de itens não é taxa de qualidade.


### Fechamento P0 — diagnóstico inicial

Os cinco critérios de saída foram atendidos no alcance declarado: conjunto reproduzível; classificação por primeira divergência; causas por frequência na amostra e impacto confirmado pela avaliação humana; baseline; e justificativa da primeira entrega. Evidência: `2026-11-05-genai-p0-consolidacao.md`, relatórios e fixtures referenciados. A reserva autoral de 12 perguntas está separada e não foi executada. A pessoa usuária confirmou os critérios de negócio no chat.

Este fechamento não aprova qualidade numérica global, Gold/Gemini/portal reais, benchmark cego independente ou operações ainda não implementadas. O caso de negócio 16 permanece aberto. Não altera os estados de aceite IA do PRD e não indica melhora de código de produção. Próxima etapa: avaliação da interpretação quantitativa em modo de observação, com os critérios já fixados.

### P1 — preparação e primeira prova Gemini

- [x] Provar conexão e aceitação do schema tipado pelo Gemini real.
- [x] Incluir cobertura temporal e valores públicos do catálogo no contexto.
- [x] Validar contexto de acesso antes de chamar o provedor e excluir metadados pessoais.
- [x] Criar runner reproduzível `python -m tests.semantic_provider_probe` com histórico e cobertura da fixture.
- [ ] Comparar semanticamente todos os slots contra rótulos independentes e baseline.
- [ ] Validar filtros propostos; atualmente continuam rejeitados.
- [ ] Integrar observação ao consumidor, definir orçamento, avaliar reserva e promover fallback somente após aprovação dos gates.

Última execução: sete casos de desenvolvimento; cinco contratos válidos e dois erros HTTP 503. Contrato válido não significa intenção correta: REAL-01 inferiu maior a partir de maio e precisa ser avaliado contra a confirmação exigida. REAL-02C preservou receita/janeiro de 2024/classe após envio do histórico correto. Relatório local `ai-agent/reports/genai-semantic-probe.json`. Ruff passou; três testes do observador passaram. Sem aceite Gold, mudança do fluxo produtivo ou conclusão da P1. A rodada anterior do probe omitia contexto/cobertura; foi corrigida e não serve como comparação de qualidade.

### Retomada do fechamento detalhado do diagnóstico

Branch de conferência: `feat/genai-diagnostico-final`, worktree `work/genai-diagnostico-final`. Baseline reexecutado: 40/46 e 4/7, preservando divergências. Conferência e pendências em `2026-11-05-genai-diagnostico-conferencia.md`. O fechamento anterior refere-se ao diagnóstico inicial; os checkboxes detalhados ainda precisam ser reconciliados com evidências. P0 ampliado permanece aberto. Não há requisito de produto concluído nesta conferência.

### Rodada — conferência dos oráculos (05/11/2026)

- [x] Auditar presença de métrica, período e filtros nas 55 perguntas de planejamento (46 + sete + duas, denominadores separados).
- [x] Completar janela janeiro–março/2025 nos quatro casos P0-35/36/37/38 e ausência explícita de filtros em nove expectativas, derivadas das perguntas.
- [x] Reexecutar os três conjuntos com os oráculos mais fortes: 40/46, 4/7 e 0/2. A contagem de conformidade não mudou; isso não representa melhoria do chatbot.
- [ ] Completar referência numérica independente por família quantitativa; fixtures de planejamento não substituem SQL.
- [ ] Conferir ordenação, limite, agregação, intenção e primeira divergência de todos os oráculos.
- [ ] Concluir métricas da seção 1.3 e jornada visual atual.

Evidências: `ai-agent/reports/genai-p0-oracle-audit.json` registra a fotografia anterior à correção (quatro janelas e nove filtros ausentes); `genai-p0-oracles-recheck.json` registra a nova execução. Versões das duas fixtures receberam sufixo `-oracle-audit-1`; o relatório anterior permanece separado. O P0 segue aberto. Ao fim de cada rodada, atualizar este arquivo e apresentar seu link no chat.


### Rodada — tentativa visual e conferência de formato/medição

- [x] Conferir os sete itens do formato mínimo e os dez itens da seção 1.3, registrando evidências e alcance individual na conferência do diagnóstico.
- [x] Medir plano esperado versus esclarecimento: 3/46, 1/7 e 2/2; não apresentar como taxa de recusa de segurança.
- [ ] Executar jornada visual: ferramenta interrompeu o controle porque Firefox não suporta política de URLs neste ambiente. Precisa de navegador suportado.

Pergunta/contexto e separação de reserva foram marcados com evidências; os demais itens listados continuam abertos por cobertura parcial. Stack compilada nesta rodada; banco e GenAI saudáveis no último resultado observado, loader em andamento. Não houve pergunta exibida validada. [Abrir detalhes da conferência](2026-11-05-genai-diagnostico-conferencia.md).


### Rodada executada — runner de medições P0

- [x] Implementar e executar `python -m tests.p0_measurements` em `ai-agent`.
- [x] Registrar por caso pergunta/contexto, expectativa, saída observada, mensagem, checks e primeira fronteira observável de divergência.
- [x] Medir por campo e por conjunto sem misturar denominadores: 40/46, 4/7 e 0/2 conformes.
- [x] Reexecutar síntese numérica artificial: 14/14; gate do runner falha se houver erro de avaliação ou falha numérica. Divergências conhecidas de planejamento permanecem contadas e visíveis.
- [x] Registrar p50/p95 de planejamento local e ausência de tokens/custo reais; nenhuma chamada externa.
- [x] Ruff do runner passou.

Relatório: `ai-agent/reports/genai-p0-measurements.json`. As latências incluem montagem de fixtures e não são produção. `first_observed_divergence=planning_http` indica fronteira observável; a causa interna não é inferida apenas do status. A reserva continua sem execução. Intenção interna isolada, referências SQL para todo corpus e classificação de capacidade versus esclarecimento continuam pendentes. Backend saudável e frontend iniciados após o build; jornada visual segue pendente por Firefox não suportado pela ferramenta. P0 completo permanece aberto.


### Rodada — consolidação na branch P1 e medições pendentes

- [x] Reunir os arquivos de diagnóstico na `feat/genai-interpretacao`, preservando alterações P1 e configurações locais.
- [x] Capturar a intenção selecionada pelo planner em execução HTTP real de teste; conferir campos anotados e explicitar os limites de operações não representáveis.
- [x] Separar capacidades ausentes de esclarecimentos indevidos e conferir motivo dos esclarecimentos esperados.
- [x] Comparar 53 casos com baseline: zero regressões novas; dois casos novos divergentes.
- [x] Revisar qualitativamente 18 mensagens de esclarecimento sem atribuir texto aos seis casos com somente plano.
- [x] Medir sete solicitações Gemini com uma tentativa por chamada, tokens disponíveis, latência e erros; custo permanece indisponível.
- [ ] Repetir prova SQL: tentativa Windows interrompida sem resultado; execução Linux no PostgreSQL descartável em andamento nesta rodada. Não marcar como passada antes do término.

Evidências: `genai-p0-measurements.json`, `genai-p0-language-review.json`, `genai-semantic-probe.json`, em `ai-agent/reports`. TODO continua local. A branch separada de diagnóstico não é mais o roteiro ativo.


### Fechamento da rodada — SQL independente repetido

- [x] Repetir a integração autenticada em PostgreSQL 16 descartável limpo: 1 passou em 145,96 s, com aviso preexistente de Starlette/httpx.
- [x] Registrar referência independente e alcance em `ai-agent/reports/genai-p0-sql-recheck.json`; JUnit privado em `work/p0-sql-linux-result.xml`.
- [x] Encerrar/remover o container descartável após a prova; banco do portal preservado.

Todos os dez itens de medição da seção 1.3 têm agora evidência no alcance explicitado por item. Isso não conclui todas as capacidades de produto nem o P0 inteiro: ainda faltam uniformização completa dos oráculos e referências por pergunta quantitativa, além da jornada visual impedida pela ferramenta. Não apresentar revisão de 18 esclarecimentos como avaliação de seis respostas finais ausentes, nem 1 teste SQL como 55 consultas reconciliadas.
