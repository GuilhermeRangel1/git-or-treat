# PRD — V-Energy Grid 360

**Versão:** 1.2 documental · **Data:** 16/10/2026 · **Estado da implementação:** não iniciada

**Origem:** case final Visagio, Rocket Lab 2026.2, fornecido pela pessoa usuária em dez páginas de imagem. Este documento reescreve o enunciado em texto pesquisável, organiza critérios de aceite e separa exigências do case de decisões futuras do time. As imagens não integram o repositório.  
**Classificação do material de origem:** o enunciado traz indicação de confidencialidade. O mesmo enunciado exige repositório GitHub público na entrega. Essa tensão precisa de confirmação com a organização antes da publicação de conteúdo ou dados do case.

## 0. Como usar este PRD

Este é o **registro canônico** de produto, requisitos e progresso. O texto em `docs/services/` explica responsabilidades técnicas, mas não substitui os critérios daqui. Cada requisito tem um ID estável, prioridade `Obrigatório` ou `Diferencial`, estado e forma de comprovação. Requisitos sem prova estão `Pendente`, mesmo que haja uma proposta de solução.

Leitura sugerida: seções 1–3 para o problema e o vocabulário; 4–5 para entradas e arquitetura; 6 para os IDs que controlam progresso; 7–9 para fluxos, definições e qualidade; 10–14 para execução, entrega e registro; seção 15 para a conferência de cobertura das dez páginas. Os guias de serviço detalham a futura implementação sem criar uma segunda fonte de requisitos.

Estados permitidos: `Pendente`, `Em andamento`, `Em validação`, `Concluído`, `Bloqueado`. Para concluir: implementação funcional, testes relevantes aprovados, evidência vinculada no [registro de progresso](#14-registro-de-progresso) e revisão humana do resultado de negócio. Não marcar itens apenas porque diretórios, mocks, notebooks incompletos ou contratos foram criados. Mudanças de escopo devem citar a decisão em `docs/decisions/`.

### 0.1 Natureza das afirmações

- **Exigência do case:** conteúdo obrigatório ou diferencial enunciado nas páginas recebidas.
- **Proposta de execução:** critério operacional adicional criado neste PRD para tornar a verificação objetiva; pode ser ajustado por decisão registrada sem enfraquecer a exigência original.
- **A definir:** informação ausente, ambígua ou dependente de inspeção do dataset. Não é fato estabelecido.

### 0.2 Mapa das páginas recebidas

| Página | Conteúdo incorporado neste PRD |
| --- | --- |
| 1 | Título, trilhas e aviso de confidencialidade |
| 2 | Contexto, falas da diretoria, objetivo e abertura do desafio de dados |
| 3 | Inventário de arquivos e definição da visão 360 |
| 4 | Fluxo conceitual e glossário setorial |
| 5 | Estrutura dos módulos e Bronze/Silver/Gold |
| 6 | Stack web e necessidades das áreas de negócio |
| 7 | IA, integração e entregáveis mínimos |
| 8 | Histórias de engenharia de dados e portal |
| 9 | Continuação das histórias, IA e diagnóstico da receita |
| 10 | Formato de entrega, README, acompanhamento, apresentação e orientações |

## 1. Contexto do negócio

A V-Energy é uma distribuidora de energia elétrica com concessão na região metropolitana do Recife. O case descreve aproximadamente **45 mil unidades consumidoras**, distribuídas em **14 municípios**, quase **300 bairros** e mais de **120 alimentadores**. Atende perfis residenciais, comerciais, industriais, rurais e de poder público. O histórico cobre quatro anos, com mais de **2,1 milhões de leituras** e **2,1 milhões de faturas** na narrativa. A tabela de arquivos detalha cerca de **46 mil registros de cadastro** e **2,18 milhões** em leituras e faturas; são números aproximados e não devem virar assertions de cardinalidade exata.

Os sistemas cresceram sem uma estratégia integrada. Cadastro comercial, medição, ocorrências de rede, atendimento e inspeções possuem versões desconectadas do cliente. Há exportações em CSV, JSON aninhado e planilhas Excel; chaves, formatos, duplicatas, ausências e inconsistências precisam ser examinados. Cada área usa números diferentes. O produto deve reconciliar essas fontes e oferecer uma fonte única de verdade rastreável.

A pergunta que originou o projeto é: **por que a receita residencial caiu 8% nos últimos 12 meses em comparação com o primeiro ano da base, enquanto a tarifa residencial acumulou reajuste homologado de 10,5% desde meados de 2022 e o volume de energia faturada caiu quase 4%?** O time deve explicar a variação com dados, decompondo preço e quantidade, investigando município, bairro e classe, e encerrando com recomendações de negócio e ordem de grandeza do impacto esperado. Os percentuais são premissas do enunciado; o diagnóstico final precisa reconciliá-los com os dados recebidos e declarar qualquer divergência.

A diretoria também quer que uma pessoa consiga fazer perguntas em português e receber uma resposta fundamentada sem abrir chamado técnico. Se o agente não souber, deve dizer que não sabe. A precisão da resposta e a integridade dos dados têm prioridade sobre funcionalidades extras.

### 1.1 Situação atual descrita no case

O cadastro comercial está em um sistema; a medição, em outro; as ocorrências de rede, em um terceiro. O call center exporta planilhas e as inspeções de campo chegam em arquivos Excel preenchidos manualmente. O faturamento é exportado em CSV com pontuação regional; o atendimento chega em JSON; cada área apresenta um número diferente para a mesma pergunta. A extração de TI é um retrato bruto dos sistemas, com inconsistências, duplicatas, valores ausentes e formatos não padronizados. Isso é parte intencional do desafio, não uma licença para ocultar registros ruins.

A visão 360 precisa conectar os fragmentos da mesma UC sem apagar diferenças entre cliente, ponto de consumo, medidor, fatura, ocorrência e chamado. O caso de uso que mais evidencia essa integração é o atendimento: hoje a pessoa atende uma ligação sem conseguir ver, em um só lugar, o comportamento recente da conta e os incidentes que possam explicá-la. A pergunta sobre receita, por sua vez, exige que totais de faturamento e de energia sejam comparáveis entre períodos e áreas.

### 1.2 Necessidades enunciadas pelas lideranças

| Pessoa / área | Problema relatado | Resposta que a solução deve permitir | IDs relacionados |
| --- | --- | --- | --- |
| Henrique Duarte, diretor comercial | Reajuste residencial homologado de 10,5% convive com volume faturado quase 4% menor e receita 8% menor. A diretoria não consegue localizar a razão. | Decompor a variação por preço/tarifa e quantidade; abrir por bairro, classe e município; perguntar rapidamente qual recorte mais perdeu volume e quanto cresceu a receita comercial em Jaboatão. | WEB-01, WEB-02, IA-01, IA-03, ENT-01 |
| Patrícia Lins, diretora de tecnologia | Exportações heterogêneas e números divergentes tornam cada pergunta dependente de engenharia de dados. | Criar fonte rastreável; integrar portal e IA; responder em português com base identificável; dizer claramente quando os dados não sustentam resposta. | DE-01 a DE-08, IA-01 a IA-06 |
| Camila Barreto, gerente de atendimento | Durante a ligação, o atendente precisa verificar se a conta realmente subiu e por quê. | Buscar por número da UC e ver cliente, consumo histórico, faturas em aberto, medidor, solar, interrupções e chamados na mesma jornada. | WEB-03, IA-01 |
| Rafael Coutinho, gerente de perdas | Mais de 200 inspeções por mês, menos da metade com irregularidade; deslocamentos improdutivos. | Ver fila de UCs suspeitas, motivo, energia potencialmente recuperável e prioridade; escolher quem vai a campo, abrir ordem e registrar resultado. | WEB-04, WEB-05, WEB-08, WEB-09 |
| Beatriz Farias, gerente de operação | A operação precisa localizar alimentadores/regiões com continuidade ruim e antecipar manutenção. | Acompanhar DEC e FEC por alimentador ao longo do tempo, identificar piores resultados e investigar ocorrências. | DE-05, WEB-06 |

Os números e exemplos acima são falas e contexto do enunciado, não medições reproduzidas pelo time. O relatório final deve distinguir “o case afirma” de “o dataset demonstrou”.

## 2. Visão e resultados esperados

O Grid 360 consolida **cadastro, medição, faturamento, rede e atendimento** em dados comuns e fornece um portal interno, um agente de IA, uma fila de inspeção, indicadores da qualidade do serviço e um diagnóstico da receita. Uma unidade consumidora (UC) é a entidade central para a visão de atendimento; outras granularidades — mês, fatura, leitura, medidor, alimentador, ocorrência, chamado e inspeção — precisam permanecer explícitas para evitar duplicação de métricas.

Resultados para cada público:

| Público | Decisão apoiada |
| --- | --- |
| Diretoria | Ver indicadores e comparações entre períodos; entender a receita e priorizar ações |
| Comercial | Separar variação tarifária de variação de energia e localizar quedas por município, bairro e classe |
| Atendimento | Localizar uma UC e responder com histórico completo durante a ligação |
| Perdas/inspeção | Priorizar suspeitas, estimar energia recuperável, emitir e acompanhar ordens |
| Operação | Acompanhar DEC/FEC por alimentador e localizar regiões críticas para manutenção |
| Analistas | Auditar dados, métricas e origem das respostas da IA |

**Não objetivos definidos pelo case:** faturamento transacional, despacho real de equipes, integração online com sistemas legados, operação em produção ou dados de tempo real. Se o time adicionar qualquer um, deve justificar escopo e risco. A sincronização de dados de produção não é fornecida; a agendação deve ser decidida e justificada.

### 2.1 Limites da visão 360

“Fonte única de verdade” significa definições consistentes e linhagem verificável para as perguntas deste case. Não significa que uma tabela única deva misturar fatos de granularidade diferente. A UC é o eixo da busca de atendimento; as medidas financeiras pertencem às faturas/competências, a energia às leituras e/ou faturas segundo a métrica definida, a continuidade às ocorrências e população atendida, e o trabalho de perdas às inspeções e ordens. A Gold pode conter mais de uma tabela ou visão. O time deve demonstrar que um recorte no portal e uma pergunta equivalente à IA resultam no mesmo número e apontam para a mesma versão dos dados.

### 2.2 Resultado mínimo observável

Ao final, a banca deve conseguir acompanhar uma extração pelo Workflow do Databricks até a Gold, abrir o portal alimentado pelo banco local, consultar uma UC, investigar pelo menos um recorte de receita, ver a fila/ordens e indicadores de continuidade, fazer uma pergunta em português ao agente e verificar a origem da resposta. O diagnóstico de receita deve fechar numericamente com as métricas utilizadas no portal e na IA. Esses fluxos são uma forma de demonstrar os requisitos; não impõem a quantidade de telas ou uma ordem única de navegação.

## 3. Glossário de domínio

| Termo | Definição do case e implicação para o produto |
| --- | --- |
| Unidade consumidora (UC) | Ponto que recebe energia e possui medidor; pode ser casa, loja ou fábrica. Um cliente pode ter várias UCs. É a entidade central da visão 360. |
| Competência | Mês de referência da leitura ou fatura. Uma fatura de competência 03/2025 cobra consumo de março, mesmo se paga em abril. Filtrar por competência não equivale a filtrar por data de pagamento. |
| Classe de consumo | Categoria da UC: residencial (B1), rural (B2), comercial e poder público (B3), industrial (A4, atendida em média tensão). A tarifa depende da classe e do subgrupo. |
| Alimentador | Circuito de média tensão que sai de subestação e abastece ruas e bairros. Uma falha pode afetar muitas UCs. |
| Bandeira tarifária | Acréscimo à tarifa nos patamares verde, amarela e vermelha 1/2, definidos pela ANEEL conforme custo de geração. Pode mudar receita sem mudar consumo. |
| Perdas não técnicas | Energia entregue e não faturada por furto, fraude no medidor ou erro de leitura/cadastro. A equipe de perdas tenta recuperar parte em inspeções. |
| Geração distribuída (GD) | Geração própria da UC, geralmente solar; energia gerada é abatida do consumo faturado. |
| DEC e FEC | Indicadores regulatórios de duração e frequência equivalentes de interrupção por UC. O case pede cálculo simplificado conforme a definição da ANEEL para comparar alimentadores e períodos internos, **sem afirmar conformidade com limites regulatórios reais**. Cada ocorrência corresponde a uma UC afetada, e os valores são consolidados por alimentador. |

Termos adicionais, campos reais, chaves de junção e fórmulas finais entram em `docs/data-dictionary.md` depois da inspeção dos arquivos. Não preencher com suposições não verificadas.

## 4. Dados de origem e contrato de ingestão

A extração completa estará em um `.zip` anexo à atividade na plataforma da UniVisagio. Os arquivos ainda não estão neste repositório. Todos os oito conjuntos abaixo devem entrar na camada Bronze, preservando exatamente o conteúdo extraído dos sistemas de origem, inclusive valores problemáticos e estrutura original. O formato físico das tabelas Bronze é Delta no Databricks.

| Conjunto | Formato | Volume aproximado | Significado |
| --- | --- | ---: | --- |
| `unidades_consumidoras.csv` | CSV | 46 mil registros | Cadastro de UCs e fonte central de relacionamento |
| `leituras/` (5 arquivos) | CSV particionado por ano | 2,18 milhões de registros | Medição mensal: leitura anterior, atual e consumo apurado |
| `faturas.csv` | CSV | 2,18 milhões de registros | Faturamento mensal, bandeira, vencimento e pagamento |
| `medidores.csv` | CSV | 52 mil registros | Instalação, retirada e manutenção de medidores |
| `ocorrencias_rede.csv` | CSV | 180 mil registros | Interrupções, causa e duração |
| `atendimentos.json` | JSON aninhado | 319 mil registros | Chamados, tratativas e satisfação |
| `geracao_distribuida.csv` | CSV | 3,5 mil registros | UCs com geração solar e potência instalada |
| `inspecoes.xlsx` | XLSX, 3 abas | 1,4 mil registros | Inspeções de campo e resultado da fiscalização |

### 4.1 Regras mínimas de tratamento

1. Identificar encoding, delimitador, separador decimal, datas, timezone, nomes de colunas e variantes por arquivo/ano.
2. Detectar nulos, duplicatas, valores impossíveis, identificadores órfãos, datas fora de ordem, medidores sem vínculo e relações multiplicadoras.
3. Documentar cada correção, exclusão, imputação ou quarentena com contagem antes/depois e justificativa. Preservar rastreio até a linha bruta.
4. Proteger métricas contra joins muitos-para-muitos. Agregar cada fato na granularidade pretendida antes de unir quando necessário.
5. Distinguir leitura, energia consumida, energia faturada, valor faturado e valor pago. Uma UC pode ter mais de uma fatura/medidor/chamado no tempo.
6. Não transformar valores ausentes em zero sem regra de negócio explícita.
7. Publicar dicionário da camada Gold com fórmula, unidade, granularidade, fonte, filtros, tratamentos e limitações de cada métrica.

Essas regras tornam verificáveis as exigências de qualidade e integridade do case; políticas exatas de deduplicação e métricas dependem do dataset real.

### 4.2 Perfil mínimo de cada fonte, antes de definir o modelo

O inventário abaixo especifica perguntas de inspeção; ele **não afirma** que esses campos ou chaves existam. Cada resposta deve ser preenchida em relatório de perfil com nome real da coluna, distribuição, exemplos anonimizados quando permitido e regra de tratamento. Se um vínculo necessário estiver ausente, registrar o limite do requisito afetado.

| Fonte | Conferir ao receber o arquivo | Relações e riscos a provar |
| --- | --- | --- |
| Cadastro de UCs | Identificador, cliente, município/bairro, classe/subgrupo, situação e eventuais datas de vigência. | Unicidade e mudança cadastral no tempo; endereços ou pessoas duplicadas não devem fundir UCs distintas. |
| Cinco arquivos de leituras | Ano e competências efetivas de cada arquivo, UC/medidor, leitura anterior/atual, consumo apurado, unidades e ajustes. | Sobreposição entre anos, leituras repetidas, troca de medidor, leitura decrescente, lacunas de competência e diferença entre consumo medido e faturado. |
| Faturas | Identificadores, UC, competência, valor, energia, bandeira, vencimento, pagamento, cancelamento/ajuste quando presentes. | Mais de uma fatura por UC/competência, status, sinal de estorno, distinção entre faturamento e recebimento, impossibilidade de calcular tarifa homologada apenas com preço efetivo. |
| Medidores | Identificador, UC vinculada e datas de instalação, retirada ou manutenção. | Intervalos sobrepostos, medidor atribuído a várias UCs, vínculo histórico versus medidor atual. |
| Ocorrências de rede | Identificador, início/fim/duração, causa, UC afetada e alimentador quando presentes. | Eventos duplicados, duração inválida, vínculo temporal UC–alimentador e denominador do DEC/FEC. |
| Atendimentos JSON | Estrutura aninhada, identificador de chamado, UC, data, tratativas, status e nota de satisfação quando presentes. | Explosão de listas aninhadas sem multiplicar chamados; informações textuais podem conter dados pessoais ou instruções maliciosas. |
| Geração distribuída | UC, tecnologia, potência, datas de instalação/conexão e séries de energia, se existirem. | Potência instalada não é energia gerada nem compensada; efeito na conta exige medida temporal apropriada. |
| Três abas de inspeções | Nome/finalidade de cada aba, UC/ordem, datas, motivo, resultado e energia apurada, se existirem. | Abas com grãos diferentes, preenchimento manual inconsistente, inspeção sem resultado, irregularidade suspeita versus confirmada. |

### 4.3 Livro de reconciliação da ingestão

Para cada fonte e lote, registrar: nome e versão/hash do arquivo; quantidade de linhas/objetos/abas de origem; registros lidos; falhas de parse; duplicatas identificadas; registros corrigidos, quarentenados e descartados; total aceito na Silver; total publicado nas Gold relevantes; motivo da diferença. Contagens não devem ser somadas entre entidades de grãos diferentes. Preservar acesso à linha de origem no ambiente autorizado para investigar divergências, sem incluir dados brutos no Git.

Uma regra nova de limpeza precisa declarar qual problema resolve, como decide entre valores concorrentes, se altera métricas históricas e qual amostra independente confirma a decisão. A soma de antes/depois deve fechar inclusive para registros rejeitados. Para valores monetários e energia, reconciliar também somas por competência e por classe; pequenas diferenças de arredondamento precisam ter regra explícita. O relatório de perfil fica ligado a DE-02/DE-03 e o dicionário Gold a DE-08.

## 5. Arquitetura e módulos

```text
8 conjuntos brutos
   ↓ Databricks / PySpark
Bronze (Delta, original) → Silver (tratado e relacionado) → Gold (métricas de negócio)
                                                        ↓ exportação CSV
                                            banco local SQLite ou PostgreSQL
                                               ↓                  ↓
                                         API FastAPI         agente Text-to-SQL
                                               ↓                  ↓
                                          portal React + TypeScript / Vite
                                               ↓
                               dashboards, visão UC, inspeção, operação, insights

Gold + análises → diagnóstico fundamentado da receita → apresentação à diretoria
```

O case permite **SQLite, PostgreSQL ou outro banco local justificado**. PostgreSQL é preferível se o time precisar de concorrência, recursos analíticos ou controle de acesso mais robusto; não é escolha fechada. O case recomenda **Gemini 3.1 Flash-Lite** para IA e admite outros modelos por OpenRouter. Framework de agente (PydanticAI, LangChain, LangGraph, LlamaIndex, CrewAI etc.) é escolha do time. Não introduzir dependência de Supabase como produto sem decisão: a skill da Supabase instalada aqui é um guia de PostgreSQL e só se aplica se Postgres for escolhido.

### Fronteiras e contratos entre módulos

| Transferência | O que deve atravessar a fronteira | Como conferir |
| --- | --- | --- |
| Bronze → Silver | Registros de todas as fontes, com tratamento e exceções rastreados | Contagens por arquivo/aba/competência e relatório de qualidade |
| Silver → Gold | Fatos/dimensões ou agregados com grão e fórmulas definidos | Unicidade, relacionamento e somas reconciliadas |
| Gold → CSV → banco local | Todas as tabelas necessárias aos requisitos do portal, IA e diagnóstico | Esquema, chaves, contagens, totais, lote e reexecução sem duplicatas |
| Banco → FastAPI → portal | Dados, filtros, período, unidade, atualização e estado de ausência/erro | Mesmo recorte retorna o mesmo total em API, Gold e tela |
| Banco → agente → portal | Consulta segura, resultado, fonte, período, filtros e limites da interpretação | Reproduzir resposta por consulta/consulta equivalente e testar recusa |
| Gold → diagnóstico → apresentação | Métricas e decomposição com definição idêntica à usada no produto | Tabelas/figuras fecham com Gold e perguntas da banca têm trilha |

O banco local é a ponte de execução para o portal e a IA, não uma nova definição independente dos indicadores. Dados operacionais criados no portal, como ordens de inspeção e resultados digitados, precisam ser separados das tabelas analíticas exportadas. O mecanismo de atualização desses dados operacionais e a possível incorporação a futuras Gold ficam a definir; não sobrescrever a extração histórica para simular sincronização.

### 5.1 Engenharia de dados

Toda a transformação deve ocorrer no Databricks com PySpark. A camada Bronze ingere os oito conjuntos sem alterar conteúdo. A Silver limpa, padroniza, enriquece e garante integridade referencial. A Gold consolida tabelas para perguntas de negócio, portal e IA; sua modelagem fica a critério do time e deve justificar granularidade e métricas. Gold é exportada em CSV e carregada no banco local. Um Databricks Workflow (Job) orquestra as três camadas e pode ser executado novamente de ponta a ponta. O time deve propor e justificar uma agenda de atualização para a produção, embora o case entregue uma extração única.

### 5.2 Portal web

O portal interno recebe os dados tratados no banco local. Stack indicada: React + TypeScript com Vite, FastAPI em Python, banco SQLite ou PostgreSQL. Deve oferecer indicadores e comparação temporal, decomposição da receita, visão 360 por UC, fila de inspeção, gestão das ordens, continuidade do serviço, filtros/exportações onde pedidos, acesso ao agente e insights de IA contextualizados. A quantidade de telas, navegação e visualizações é decisão de produto desde que cada história seja atendida.

### 5.3 Inteligência artificial

O agente conversacional recebe perguntas em português, traduz para consultas somente leitura ao banco Gold e responde de forma clara e fundamentada. Deve explicar números, unidades, filtros, período, fonte e limites. Precisa compreender termos cotidianos como “conta de luz” e “falta de luz”. A IA também gera insight contextual em pelo menos uma tela do portal. O agente deve reconhecer falta de informação, não inventar dado e não executar ações de escrita. Deve haver forma de auditar como cada resposta foi produzida.

### 5.4 Diagnóstico de negócio

Cada time deve responder à pergunta sobre queda de receita residencial. A explicação tem de separar os efeitos de preço/tarifa e volume, sustentar causas com dados identificados, estimar ordem de grandeza do impacto das recomendações e ser comunicável à diretoria na apresentação final. Artefatos textuais do diagnóstico ficam em `docs/`; a apresentação pode ser produzida posteriormente conforme regras da atividade. Uma hipótese plausível não substitui prova nos dados.

## 6. Histórias, critérios de aceite e rastreabilidade

### 6.1 Engenharia de dados — DE

| ID | Prioridade | Estado | Requisito e critérios de aceite |
| --- | --- | --- | --- |
| DE-01 | Obrigatório | Pendente | **Ingerir tudo em Bronze.** Os oito conjuntos, incluindo cinco arquivos de leitura e três abas de inspeção, estão em Delta; linhas, colunas, valores e arquivos de origem são rastreáveis. Diferenças de parse e rejeições são contadas e explicadas. |
| DE-02 | Obrigatório | Pendente | **Silver confiável.** Perfil de qualidade por fonte, regras de limpeza/padronização, contagens antes/depois e exceções documentadas; datas, classes, identificadores e medidas podem ser usados com significado consistente. |
| DE-03 | Obrigatório | Pendente | **Integridade referencial.** Medição, faturamento e cadastro possuem vínculos válidos ou exceções explicitamente segregadas; verificações detectam órfãos e multiplicação indevida de fatos. |
| DE-04 | Obrigatório | Pendente | **Gold para perguntas de negócio.** Tabelas consolidadas suportam indicadores, receita, visão UC, inspeção, rede e IA; granularidade, fórmulas e escolhas de modelagem estão documentadas. |
| DE-05 | Obrigatório | Pendente | **DEC/FEC por alimentador.** Implementar a definição simplificada descrita no case/ANEEL com numerador, denominador, janela e UC afetada explícitos; conferir amostras e não apresentar resultado como conformidade regulatória oficial. |
| DE-06 | Obrigatório | Pendente | **Exportar Gold ao banco local.** CSVs de Gold podem ser carregados novamente sem duplicar resultados; conferir esquema, contagens, chaves e agregados entre Databricks e banco. |
| DE-07 | Obrigatório | Pendente | **Orquestrar.** Databricks Workflow liga Bronze → Silver → Gold → exportação, possui dependências, logs de falha e execução reproduzível de ponta a ponta; arquivo de definição versionado. |
| DE-08 | Obrigatório | Pendente | **Dicionário Gold.** Toda tabela e métrica exposta ao portal/IA tem definição, tipo, unidade, granularidade, origem, transformação, chave e limitação em `docs/data-dictionary.md`. |
| DE-09 | Diferencial | Pendente | **Testes automatizados no pipeline.** Regras críticas de qualidade falham explicitamente antes de publicar Gold, incluindo unicidade, integridade, intervalos e reconciliação de totais. |

### 6.2 Portal web e backend — WEB

| ID | Prioridade | Estado | Requisito e critérios de aceite |
| --- | --- | --- | --- |
| WEB-01 | Obrigatório | Pendente | **Indicadores gerais.** A diretoria vê métricas principais com definição, unidade, competência, filtros e comparação entre períodos; uma amostra deve reconciliar com Gold. |
| WEB-02 | Obrigatório | Pendente | **Diagnóstico explorável da receita.** Comercial investiga a variação por município, bairro e classe, separando preço/tarifa e energia/volume; recortes e totais se reconciliam, com aviso para bases insuficientes. |
| WEB-03 | Obrigatório | Pendente | **Visão 360 da UC.** Busca por número de UC mostra cliente/cadastro, consumo histórico, faturas, medidor instalado/histórico, GD, interrupções e chamados em uma tela coerente; ausência de dado é explícita. |
| WEB-04 | Obrigatório | Pendente | **Fila de inspeção.** Unidades suspeitas aparecem ordenadas por prioridade, com motivo, indicadores usados e estimativa de energia a recuperar. Critério de priorização é documentado e auditável. |
| WEB-05 | Obrigatório | Pendente | **Ordens de inspeção.** A partir da fila, usuário cria ordem, altera status, registra resultado de campo e cancela ordem desnecessária; transições inválidas e repetição indevida são impedidas. |
| WEB-06 | Obrigatório | Pendente | **Operação DEC/FEC.** Gerente visualiza evolução por alimentador e identifica piores regiões; números remetem à mesma definição Gold e a ausência de denominador adequado é tratada. |
| WEB-07 | Obrigatório | Pendente | **Filtro e recorte.** Usuário filtra informações conforme necessidade, mantém contexto visível e entende quais filtros afetam cada gráfico/tabela. |
| WEB-08 | Diferencial | Pendente | **Exportar fila de inspeção.** O arquivo reflete ordem, filtros e dados exibidos, com proteção de acesso e formato documentado. |
| WEB-09 | Diferencial | Pendente | **Importar planilha de campo.** Upload valida colunas/linhas, apresenta erros, evita duplicação e grava resultados em formato digital auditável. |
| WEB-10 | Diferencial | Pendente | **Perfis.** Entrada e autorização por cargo restringem telas e ações; perfis e permissões estão documentados e testados. |
| WEB-11 | Diferencial | Pendente | **Testes automatizados no backend.** Cobrem contratos, validação, filtros, autenticação se adotada, estados de ordens e casos de erro; execução repetível. |

### 6.3 Inteligência artificial — IA

| ID | Prioridade | Estado | Requisito e critérios de aceite |
| --- | --- | --- | --- |
| IA-01 | Obrigatório | Pendente | **Perguntas em português.** Usuário não técnico pergunta sobre consumo, faturamento, interrupções e atendimento sem escrever SQL; perguntas representativas retornam números reconciliados com Gold. |
| IA-02 | Obrigatório | Pendente | **Vocabulário do negócio.** Perguntas como “conta de luz” e “falta de luz” são mapeadas corretamente para métricas/fontes; ambiguidades relevantes geram pergunta de esclarecimento. |
| IA-03 | Obrigatório | Pendente | **Resposta fundamentada.** Cada resposta quantitativa mostra período, filtros, unidade, fonte/consulta ou trilha equivalente e observações de qualidade; analista consegue reproduzir amostra. |
| IA-04 | Obrigatório | Pendente | **Insights dentro do portal.** Ao menos uma tela apresenta insight contextual gerado por IA para interpretar o dado exibido, com sinalização de base temporal e possibilidade de verificar os números. |
| IA-05 | Obrigatório | Pendente | **Agente acessível no portal.** Pessoa usuária conversa com a IA sem trocar de ferramenta; erros e indisponibilidade são comunicados. |
| IA-06 | Obrigatório | Pendente | **Somente leitura e limites.** IA não altera dados, não executa SQL arbitrário fora do esquema autorizado e responde “não sei”/explica insuficiência quando a evidência falta. Testes demonstram bloqueio de escrita e de perguntas fora do escopo. |
| IA-07 | Diferencial | Pendente | **Follow-up com contexto.** Usuário faz pergunta complementar e o agente mantém período, métrica e filtros relevantes sem confundir conversas. |
| IA-08 | Diferencial | Pendente | **Avaliação automática.** Conjunto versionado de perguntas e resultados esperados mede correção numérica, fundamentação e recusa adequada, com relatório de regressão. |

### 6.4 Diagnóstico, documentação e entrega — ENT

| ID | Prioridade | Estado | Requisito e critérios de aceite |
| --- | --- | --- | --- |
| ENT-01 | Obrigatório | Pendente | **Diagnóstico da receita.** Explica variação observada, identifica causas sustentadas pelos dados, separa efeitos de preço e volume, trata GD/bandeiras/pagamento quando relevantes, formula recomendações com impacto em ordem de grandeza e expõe incertezas. |
| ENT-02 | Obrigatório | Pendente | **Apresentação à diretoria.** Narrativa executiva concisa traz pergunta, método, evidência, causas, ações, impacto e limitações; demo da solução funcionando ao vivo. |
| ENT-03 | Obrigatório | Pendente | **Repositório organizado.** Toda solução avaliável está no GitHub público de entrega, com diretórios dos módulos, definição do Workflow e documentação; publicação depende da confirmação sobre confidencialidade. |
| ENT-04 | Obrigatório | Pendente | **README operacional.** Explica arquitetura/decisões, setup e execução local de cada módulo, evidência da execução do Databricks Workflow, links para dicionário/diagnóstico e hipóteses tomadas onde havia ambiguidade. |
| ENT-05 | Obrigatório | Pendente | **Status report intermediário.** Mostra progresso e hipóteses iniciais sobre receita, validando rumo antes da reta final conforme calendário comunicado pela organização. |

### 6.5 Entrega mínima integrada

O case cobra de todos os grupos: **pipeline Databricks completo Bronze → Silver → Gold; portal com telas principais funcionais; IA integrada; diagnóstico fundamentado; repositório GitHub público organizado e README completo.** Diferenciais não substituem nenhum desses cinco elementos. A integração precisa ser demonstrável no mesmo conjunto de dados, com números reconciliados entre camadas, API, portal, IA e apresentação.

## 7. Fluxos de uso obrigatórios

### 7.1 Diretoria: panorama e tendência

Selecionar períodos comparáveis e visualizar receita, energia faturada, consumo, UCs, continuidade e demais indicadores escolhidos. Cada KPI deve esclarecer se é faturado, pago, consumido ou entregue. Comparação por competência precisa usar janela coerente e exposição da base. A diretoria consegue navegar do agregado ao recorte sem perder os filtros.

### 7.2 Comercial: queda residencial

Partir da diferença de receita entre o primeiro ano disponível e os 12 meses mais recentes (definição exata após inspeção das competências), isolar classe residencial, decompor tarifa/preço efetivo e volume faturado, depois recortar por município/bairro/classe. Confirmar se a queda citada no enunciado se reproduz; se não, explicar cobertura, tratamento de qualidade ou base de comparação. Inspecionar hipóteses como GD, bandeiras, inadimplência, mix, perdas e cadastro apenas se os dados permitirem. O resultado é uma cadeia de evidências, não correlação apresentada como causalidade.

### 7.3 Atendimento: chamada sobre conta alta

Receber número de UC, encontrar cadastro, período atual e anterior de consumo, faturas, vencimento/pagamento, medidor, GD, interrupções e chamados. O atendente deve conseguir distinguir aumento real de consumo de tarifa/bandeira, eventuais leituras atípicas e problemas de continuidade, sempre mostrando quando não há dados suficientes. O fluxo precisa servir durante uma chamada, sem consultar cinco sistemas.

### 7.4 Perdas: inspeção priorizada

Consultar fila com motivo da suspeita e energia potencialmente recuperável; selecionar UC, criar ordem, designar/atualizar estado se o modelo operacional contemplar, registrar resultado e cancelar trabalho que perdeu sentido. Mostrar métricas úteis para evitar viagens improdutivas. A fila não pode usar rótulo de fraude comprovada antes de inspeção.

### 7.5 Operação: alimentadores críticos

Ver DEC/FEC internos por alimentador ao longo do tempo, ordenar piores resultados e investigar regiões/ocorrências. O portal deve distinguir interrupções registradas de cálculo regulatório oficial e não comparar com limites ANEEL reais sem base válida.

### 7.6 IA: pergunta natural e follow-up

Exemplos do case: quantas UCs com solar em Olinda tiveram queda de consumo acima de 30%; qual bairro mais perdeu volume residencial no último ano; quanto cresceu receita comercial em Jaboatão. O agente precisa entender entidade, classe, geografia, métrica e janela temporal, produzir consulta segura e resposta auditável, e pedir esclarecimento ou admitir ausência de evidência quando necessário. Follow-up contextual é diferencial.

### 7.7 Cenários de aceite transversais

Os cenários a seguir tornam as jornadas observáveis; são **propostas de verificação**, não telas ou endpoints prescritos pelo case.

| Cenário | Entrada/ação | Resultado observável | Ausência/erro a exercitar | IDs |
| --- | --- | --- | --- | --- |
| Comparar períodos | Selecionar duas janelas completas de competência e um recorte. | KPIs, unidades, denominadores e diferença absoluta/percentual visíveis; totais fecham com Gold. | Janela parcial, base zero, dado sem atualização ou recorte vazio não produz percentual enganoso. | WEB-01, WEB-07 |
| Achar a queda | Partir do total residencial, abrir município e bairro, ver efeito preço-volume. | Contribuição dos recortes fecha com total no mesmo universo; tarifa homologada e preço efetivo aparecem com nomes distintos. | Recorte sem clientes suficientes e classe ausente têm indicação explícita. | WEB-02, ENT-01 |
| Atender conta alta | Digitar UC informada por cliente, comparar meses e abrir fatura/medidor/GD/rede/chamados. | A pessoa consegue explicar o que os dados mostram e quais explicações são apenas hipóteses. | UC inexistente, cadastro sem fatura, medidor retirado, mês sem leitura e chamado aninhado não quebram a jornada. | WEB-03 |
| Priorizar campo | Abrir fila ordenada, ver razão da suspeita e energia estimada, criar ordem e registrar desfecho. | Prioridade e estimativa reproduzíveis; estado da ordem persiste e histórico fica auditável. | Repetição de clique, transição inválida e cancelamento de ordem já encerrada são tratados. | WEB-04, WEB-05 |
| Investigar continuidade | Selecionar período e alimentador, comparar DEC/FEC e abrir ocorrências relacionadas. | Fórmula, universo de UCs, janela e origem aparecem; ordenação dos piores é explicável. | Alimentador sem denominador confiável não recebe indicador falsamente preciso. | DE-05, WEB-06 |
| Perguntar à IA | Pergunta natural com geografia, classe e tempo, seguida de conferência independente. | Resposta em português com número, unidade, período, filtros, fonte e incerteza; o mesmo recorte fecha com Gold. | Pergunta impossível, ambígua ou pedindo alteração de dados gera esclarecimento/recusa adequada. | IA-01, IA-02, IA-03, IA-06 |
| Ver insight | Abrir tela escolhida com filtros definidos e pedir interpretação. | Insight se ancora no dado visível, identifica período/recorte e oferece caminho para verificar. | Mudança de filtro invalida ou atualiza o insight; falha do modelo não oculta o dado principal. | IA-04, IA-05 |

O fluxo de inspeção usa dados de duas naturezas: fila analítica derivada da Gold e ordens operacionais criadas depois. “Suspeita” não equivale a irregularidade comprovada. O fluxo de IA também deve passar por teste de consulta somente leitura com usuário de banco restrito, não apenas por inspeção do texto gerado pelo modelo.

## 8. Contratos de dados e métricas a definir antes da implementação

As definições abaixo são pontos de decisão obrigatórios para evitar números incompatíveis. Registrar conclusão no dicionário e, quando arquitetural, em ADR.

| Tema | Pergunta a resolver com os dados | Critério para a decisão |
| --- | --- | --- |
| Identidade da UC | Há uma chave única estável? Há mudanças cadastrais? | Join temporal correto, órfãos contados |
| Cliente x UC | É possível identificar cliente ou só UC? | Não exibir relação inventada |
| Competências | Quais meses existem nos cinco arquivos de leitura/faturas? | Janela histórica reproduzível |
| Consumo | Leitura atual − anterior coincide com consumo apurado? | Tratar trocas de medidor/ajustes sem zerar silenciosamente |
| Receita | Valor faturado, pago ou líquido? Impostos, multas e ajustes entram? | Nome e fórmula explícitos |
| Preço efetivo | Receita/energia faz sentido por classe/subgrupo? | Evitar divisão por zero e confusão com tarifa homologada |
| Decomposição preço-volume | Qual método separa efeitos e interação? | Soma dos componentes reconcilia com variação total |
| GD | Energia gerada, compensada ou apenas potência instalada? | Não atribuir efeito quantitativo sem série necessária |
| Suspeita de perdas | Há rótulos de inspeção suficientes e ausência de viés óbvio? | Fila explicável; nenhum falso diagnóstico de fraude |
| Energia recuperável | Qual referência/limite para estimativa? | Intervalo ou ordem de grandeza e incerteza |
| DEC/FEC | Denominador de UCs por alimentador e tratamento de períodos? | Implementar regra simplificada com teste manual |
| Dados pessoais | Quais campos identificáveis vêm no dataset? | Minimização na Gold, API, demo e exportação |

### 8.1 Contrato obrigatório para cada métrica publicada

Antes de uma métrica aparecer em API, portal, IA ou apresentação, seu registro no dicionário precisa responder: nome de negócio; população incluída/excluída; grão; período e relógio de referência; fórmula com unidade, denominador e arredondamento; fontes e transformações; tratamento de nulos/estornos; limite de qualidade; consulta ou cálculo independente de reconciliação; responsável pela definição. Um alias visível na tela deve remeter a esse mesmo registro. Mudanças de fórmula exigem nova verificação nos quatro consumidores.

| Família de métricas | Distinção que o time precisa preservar | Prova mínima antes de uso |
| --- | --- | --- |
| Receita | Faturado, pago e eventualmente líquido são grandezas diferentes; reajuste homologado não é preço médio efetivo. | Fechamento com faturas para competências escolhidas, incluindo estornos/ajustes quando existirem. |
| Energia | Leitura, consumo apurado, energia faturada, gerada e compensada podem divergir. | Unidade e origem de cada série, teste para troca de medidor e comparação com amostra de fatura. |
| Base de UCs | Cadastro total, UCs ativas no período e UCs com fatura/leitura não têm o mesmo denominador. | Regra temporal de atividade e contagem reconciliada por competência. |
| Variação percentual | Percentual depende de base e sinal; queda percentual pode ser grande em base pequena. | Valor inicial/final e absoluto exibidos, divisão por zero tratada, janela fechada. |
| Preço × volume | Método escolhido pode distribuir termo de interação de maneiras diferentes. | Componentes somam exatamente à variação de receita conforme arredondamento declarado. |
| Perdas e recuperação | Suspeita, irregularidade confirmada, energia não faturada e energia recuperável não são sinônimos. | Regra de prioridade e estimativa auditável, com limites e revisão contra inspeções. |
| Continuidade | DEC e FEC exigem duração/frequência e população afetada/atendida por período. | Cálculo manual de amostra, denominador por alimentador e rótulo de indicador simplificado. |

As definições finais dependem da inspeção do dataset. As opções nessa tabela são perguntas de contrato, não valores ou regras escolhidas antecipadamente.

## 9. Requisitos não funcionais e políticas de qualidade

### 9.1 Confiabilidade e auditoria

Os números exibidos devem ser reconciliáveis entre origem, Silver, Gold, banco, API, portal e agente. Qualquer filtro, join ou exclusão que mude totais deve ser documentado. A automação do pipeline deve ter logs, status de falha e opção de reexecução sem duplicação. Alterações em ordens de inspeção precisam de histórico suficiente para auditoria. O agente deve permitir rastrear fonte/consulta da resposta sem expor dados sensíveis desnecessários.

### 9.2 Segurança e privacidade

O portal é interno. O diferencial de perfis detalha controle por cargo; mesmo na entrega mínima, credenciais de Databricks, banco e modelo não podem estar no frontend nem no repositório. Queries do agente devem usar usuário de banco somente leitura, esquema/tabelas permitidos, limites de resultado e timeout. Entrada do usuário não pode virar SQL executável sem validação. Dados do case não devem ser publicados sem autorização. O hook de segredos é proteção adicional, não garantia absoluta.

### 9.3 Experiência e acessibilidade

As telas precisam ser legíveis para quem decide sob pressão: rótulos, unidades, período, comparação, estado vazio, erro e atualização visíveis. Busca por UC e filtros devem responder com feedback claro. Tabelas, gráficos e insights precisam de equivalente textual suficiente para interpretação; navegação por teclado e contraste devem ser verificados. A escolha do layout fica com o time e pode usar Figma; nenhum design é exigido nas páginas recebidas.

#### Preparação do protótipo — solicitação da pessoa usuária em 16/10/2026

Como orientação adicional de trabalho, criar o protótipo pelo **Figma MCP** em um arquivo Figma Design organizado em quatro páginas:

1. Componentes e estilos — modo claro.
2. Componentes e estilos — modo escuro.
3. Páginas e fluxos — modo claro.
4. Páginas e fluxos — modo escuro.

As páginas de fluxos conterão as telas necessárias às jornadas; essa organização não limita o portal a quatro telas. Componentes e tokens serão compartilhados entre os dois temas. A identidade visual será discutida após a criação da skill [git-or-treat-figma](../.agents/skills/git-or-treat-figma/SKILL.md), usando React Bits, Aceternity UI, Magic UI, Motion Primitives e Codrops como referências. A pessoa usuária escolheu uma direção inicial que combina estrutura técnica e atmosfera profunda no modo escuro com detalhes tecnológicos expressivos, mantendo também a versão clara. Paleta, tipografia, intensidade de movimento, dispositivos e diferenciais ainda não foram escolhidos. A skill e o protótipo são preparação: não substituem a aplicação integrada nem concluem requisitos WEB/IA/ENT.

### 9.4 Desempenho e volume

O banco e a API devem tratar aproximadamente 2,18 milhões de leituras e faturas sem trazer todo o histórico ao navegador. Aplicar paginação, agregação e índices conforme perfil real de consulta. Limiares de latência e carga não foram especificados no case; medir com dataset recebido e registrar metas realistas antes de marcar desempenho como aceito.

### 9.5 Testes e evidência

O mínimo de verificação por entrega inclui: teste da transformação/consulta/API/componente afetado, reconciliação com amostra ou total de controle, fluxo manual de usuário pertinente, lint/formatação quando a ferramenta existir, e revisão de segurança/segredos. Os diferenciais DE-09, WEB-11 e IA-08 pedem automação adicional. A ausência de dataset no repositório implica que validações numéricas de negócio só poderão ocorrer quando a extração for disponibilizada.

## 10. Dependências e sequência sugerida

1. Receber o `.zip`, autorização de uso e acesso ao Databricks; perfilar os oito conjuntos e resolver as decisões da seção 8.
2. Definir modelo de dados e métricas; implementar Bronze/Silver/Gold com dicionário e reconciliação.
3. Exportar Gold ao banco e criar API de leitura; estabelecer contratos para os fluxos do portal.
4. Construir portal incrementalmente: indicadores/receita, visão UC, inspeção, operação; incorporar IA e insights.
5. Rodar diagnóstico da receita continuamente desde o perfil inicial; fechar narrativa e recomendações depois da reconciliação.
6. Preparar relatório intermediário, README operacional, demo e apresentação final.

Esta é uma proposta de execução, não cronograma imposto. Entregas podem avançar em paralelo quando contratos e amostras estáveis existirem. A conclusão de um serviço não presume integração dos demais.

### 10.1 Marcos verificáveis entre equipes

| Marco | Condição para avançar com confiança | Documentos que devem refletir o resultado |
| --- | --- | --- |
| Perfil das fontes | Oito conjuntos inventariados; problemas e relacionamentos prováveis registrados; contagens brutas reconciliadas. | PRD (dependências/estado), relatório de qualidade e dicionário inicial. |
| Contrato Gold | Tabelas, grãos, chaves, fórmulas e amostras manuais suficientes para consumo dos fluxos prioritários. | `docs/data-dictionary.md`, guias de serviço e ADRs de decisões materiais. |
| Integração mínima | Workflow executa; Gold exporta e carrega; API e uma jornada do portal consultam o mesmo lote com totais iguais. | README operacional em evolução, evidência no PRD e contrato de API. |
| Cobertura do case | Diretoria, comercial, atendimento, perdas, operação e IA exercitados; cenários de ausência/erro tratados. | Tabela de IDs, registro de progresso, guias afetados e testes. |
| Diagnóstico defendível | Variação reconciliada, decomposição fechada, hipóteses julgadas e recomendações com impacto limitado pela evidência. | `docs/revenue-diagnosis.md`, dicionário e roteiro da apresentação. |
| Entrega final | Repositório permitido para publicação, README reproduzível, Workflow comprovado, demo e artefatos presentes. | README, PRD, status final e documentos de entrega. |

Cada marco é um ponto de integração, não um novo requisito obrigatório independente. O progresso dos IDs da seção 6 continua a determinar o estado oficial. Se uma condição falhar, registrar causa, responsável e próximo teste antes de tratar o marco como ultrapassado.

## 11. Formato de entrega e calendário do case

O case sugere estrutura `data-engineering/`, `backend/`, `frontend/`, `ai-agent/`, `docs/` e `README.md`; este repositório a espelha com guias documentais. O repositório GitHub deve ser público, organizado e ser o local oficial de entrega; tudo que não estiver nele não será avaliado. O README final deve incluir: descrição/decisões arquiteturais, configuração e execução local de cada módulo, comprovação de execução do Databricks Workflow, links para dicionário e diagnóstico, e hipóteses para pontos não explícitos.

Há status report intermediário para apresentar progresso e primeiras hipóteses à diretoria durante as semanas do projeto. O enunciado indica **entrega final em 04/11**, **apresentação prévia em 05/11** e **apresentação final à banca em 10/11, à tarde**; o horário final ainda seria definido. O ano não aparece ao lado dessas três datas nas páginas fornecidas (cabeçalho 2026.2); confirmar no calendário oficial antes de tratar as datas como compromisso vigente.

Formato da apresentação final: **15 minutos** para apresentar a solução, por slides, demonstração ao vivo ou combinação, com recomendação do case de demonstrar funcionando; depois **15 minutos** de perguntas técnicas e de negócio. Todos os membros devem estar preparados para responder. A apresentação prévia é para organização do Rocket Lab e padrinhos; a final, para banca avaliadora.

### 11.1 Conferência dos artefatos de entrega

| Artefato | Conteúdo verificável esperado | Estado inicial |
| --- | --- | --- |
| Repositório | Pastas de engenharia, backend, frontend, IA e docs; código e documentação necessários para avaliar a solução; histórico de trabalho coerente. | Estrutura documental criada; código de produto pendente. |
| Pipeline | Notebooks/arquivos de transformação, definição versionada do Workflow, dependências e parâmetros suficientes para repetir Bronze → Silver → Gold → exportação. | Pendente de dataset e acesso Databricks. |
| Banco local e portal | Carga reproduzível da Gold, instruções de configuração/execução, API e telas principais funcionando no mesmo conjunto de dados. | Pendente. |
| Agente de IA | Integrado ao portal, com consulta a Gold, respostas fundamentadas e pelo menos um insight embutido em tela. | Pendente. |
| Diagnóstico | Texto em `docs/revenue-diagnosis.md` com método, números reconciliados, causas sustentadas, recomendações e impacto estimado. | Modelo criado; achados pendentes. |
| Dicionário | Tabelas e métricas Gold com fórmulas, grãos, fontes e limitações. | Modelo criado; campos reais pendentes. |
| README final | Descrição, arquitetura e decisões, configuração/execução local de cada módulo, evidência de execução bem-sucedida do Workflow, links de dicionário e diagnóstico, hipóteses assumidas. | README de navegação documental; instruções operacionais pendentes. |
| Status report | Progresso real, demonstrações e primeiras hipóteses discutidas no ponto intermediário combinado com a organização. | Modelo criado; apresentação pendente. |
| Apresentação final | Narrativa de 15 minutos e preparação para 15 minutos de perguntas; solução preferencialmente demonstrada ao vivo. | Pendente. |

O README atual não deve ser confundido com o README operacional exigido para a entrega final. Evidência de Workflow deve conter identificação da execução e resultado, não apenas uma captura sem contexto. Links e artefatos finais devem estar no repositório que será avaliado, sujeitos à decisão de publicação da seção 12.

## 12. Premissas, ambiguidades e bloqueios iniciais

| ID | Situação | Consequência/ação |
| --- | --- | --- |
| P-01 | Dataset não fornecido junto com as imagens. | Não validar esquema, chaves, números reais ou hipóteses de receita até receber o `.zip`. |
| P-02 | Narrativa cita 45 mil UCs e >2,1 milhões de leituras/faturas; tabela cita 46 mil e 2,18 milhões. | Tratar como aproximações de apresentação; registrar contagem real por arquivo após ingestão. |
| P-03 | O texto sobre portal remete a “user stories da seção 6.2”, enquanto as páginas numeram essas histórias em 5.2. | IDs WEB deste PRD são a referência estável. |
| P-04 | SQL local: SQLite/PostgreSQL/outro; framework e modelo de IA ainda abertos. | Decidir por ADR com razões e consequências antes de acoplar módulos. |
| P-05 | Definição de DEC/FEC depende de campos e população de UCs por alimentador. | Documentar fórmula e limitar interpretação; não reivindicar cálculo regulatório oficial. |
| P-06 | Case exige GitHub público e imprime aviso de confidencialidade. | Confirmar permissão de publicação; evitar subir dataset e informação identificável. |
| P-07 | Não há ano explícito nas datas 04/11, 05/11 e 10/11. | Conferir calendário do programa. |
| P-08 | Não existe URL de Figma ou design entregue; a organização futura em quatro páginas e dois temas foi solicitada em 16/10/2026 (§9.3). | Skill de preparação criada; identidade visual, criação do arquivo pelo MCP e evidência do protótipo permanecem para a próxima etapa. Não assumir telas prontas ou conta conectada. |

## 13. Critérios de pronto por etapa

### Definição pronta para começar uma história

- ID, usuário e resultado pretendido claros.
- Fontes e campos necessários identificados ou dependência marcada.
- Critérios de aceite verificáveis e teste de negócio de amostra descrito.
- Decisões abertas documentadas, com responsável ou gatilho para resolução.

### Definição de concluído

- Comportamento real atende cada critério do ID, inclusive erros e ausência de dados.
- Testes relevantes passaram, com comandos/versões/resultado registrados.
- Métrica ou resposta numérica reconciliada com fonte confiável; interface revisada no fluxo real.
- Dicionário, contrato de API, guia do serviço e ADR atualizados quando afetados.
- Segurança, privacidade e secrets revisados; nenhum dado bruto ou credencial foi commitado.
- Entrada de evidência adicionada abaixo e estado do ID alterado para `Concluído` na mesma mudança.

## 14. Registro de progresso

**Marco atual (16/10/2026):** documentação e instruções para agentes criadas e ampliadas após conferência das dez páginas; nenhum requisito funcional DE/WEB/IA/ENT foi implementado ou validado. A instalação de skills e hooks é preparação do repositório e não atende um requisito do produto. Atualize as tabelas da seção 6 e acrescente uma entrada por lote de entrega.

### 2026-10-16 — preparação de WEB-01 a WEB-07 e IA-01 a IA-06 — skill de prototipação

- Estado anterior → novo estado: requisitos funcionais permanecem `Pendente`; skill própria criada como preparação documental.
- Mudança observável para usuário/negócio: instrução reutilizável para planejar e revisar o protótipo, com quatro páginas Figma e temas claro/escuro compartilhando componentes e tokens; direção visual inicial híbrida registrada em §9.3, com escolhas específicas ainda abertas.
- Arquivos/commit/PR: branch `feat/git-or-treat-figma`; [skill](../.agents/skills/git-or-treat-figma/SKILL.md), seus três guias de apoio, metadados Codex e adaptador Claude; [catálogo de ferramentas](agents/tooling.md#skill-própria-de-prototipação) e §9.3/§12 deste PRD. Sem publicação ou arquivo Figma criado nesta etapa.
- Dados usados: PRD, guias frontend/backend/IA e dicionário ainda sem esquema real; consulta às cinco referências oficiais em 16/10/2026, com a limitação de abertura de Motion Primitives documentada no guia. Nenhum dataset ou dado pessoal utilizado.
- Verificações: `python -X utf8 <pasta-da-skill-creator>/scripts/quick_validate.py .agents/skills/git-or-treat-figma` aprovou nome/frontmatter/estrutura; bloco Python do workflow `.github/workflows/quality.yml` executado localmente aprovou configurações, seis imports e links em 33 documentos; `python -m compileall -q .hooks` passou. Links internos da skill e correspondência do adaptador foram conferidos. `git diff --check` inicialmente detectou espaços finais no cabeçalho alterado, corrigidos antes da verificação final aprovada.
- Reconciliação ou amostra manual: teste de comportamento por subagente antes/depois da skill, sem escrita externa. Na revisão com a skill, o plano propôs quatro páginas com uma biblioteca e dois modos; distinguiu números do enunciado de achados e limitou paralelismo à análise, mantendo futura escrita coordenada no Figma. Uma ambiguidade sobre iniciar entrevista em pedidos preparatórios foi corrigida e revalidada.
- Critérios de aceite revisados e pendências: matriz cobre jornadas obrigatórias, estados alternativos e diferenciais selecionáveis. Essa revisão é documental; nenhuma integração, cálculo Gold, controle de acesso ou requisito funcional foi validado. Pendentes direção visual, dispositivo, diferenciais, plano/acesso e criação via Figma MCP, capturas e navegação do protótipo.
- Responsável/revisor: Codex (autoria e verificações locais); subagente de revisão comportamental; revisão humana do resultado e critérios funcionais pendente.

### Modelo de entrada

```markdown
### AAAA-MM-DD — ID(s) — resumo
- Estado anterior → novo estado:
- Mudança observável para usuário/negócio:
- Arquivos/commit/PR:
- Dados usados (versão/fonte; sem anexar dados sensíveis):
- Verificações: comando ou procedimento, resultado e data:
- Reconciliação ou amostra manual:
- Critérios de aceite revisados e pendências:
- Responsável/revisor:
```

Se o teste falhar ou o resultado não for reproduzível, permaneça em `Em validação` ou `Bloqueado` e descreva o impedimento. Uma evidência não substitui outras exigências do mesmo ID.

## 15. Conferência de cobertura do enunciado por página

Esta matriz é um índice de auditoria do material recebido. Ela ajuda a localizar onde cada ponto entrou no PRD e a perceber omissões quando o case for revisitado. O texto acima continua sendo a especificação; a matriz não cria requisitos novos. Páginas se referem às dez imagens fornecidas pela pessoa usuária, que não são versionadas.

| Página | Conteúdo específico preservado | Onde aparece / como será demonstrado |
| --- | --- | --- |
| 1 | Visagio, Rocket Lab 2026.2; caso final V-Energy Grid 360; três trilhas — engenharia de dados, web e IA — e aviso de confidencialidade. | Abertura, seções 5 e 12; decisão de publicação ainda aberta. |
| 2 | Distribuidora na região metropolitana do Recife; 45 mil UCs, 14 municípios, quase 300 bairros, mais de 120 alimentadores, quatro anos, >2,1 milhões de leituras/faturas; fontes isoladas; reajuste 10,5%, volume quase −4%, receita −8%; missão de construir e defender solução integrada. | Seções 1, 1.1, 1.2, 2, 5.4 e 7.2; reconciliação em ENT-01. |
| 3 | Extração bruta e heterogênea; oito conjuntos, com formato/volume/função, `.zip` disponibilizado na atividade; visão 360 que une consumo, faturamento, continuidade e atendimento. | Seções 2 e 4; DE-01 a DE-04, WEB-03. |
| 4 | Fluxo conceitual de cinco origens para Grid 360, portal, IA, diagnóstico, fila e qualidade; glossário de UC, competência, classe, alimentador, bandeira, perdas, GD e DEC/FEC. | Seções 2, 3 e 5; vínculos testados nos cenários de 7.7. |
| 5 | Três módulos técnicos e um entregável de negócio; Bronze original, Silver tratada, Gold modelada; Databricks/PySpark/Delta, exportação CSV ao banco local, Workflow e agenda futura justificada. | Seções 4 e 5; DE-01 a DE-08 e ENT-01. |
| 6 | React/TypeScript/Vite, FastAPI, SQLite/PostgreSQL ou opção justificada; falas concretas de comercial, atendimento, perdas e operação; liberdade de dividir telas com justificativa. | Seções 1.2, 5.2, 6.2 e 7; WEB-01 a WEB-07. |
| 7 | Agente Text-to-SQL em português, insight dentro do portal, integração Python/FastAPI, opções de framework, modelo recomendado e OpenRouter; obrigação de dizer “não sei”; entrega integrada mínima. | Seções 5.3, 6.3, 6.5 e 7.6–7.7; IA-01 a IA-06. |
| 8 | Histórias de Bronze, Silver, integridade, Gold, DEC/FEC, exportação, Workflow, dicionário e testes diferenciais; histórias de diretoria, comercial, atendimento, perdas, operação, filtros, exportação/importação diferenciais. | Tabelas DE/WEB na seção 6; verificações concretas nas seções 4.2, 4.3, 7.7 e 8.1. |
| 9 | Perfis e testes de backend como diferenciais; histórias de IA, follow-up/avaliação diferenciais; diagnóstico explicativo, causas e impacto das recomendações. | Tabelas WEB/IA/ENT na seção 6; seções 5.4, 7.6, 8.1 e guia do diagnóstico. |
| 10 | Repositório público e estrutura sugerida; README com arquitetura, setup, execução do Workflow, dicionário, diagnóstico e hipóteses; status report; datas 04/11, 05/11 e 10/11; 15+15 minutos; qualidade e dados no centro. | Seções 9, 11, 11.1 e 12; ENT-02 a ENT-05; workflow de qualidade em `docs/agents/workflow.md`. |

### 15.1 Lacunas legítimas que o enunciado não resolve

O case não traz o dataset nas páginas, nomes reais de colunas, chaves de junção, regra operacional de deduplicação, modelo Gold, fórmula detalhada de cada métrica, desenho de telas, rotas da API, credenciais, URL de Figma ou decisão definitiva de banco/framework/modelo. Também não explicita o ano ao lado das datas de novembro. Essas lacunas são decisões e descobertas futuras, registradas nas seções 8 e 12. Ao receber novos artefatos oficiais, atualizar este PRD com origem e data, sem reescrever retroativamente uma hipótese como exigência original.

## 16. Referências internas

- [Guia de engenharia de dados](services/data-engineering.md)
- [Guia de backend](services/backend.md)
- [Guia de frontend](services/frontend.md)
- [Guia de IA](services/ai-agent.md)
- [Guia do diagnóstico](services/revenue-diagnosis.md)
- [Relatório de diagnóstico a preencher](revenue-diagnosis.md)
- [Status report intermediário a preencher](status-report.md)
- [Fluxo de agentes e qualidade](agents/workflow.md)
- [Ferramentas e hooks](agents/tooling.md)
- [Dicionário de dados](data-dictionary.md)
