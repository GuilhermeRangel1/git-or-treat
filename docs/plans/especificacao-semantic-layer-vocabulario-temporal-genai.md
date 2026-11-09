# Especificação de Semantic Layer, Vocabulário de Negócio e Interpretação Temporal do GenAI

**Projeto:** V-Energy Grid 360\
**Repositório de referência:** `GuilhermeRangel1/git-or-treat`\
**Vinculado a:** TODO 3 --- Migração do GenAI para Text-to-SQL
Generativo\
**Escopo funcional:** vocabulário do negócio, interpretação de linguagem
natural, regras temporais, cobertura Gold/F1, geração SQL e respostas
fundamentadas\
**Última competência confirmada da base:** `2026-06`\
**Versão:** 1.1 --- ajuste da resolução contextual de "volume"\
**Status:** especificação de implementação e validação --- decisões
físicas devem ser conferidas no repositório antes de codificar

------------------------------------------------------------------------

# 0. Instruções ao agente de desenvolvimento

Este documento deve orientar uma evolução completa do GenAI. Não trate o
trabalho como uma simples alteração de prompt ou como a inclusão de uma
lista de sinônimos.

O objetivo é fazer o agente compreender perguntas naturais e coloquiais
sobre a V-Energy, identificar corretamente métricas, dimensões, filtros
e períodos, reconhecer o que está ou não disponível na Gold e produzir
consultas e respostas somente quando houver capacidade e evidência
suficientes.

## 0.1. Resultado esperado

Ao final da implementação, o usuário deve conseguir perguntar de
diferentes maneiras sobre o mesmo conceito sem precisar reproduzir o
nome técnico da coluna ou uma frase previamente cadastrada.

Exemplo de paráfrases e formulações próximas:

-   "Qual foi o consumo residencial?"
-   "Quanto de energia as casas consumiram?"
-   "Qual foi o volume residencial?"
-   "Como ficou o consumo das unidades residenciais?"
-   "O volume caiu em quais bairros?"

Essas frases podem expressar intenções semelhantes, mas não devem ser
forçadas para a mesma métrica apenas por compartilharem palavras. O
agente deve identificar o contexto e resolver cada expressão para o
conceito canônico correto. Em particular, "volume residencial" exige
atenção ao contexto: no diagnóstico comercial de Henrique, a leitura
prioritária é volume de energia faturada; em uma conversa explicitamente
sobre consumo medido, a leitura pode ser consumo residencial.

Isso **não** significa que todas as perguntas devam ser executadas. O
sistema deve distinguir:

1.  Entendeu o que o usuário quis dizer.
2.  Encontrou uma métrica correspondente e validada.
3.  A métrica está publicada e coberta.
4.  A capacidade está habilitada na versão do Text-to-SQL.
5.  A consulta é segura e semanticamente válida.
6.  Os dados permitem responder.

## 0.2. Ordem obrigatória antes de alterar código

Antes de implementar:

1.  Ler o `TODO_3_Text_to_SQL_Generativo.md` e preservar suas fases e
    decisões arquiteturais.
2.  Ler o `PRD.md` e identificar os requisitos relacionados ao GenAI.
3.  Ler o dicionário Gold vigente (`dicionario_gold.md`).
4.  Ler o catálogo Gold vigente (`gold-catalog.md`).
5.  Ler o documento de implementação por domínio
    (`contracts/genai-domain-implementation.md`).
6.  Ler o levantamento de cobertura (`gold-coverage-v0.md`).
7.  Ler os contratos e ADRs relacionados a consultas, janelas temporais,
    execução, auditoria, follow-up, publicação e autorização.
8.  Inspecionar o código real, os testes e o estado da branch antes de
    propor alterações.
9.  Comparar documentação, catálogo, banco publicado e código. Registrar
    divergências.
10. Só então decidir quais componentes serão reaproveitados, adaptados,
    substituídos ou criados.

Se algum arquivo não existir no checkout, procurar sua localização real.
Não inventar conteúdo, caminho, coluna, tabela, relacionamento ou
comportamento ausente.

**Não considerar este documento uma autorização para alterar a Gold.** O
escopo principal é o GenAI e seus contratos. Alterações na modelagem
Gold exigem evidência, justificativa e revisão próprias.

## 0.3. Proteção do trabalho existente

-   Conferir `git status`, branch atual e diferenças locais.
-   Não descartar alterações não commitadas.
-   Não reescrever histórico, resetar branches ou apagar arquivos sem
    autorização explícita.
-   Não substituir componentes existentes antes de mapear seus
    consumidores.
-   Não remover o fluxo anterior antes de comprovar a migração, a
    regressão e o rollback.
-   Não marcar tarefas como concluídas sem teste ou evidência
    reproduzível.
-   Não afirmar que a implementação foi validada se os testes não foram
    executados.

## 0.4. Fonte de verdade e precedência

Em caso de divergência, seguir esta ordem:

1.  Contratos e decisões técnicas aprovados e vigentes.
2.  Dicionário Gold e catálogo físico efetivamente publicados.
3.  PRD e requisitos de negócio do case.
4.  Este documento, como proposta de comportamento e orientação de
    implementação.
5.  Inferências do modelo.

Este documento não deve sobrepor uma definição aprovada da Gold. Se uma
regra aqui sugerida conflitar com a fonte oficial, registrar a
divergência e solicitar decisão, em vez de escolher silenciosamente.

------------------------------------------------------------------------

# 1. Princípios que não podem ser violados

1.  **Flexibilidade na linguagem; rigor na semântica.** O usuário não
    precisa conhecer os nomes físicos das colunas.
2.  **Uma métrica canônica por conceito validado.** Sinônimos diferentes
    podem apontar para o mesmo ID semântico, mas métricas diferentes não
    podem ser fundidas.
3.  **Entendimento não é capacidade.** O agente pode entender uma
    pergunta e ainda assim informar que a F1 não executa aquela análise.
4.  **Gold não é sinônimo de F1.** Uma coluna existir na Gold ou ser
    usada por outro fluxo não significa que esteja liberada no
    Text-to-SQL F1.
5.  **Tempo deve ser resolvido antes da geração SQL.** O modelo não deve
    inventar datas nem usar a data do computador como referência dos
    dados.
6.  **Métrica, unidade, granularidade e população devem ser
    compatíveis.**
7.  **O LLM propõe; código determinístico valida.** O modelo não escolhe
    permissões, não amplia escopo e não executa SQL.
8.  **Nenhuma substituição silenciosa de métrica.** Consumo medido não
    substitui energia faturada; receita faturada não substitui
    arrecadação.
9.  **Ausência, zero, nulo, falta de cobertura e falta de capacidade são
    estados diferentes.**
10. **Respostas quantitativas precisam ser reproduzíveis.** Valores e
    percentuais devem vir do SQL ou de cálculos determinísticos
    validados.
11. **Toda comparação deve declarar os períodos.**
12. **Não afirmar causalidade sem evidência.** Uma variação observada
    não prova sua causa.
13. **Não adicionar sinônimos isolados para mascarar limitações
    estruturais.** A solução deve operar sobre conceitos, regras e
    capacidades, não sobre frases decoradas.
14. **Não liberar novos domínios ou operações apenas porque o LLM
    consegue gerar SQL para eles.** A expansão exige validação ponta a
    ponta.

------------------------------------------------------------------------

# 2. Escopo da F1 e cobertura por domínio

## 2.1. Distinção importante

Neste documento, **F1** significa a primeira versão/fatia do
Text-to-SQL. Não significa Fase 1 do TODO 3.

A cobertura executável da F1 está restrita ao domínio de
**faturamento**, conforme a delimitação informada para o projeto.

O vocabulário do negócio pode ser mais amplo do que a F1. O agente deve
conseguir reconhecer termos de consumo, interrupções, atendimento, GD e
outros domínios para classificá-los corretamente, mas não deve executar
consultas fora da capacidade publicada e aprovada da F1.

## 2.2. Estados de cobertura obrigatórios

Cada métrica, dimensão, operação e domínio deve possuir um estado
explícito:

  ---------------------------------------------------------------------------
  Estado                     Significado                Comportamento
  -------------------------- -------------------------- ---------------------
  `SUPPORTED`                Existe na Gold, está no    Pode executar
                             catálogo da F1, tem
                             consulta autorizada,
                             validação e teste ponta a
                             ponta

  `PARTIAL`                  Existe apenas com          Explicar o limite;
                             recortes, períodos,        executar somente a
                             dimensões ou regras        parte validada
                             limitadas

  `OUT_OF_SCOPE`             O conceito pode existir no Reconhecer e informar
                             projeto, mas não está      que ainda não é
                             habilitado na F1           consultável nesta
                                                        versão

  `UNSUPPORTED`              Não existe                 Não inventar
                             métrica/capacidade         substituto
                             comprovada para responder

  `CLARIFICATION_REQUIRED`   Mais de uma interpretação  Fazer uma pergunta
                             relevante é possível       objetiva

  `DATA_UNAVAILABLE`         A capacidade existe, mas a Informar a
                             publicação/período/dados   indisponibilidade
                             necessários não estão
                             disponíveis

  `UNAUTHORIZED`             A solicitação não está     Recusar sem revelar
                             autorizada para o usuário  dados
  ---------------------------------------------------------------------------

Não confundir `OUT_OF_SCOPE` com `UNSUPPORTED`: o primeiro é uma
limitação de versão; o segundo é ausência de suporte comprovado nos
dados ou na implementação.

## 2.3. Regra de promoção para `SUPPORTED`

Uma capacidade só pode receber `SUPPORTED` quando todos os itens forem
verdadeiros:

-   A métrica ou dimensão está definida no dicionário.
-   A coluna/tabela física existe na publicação usada pela aplicação.
-   A granularidade é conhecida.
-   A coluna temporal é conhecida.
-   A agregação é válida.
-   Os filtros e dimensões são compatíveis.
-   Os relacionamentos necessários estão aprovados.
-   A capacidade está liberada no contrato da F1.
-   O validador consegue verificar seu uso.
-   Existe consulta de referência independente.
-   O resultado foi reconciliado na mesma publicação Gold.
-   A resposta pública apresenta período, unidade e limitações.

A presença de um campo no banco, isoladamente, não satisfaz esses
critérios.

## 2.4. Primeira fatia

A primeira fatia deve permanecer restrita ao faturamento e às
métricas/dimensões explicitamente aprovadas no contrato de domínio da
F1.

O agente deve consultar `genai-domain-implementation.md` e o catálogo
efetivo para descobrir a lista real. Não presumir que toda métrica
citada neste documento esteja habilitada.

O vocabulário fora da F1 pode ser mantido no catálogo com status
`OUT_OF_SCOPE`, para que o agente reconheça a intenção e responda
corretamente sem tentar executar SQL.

Exemplo de resposta fora do escopo:

> Entendi que você quer analisar interrupções de energia. Essa análise
> pertence ao domínio de continuidade da rede, que ainda não está
> habilitado no Text-to-SQL F1. Posso consultar as métricas de
> faturamento disponíveis nesta versão.

------------------------------------------------------------------------

# 3. Modelo de vocabulário: linguagem natural → conceito canônico

## 3.1. Como interpretar termos convencionais

O agente deve reconhecer:

-   Sinônimos e paráfrases.
-   Singular e plural.
-   Variações de gênero.
-   Acentos e ausência de acentos.
-   Diferenças de maiúsculas/minúsculas.
-   Pontuação e pequenas variações de escrita.
-   Abreviações conhecidas do domínio.
-   Expressões coloquiais.
-   Perguntas incompletas que dependem do contexto anterior.

A normalização textual ajuda a recuperar candidatos, mas não decide
sozinha o significado. A decisão deve considerar o contexto completo da
frase, a métrica solicitada, os filtros e o histórico relevante.

Exemplo: "volume" pode indicar uma quantidade, mas, no domínio de
energia, não determina sozinho se a medida é consumo medido ou energia
faturada. "Volume de receita" também não deve ser fundido com volume em
kWh: pode ser uma formulação imprecisa para valor monetário faturado e
deve ser resolvida pelo contexto ou esclarecida.

### Regra comum para todos os domínios

Resolva o conceito pela pergunta, pelos turnos recentes e pelos filtros
ativos. Preserve qualificadores explícitos e aplique os padrões
documentados. Peça esclarecimento apenas quando uma escolha ainda aberta
mudar a resposta. Reconhecer um termo permite explicar o limite da
capacidade quando a consulta estiver fora do escopo.

  -----------------------------------------------------------------------
  Formulação cotidiana                Leitura esperada
  ----------------------------------- -----------------------------------
  Quanto as casas consumiram?         Consumo medido em kWh, classe
                                      residencial.

  Quanto deu a conta de luz?          Valor faturado quando a conversa
                                      trata do valor da fatura. Se o
                                      contexto permitir valor pago ou
                                      consumo, esclarecer.

  Quanto entrou de pagamento?         Arrecadação. Exige evidência de
                                      pagamento.

  Quanto custou o kWh em média?       Preço médio efetivo, com população
                                      e período comparáveis. "Tarifa
                                      homologada" pede a medida
                                      regulatória.

  Quantas unidades com painel solar?  Identificar a população solar. Usar
                                      GD como aproximação somente se a
                                      definição aprovada permitir e
                                      explicitar isso.

  Quantas vezes a luz caiu?           Contar ocorrências no recorte,
                                      quando houver cobertura. DEC e FEC
                                      mantêm suas definições próprias.

  Quanto tempo ficou sem luz?         Duração da interrupção no recorte
                                      solicitado.

  Quantos chamados abriram?           Contar protocolos. "Reclamações"
                                      exige categoria de reclamação
                                      validada.

  Como o pessoal avaliou o            Satisfação a partir das notas
  atendimento?                        válidas.

  E no comercial?                     Trocar para classe comercial e
                                      preservar métrica, período e demais
                                      filtros compatíveis.
  -----------------------------------------------------------------------

Na avaliação, use paráfrases inéditas de cada domínio, casos em que o
contexto resolve o termo e casos em que uma distinção explícita muda a
métrica. Verifique conceito, unidade, filtros, período e estado de
cobertura. Para operações habilitadas, confira o resultado com uma
referência independente. Para operações fora da F1, confira que o agente
explica o limite sem executar uma consulta substituta.

## 3.2. Regra específica para "volume"

O termo "volume" não deve possuir um mapeamento universal para uma única
métrica. No domínio de energia, ele indica uma quantidade, mas não
determina sozinho se essa quantidade representa consumo medido, energia
efetivamente faturada ou outra medida. A interpretação deve considerar a
pergunta completa, os qualificadores, o contexto analítico e a métrica
já estabelecida na conversa.

Regras de resolução:

1.  **Qualificador explícito prevalece.** "Volume consumido" aponta para
    consumo medido/apurado em kWh, se essa métrica estiver validada.
    "Volume faturado" ou "volume de energia faturada" aponta para
    energia efetivamente faturada em kWh, se houver medida específica.
2.  **Contexto conversacional prevalece sobre um alias genérico.** Se a
    conversa já está analisando consumo medido, "e o volume por bairro?"
    deve preservar essa métrica. Se está analisando energia faturada,
    deve preservar a métrica faturada.
3.  **Contexto original de Henrique.** Na pergunta "Qual bairro mais
    perdeu volume residencial no último ano?", o contexto é o
    diagnóstico comercial em que Henrique descreve a queda do volume de
    energia faturada e a compara com a receita. Portanto, a
    interpretação prioritária proposta é volume de energia faturada da
    classe residencial, desde que exista uma métrica específica,
    publicada e autorizada. Essa associação é uma inferência contextual
    a partir do encadeamento do case; o PDF não define uma coluna física
    nem comprova que a Gold disponibilize essa medida. Validar a
    interpretação com a definição de negócio e o catálogo. Não tratá-la
    como alias universal para toda ocorrência de "volume residencial".
4.  **Sem contexto suficiente.** Se "volume" puder apontar para consumo
    medido ou energia faturada e essa escolha alterar o resultado, pedir
    esclarecimento. Não escolher uma das métricas por conveniência.
5.  **Sem substituição silenciosa.** Se a métrica entendida não existir
    ou estiver fora da cobertura, informar a limitação. Não usar outra
    métrica parecida como substituta.

"Volume de chamados" pode indicar quantidade de protocolos, desde que
esse seja o conceito usado no contexto. "Volume de receita" é uma
formulação ambígua entre quantidade de energia e valor monetário; usar o
contexto ou perguntar. Na resposta, nomear a medida usada e informar a
unidade.

A mesma regra de interpretação contextual vale para paráfrases
convencionais. "Faltou luz", "queda de luz" e "apagão" apontam para
interrupções de fornecimento. "Quantas vezes faltou luz?" pede contagem
de ocorrências. "Por quanto tempo?" pede duração. Esclarecer quando a
pergunta deixar em aberto qual desses resultados ela quer. O termo
"apagão" por si só não define porte, causa ou número de unidades
afetadas.

  -----------------------------------------------------------------------
  Formulação              Interpretação proposta  Regra
  ----------------------- ----------------------- -----------------------
  "volume residencial"    Dependente do contexto; Não cadastrar como
                          no diagnóstico de       alias incondicional de
                          Henrique, volume de     consumo medido.
                          energia faturada        Confirmar a métrica
                          residencial             faturada na Gold e na
                                                  cobertura da versão.

  "volume por bairro"     Quantidade de energia   Herdar a métrica do
                          por bairro              contexto; sem contexto,
                                                  esclarecer se consumo
                                                  medido ou energia
                                                  faturada.

  "volume consumido"      Consumo de energia      Usar a métrica canônica
                          medido/apurado          de consumo validada, se
                                                  disponível e
                                                  autorizada.

  "volume faturado"       Energia efetivamente    Exigir medida
                          faturada em kWh         específica de energia
                                                  faturada.

  "volume de energia      Energia efetivamente    Não substituir
  faturada"               faturada em kWh         automaticamente por
                                                  consumo medido.

  "volume caiu"           Queda na quantidade     Herdar a métrica e o
                          associada à métrica em  período do contexto;
                          análise                 sem contexto
                                                  suficiente, esclarecer.

  "volume de chamados"    Quantidade de           Usar a definição de
                          protocolos/chamados     contagem aprovada para
                                                  atendimento.

  "volume de receita"     Expressão ambígua       Perguntar se a pessoa
                                                  quer valor monetário de
                                                  receita ou quantidade
                                                  de energia.
  -----------------------------------------------------------------------

**Mapeamento candidato informado no levantamento:** `consumo_total_kwh`
representa consumo medido e possui recortes de consumo por
bairro/classe. Confirmar essa definição e a disponibilidade no contrato
da F1 antes de liberar a consulta.

O agente nunca deve assumir que `consumo_total_kwh` prova o volume
efetivamente faturado.

## 3.3. Vocabulário de consumo e energia

  -----------------------------------------------------------------------
  Termos usados pelo      Conceito canônico       Regra de interpretação
  usuário                 candidato
  ----------------------- ----------------------- -----------------------
  consumo, energia        Consumo de energia      Identificar se a
  consumida, energia                              métrica é
  utilizada                                       medida/apurada ou
                                                  faturada

  volume, volume de       Quantidade de energia   Não mapear para uma
  energia                                         métrica fixa; resolver
                                                  entre consumo medido e
                                                  energia faturada pelo
                                                  contexto

  quantidade consumida,   Consumo medido/apurado  Usar a métrica canônica
  volume consumido                                de consumo validada

  consumo residencial     Consumo da classe       Aplicar classe
                          residencial             residencial conforme
                                                  catálogo

  volume residencial      Dependente do contexto  o diagnóstico de
                          N                       Henrique, priorizar
                                                  energia faturada
                                                  residencial; em outros
                                                  contextos, resolver ou
                                                  esclarecer

  consumo comercial       Consumo da classe       Não confundir com
                          comercial               receita comercial

  consumo industrial      Consumo da classe       Confirmar classificação
                          industrial              Gold

  energia faturada,       Energia faturada em kWh Exigir métrica de
  volume faturado                                 faturamento de energia
                                                  específica

  consumo medido, consumo Energia registrada pela Não chamar de energia
  apurado                 medição                 faturada

  gasto de energia, gasto Ambíguo entre consumo e Usar contexto ou
  energético              valor monetário         perguntar

  conta veio alta, conta  Valor faturado ou       Se a frase falar do
  aumentou                consumo                 valor da conta, usar
                                                  valor da fatura; se
                                                  falar de kWh/consumo,
                                                  usar consumo

  quanto consumiu         Consumo de energia      Informar unidade e
                                                  período

  quanto pagou            Valor pago/recebido     Não usar valor faturado
                                                  como substituto
  -----------------------------------------------------------------------

## 3.4. Vocabulário de faturamento, receita e pagamento

  -----------------------------------------------------------------------
  Termos usados pelo      Conceito canônico       Regra de interpretação
  usuário                 candidato
  ----------------------- ----------------------- -----------------------
  faturamento, valor      Receita/valor das       Usar a métrica de
  faturado                faturas emitidas        receita faturada
                                                  aprovada

  receita, receita total  Receita conforme        Não presumir que
                          definição Gold          significa valor
                                                  recebido

  receita comercial       Receita filtrada pela   Confirmar dimensão e
                          classe comercial        métrica disponíveis

  receita residencial     Receita filtrada pela   Não confundir com
                          classe residencial      consumo residencial

  valor da conta, valor   Valor faturado          Não inferir pagamento
  da fatura

  conta de luz            Ambíguo                 Pode significar valor
                                                  faturado, consumo ou
                                                  pagamento; usar
                                                  contexto ou perguntar

  pagamento, valor pago   Valor efetivamente pago Exige métrica de
                                                  pagamento/recebimento

  arrecadação, receita    Valor efetivamente      Não usar faturamento
  recebida                arrecadado              como substituto

  inadimplência, fatura   Saldo/estado de         Exige campos e regras
  em aberto               pagamento               específicas de
                                                  vencimento/pagamento

  cresceu, aumentou,      Variação positiva       Exige período de
  subiu                                           referência

  caiu, diminuiu, reduziu Variação negativa       Exige período de
                                                  referência

  maior receita           Maior total de receita  Não confundir com maior
                                                  crescimento

  receita por mês         Série temporal de       Agregar na competência
                          receita                 correta
  -----------------------------------------------------------------------

Se o usuário disser "quanto a receita cresceu", o agente deve apresentar
valor do período atual, valor de referência, diferença absoluta em reais
e variação percentual, quando os dados permitirem.

## 3.5. Vocabulário de tarifa, preço e efeito-preço

  -----------------------------------------------------------------------
  Termo                  Significado              Limite
  ---------------------- ------------------------ -----------------------
  tarifa homologada      Tarifa definida/aprovada Não é automaticamente a
                         pelo órgão competente    tarifa média observada
                                                  na Gold

  tarifa média efetiva   Preço observado por      Confirmar cálculo,
                         unidade de energia,      universo e
                         candidato                granularidade
                         `tarifa_media_efetiva`
                         em R\$/kWh

  preço médio do kWh     Pode corresponder à      Confirmar definição e
                         tarifa média efetiva     ponderação

  bandeira tarifária     Acréscimo tarifário por  Não representa aumento
                         bandeira                 de consumo

  reajuste tarifário     Alteração tarifária      Não atribuir variação
                         homologada               de receita apenas ao
                                                  reajuste sem
                                                  decomposição

  efeito-preço           Parcela da variação de   Exige metodologia
                         receita associada à      documentada
                         mudança de preço/tarifa

  efeito-volume          Parcela da variação de   Exige mesma população e
                         receita associada à      períodos comparáveis
                         quantidade de energia
  -----------------------------------------------------------------------

O candidato `tarifa_media_efetiva` deve ser conferido no dicionário e na
implementação. O agente não deve tratá-lo como sinônimo de tarifa
homologada.

A decomposição preço-volume exige:

-   Receita e consumo da mesma população.
-   Mesmos períodos e filtros.
-   Unidade consistente.
-   Regra explícita para mix de classes e consumidores.
-   Metodologia documentada e revisada.
-   Cálculo determinístico e reproduzível.

Não criar uma decomposição empresarial arbitrária apenas porque o SQL
parece plausível.

## 3.6. Vocabulário de geração distribuída e solar

  -----------------------------------------------------------------------
  Termos usados           Conceito canônico       Regra
  ----------------------- ----------------------- -----------------------
  solar, painel solar,    Geração distribuída     Não inferir tecnologia
  energia solar           (GD), se o cadastro     ou data de instalação
                          confirmar               além do cadastro

  GD, geração distribuída Unidade com geração     Usar a flag/cadastro
                          própria conectada       validado

  unidade solar, UC solar UC marcada com GD       Não presumir que a flag
                                                  contém histórico de
                                                  instalação

  queda de consumo solar  Variação do consumo de  Exige mesma métrica e
                          UCs com GD              períodos comparáveis

  queda acima de 30%      Queda percentual        Denominador válido e
                          estritamente superior a regra de período
                          30%                     explícita
  -----------------------------------------------------------------------

O levantamento informa a existência de `queda_consumo_superior_30_pct`
na Gold. O agente deve confirmar no catálogo:

-   A definição exata da flag.
-   A população usada.
-   A métrica subjacente.
-   Os períodos comparados.
-   O tratamento de nulos, zeros e UCs sem histórico.
-   Se a flag está publicada e habilitada na F1.

**Janela já documentada para a flag existente:**

-   Referência: julho de 2022 a junho de 2023.
-   Período atual: julho de 2025 a junho de 2026.

Não reinterpretar essa flag como comparação entre janeiro--junho de 2025
e janeiro--junho de 2026.

Se o usuário pedir explicitamente a comparação semestral, o agente só
poderá recalcular se existirem dados mensais por UC, métrica compatível,
cobertura suficiente e capacidade autorizada. A flag anual existente não
substitui esse recálculo.

## 3.7. Vocabulário de interrupções e continuidade

Este domínio deve ser reconhecido, mas permanece fora da F1 enquanto a
primeira versão estiver restrita ao faturamento.

  -----------------------------------------------------------------------
  Termos usados           Conceito candidato      Regra
  ----------------------- ----------------------- -----------------------
  falta de luz, queda de  Interrupção de          Reconhecer como
  luz, sem energia        fornecimento            ocorrência de rede

  apagão                  Interrupção de          Não inferir grande
                          fornecimento            alcance, causa ou
                                                  número de pessoas
                                                  afetadas

  quantas vezes faltou    Contagem de ocorrências Não substituir por DEC
  luz                                             ou FEC

  quanto tempo ficou sem  Duração de interrupções Exige métrica de
  luz                                             duração e unidade

  DEC                     Duração equivalente de  Não tratar como
                          interrupção por UC      contagem simples de
                                                  eventos

  FEC                     Frequência equivalente  Não tratar como
                          de interrupção por UC   contagem simples de
                                                  eventos

  alimentador             Circuito da rede que    Usar dimensão de
                          abastece um conjunto de alimentador validada
                          regiões/UCs

  região mais afetada     Pode significar mais    Perguntar qual critério
                          eventos, maior duração  se a frase não resolver
                          ou mais UCs afetadas

  pior continuidade       Pode envolver DEC, FEC  Exibir cada indicador
                          ou ambos                separadamente
  -----------------------------------------------------------------------

O case informa que os valores absolutos simplificados de DEC/FEC servem
para comparar alimentadores e períodos entre si, não para comparação com
limites regulatórios reais. O agente deve preservar essa limitação.

## 3.8. Vocabulário de atendimento

Este domínio também deve ser reconhecido, mas não executado na F1 sem
habilitação explícita.

  -----------------------------------------------------------------------
  Termos usados           Conceito candidato      Regra
  ----------------------- ----------------------- -----------------------
  chamado, protocolo      Registro de atendimento Não assumir que todo
                                                  protocolo é reclamação

  reclamação              Chamado classificado    Exige
                          como reclamação         categoria/rotulagem
                                                  confiável

  atendimento             Pode significar         Usar contexto ou
                          protocolo, interação,   perguntar
                          duração ou resolução

  satisfação, nota de     Nota válida de          Não confundir com tempo
  atendimento             satisfação              de resolução

  cliente reclamou        Registro de reclamação, Não inferir apenas pela
                          se classificado         existência de protocolo

  tempo para resolver     Tempo de resolução      Exige datas e definição
                                                  de início/fim
  -----------------------------------------------------------------------

Total de protocolos não é total de reclamações. Nota de satisfação não é
tempo de resolução.

## 3.9. Vocabulário estrutural do setor

O agente deve conhecer os conceitos do glossário do case:

  ---------------------------------------------------------------------
  Termo                              Significado operacional
  ---------------------------------- ----------------------------------
  UC / unidade consumidora           Ponto que recebe energia e possui
                                     medidor; entidade central do case

  competência                        Mês de referência da
                                     leitura/fatura, distinto da data
                                     de pagamento

  classe de consumo                  Categoria tarifária da UC

  alimentador                        Circuito da rede de média tensão
                                     que abastece um conjunto de
                                     ruas/bairros

  bandeira tarifária                 Acréscimo tarifário definido
                                     conforme o custo de geração

  perdas não técnicas                Energia entregue e não faturada
                                     por furto, fraude ou erros de
                                     leitura/cadastro

  GD                                 Geração distribuída; energia
                                     própria pode ser abatida do
                                     consumo faturado

  DEC/FEC                            Indicadores equivalentes de
                                     duração/frequência de interrupção
  ---------------------------------------------------------------------

O case apresenta como referências de classe: residencial (B1), rural
(B2), comercial e poder público (B3) e industrial (A4). Conferir a
correspondência efetiva na Gold antes de transformar esses códigos em
filtros físicos.

------------------------------------------------------------------------

# 4. Regras de resolução de ambiguidade

## 4.1. Ambiguidade contextual

O agente deve resolver termos genéricos usando:

1.  A pergunta completa.
2.  Os termos próximos.
3.  A métrica mencionada anteriormente na conversa.
4.  O domínio ativo da pergunta.
5.  Os filtros e dimensões.
6.  O catálogo e as capacidades habilitadas.

Exemplos:

  ---------------------------------------------------------------------
  Pergunta                           Interpretação esperada
  ---------------------------------- ----------------------------------
  "Qual foi o volume residencial?"   No contexto do diagnóstico de
                                     Henrique, priorizar volume de
                                     energia faturada residencial. Fora
                                     desse contexto, resolver pela
                                     conversa ou esclarecer.

  "Qual foi o volume faturado?"      Energia efetivamente faturada; não
                                     substituir por consumo medido

  "Qual bairro mais perdeu volume?"  Herdar a métrica do contexto; sem
                                     contexto, esclarecer se é consumo
                                     medido ou energia faturada

  "Quanto a receita comercial        Receita faturada comercial, se
  aumentou?"                         essa for a definição aprovada

  "Quanto os clientes pagaram?"      Receita recebida/paga; não usar
                                     faturamento

  "A conta aumentou?"                Ambígua entre valor faturado e
                                     consumo, salvo contexto

  "O consumo aumentou?"              Métrica de consumo, não valor
                                     monetário

  "Onde mais faltou luz?"            Ambígua entre quantidade de
                                     eventos, duração e UCs afetadas

  "Qual bairro teve a maior queda?"  Perguntar ou usar contexto para
                                     identificar métrica; não adivinhar
  ---------------------------------------------------------------------

## 4.2. Quando perguntar

Pedir esclarecimento somente quando a informação ausente for necessária
e não houver um padrão de negócio aprovado que resolva a intenção.

A pergunta de esclarecimento deve ser curta e apresentar alternativas
concretas.

Exemplos:

-   "Quando você diz volume faturado, quer a energia efetivamente
    faturada em kWh ou o consumo medido?"
-   "Por receita, você quer o valor faturado ou o valor efetivamente
    recebido?"
-   "Quando diz que faltou mais energia, quer comparar a quantidade de
    ocorrências, a duração ou as unidades afetadas?"
-   "Você quer comparar os últimos 12 meses com os 12 meses anteriores
    ou com o primeiro ano da base?"

Não perguntar novamente por filtros ou períodos que já estejam definidos
de forma inequívoca no contexto conversacional.

## 4.3. Estados de resposta

A API/contrato deve distinguir, conforme os estados já existentes no
projeto:

-   Pergunta respondida.
-   Esclarecimento necessário.
-   Capacidade não suportada.
-   Dados/evidências indisponíveis.
-   Cobertura incompleta.
-   Acesso não autorizado.
-   Provedor indisponível.
-   Erro técnico.

Não transformar todos esses estados em uma mensagem genérica de "não
entendi".

------------------------------------------------------------------------

# 5. Política temporal do projeto

## 5.1. Âncora temporal

A última competência disponível confirmada para esta base é **junho de
2026** (`2026-06`).

Para esta publicação congelada:

-   Últimos 12 meses completos: julho de 2025 a junho de 2026.
-   12 meses imediatamente anteriores: julho de 2024 a junho de 2025.
-   Últimos 6 meses: janeiro a junho de 2026.
-   Últimos 9 meses: outubro de 2025 a junho de 2026.
-   Competência de três meses antes de junho de 2026: março de 2026.

A implementação deve resolver a âncora a partir da última competência
completa da publicação Gold ou de metadado/configuração oficial da
publicação. Não usar `datetime.now()` como substituto da competência dos
dados.

Se a publicação for atualizada no futuro, as janelas relativas devem
acompanhar a nova última competência completa, sem alterar as regras
semânticas.

Se tabelas ou domínios possuírem competências máximas diferentes,
resolver a âncora por métrica/publicação e informar a diferença. Não
assumir que todas as tabelas têm cobertura idêntica.

## 5.2. Estratégias temporais canônicas

A Semantic Layer deve representar estratégias separadas:

  -------------------------------------------------------------------------
  ID sugerido                     Nome                 Uso
  ------------------------------- -------------------- --------------------
  `explicit_period`               Período explícito    Respeitar exatamente
                                                       o intervalo
                                                       informado

  `rolling_n_months`              Janela móvel de N    Consultar N
                                  meses                competências
                                                       completas sem
                                                       comparação
                                                       automática

  `rolling_12m_vs_previous_12m`   Últimos 12 meses     Crescimento/queda
                                  vs. 12 anteriores    recente

  `same_period_previous_year`     Mesmo período do ano Comparação sazonal
                                  anterior

  `first_year_vs_latest_12m`      Primeiro ano         Diagnóstico
                                  vs. últimos 12 meses histórico de
                                                       Henrique

  `fixed_business_window`         Janela de negócio    Métricas/flags
                                  fixa                 previamente
                                                       calculadas com
                                                       períodos definidos

  `single_relative_competence`    Competência relativa "Há três meses",
                                  única                "mês retrasado" etc.
  -------------------------------------------------------------------------

Não usar uma estratégia global para todas as perguntas.

## 5.3. Regras de linguagem temporal

  ---------------------------------------------------------------------
  Expressão                          Interpretação padrão
  ---------------------------------- ----------------------------------
  "em 2025"                          Ano-calendário: jan--dez/2025

  "no ano passado"                   Ano-calendário anterior à âncora
                                     temporal, quando a intenção for
                                     calendário

  "últimos 12 meses"                 Janela móvel de 12 competências
                                     completas até a última competência

  "último ano"                       Janela móvel de 12 competências
                                     completas; em pergunta de
                                     variação, comparar com os 12 meses
                                     anteriores

  "últimos seis meses"               Seis competências completas até a
                                     âncora

  "nos últimos nove meses"           Nove competências completas até a
                                     âncora

  "há três meses"                    Uma competência específica, três
                                     meses antes da âncora

  "mesmo período do ano passado"     Mesmas competências deslocadas 12
                                     meses

  "primeiro ano da base"             Primeiras 12 competências
                                     completas disponíveis

  "desde o início da base"           Todo o intervalo disponível,
                                     somente se a pergunta pedir
                                     explicitamente

  "primeiro semestre"                Jan--jun do ano indicado pelo
                                     contexto; se não houver ano,
                                     esclarecer

  "último semestre"                  Não assumir automaticamente
                                     semestre-calendário ou janela
                                     móvel; usar contexto ou perguntar
  ---------------------------------------------------------------------

A expressão "há três meses" indica uma competência; "nos últimos três
meses" indica uma janela de três competências. Não confundir as duas.

## 5.4. Comparação correta para cada intenção

### A. Diagnóstico original de Henrique

O case pede comparar os últimos 12 meses com o primeiro ano da base para
explicar a variação de energia faturada e receita.

Regra:

-   Período inicial: primeiras 12 competências completas disponíveis.
-   Período final: julho/2025 a junho/2026.
-   Não substituir o primeiro ano por julho/2024 a junho/2025.
-   Exibir os dois períodos e os valores de cada métrica.
-   Investigar por município, bairro e classe somente quando a Gold e a
    capacidade permitirem.
-   Separar efeito-preço e efeito-volume apenas com metodologia
    documentada e população comparável.

### B. Crescimento/queda no último ano

Para uma pergunta de tendência recente, como "quanto a receita cresceu
no último ano?":

-   Atual: julho/2025 a junho/2026.
-   Referência: julho/2024 a junho/2025.
-   Mostrar valores, diferença absoluta e percentual.

### C. Comparação sazonal

Para "compare janeiro a junho com o mesmo período do ano passado":

-   Atual: janeiro--junho/2026.
-   Referência: janeiro--junho/2025.

Não substituir por janela móvel de 12 meses.

### D. Valor em período explícito

"Qual foi a receita em 2025?" deve consultar janeiro--dezembro/2025. Não
acrescentar comparação automaticamente.

### E. Valor em janela móvel sem pedido de comparação

"Quanto consumimos nos últimos seis meses?" deve retornar
janeiro--junho/2026, sem comparação automática. Uma comparação pode ser
oferecida como continuação, mas não deve alterar a pergunta original.

## 5.5. Cobertura temporal

Antes de executar uma comparação:

-   Confirmar que todas as competências existem.
-   Verificar se os meses estão completos.
-   Conferir se os dois períodos possuem a mesma duração.
-   Conferir se a população/dimensões são comparáveis.
-   Identificar meses ausentes e registros duplicados.
-   Não converter ausência de registros em zero sem regra aprovada.
-   Se a cobertura for parcial, informar a limitação e não apresentar a
    comparação como equivalente.

Toda resposta comparativa deve apresentar o intervalo exato usado.

------------------------------------------------------------------------

# 6. Regras para variação, ranking e agregação

## 6.1. Fórmulas

Diferença absoluta:

``` text
delta = valor_atual - valor_referencia
```

Variação percentual:

``` text
variacao_percentual =
    (valor_atual - valor_referencia)
    / valor_referencia
    * 100
```

Queda percentual:

``` text
queda_percentual =
    (valor_referencia - valor_atual)
    / valor_referencia
    * 100
```

Esses cálculos devem ser feitos no SQL validado ou em código
determinístico, não por estimativa textual do LLM.

## 6.2. Casos especiais

-   Referência igual a zero: percentual indefinido; não dividir por
    zero.
-   Referência nula: percentual não calculável; não substituir por zero.
-   Atual igual a zero: é valor observado zero, não ausência de dados.
-   Resultado vazio: informar ausência de registros no recorte, não
    afirmar que o valor é zero.
-   Competência ausente: sinalizar cobertura incompleta.
-   População diferente: não afirmar comparação equivalente sem explicar
    a diferença.
-   Empate: definir desempate determinístico e informar quando
    relevante.
-   Arredondamento: manter precisão nos cálculos; arredondar somente na
    apresentação.

## 6.3. Ranking: entender "maior" corretamente

  ---------------------------------------------------------------------
  Pergunta                           Ordenação
  ---------------------------------- ----------------------------------
  "Qual bairro mais perdeu volume?"  Maior perda absoluta em kWh da
                                     métrica resolvida pelo contexto

  "Qual bairro teve a maior queda    Maior queda percentual
  percentual?"

  "Qual bairro teve maior consumo?"  Maior consumo total no período

  "Qual bairro mais cresceu?"        Maior crescimento conforme métrica
                                     e período

  "Quais foram os cinco maiores?"    Herdar a métrica, período e
                                     critério do contexto anterior

  "Qual teve a maior receita?"       Maior receita total, não maior
                                     crescimento
  ---------------------------------------------------------------------

Para "qual bairro mais perdeu volume residencial no último ano?":

-   Preservar o contexto do diagnóstico comercial de Henrique.
-   Interpretar prioritariamente "volume residencial" como volume de
    energia faturada da classe residencial, não como consumo medido.
-   Confirmar que existe uma métrica específica de energia faturada em
    kWh, com cobertura e autorização para a consulta. Não usar
    `consumo_total_kwh` como substituto.
-   Comparar julho/2025--junho/2026 com julho/2024--junho/2025, conforme
    a regra temporal desta especificação para essa pergunta.
-   Filtrar classe residencial.
-   Agrupar por bairro.
-   Calcular diferença em kWh.
-   Ordenar pela maior perda absoluta.
-   Mostrar também variação percentual.
-   Não ordenar apenas pela maior porcentagem.
-   Se a métrica faturada não estiver disponível, informar a limitação
    ou pedir uma decisão; não retornar um ranking de consumo medido como
    se fosse volume faturado.

## 6.4. Agregações

Cada métrica deve declarar como pode ser agregada:

-   `SUM`: somente para métricas aditivas e grão compatível.
-   `AVG`: somente quando a média fizer sentido e a ponderação estiver
    definida.
-   `COUNT`: distinguir contagem de linhas, UCs, faturas, protocolos e
    eventos.
-   `COUNT DISTINCT`: usar somente quando a entidade e o universo
    estiverem definidos; não usar `DISTINCT` para esconder fan-out.
-   Métricas semi-aditivas ou não aditivas precisam de regra específica.

O agente não pode escolher `SUM` apenas porque a pergunta usa "total".

------------------------------------------------------------------------

# 7. Contrato do catálogo semântico

O catálogo precisa ser versionado e validável por código. A estrutura
física deve seguir os padrões encontrados no repositório; o exemplo
abaixo é conceitual.

## 7.1. Campos mínimos por métrica

Cada métrica deve registrar:

-   ID canônico estável.
-   Nome de negócio.
-   Definição detalhada.
-   Sinônimos inequívocos (`aliases`) e expressões coloquiais.
-   Termos dependentes de contexto (`contextual_terms`), com condições
    explícitas de resolução e fallback.
-   Regras de desambiguação (`disambiguation_rules`), incluindo
    qualificadores, contexto herdado e quando pedir esclarecimento.
-   Unidade.
-   Domínio.
-   Status de cobertura por versão.
-   Tabela/view física autorizada.
-   Coluna ou expressão física.
-   Granularidade.
-   Coluna temporal.
-   Agregações permitidas.
-   Dimensões compatíveis.
-   Filtros válidos.
-   Regras de cálculo.
-   Tratamento de nulos e zeros.
-   Limitações e caveats.
-   Exemplos de perguntas.
-   Exemplos de consultas corretas e incorretas.
-   Fonte documental e versão.

## 7.2. Campos mínimos por dimensão

-   ID canônico.
-   Nome de negócio.
-   Sinônimos.
-   Valores/códigos válidos.
-   Normalização de valores.
-   Tabela/coluna física autorizada.
-   Granularidade.
-   Métricas compatíveis.
-   Regras de relacionamento.
-   Status de cobertura.
-   Limitações.

## 7.3. Campos mínimos por relação

-   Tabela/view de origem.
-   Tabela/view de destino.
-   Chave(s) de junção.
-   Cardinalidade.
-   Grão antes e depois do join.
-   Métricas afetadas.
-   Condições permitidas.
-   Risco de fan-out.
-   Necessidade de pré-agregação.
-   Evidência/testes que aprovam o relacionamento.

## 7.4. Exemplo conceitual de métrica

``` yaml
metric_id: energy.measured_consumption
business_name: Consumo de energia medido
definition: >
  Quantidade de energia medida/apurada para o recorte e período solicitados.
aliases:
  - consumo
  - energia consumida
  - energia utilizada
  - volume consumido
unit: kWh
domain: consumption
candidate_physical_field: consumo_total_kwh
temporal_grain: monthly_competence
aggregation: sum
supported_dimensions:
  - municipality
  - neighborhood
  - consumption_class
coverage:
  gold: candidate
  text_to_sql_f1: verify_against_domain_contract
limitations:
  - Não equivale automaticamente à energia efetivamente faturada.
  - Só pode ser executada se estiver liberada no catálogo F1.
```

Os nomes e valores acima são ilustrativos/candidatos. O agente deve
validar cada referência física no dicionário, catálogo, publicação e
código antes de persistir a definição.

Se a Gold comprovar uma métrica distinta de energia efetivamente
faturada em kWh, seu conceito canônico pode ser representado
conceitualmente como `energy.billed_volume`. Esse ID é uma proposta de
nomenclatura, não um identificador já existente nem uma afirmação de que
a métrica esteja publicada. Confirmar definição, grão, unidade,
agregação, dimensões, período, fonte física e cobertura antes de
registrá-lo ou habilitá-lo.

O catálogo deve distinguir: - `aliases`: expressões suficientemente
inequívocas para apontar diretamente para um conceito. -
`contextual_terms`: expressões como "volume residencial", que exigem
contexto, regra de negócio ou esclarecimento antes de resolver. -
`disambiguation_rules`: condições para selecionar a métrica, herdar
contexto ou pedir esclarecimento.

Não cadastrar "volume residencial" como alias incondicional de
`energy.measured_consumption`. Essa expressão depende do contexto. No
diagnóstico de Henrique, a interpretação prioritária é volume de energia
faturada residencial, que deve possuir conceito canônico próprio se a
Gold realmente disponibilizar essa medida. Em conversas explicitamente
sobre consumo, pode ser resolvida para consumo medido. Sem contexto
suficiente, solicitar esclarecimento. O ID e o mapeamento físico da
métrica faturada devem ser confirmados antes de serem criados.

## 7.5. Não duplicar aliases em prompts diferentes

-   Manter uma fonte única de vocabulário.
-   Não espalhar sinônimos divergentes em vários prompts.
-   O prompt deve receber o subconjunto relevante do catálogo.
-   O mesmo conceito deve manter o mesmo ID em todas as etapas.
-   Mudanças de definição devem ser versionadas e testadas.
-   Aliases devem apontar para IDs canônicos, não diretamente para
    colunas físicas.

------------------------------------------------------------------------

# 8. Contrato de interpretação antes da geração SQL

A interpretação deve produzir uma estrutura tipada antes da geração SQL.
O formato final precisa respeitar os contratos reais do projeto; o
exemplo abaixo demonstra os campos conceituais.

``` json
{
  "status": "interpreted",
  "domain": "billing",
  "metric_ids": ["billing.billed_revenue"],
  "dimensions": ["geography.municipality"],
  "filters": [
    {
      "dimension_id": "billing.consumption_class",
      "operator": "eq",
      "value_id": "class.commercial"
    }
  ],
  "temporal": {
    "intent": "recent_growth",
    "strategy": "rolling_12m_vs_previous_12m",
    "anchor_competence": "2026-06",
    "current_period": {
      "start": "2025-07",
      "end": "2026-06"
    },
    "comparison_period": {
      "start": "2024-07",
      "end": "2025-06"
    }
  },
  "aggregation": "sum",
  "comparison": {
    "absolute_delta": true,
    "percentage_change": true
  },
  "ranking": null,
  "clarification": null,
  "assumptions": [
    "Receita interpretada como receita faturada",
    "Crescimento recente comparado aos 12 meses anteriores"
  ]
}
```

## 8.1. O que a interpretação deve extrair

-   Intenção analítica.
-   Domínio.
-   Métrica(s) canônica(s).
-   Dimensões.
-   Filtros.
-   Período explícito ou relativo.
-   Estratégia temporal.
-   Período de referência, quando necessário.
-   Agregação.
-   Comparação.
-   Ordenação/ranking.
-   Limite de resultados.
-   Continuidade conversacional.
-   Ambiguidades.
-   Estado de cobertura.
-   Necessidade de esclarecimento.

## 8.2. Autoridade de cada componente

**LLM:**

-   Interpretar a pergunta.
-   Propor IDs semânticos existentes.
-   Sugerir a estratégia temporal.
-   Identificar ambiguidades.
-   Propor SQL candidato somente com o contexto autorizado.

**Código determinístico/Backend:**

-   Resolver datas pela competência publicada.
-   Validar cobertura.
-   Validar IDs do catálogo.
-   Validar dimensões e métricas compatíveis.
-   Validar agregações, filtros e comparações.
-   Aplicar autorização e limites.
-   Validar e executar SQL.
-   Calcular valores derivados.

O LLM nunca deve ser autoridade final sobre datas, permissões, escopo ou
correção dos resultados.

------------------------------------------------------------------------

# 9. Recuperação semântica e contexto enviado ao Gemini

O componente de recuperação deve selecionar somente o contexto
necessário à pergunta.

Para uma pergunta sobre receita comercial em Jaboatão, recuperar:

-   Definição da receita.
-   Unidade monetária.
-   Regra de agregação.
-   Classe comercial.
-   Município.
-   Coluna de competência.
-   Estratégia temporal.
-   Tabelas/views autorizadas.
-   Relacionamentos aprovados.
-   Status da capacidade na F1.
-   Exemplos pertinentes.

Não enviar o banco inteiro quando um subconjunto autorizado for
suficiente.

O contexto precisa conter explicitamente:

1.  O que a métrica significa.
2.  O que ela não significa.
3.  Como agregá-la.
4.  Quais dimensões são compatíveis.
5.  Quais períodos podem ser comparados.
6.  Quais objetos físicos estão autorizados.
7.  Quais limitações impedem uma resposta.

Conteúdo recuperado do catálogo, histórico e pergunta deve ser tratado
como dado, não como instrução privilegiada. Nenhuma dessas fontes pode
alterar as regras de segurança do sistema.

Registrar a versão do catálogo e os IDs recuperados para permitir
auditoria.

------------------------------------------------------------------------

# 10. Geração SQL e validação semântica

## 10.1. Regras do SQL Generator

O SQL Generator deve:

-   Utilizar apenas tabelas, views e colunas fornecidas no contexto
    autorizado.
-   Respeitar o dialeto real do banco.
-   Usar parâmetros vinculados para valores variáveis.
-   Separar SQL e parâmetros.
-   Não inventar métricas ou dimensões.
-   Não trocar uma métrica por outra semelhante.
-   Respeitar a granularidade.
-   Respeitar as janelas temporais já resolvidas.
-   Usar apenas relacionamentos aprovados.
-   Produzir estado explícito quando precisar esclarecer ou recusar.
-   Não executar SQL diretamente.

## 10.2. Validação estrutural

O validador deve analisar a AST e, no mínimo:

-   Rejeitar instruções múltiplas.
-   Permitir apenas consultas de leitura aprovadas.
-   Bloquear DDL, DML e comandos administrativos.
-   Bloquear objetos fora da allowlist.
-   Bloquear colunas não autorizadas.
-   Bloquear funções não permitidas.
-   Aplicar limite de linhas, timeout e orçamento.
-   Não depender exclusivamente de regex.

## 10.3. Validação semântica

Além da AST, verificar:

-   Métrica existe e está habilitada.
-   Dimensão existe e é compatível.
-   Filtro usa valor canônico válido.
-   Agregação respeita a métrica.
-   Período respeita a coluna temporal.
-   Comparação usa janelas compatíveis.
-   Join respeita cardinalidade e grão.
-   Não há fan-out que duplique valores.
-   Unidade permanece consistente.
-   A consulta não ultrapassa a cobertura F1.
-   O SQL representa a intenção original.

SQL sintaticamente válido não significa SQL semanticamente correto.

## 10.4. Execução

-   Backend continua como responsável exclusivo pela execução.
-   Utilizar credencial read-only.
-   Aplicar autorização no servidor.
-   Não confiar em filtros de segurança gerados pelo LLM.
-   Aplicar timeout, limite de linhas e cancelamento.
-   Registrar SQL executado, parâmetros sanitizados, publicação e versão
    do catálogo.
-   Não executar consulta rejeitada como fallback.

------------------------------------------------------------------------

# 11. Resposta final e apresentação

A resposta deve ser natural, mas precisa preservar o significado dos
dados.

## 11.1. Toda resposta quantitativa deve informar

-   Métrica utilizada.
-   Unidade.
-   Período.
-   Período de comparação, quando houver.
-   Filtros.
-   Dimensões.
-   Critério de ranking, quando houver.
-   Limitações de cobertura.
-   Resultado numérico.
-   Interpretação sustentada pelos dados.

## 11.2. Exemplo de resposta comparativa

``` text
A receita comercial de Jaboatão aumentou X% na comparação analisada.

Período atual: jul/2025 a jun/2026
Período de referência: jul/2024 a jun/2025

Receita atual: R$ ...
Receita de referência: R$ ...
Diferença: R$ ...
Variação: X%

A comparação utiliza receita faturada e considera a classe comercial.
```

## 11.3. Respostas fora do escopo

Ser claro e útil:

-   Dizer que entendeu a intenção.
-   Informar que a capacidade não está habilitada na F1.
-   Não gerar SQL alternativo com outra métrica.
-   Não sugerir que o dado inexiste se ele apenas está fora do escopo.
-   Quando possível, indicar o tipo de dado necessário.

## 11.4. Insight Generator

O Insight Generator deve receber resultados reais e metadados da
execução.

Não deve:

-   Inventar valores.
-   Calcular percentuais de cabeça.
-   Alterar filtros.
-   Omitir período relevante.
-   Transformar associação em causalidade.
-   Apresentar estimativa como dado observado.
-   Confundir ausência de dados com zero.

Afirmações quantitativas devem ser verificáveis contra o resultado ou um
cálculo determinístico registrado.

------------------------------------------------------------------------

# 12. Contexto conversacional e follow-up

O contexto deve preservar os elementos relevantes da análise anterior:

-   Métrica.
-   Dimensões.
-   Filtros.
-   Período.
-   Estratégia temporal.
-   Comparação.
-   Unidade.
-   Publicação/versão dos dados.
-   Critério de ordenação.

Exemplos:

**Conversa 1**

Usuário: "Mostre o faturamento comercial de Jaboatão nos últimos 12
meses."

Usuário: "E no período anterior?"

Esperado: manter receita, classe comercial e município; alterar somente
o período de comparação.

**Conversa 2**

Usuário: "Qual bairro mais perdeu volume residencial no último ano?"

Usuário: "E qual teve a maior queda percentual?"

Esperado: manter a métrica resolvida no primeiro turno, a classe, os
períodos e o agrupamento; alterar somente o critério de ordenação para
percentual. No contexto do diagnóstico de Henrique, a métrica
prioritária é volume de energia faturada residencial, não consumo
medido.

**Conversa 3**

Usuário: "Compare a receita de Recife e Olinda."

Usuário: "Agora só Jaboatão."

Esperado: substituir o filtro de município; preservar métrica e período.

**Conversa 4**

Usuário: "Quanto foi a receita em 2025?"

Usuário: "E quanto foi pago?"

Esperado: reconhecer que a métrica mudou de faturamento para
pagamento/recebimento; não manter a métrica anterior por engano.

Toda pergunta de continuidade deve gerar uma nova interpretação,
validação e consulta. Não reutilizar resultado anterior como se fosse
resultado da nova pergunta.

------------------------------------------------------------------------

# 13. Benchmark de linguagem natural e regras temporais

Criar um conjunto versionado de perguntas. O conjunto deve conter
perguntas conhecidas, paráfrases, expressões coloquiais, ambiguidades,
perguntas fora do escopo e casos de segurança.

Os exemplos abaixo definem comportamento esperado, não valores
numéricos. Os resultados devem ser calculados na publicação Gold de
teste e revisados independentemente.

## 13.1. Volume e consumo

  -----------------------------------------------------------------------
  ID                      Pergunta                Comportamento esperado
  ----------------------- ----------------------- -----------------------
  V01                     "Qual foi o consumo     Resolver para consumo
                          residencial?"           residencial, se métrica
                                                  suportada

  V02                     "Quanto de energia as   Mesmo conceito de V01
                          casas consumiram?"

  V03                     "Qual foi o volume      Resolver pelo contexto;
                          residencial?"           no diagnóstico de
                                                  Henrique, priorizar
                                                  energia faturada
                                                  residencial. Sem
                                                  contexto suficiente,
                                                  esclarecer.

  V03B                    Contexto anterior:      Preservar consumo
                          "Mostre o consumo       medido porque o
                          residencial medido." e  contexto stabelece essa
                          Follow-up: "E o n       métrica; ão trocar para
                          volume residencial?" f  energia aturada apenas
                                                  pela palavra "volume".

  V03C                    "Qual foi o volume      Sem contexto e sem
                          residencial?"           padrão aprovado, pedir
                                                  esclarecimento entre
                                                  consumo medido e
                                                  energia faturada.

  V04                     "Qual bairro mais       Herdar a métrica do
                          perdeu volume?"         contexto. Sem contexto,
                                                  esclarecer se é consumo
                                                  medido ou energia
                                                  faturada.

  V04A                    "Qual bairro mais       No contexto original de
                          perdeu volume           Henrique, usar volume
                          residencial no último e de nergia faturada
                          ano?"                   residencial, se houver
                                                  métrica específica,
                                                  publicada e autorizada.
                                                  Não substituir por
                                                  consumo medido.
                                                  Registrar que a
                                                  resolução é contextual
                                                  e inferida do
                                                  encadeamento do case.

  V05                     "Qual foi o volume de   Exigir métrica de
                          energia faturada?"      energia efetivamente
                                                  faturada; não usar
                                                  consumo medido

  V06                     "Quanto gastamos com    Esclarecer consumo em
                          energia?"               kWh ou valor monetário
                                                  se contexto não
                                                  resolver

  V07                     "O consumo aumentou ou  Exigir referência
                          diminuiu?"              temporal ou aplicar
                                                  padrão aprovado e
                                                  mostrar períodos
  -----------------------------------------------------------------------

## 13.2. Receita e faturamento

  -----------------------------------------------------------------------
  ID                      Pergunta                Comportamento esperado
  ----------------------- ----------------------- -----------------------
  R01                     "Quanto faturamos em    Receita faturada, se
                          Jaboatão?"              suportada

  R02                     "Quanto a receita       Classe comercial;
                          comercial cresceu em    últimos 12 meses vs. 12
                          Jaboatão?"              anteriores como padrão
                                                  de crescimento recente

  R03                     "Quanto os clientes     Exigir métrica de
                          pagaram?"               recebimento; não
                                                  substituir por
                                                  faturamento

  R04                     "A conta de luz         Esclarecer valor
                          aumentou?"              faturado ou consumo se
                                                  não houver contexto

  R05                     "Qual município teve    Ranking por receita
                          maior receita?"         total, não por
                                                  crescimento

  R06                     "Qual município mais    Ranking por variação
                          cresceu em receita?"    conforme período
                                                  definido

  R07                     "Compare receita com o  Primeiro ano
                          primeiro ano da base."  vs. últimos 12 meses
  -----------------------------------------------------------------------

## 13.3. Tempo

  ----------------------------------------------------------------------
  ID                     Pergunta               Comportamento esperado
  ---------------------- ---------------------- ------------------------
  T01                    "Compare os últimos 12 Primeiras 12
                         meses com o primeiro   competências completas
                         ano da base."          vs. jul/2025--jun/2026

  T02                    "Quanto cresceu no     Jul/2025--jun/2026
                         último ano?"           vs. jul/2024--jun/2025

  T03                    "Quanto consumimos em  Jan--dez/2025, sem
                         2025?"                 comparação automática

  T04                    "Quanto consumimos nos Jan--jun/2026, sem
                         últimos seis meses?"   comparação automática

  T05                    "Quanto consumimos nos Out/2025--jun/2026
                         últimos nove meses?"

  T06                    "Quanto consumimos há  Mar/2026
                         três meses?"

  T07                    "Compare janeiro a     Jan--jun/2026
                         junho com o mesmo      vs. jan--jun/2025
                         período do ano
                         passado."

  T08                    "Qual foi a receita em Identificar ano pelo
                         março?"                contexto ou pedir
                                                esclarecimento

  T09                    "Compare o primeiro    Identificar
                         semestre."             anos/intervalos pelo
                                                contexto; esclarecer se
                                                faltar

  T10                    "Compare o último      Não confundir
                         semestre."             semestre-calendário com
                                                janela móvel
  ----------------------------------------------------------------------

## 13.4. Outros domínios e limites

  -----------------------------------------------------------------------
  ID                      Pergunta                Comportamento esperado
  ----------------------- ----------------------- -----------------------
  D01                     "Quantas UCs solares em Reconhecer domínio GD;
                          Olinda caíram mais de   conferir flag/períodos;
                          30%?"                   fora da F1 se não
                                                  habilitado

  D02                     "Onde mais faltou luz?" Reconhecer interrupção;
                                                  esclarecer contagem,
                                                  duração ou UCs afetadas

  D03                     "Quantas reclamações    Não usar total de
                          tivemos?"               protocolos como total
                                                  de reclamações

  D04                     "Qual foi a satisfação  Usar notas válidas, se
                          do atendimento?"        habilitadas; não
                                                  confundir com resolução

  D05                     "Qual alimentador teve  Usar DEC, não contagem
                          pior DEC?"              simples de ocorrências

  D06                     "Qual foi o reajuste da Exigir dado de tarifa
                          tarifa?"                homologada; não usar
                                                  tarifa média efetiva
                                                  como substituto
  -----------------------------------------------------------------------

## 13.5. Testes de integridade

  -----------------------------------------------------------------------
  ID                      Cenário                 Resultado esperado
  ----------------------- ----------------------- -----------------------
  I01                     Métrica de referência   Não calcular percentual
                          igual a zero

  I02                     Métrica de referência   Não substituir por zero
                          nula

  I03                     Período com mês ausente Sinalizar cobertura
                                                  incompleta

  I04                     Métrica existe na Gold, `OUT_OF_SCOPE`
                          mas não na F1

  I05                     Métrica não existe na   `UNSUPPORTED`
                          Gold

  I06                     Usuário sem permissão   `UNAUTHORIZED`

  I07                     SQL com DML/DDL         Bloquear antes da
                                                  execução

  I08                     JOIN com fan-out        Rejeitar ou exigir
                                                  estratégia aprovada

  I09                     Alias desconhecido, mas Recuperar conceito
                          semanticamente claro    canônico ou pedir
                                                  esclarecimento; não
                                                  inventar coluna

  I10                     Prompt injection no     Ignorar instrução
                          histórico               maliciosa e preservar
                                                  políticas

  I11                     Provedor indisponível   Informar falha técnica,
                                                  sem inventar resposta

  I12                     Resultado vazio         Diferenciar ausência de
                                                  registros de valor zero
  -----------------------------------------------------------------------

Cada fixture deve guardar:

-   Pergunta.
-   Contexto conversacional.
-   Intenção esperada.
-   Métrica e dimensão.
-   Filtros.
-   Período.
-   Estratégia temporal.
-   Estado de cobertura esperado.
-   SQL de referência, quando executável.
-   Resultado de referência, quando aplicável.
-   Resposta/estado esperado.
-   Justificativa da decisão.

Manter conjunto de desenvolvimento e conjunto reservado de perguntas
inéditas. Não ajustar o sistema usando o conjunto reservado e depois
apresentá-lo como prova independente.

------------------------------------------------------------------------

# 14. Plano de implementação alinhado ao TODO 3

As alterações devem ser feitas de ponta a ponta, mas em etapas
verificáveis. Não tentar resolver todas as falhas adicionando aliases ao
prompt.

## Fase 0 --- Inventário

-   [ ] Inspecionar o fluxo atual.
-   [ ] Conferir a implementação física da F1.
-   [ ] Conferir contratos e consumidores.
-   [ ] Conferir dicionário, catálogo e publicação.
-   [ ] Identificar métricas, dimensões, grãos e joins.
-   [ ] Identificar divergências documentais.
-   [ ] Registrar componentes reaproveitados/adaptados/substituídos.
-   [ ] Definir o escopo executável da F1.

**Saída:** mapa real do sistema e matriz de cobertura.

## Fase 1 --- Benchmark e baseline

-   [ ] Criar fixtures de linguagem natural.
-   [ ] Incluir os casos desta especificação.
-   [ ] Incluir perguntas reais que falharam.
-   [ ] Incluir paráfrases que não estejam no catálogo literal.
-   [ ] Incluir ambiguidades e fora de escopo.
-   [ ] Definir SQL e resultados de referência.
-   [ ] Registrar desempenho atual por categoria.
-   [ ] Separar falhas de interpretação, cobertura, planejamento,
    execução e síntese.

**Saída:** conjunto reproduzível de avaliação antes das mudanças.

## Fase 2 --- Semantic Layer e Business Glossary

-   [ ] Criar/atualizar catálogo semântico versionado.
-   [ ] Definir IDs canônicos de métricas e dimensões.
-   [ ] Adicionar vocabulário convencional e coloquial.
-   [ ] Documentar unidades, grãos e agregações.
-   [ ] Documentar compatibilidade entre métricas e dimensões.
-   [ ] Documentar regras temporais.
-   [ ] Documentar cobertura por versão/domínio.
-   [ ] Documentar limitações e conceitos que não podem ser confundidos.
-   [ ] Criar validação automática do catálogo contra Gold e contrato
    F1.
-   [ ] Adicionar testes de aliases e interpretação contextual.

**Saída:** uma fonte única de verdade para o significado do negócio e o
escopo executável.

## Fase 3 --- Schema Context Retrieval

-   [ ] Recuperar métricas e dimensões relevantes.
-   [ ] Recuperar aliases e definições.
-   [ ] Recuperar regras temporais.
-   [ ] Recuperar status de cobertura.
-   [ ] Recuperar somente tabelas/colunas autorizadas.
-   [ ] Recuperar joins aprovados.
-   [ ] Registrar IDs e versão do catálogo enviados ao modelo.
-   [ ] Testar perguntas com mais de uma métrica ou dimensão.

**Saída:** contexto pequeno, relevante e autorizado.

## Fase 4 --- SQL Generator

-   [ ] Receber pergunta e contexto resolvido.
-   [ ] Receber interpretação temporal estruturada.
-   [ ] Receber métricas canônicas e limitações.
-   [ ] Gerar SQL no dialeto real.
-   [ ] Separar parâmetros.
-   [ ] Recusar IDs ou objetos não presentes no catálogo.
-   [ ] Pedir esclarecimento quando necessário.
-   [ ] Não executar consultas.
-   [ ] Testar paráfrases, filtros, agregações e comparações.

**Saída:** candidato SQL alinhado à intenção, ainda sem execução.

## Fase 5 --- SQL Parser, Validator e Guardrails

-   [ ] Validar AST.
-   [ ] Validar allowlist de objetos.
-   [ ] Validar métricas e dimensões.
-   [ ] Validar compatibilidade semântica.
-   [ ] Validar período e cobertura.
-   [ ] Validar agregação e grão.
-   [ ] Validar joins/cardinalidade.
-   [ ] Validar escopo F1.
-   [ ] Bloquear comandos proibidos.
-   [ ] Aplicar autorização e limites.
-   [ ] Testar SQL válido sintaticamente, mas incorreto semanticamente.

**Saída:** somente consultas seguras e semanticamente aprovadas podem
avançar.

## Fase 6 --- Executor e normalização

-   [ ] Executar somente consultas aprovadas.
-   [ ] Usar read-only.
-   [ ] Aplicar parâmetros.
-   [ ] Normalizar tipos e unidades.
-   [ ] Preservar nulos e precisão.
-   [ ] Preservar período, filtros e proveniência.
-   [ ] Tratar resultado vazio e cobertura parcial.

**Saída:** resultado real, normalizado e rastreável.

## Fase 7 --- Query Repair

-   [ ] Classificar erros corrigíveis.
-   [ ] Manter reparo desligado até existir evidência de benefício.
-   [ ] Limitar tentativas e orçamento.
-   [ ] Não relaxar catálogo, autorização ou guardrails.
-   [ ] Revalidar integralmente toda consulta corrigida.
-   [ ] Registrar cadeia de tentativas.

**Saída:** reparo seguro e mensurado, não um bypass do validador.

## Fase 8 --- Insight Generator

-   [ ] Receber resultados e metadados reais.
-   [ ] Explicar métricas, unidades e períodos.
-   [ ] Distinguir observação de hipótese.
-   [ ] Validar afirmações quantitativas.
-   [ ] Não inventar causas.
-   [ ] Não substituir métricas.
-   [ ] Testar consistência entre texto, tabela e gráfico.

**Saída:** resposta natural, fundamentada e coerente com a execução.

## Fase 9 --- Contexto conversacional

-   [ ] Preservar métrica, filtros, período e comparação.
-   [ ] Alterar somente o que o usuário pediu.
-   [ ] Reinterpretar follow-ups.
-   [ ] Gerar nova consulta para cada alteração.
-   [ ] Resolver referências temporais no contexto.
-   [ ] Pedir esclarecimento quando houver referências conflitantes.

**Saída:** continuidade sem perda ou herança indevida de contexto.

## Fase 10 --- Tabelas e gráficos

-   [ ] Preservar contratos atuais do portal.
-   [ ] Apresentar unidade e período.
-   [ ] Garantir coerência com o resultado SQL.
-   [ ] Não mostrar gráficos de domínio fora do escopo.
-   [ ] Testar resultado único, múltiplas linhas e série temporal.

## Fase 11 --- Observabilidade

-   [ ] Registrar estágio da falha.
-   [ ] Registrar intenção e IDs semânticos.
-   [ ] Registrar período resolvido.
-   [ ] Registrar cobertura e versão do catálogo.
-   [ ] Registrar geração, validação, execução e síntese.
-   [ ] Registrar latência, custo e erros.
-   [ ] Sanitizar dados sensíveis.
-   [ ] Distinguir recusa, esclarecimento, ausência de dados e erro
    técnico.

## Fase 12 --- Avaliação, rollout e migração

-   [ ] Executar benchmark completo.
-   [ ] Executar conjunto reservado.
-   [ ] Comparar correção semântica e numérica.
-   [ ] Testar segurança.
-   [ ] Testar jornada autenticada no portal.
-   [ ] Definir limites de latência e custo a partir do baseline.
-   [ ] Ativar gradualmente.
-   [ ] Manter rollback.
-   [ ] Remover legado somente após comprovar ausência de consumidores.

------------------------------------------------------------------------

# 15. Orientações específicas para o agente que vai modificar o repositório

## 15.1. Inspecionar antes de criar

Como ponto de partida, verificar se estes arquivos e componentes ainda
existem e qual é sua responsabilidade atual:

-   `ai-agent/app/agent/interpreter.py`
-   `ai-agent/app/agent/read_plan.py`
-   `ai-agent/app/schemas/read_plan.py`
-   `backend/app/schemas/genai_plan.py`
-   `ai-agent/app/profiles/grid360_gold.py`
-   `ai-agent/app/agent/orchestrator.py`
-   `ai-agent/app/generation/prompts.py`
-   `ai-agent/app/generation/selection.py`
-   `ai-agent/app/agent/evidence_guard.py`
-   `backend/app/services/genai_executor.py`
-   `ai-agent/app/gold_runtime.py`
-   `frontend/src/features/assistente/api.ts`

Esses caminhos são referências do levantamento anterior, não garantia de
que permaneçam iguais. Confirmar a estrutura real antes de editar.

## 15.2. Não criar uma segunda fonte de verdade

Antes de criar novo catálogo, glossário, resolver ou serviço:

-   Procurar implementações existentes.
-   Conferir o formato atual dos contratos.
-   Conferir se há aliases já registrados.
-   Conferir como o catálogo é carregado.
-   Conferir se a recuperação semântica já existe.
-   Conferir como o executor recebe os planos.
-   Conferir como a auditoria registra as decisões.

Reaproveitar o que estiver correto. Evitar duplicar glossário no prompt,
no código e em arquivos independentes.

## 15.3. Mudanças devem atravessar o fluxo completo

Quando um novo conceito for habilitado, conferir todas as fronteiras:

1.  Catálogo semântico.
2.  Recuperação de contexto.
3.  Interpretação.
4.  Contrato de geração.
5.  SQL Generator.
6.  Validador estrutural.
7.  Validador semântico.
8.  Executor.
9.  Normalização/proveniência.
10. Insight Generator.
11. Contrato da API.
12. Portal.
13. Benchmark e testes.
14. Documentação.

Não declarar uma métrica suportada porque o prompt passou a
reconhecê-la. Ela só está suportada quando funciona de ponta a ponta.

## 15.4. Não alterar a F1 por acidente

-   Não ampliar automaticamente a F1 para consumo, GD, interrupções ou
    atendimento.
-   Não usar campos fora da allowlist.
-   Não criar JOIN novo sem prova de cardinalidade.
-   Não inferir métricas ausentes a partir de colunas parecidas.
-   Não trocar o domínio de uma pergunta para produzir alguma resposta.
-   Registrar propostas de expansão como pendências separadas, com
    justificativa e testes necessários.

## 15.5. Entrega de cada etapa

Ao concluir uma etapa, apresentar:

-   Arquivos alterados.
-   Responsabilidade de cada alteração.
-   Decisões semânticas implementadas.
-   Testes adicionados.
-   Comandos executados.
-   Resultado real dos testes.
-   Limitações restantes.
-   Mudanças de contrato.
-   Riscos e rollback, se aplicável.

Se um teste não puder ser executado, declarar isso explicitamente. Não
marcar como aprovado.

------------------------------------------------------------------------

# 16. Critérios globais de aceite

A implementação só deve ser considerada concluída quando:

## Compreensão semântica

-   [ ] Paráfrases e termos convencionais são mapeados para conceitos
    canônicos.
-   [ ] "Volume" é interpretado pelo contexto, sem mapeamento universal
    para consumo medido ou energia faturada.
-   [ ] "Volume residencial" no diagnóstico de Henrique é resolvido
    contextualmente como volume de energia faturada residencial, se a
    métrica específica estiver comprovada e autorizada.
-   [ ] "Volume residencial" não é alias incondicional de
    `energy.measured_consumption`.
-   [ ] Receita faturada é distinta de arrecadação/pagamento.
-   [ ] Tarifa média efetiva é distinta de tarifa homologada.
-   [ ] Chamado é distinto de reclamação.
-   [ ] Contagem de ocorrências é distinta de DEC/FEC.
-   [ ] GD/solar respeita as limitações do cadastro e das flags.

## Interpretação temporal

-   [ ] Última competência é resolvida pela publicação Gold.
-   [ ] Junho/2026 é usado para a publicação atual confirmada.
-   [ ] Últimos 12 meses são jul/2025--jun/2026.
-   [ ] Os 12 meses anteriores são jul/2024--jun/2025.
-   [ ] Primeiro ano da base não é confundido com os 12 meses
    anteriores.
-   [ ] Comparação sazonal usa os mesmos meses do ano anterior.
-   [ ] Período explícito é respeitado.
-   [ ] "Há N meses" é distinguido de "nos últimos N meses".
-   [ ] Lacunas e períodos parciais são identificados.

## Cobertura e segurança

-   [ ] Gold e F1 possuem matrizes de cobertura separadas.
-   [ ] Conceitos fora da F1 são reconhecidos sem execução.
-   [ ] Métricas inexistentes não são inventadas.
-   [ ] SQL passa por validação estrutural e semântica.
-   [ ] Backend mantém autoridade de execução.
-   [ ] Banco usa acesso read-only.
-   [ ] JOINs não duplicam medidas.
-   [ ] Autorização não depende do LLM.

## Respostas e avaliação

-   [ ] Respostas mostram período, unidade e filtros.
-   [ ] Percentuais e diferenças são calculados deterministicamente.
-   [ ] Zero, nulo, vazio e ausência de cobertura são distintos.
-   [ ] Rankings usam o critério solicitado.
-   [ ] Afirmações causais não são inventadas.
-   [ ] Tabelas, gráficos e narrativa usam os mesmos resultados.
-   [ ] Benchmark mede intenção, SQL, resultado, recusa, esclarecimento,
    custo e latência.
-   [ ] Existe conjunto reservado de perguntas inéditas.
-   [ ] Não há regressão relevante nas perguntas já suportadas.

------------------------------------------------------------------------

# 17. Decisões que precisam ser confirmadas durante a inspeção

O agente deve preencher esta tabela com evidência real do repositório
antes de finalizar a implementação:

  ---------------------------------------------------------------------
  Decisão                            Estado esperado
  ---------------------------------- ----------------------------------
  Quais métricas exatas a F1 de      Confirmar em
  faturamento libera?                `genai-domain-implementation.md` e
                                     código

  `consumo_total_kwh` está na F1 ou  Confirmar
  apenas na Gold?

  Qual tabela/view física fornece    Confirmar
  receita faturada?

  `tarifa_media_efetiva` está        Confirmar
  publicada e qual seu cálculo?

  A competência é armazenada como    Confirmar no contrato físico
  texto `YYYY-MM` ou tipo de data?

  Quais dimensões de município,      Confirmar
  bairro e classe estão liberadas?

  Quais joins são permitidos e com   Confirmar
  quais cardinalidades?

  A flag                             Confirmar
  `queda_consumo_superior_30_pct`
  está publicada na versão consumida
  pelo Backend?

  A flag usa jul/2022--jun/2023      Confirmar no catálogo
  contra jul/2025--jun/2026?

  Existe métrica de receita          Confirmar
  paga/arrecadada?

  Há cobertura mensal por UC para    Confirmar
  recalcular a janela semestral de
  GD?

  Qual é a última competência        Confirmar
  completa por tabela/domínio?

  Quais estados de erro já existem   Reutilizar ou versionar
  nos contratos da API?

  Quais métricas e dimensões são     Documentar e testar
  compatíveis na primeira fatia?
  ---------------------------------------------------------------------

Se a resposta não puder ser encontrada, manter a decisão como pendente.
Não completar a tabela com suposições.

------------------------------------------------------------------------

# 18. Referências do projeto

Consultar as versões vigentes no checkout:

-   `TODO_3_Text_to_SQL_Generativo.md`
-   `PRD.md`
-   `dicionario_gold.md`
-   `gold-catalog.md`
-   `contracts/genai-domain-implementation.md`
-   `gold-coverage-v0.md`
-   Contratos de execução, coordenação, chat, auditoria, follow-up e
    memória.
-   ADRs de propriedade da consulta, janelas relativas e continuidade.
-   Código de catálogo/runtime Gold, gerador, validador, executor e
    portal.

Referência de negócio:

-   **Case Final V-Energy Grid 360**, especialmente o contexto de
    Henrique, o glossário do setor, as necessidades de faturamento, a
    pergunta de GD de Patrícia e os requisitos de IA.
-   **Premissa confirmada pelo responsável pelo projeto:** a última
    competência disponível da base é junho de 2026.
-   **Levantamento de vocabulário apresentado para revisão:** candidatos
    `consumo_total_kwh`, `tarifa_media_efetiva` e
    `queda_consumo_superior_30_pct`, sujeitos à conferência documental e
    física.

------------------------------------------------------------------------

# 19. Instrução final de execução

Implemente a evolução com foco em compreensão semântica real, regras
temporais corretas e cobertura explícita.

Não tente resolver o problema apenas aumentando o prompt. Não cadastre
uma frase para cada pergunta. Não amplie a F1 sem evidência. Não use uma
métrica como substituta de outra. Não trate SQL executável como sinônimo
de análise correta.

O comportamento desejado é:

1.  O usuário fala naturalmente, inclusive com termos coloquiais.
2.  O agente entende o conceito de negócio pretendido.
3.  O catálogo identifica a métrica canônica e suas limitações.
4.  O sistema identifica se a capacidade está disponível na F1.
5.  O resolver temporal define as competências e comparações corretas.
6.  O gerador cria SQL apenas com objetos autorizados.
7.  Os validadores verificam estrutura, semântica, cobertura e
    segurança.
8.  O Backend executa somente o que foi aprovado.
9.  Os resultados são normalizados e rastreáveis.
10. O Insight Generator explica os dados sem inventar números ou causas.
11. A resposta informa o que foi consultado e quais limitações existem.
12. Os testes demonstram que perguntas diferentes, mas semanticamente
    equivalentes, produzem a mesma interpretação correta.

**Definição de sucesso:** o agente deixa de depender de formulações
rígidas e passa a compreender diferentes maneiras de expressar uma
intenção de negócio, sem ultrapassar os limites reais dos dados e da
versão implementada.
