# PRD — V-Energy Grid 360

**Versão:** 1.4 documental · **Data:** 20/10/2026 · **Estado da implementação:** parcial — fundação, primeira fatia visual e consulta sintética integrada disponíveis; requisitos funcionais pendentes

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

Como decisão da equipe em 18/10/2026, o frontend adota também Tailwind CSS para estilização e Lucide para ícones. A fundação modular, layout persistente e responsabilidade dos provedores estão descritos na [arquitetura do frontend](architecture/frontend.md) e na [ADR-0001](decisions/0001-arquitetura-frontend.md). A primeira etapa prepara a arquitetura. A etapa visual começou pela sidebar e pelo topo estático do Panorama, sem filtros nem dados; integração e critérios funcionais continuam pendentes.

Em 20/10/2026, a DEV-01 prepara contratos analíticos versionados e uma fonte sintética substituível, conforme a [ADR-0004](decisions/0004-contratos-analiticos-e-fonte-sintetica.md) e o [catálogo de contratos](contracts/analytics-api.md). A rota interna `/dev/contratos`, disponível somente em desenvolvimento, consulta a API real e mostra origem, período, filtros, unidades e limitações. Essa demonstração não conclui as jornadas WEB/IA nem comprova integração ou reconciliação com a Gold; campos e fórmulas provisórios estão identificados no catálogo.

### 5.3 Inteligência artificial

O agente conversacional recebe perguntas em português, traduz para consultas somente leitura ao banco Gold e responde de forma clara e fundamentada. Deve explicar números, unidades, filtros, período, fonte e limites. Precisa compreender termos cotidianos como “conta de luz” e “falta de luz”. A IA também gera insight contextual em pelo menos uma tela do portal. O agente deve reconhecer falta de informação, não inventar dado e não executar ações de escrita. Deve haver forma de auditar como cada resposta foi produzida.

### 5.4 Diagnóstico de negócio

Cada time deve responder à pergunta sobre queda de receita residencial. A explicação tem de separar os efeitos de preço/tarifa e volume, sustentar causas com dados identificados, estimar ordem de grandeza do impacto das recomendações e ser comunicável à diretoria na apresentação final. Artefatos textuais do diagnóstico ficam em `docs/`; a apresentação pode ser produzida posteriormente conforme regras da atividade. Uma hipótese plausível não substitui prova nos dados.

## 6. Histórias, critérios de aceite e rastreabilidade

### 6.1 Engenharia de dados — DE

| ID | Prioridade | Estado | Requisito e critérios de aceite |
| --- | --- | --- | --- |
| DE-01 | Obrigatório | Em validação | **Ingerir tudo em Bronze.** Os oito conjuntos, incluindo cinco arquivos de leitura e três abas de inspeção, estão em Delta; linhas, colunas, valores e arquivos de origem são rastreáveis. Diferenças de parse e rejeições são contadas e explicadas. |
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
| WEB-01 | Obrigatório | Em validação | **Indicadores gerais.** A diretoria vê métricas principais com definição, unidade, competência, filtros e comparação entre períodos; indicadores devem conferir com uma amostra reconciliada com Gold. A implementação sintética está em validação e não conclui esse aceite. |
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

A [ADR-0005](decisions/0005-backend-python312-alpine.md), aprovada em 20/10/2026, mantém Python 3.12 e usa `dhi.io/python:3.12-alpine3.24-dev`, base oficial Docker Hardened com zlib já corrigida para CVE-2026-85091. O CI passa a testar dentro da imagem com PostgreSQL descartável. A varredura de base e imagem final permanece manual; o resultado precisa ser revalidado em atualizações e não comprova segurança integral para publicação.

### 9.3 Experiência e acessibilidade

As telas precisam ser legíveis para quem decide sob pressão: rótulos, unidades, período, comparação, estado vazio, erro e atualização visíveis. Busca por UC e filtros devem responder com feedback claro. Tabelas, gráficos e insights precisam de equivalente textual suficiente para interpretação; navegação por teclado e contraste devem ser verificados. A escolha do layout fica com o time e pode usar Figma; nenhum design é exigido nas páginas recebidas.

#### Preparação do protótipo — solicitação da pessoa usuária em 16/10/2026

Como orientação adicional de trabalho, criar o protótipo pelo **Figma MCP** em um arquivo Figma Design organizado em quatro páginas:

1. Componentes e estilos — modo claro.
2. Componentes e estilos — modo escuro.
3. Páginas e fluxos — modo claro.
4. Páginas e fluxos — modo escuro.

As páginas de fluxos contêm as telas necessárias às jornadas; essa organização não limita o portal a quatro telas. O [protótipo editável no Figma](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K) foi criado pelo MCP com 16 frames por tema e uma biblioteca compartilhada. A direção combina estrutura técnica, atmosfera profunda no modo escuro e detalhes tecnológicos expressivos. A pessoa usuária aprovou a paleta **cacau, goiaba e pistache**; tipografia Manrope, DM Sans e IBM Plex Mono; primeira versão desktop. Backgrounds editáveis e transições nativas estão representados no Figma; efeitos contínuos e suporte a movimento reduzido pertencem à futura implementação. Veja o [registro visual, jornadas e verificações](design/grid360-prototype.md). Os diferenciais WEB-08 a WEB-10 e IA-07 não integram esta primeira versão. A [skill git-or-treat-figma](../.agents/skills/git-or-treat-figma/SKILL.md) orienta a continuidade. Skill e protótipo são preparação: não substituem a aplicação integrada nem concluem requisitos WEB/IA/ENT.

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
| P-08 | Protótipo próprio criado pelo Figma MCP em 16/10/2026, com quatro páginas, dois temas e dados sintéticos (§9.3). | [Arquivo, jornadas e limites](design/grid360-prototype.md) documentados. Restam revisão manual das interações no player, implementação e validação com API/Gold reais; design não comprova requisito funcional. |

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

**Marco atual (16/10/2026):** documentação e protótipo visual em Figma criados; há protótipos locais de GenAI com contratos e fixtures sintéticas. Nenhum requisito funcional DE/WEB/IA/ENT foi concluído com integração e dados validados. Skills, hooks, protótipos e mocks são preparação/evidência técnica parcial, não substituem os critérios funcionais do produto. Atualize as tabelas da seção 6 e acrescente uma entrada por lote de entrega.

### 2026-10-21 — WEB-01, WEB-05, WEB-10 e WEB-11 — contenção das vulnerabilidades confirmadas

- Estado: WEB-01 permanece `Em validação`; WEB-05, WEB-10 e WEB-11 permanecem `Pendente`. Corrigir vulnerabilidades não conclui jornadas com Gold, perfis de usuário ou auditoria operacional durável.
- Mudança observável: rotas de ordens negam acesso anônimo e exigem Bearer de serviço com leitura/escrita distintas. Campos e IDs são limitados antes do banco; transições conservadoras impedem reabrir ou alterar ordens finais e conclusão exige resultado. Atualização condicional por status impede sobrescrita concorrente. Política e limites na [ADR-0007](decisions/0007-contencao-seguranca-ordens-e-entradas.md).
- Proteção de entrada: corpo limitado a 65.536 bytes, JSON UTF-8 a 32 níveis, rejeição de NaN/Infinity, overflow numérico, Unicode inválido/NUL e tipos inesperados; antigos erros 500 agora geram respostas 400/413/415/422 conforme o caso. Host é validado e a API recebe headers defensivos.
- Arquivos: `backend/app/core/order_access.py`, configuração, middleware, endpoints/schemas/serviço de ordens, `backend/alembic/env.py` (preserva loggers), Dockerfile, testes e guias de backend; [relatório atualizado](security/2026-10-21-auditoria-local.md). Não foi alterado o esquema ou aplicado dado real.
- Verificações reproduzíveis: suíte completa no container com `TEST_POSTGRES_URL` apontando exclusivamente a banco temporário `*_test`: **132 testes aprovados**, sem ignorados; `python -m compileall -q app tests alembic` aprovado. Incluídos migrações, persistência, disputa de status, validação de comprimentos em PostgreSQL 18 com papel sem superusuário, autenticação/escopos e eventos sem token/payload em log. O banco descartável foi encerrado; banco de desenvolvimento preservado.
- Amostra real somente leitura: servidor local devolveu Panorama 200, ordens anônimas 401, JSON profundo 413, NaN 400 e Host externo 400. A bateria adversarial atualizada executou 40 verificações sem desvio de status e 40 leituras reais a concorrência quatro, todas 200. Evidência local ignorada em `work/security-fixes/`.
- Dependências: pip 26.2.2 aplicado ao container local e previsto no Dockerfile; pip-audit reexecutado sem avisos conhecidos nos 36 pacotes. O rebuild da imagem exata está pendente por 401 do registro dhi.io na resolução da base Hardened. Requer `docker login dhi.io` e repetir `docker compose build backend`; recriar a partir da imagem antiga não preserva a atualização feita no container. Esse limite não foi ocultado nem substituído por outra base.
- Critérios e pendências: credenciais reais não foram criadas nem expostas; ordens ficam fechadas até configuração privada. Identidade humana, posse por usuário, cargos, idempotência de criação, auditoria durável, limites distribuídos de taxa e Gold não são concluídos por esta contenção. Revisão do time pendente; Trello não sincronizado porque o MCP está ausente. Responsável: Codex.

### 2026-10-21 — WEB-01, WEB-05 e WEB-11 — teste local de segurança

- Estado: WEB-01 permanece `Em validação`; WEB-05 e WEB-11 permanecem `Pendente`. Não houve correção de produto nem conclusão de requisito nesta auditoria.
- Evidência: [relatório local de segurança](security/2026-10-21-auditoria-local.md), `frontend/src/features/panorama/PanoramaSecurity.test.tsx` e roteiro/resultados sanitizados locais em `work/security-audit/` (ignorados pelo Git). Base auditada: `5616f59`, branch `dev02`.
- Testes: 39 verificações HTTP mais 40 leituras com concorrência quatro; operações de escrita somente em SQLite em memória, sem modificar ordens PostgreSQL. Confirmados HTTP 500 por JSON profundo (`RecursionError`) e ID fora do intervalo (`OverflowError`), ordens sem identidade/autorização, ausência de controle de transições e aceitação de campos vazios/excessivos. Processo permaneceu disponível. Não houve exploração demonstrada de SQL injection ou execução do HTML malicioso nos recortes testados.
- Verificações frontend: `docker compose exec -T frontend npm test` aprovou 61 testes em sete arquivos; lint, fronteiras (52 arquivos) e build aprovados. Os dois testes novos verificam escape React e recuperação visual de HTTP 500, sem afirmar correção das falhas da API.
- Dependências: npm audit sem avisos conhecidos em 206 dependências; pip-audit examinou 36 pacotes e encontrou seis avisos únicos no pip 25.0.1, com aplicabilidade e duplicatas descritas no relatório. O auditor foi instalado em ambiente temporário separado no container.
- Limites: navegador não abriu nesta passada; teste de UI em React/JSDOM com HTTP simulado. Não houve saturação destrutiva, varredura externa, escrita PostgreSQL, uso do dataset ou teste do serviço GenAI separado.
- Próximos passos: tratar controle de acesso, validação que produz 500 e integridade das ordens; revisar dependências/ferramentas e endurecimento de produção. Trello não sincronizado (MCP ausente). Responsável: Codex; revisão pelo time pendente.

### 2026-10-21 — WEB-01 e WEB-07 — demonstração local e responsividade

- Estado: WEB-01 permanece `Em validação`; WEB-07 permanece `Pendente` para as demais jornadas.
- Causa reproduzida: `docker compose exec -T backend python -c "from app.core.config import settings; print(settings.ANALYTICS_SOURCE)"` retornou `unavailable`, explicando o HTTP 503 e a tela de erro. O Compose agora seleciona explicitamente `synthetic`; o padrão da API fora dele permanece indisponível.
- Mudança observável: API acessada por `/api` na origem do portal, com proxy Vite para backend no Docker; funciona sem endereço localhost da API embutido no navegador. Polling permite refletir mudanças do volume Windows. Cabeçalho e conteúdo centralizados até 1920 px, KPIs em uma/duas/quatro colunas, filtros e controles com quebra de linha e decoração contida na abertura.
- Arquivos: `docker-compose.yml`, `backend/.env.example`, `frontend/vite.config.ts`, transporte HTTP e seus testes, layout/header, componentes do Panorama, cartões/select e documentos de execução/arquitetura.
- Verificações: container frontend com `npm test` (59 aprovados), `npm run lint`, `npm run check:boundaries` (51 arquivos) e `npm run build` aprovados. Regressão do teste legado de produção ajustada: a rota interna continua excluída, mas o redirecionamento ao Panorama permite sua consulta própria. Nova regressão verifica URLs da mesma origem. No backend, `docker compose exec -T backend python -m pytest -q` aprovou 79 testes, com 1 ignorado e aviso Starlette/httpx; o teste de fonte desabilitada passou a selecionar seu estado explicitamente para não depender do ambiente sintético do container.
- Amostra integrada: `GET http://localhost:5173/api/v1/panorama?competencia=2024-04` devolveu R$ 76.500 e nove registros; interação no navegador com município Recife exibiu R$ 38.000 e 620 UCs. Dados exclusivamente sintéticos, sem diagnóstico real.
- Revisão visual: navegador local com API real nos temas claro/escuro. Larguras 320, 390, 768, 1024, 1440 e 2560 px tiveram `scrollWidth == clientWidth`; colunas verificadas em DOM e capturas inspecionadas. Captura local `panorama-desktop.png` salva fora do repositório, na pasta de visualizações da sessão. Esta evidência substitui o bloqueio de acesso local registrado na passada anterior, sem afirmar nova leitura do Figma.
- Pendências: Gold e reconciliação real, comparação direta com Figma e sincronização Trello (MCP ausente). Responsável: Codex; revisão pelo time pendente.

### 2026-10-21 — WEB-01 — implementação funcional do Panorama com filtros, KPIs, séries e base sintética

- Estado anterior → novo estado: `Pendente` → `Em validação` no escopo demonstrativo; a reconciliação com a Gold e as definições oficiais das fórmulas permanecem pendentes, porque o conjunto de dados do case não está no repositório e a fonte usada é sintética.
- Mudança observável para usuário/negócio: o Panorama (`/panorama`) oferece a visualização executiva completa da diretoria, com 8 KPIs essenciais (Receita Faturada, Receita Paga, Energia Consumida, Energia Faturada, Preço Médio Efetivo, UCs Ativas, DEC e FEC médios simplificados), distinção explícita entre grandezas faturadas/pagas e consumidas/faturadas, e gráfico de séries históricas mensais com alternância financeira e física. Filtros de competência, comparação (m-1, m-12 e sem comparação), município e classe sincronizam bidirecionalmente com os search params da URL, preservando recarga e navegação no histórico (voltar/avançar). Todos os estados transversais foram implementados: carregamento (skeletons), erro com retentativa, vazio legítimo com botão de restauração, aviso de período incompleto (2024-05) e divisão por zero/base zero tratada (N/D).
- Componentes compartilhados extraídos: `FilterBar`, `usePanoramaFilters`, `MetricCard`, `Badge`, `Button`, `Select`, `ContentState` e `PanoramaSeriesChart` criados respeitando os tokens de design do Figma nos modos Claro e Escuro e as regras de fronteiras (`check-boundaries.mjs`).
- Backend integrado: o contrato de produto do Panorama foi publicado em `GET /api/v1/panorama`, na mesma arquitetura analítica da DEV-01 (rota → serviço → repositório → base sintética), com cálculo e agregação por competência, comparação, município e classe. O contrato analítico da DEV-01 em `GET /api/v1/kpis` foi preservado sem alteração; a decisão de manter as duas fontes está registrada em [ADR-0006](decisions/0006-panorama-fonte-produto-e-contrato-dev01.md) e em [contratos analíticos](contracts/analytics-api.md).
- Dados usados: controles sintéticos oficiais do protótipo Figma e do PRD (Benchmark 2024-04 vs 2024-03: Receita Faturada R$ 76.500 vs R$ 80.000 [-4,38%]; Receita Paga R$ 74.200 vs R$ 78.500 [-5,48%]; Energia Consumida/Faturada 90.000 kWh vs 100.000 kWh [-10%]; Preço Médio R$ 0,85/kWh vs R$ 0,80/kWh; UCs Ativas 1.248 vs 1.250). Totais dos municípios somam exatamente R$ 76.500 (Recife R$ 38.000, Olinda R$ 22.500, Jaboatão R$ 16.000).
- Verificações: no frontend, `npm test` aprovou 55 testes em 6 arquivos, `npm run check:boundaries` validou 43 arquivos, `npm run lint`, `npm run format:check` e `npm run build` passaram sem erros; no backend, `python -m pytest -q` aprovou 76 testes com 1 ignorado, cobrindo agregação, filtro por município, comparação sem período anterior, recorte vazio legítimo, recusa de entrada inválida (422) e falha fechada sem fonte selecionada (503).
- Critérios de aceite revisados: alterar filtros modifica os dados consultados e exibidos; indicadores conferem com os controles da base sintética do protótipo Figma; a reconciliação exigida contra a Gold segue pendente e registrada como limitação da fonte sintética.
- Responsável/revisor: Antigravity / Pair programming; consolidação do contrato com a DEV-01 e revisão do PR por Guilherme pendentes.
### 2026-10-22 — IA-08 e IA-06 — avaliação pela composição oficial, plano na fonte e falhas conhecidas específicas

- Estado anterior → novo estado: IA-08 `Pendente` → `Pendente`; IA-06 `Pendente` → `Pendente`. Ajustes pedidos na revisão do PR #31; nenhum comportamento do agente foi alterado.
- Mudança observável para usuário/negócio: a avaliação sintética passa a exercitar o serviço como ele é montado de fato. `create_app` recebe perfil, fonte e modelo, cria o `ExecutionController` e chama `compose_core`, em vez de o teste montar orquestradores à mão. A fonte de teste encapsula a `SyntheticScenarioTool` e registra o `LogicalReadPlan` aprovado. Os 17 casos com chamada de ferramenta esperada declaram `expected_plan` (domínio, métrica, dimensões, janela e filtros que o negócio esperaria), conferido pela checagem `plan`. Cada falha conhecida registra as checagens que devem falhar e o status devolvido hoje; o teste reprova se o caso passar (pedindo a remoção da marcação), se falhar por outras checagens ou com outro status, e só aprova a falha exatamente registrada. O relatório (fixture 3.2.0) traz `outcome`, `failing_checks` e `actual_plan` por caso e conta falhas conhecidas confirmadas, alteradas e atendidas; o comando termina com erro em qualquer resultado diferente de `passed` ou `known_failure_confirmed`.
- Arquivos/commit/PR: branch `feat/ia-avaliacao-ptbr`, PR #31; `ai-agent/tests/test_genai_regression.py`, `ai-agent/tests/fixtures/genai_regression.json`, `ai-agent/reports/synthetic-regression-report.json`, [guia do serviço](services/ai-agent.md) e este PRD. Alterações ainda não commitadas.
- Dados usados: fixtures sintéticas do Grid 360, perguntas escritas para a avaliação e adaptador de linguagem falso. Nenhum dataset do case, dado pessoal real, chave ou chamada a modelo real.
- Verificações: em `ai-agent/`, em 22/10/2026, com a `.venv` ativa: `python -m pytest` aprovou 476 testes e pulou 1 (smoke live do Groq, sem opt-in), sem xfail; `python -m ruff check .` e `python -m compileall -q app tests` passaram sem erros; `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` terminou com código 0, com 26 falhas conhecidas confirmadas, 0 alteradas, 0 atendidas e 0 falhas inesperadas; `git diff --check` passou na raiz. Com a montagem por `create_app`, os 55 casos devolveram os mesmos status e as mesmas contagens de chamadas da montagem manual anterior. As três saídas da regra (caso marcado que passa, falha com checagens diferentes e falha com outro status) foram exercitadas com cópias alteradas dos casos, sem mudar a fixture.
- Taxa de acerto: 29/55 (52,7%), igual à de 21/10; entre as 42 perguntas novas, 16/42. Medida sobre fixtures sintéticas e modelo falso, não sobre o Gemini nem sobre a Gold.
- Plano na fonte: dos 17 casos com `expected_plan`, 10 recebem na fonte exatamente o plano esperado. A checagem `plan` falha em 7 falhas conhecidas: #3–#7 e #20 não chegam à fonte, e #41 (“interrupções por município”) chega sem a dimensão `geography.municipality`.
- Critérios de aceite revisados e pendências: IA-08 passa a verificar o plano lógico entregue à fonte, além do status; continua sem medir correção numérica contra Gold. O caso #40 (“consumo de Recife”) mantém o esperado `needs_clarification` sem chamada de ferramenta e, por isso, não tem `expected_plan`; a alternativa de esperar um plano com filtro de município “Recife” e resultado `no_evidence` aguarda decisão. Seguem pendentes as correções do `QuestionSafetyGate` e do interpretador e a remoção de cada `known_failure` conforme o caso passar. A sincronização com o Trello continua pendente.
- Responsável/revisor: laura-amiranda, com apoio do Claude Code; ajustes solicitados por Guilherme, nova revisão pendente.

### 2026-10-21 — IA-08 e IA-06 — avaliação em português com falhas conhecidas

- Estado anterior → novo estado: IA-08 `Pendente` → `Pendente`; IA-06 `Pendente` → `Pendente`. A entrega amplia a avaliação e documenta lacunas; nenhum comportamento do agente foi alterado.
- Mudança observável para usuário/negócio: o conjunto de regressão sintética passou de 13 para 55 casos (versão 3.1.0), com 42 perguntas em português em sete categorias: vocabulário do negócio, ambiguidade, escrita/SQL, injeção de instruções, dados pessoais, fora de escopo e recorte sem evidência. Os 26 casos que o código atual não atende ficam como falha conhecida (`known_failure` na fixture, `xfail(strict=True)` no pytest), com o motivo registrado. O relatório passa a informar `pass_rate`, `known_failures`, `unexpected_failures` e `known_failures_now_passing`, e o comando termina com erro apenas diante de falha inesperada ou de falha conhecida que passou a ser atendida.
- Arquivos/commit/PR: branch `feat/ia-avaliacao-ptbr`, criada a partir de `origin/develop` (`ebccc23`), PR #31; `ai-agent/tests/fixtures/genai_regression.json`, `ai-agent/tests/test_genai_regression.py`, `ai-agent/reports/synthetic-regression-report.json`, [guia do serviço](services/ai-agent.md) e este PRD. Alterações ainda não commitadas.
- Dados usados: perguntas escritas para a avaliação, fixtures sintéticas do Grid 360 e adaptador de linguagem falso. CPF, CNPJ, e-mail e UC das perguntas são fictícios. Nenhum dataset do case, dado pessoal real, chave ou chamada a modelo real.
- Verificações: em `ai-agent/`, em 21/10/2026, com a `.venv` ativa: `python -m pytest` aprovou 389 testes, com 26 xfail e nenhuma falha; `python -m ruff check .` e `python -m compileall -q app tests` passaram sem erros; `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` terminou com código 0, 0 falhas inesperadas e 0 falhas conhecidas atendidas; `git diff --check` passou na raiz. A lista de casos que falharam coincidiu com a lista prevista na análise estática (3–7, 15–20, 22–26, 28–31, 33–36, 40 e 41).
- Taxa de acerto: 29/55 (52,7%); entre as 42 perguntas novas, 16/42. É uma medida sobre fixtures sintéticas e modelo falso, não sobre o Gemini nem sobre a Gold.
- Falhas graves: em dez casos a pergunta deveria ser recusada, esclarecida ou ficar sem evidência, mas chega ao modelo e volta como `answered`. Escrita não bloqueada (#18 “remova os registros”, #19 “zere o faturamento”): o pedido de alteração é tratado como leitura e respondido. Injeção não detectada (#22 “esqueça as instruções”, #23 instruções em inglês, #24 troca de papel, #25 marcação falsa de sistema): o texto injetado chega ao modelo junto com a evidência. Dados pessoais não detectados (#28 CNPJ, #29 e-mail): o identificador é ignorado e o total sem filtro é respondido. Recorte descartado em silêncio (#40 “de Recife”, #41 “por município”): a resposta traz o total geral como se atendesse ao recorte pedido. As demais 16 falhas conhecidas terminam em pedido de esclarecimento ou recusa indevida, sem resposta numérica.
- Critérios de aceite revisados e pendências: IA-08 ganha cobertura de sinônimos, recusa e injeção, mas continua sem medir correção numérica contra Gold. IA-06 segue com lacunas de bloqueio de escrita, injeção e dados pessoais demonstradas pelos casos acima. Próximos passos: corrigir `QuestionSafetyGate` (verbos e SQL sem alvo, injeção, CNPJ/e-mail/nome completo, fora de escopo) e o interpretador (sinônimos, detecção de local sem preposição, “em kWh”/“em 2024”, quebra por dimensão) e remover cada `known_failure` conforme o caso passar. As mensagens de esclarecimento dos casos 8, 9 e 42 passam no status, mas ainda são genéricas ou indicam local desconhecido. A sincronização com o Trello continua pendente.
- Responsável/revisor: laura-amiranda, com apoio do Claude Code; revisão por Guilherme pendente.

### 2026-10-20 — IA-06 — fallback configurável Gemini → Groq no protótipo GenAI

- Estado anterior → novo estado: `Pendente` → `Pendente`; a cadeia multi-provedor foi testada só com chamadas simuladas e não muda os critérios de somente leitura e limites do IA-06.
- Mudança observável para usuário/negócio: o serviço pode usar Groq como provedor principal ou como fallback de outro provedor. Com `GENAI_MODEL_PROVIDER=gemini` e `GENAI_MODEL_FALLBACK_PROVIDERS=groq`, uma indisponibilidade transitória do Gemini (429, 5xx, timeout ou rede) faz a mesma pergunta ser respondida pelo Groq, com a mesma validação de evidência e de saída. Rejeição definitiva (demais 4xx) ou resposta inválida encerra a cadeia sem trocar de provedor. O total de modelos, somando todos os provedores, respeita `GENAI_MODEL_MAX_CALLS`, e o cache separa as respostas por ordem de provedores, modelos (inclusive o do Groq) e digest do prompt.
- Arquivos/commit/PR: commits `c67d9ca` (adaptador Groq) e `dbea5bd` (merge de `develop`), na branch `feat/ia-provedor-groq`, PR do provedor Groq (#22) em revisão; `ai-agent/app/providers/groq.py`, `app/providers/factory.py`, `app/config.py`, `ai-agent/tests/test_groq_adapter.py`, `tests/live/test_groq_live_smoke.py`, `ai-agent/pyproject.toml` (extra `groq` e marcador `live`), `ai-agent/.env.example`, [README do GenAI](../ai-agent/README.md) e [guia do serviço](services/ai-agent.md).
- Dados usados: perfil e fixtures sintéticas do Grid 360 e chaves fictícias nos testes automatizados; nas duas chamadas reais, apenas pergunta e evidência sintéticas, com chave Groq real definida só no ambiente local. Nenhum dataset do case ou dado pessoal.
- Verificações: em `ai-agent/`, com a `.venv` (Python 3.13.5), em 20/10/2026, após trocar o modelo padrão do Groq para `openai/gpt-oss-120b`: `python -m pytest` aprovou 366 testes e pulou 1 (o smoke test live, sem as variáveis de opt-in); `python -m ruff check .` e `python -m compileall -q app tests` passaram. Os testes automatizados continuam simulando as chamadas ao Groq com `httpx.MockTransport` e cobrem formato da requisição, classificação de 4xx/429/5xx/timeout/rede/JSON inválido, ausência da chave e da pergunta em mensagens e logs, ordem da cadeia nos dois sentidos, cadeia acima de `GENAI_MODEL_MAX_CALLS`, isolamento do namespace do cache e o orquestrador respondendo pelo Groq com o Gemini fora do ar.
- Chamadas reais ao Groq (laura-amiranda, 20/10/2026):
  - Smoke test (`python -m pytest -m live -rs tests/live`) com `GENAI_GROQ_MODEL=openai/gpt-oss-120b`: 1 teste aprovado em 4,19 s. O modelo padrão anterior, `llama-3.3-70b-versatile`, não constava mais na lista de modelos da conta, por isso o padrão foi trocado para `openai/gpt-oss-120b` em `app/config.py`, `.env.example`, README e guia do serviço.
  - Servidor: `uvicorn` local em modo demonstração (`GENAI_ENVIRONMENT=local`, `GENAI_ENABLE_DEMO_ACCESS=true`, `GENAI_MODEL_PROVIDER=groq`, `GENAI_GROQ_MODEL=openai/gpt-oss-120b`), com `POST /api/v1/questions` e a pergunta “Qual foi o consumo no período de demonstração?”. A resposta voltou com status `answered`, evidência sintética (`is_demo: true`) e a limitação de valor inventado. O número vem da fixture; o Groq só escolheu as observações citadas.
  - Alcance: uma execução de cada, um único modelo, dados sintéticos, sem Gold e sem fallback exercitado. Não houve medição de custo, latência (os 4,19 s são só a duração do pytest) nem qualidade das respostas.
- Reconciliação ou amostra manual: não se aplica; não há Gold nem número real envolvido. A resposta sintética (`420 unidades fictícias`) é composta pelo serviço a partir das observações escolhidas pelo modelo.
- Critérios de aceite revisados e pendências: o smoke test real opt-in (`tests/live/test_groq_live_smoke.py`, marcador `live`, fora do CI) passou uma vez com `openai/gpt-oss-120b`, o que confirma, só nesse recorte, que o modelo estava disponível na conta e respondeu em JSON mode dentro do contrato. Falta confirmar com o Felipe qual modelo ele usou e combinar a política de chave do Groq do grupo. O prazo de modelo do orçamento (`GENAI_MODEL_TIMEOUT_MS`) cobre a cadeia inteira; com dois provedores, o Groq pode ficar sem tempo se o Gemini demorar a falhar. IA-06 continua exigindo identidade verificada, credencial somente leitura e prova integrada com Gold.
- Responsável/revisor: laura-amiranda, com apoio do Claude Code (implementação e testes simulados); revisão do PR por Guilherme pendente.

### 2026-10-20 — IA-06 — roteador de níveis de modelo ligado ao fluxo de perguntas

- Estado anterior → novo estado: `Pendente` → `Pendente`; o roteador foi exercitado com adaptadores falsos na suíte e em um smoke test manual com Gemini real usando fixtures sintéticas. A evidência não satisfaz os critérios restantes de IA-06.
- Mudança observável para usuário/negócio: a factory lê `GENAI_MODEL_ROUTING_ENABLED`, `GENAI_MODEL_LIGHT_MODEL`, `GENAI_MODEL_LIGHT_INTENTS` e limites opcionais e injeta o roteador ao compor o serviço somente para `GRID360_DEMO_PROFILE` com `synthetic.fixture`; ativação em outro perfil ou fonte falha na criação da aplicação. O roteamento continua desligado por padrão; sem domínios leves, todas as perguntas usam o modelo forte, e os níveis precisam usar IDs Gemini distintos. Quando configurado, o fluxo escolhe o nível depois de reduzir a evidência, pelo domínio da intenção, número de registros e tamanho serializado. Se a resposta do nível leve não selecionar observações válidas (IDs ausentes, repetidos ou inexistentes), tenta o forte uma vez; se o forte também falhar, recusa com `ungrounded_output`. Indisponibilidade, recusa e resposta inválida do leve seguem o tratamento habitual e não acionam escalada. A resposta quantitativa pública é montada pelo serviço a partir das observações escolhidas, nunca do texto livre do modelo. A escalada e os fallbacks respeitam `GENAI_MODEL_MAX_CALLS`; um evento seguro `model`/`escalated` não contém pergunta, evidência ou resposta do modelo. O insight de tela mantém o adaptador forte. A resposta da pergunta informa `model_tier` (`light`/`strong`) quando há geração concluída, sem expor provedor ou ID do modelo; sem isso, o campo é `null`.
- Arquivos/commit/PR: branch `feat/ia-roteador-modelos`, PR #23; `ai-agent/app/config.py`, `app/providers/factory.py`, `app/main.py`, `app/agent/composition.py`, `app/agent/orchestrator.py`, `app/agent/execution.py`, `app/ports/events.py`, `ai-agent/.env.example`, `ai-agent/README.md`, `ai-agent/tests/test_config.py`, `tests/test_gemini_adapter.py`, `tests/test_core_composition.py`, `tests/test_model_routing.py`, `tests/test_model_router_flow.py` e [guia do serviço](services/ai-agent.md).
- Dados usados: perfil e fixtures sintéticas do Grid 360 e adaptadores falsos nos testes automatizados; o smoke test usou o Gemini real com a fonte `synthetic.fixture`. Nenhum dataset do case, dado pessoal ou chave foi incluído na alteração.
- Verificações: em `ai-agent/`, em 20/10/2026, Python 3.12.6 do ambiente local: `python -m pytest -q` aprovou 368 testes; `python -m ruff check .`, `python -m compileall -q app tests` e `git diff --check` passaram. O ambiente usou pytest 9.0.3, acima da faixa declarada no extra `dev` (`pytest<9`), limitação da verificação local. Os testes passam pelo `QuestionOrchestrator` e pela criação HTTP da aplicação e cobrem configuração/factory, roteamento, escalada, fallback sem escalada, orçamento e evento seguro; também confirmam que o roteador só pode ser ativado com o perfil e a fonte sintéticos e que os IDs dos dois níveis Gemini são distintos. O fluxo também verifica que a resposta HTTP informa o nível final, inclusive `strong` após escalada.
- Reconciliação ou amostra manual: não há Gold nem número real envolvido. No smoke test, `POST /api/v1/questions` com `Qual foi o consumo no período de demonstração?` retornou HTTP 200, status `answered`, `model_tier: light`, uma referência de evidência e `420 unidades fictícias`, com a limitação de que o valor não representa leitura ou consumo real. O campo confirma que essa resposta veio do nível leve e não escalou para `strong`.
- Critérios de aceite revisados e pendências: `light_intents` é vazio por padrão, então toda pergunta vai para o nível forte até a equipe definir e configurar os domínios autorizados. O roteamento fica limitado ao perfil e à fonte sintéticos; nenhuma integração Gold é alterada. A factory desta etapa monta níveis Gemini; outros fornecedores exigem um builder apropriado. A escolha considera domínio e tamanho da evidência, não complexidade da pergunta ou histórico. O smoke test confirma uma resposta real no nível `light` sobre fixture sintética, sem medir custo, latência ou qualidade comparativa. IA-06 continua exigindo identidade verificada, credencial somente leitura e prova integrada com Gold.
- Responsável/revisor: laura-amiranda, com apoio do Claude Code (implementação e testes com adaptadores falsos); revisão do PR por Guilherme pendente.

### 2026-10-20 — IA-06 — escalada após divergência numérica do modelo

- Estado anterior → novo estado: `Pendente` → `Pendente`; a checagem usa somente respostas roteadas e evidência sintética, sem reconciliação com Gold.
- Mudança observável para usuário/negócio: além de validar referências, o orquestrador compara números no rascunho `answered` do modelo com valores, períodos e dimensões das observações selecionadas. Divergência no nível `light` tenta `strong` uma vez dentro do mesmo orçamento; se o nível forte também falhar na checagem, a resposta é recusada com `ungrounded_output`. A indisponibilidade do provedor continua seguindo o fallback próprio. A API nunca publica o rascunho: a resposta quantitativa pública continua composta a partir das observações.
- Arquivos/commit/PR: worktree local na branch `feat/ia-roteador-modelos`, acompanhando `origin/feat/ia-roteador-modelos` do PR #23; alterações pendentes de commit em `ai-agent/app/agent/orchestrator.py`, `ai-agent/app/generation/prompts.py`, `ai-agent/app/providers/routing.py`, `ai-agent/tests/test_model_router_flow.py`, `ai-agent/tests/manual_gemini_numeric_retry_smoke.py`, `ai-agent/README.md`, `docs/PRD.md` e [guia do serviço](services/ai-agent.md).
- Dados usados: fixture sintética do Grid 360, adaptadores roteados programados nos testes automatizados e chamadas Gemini reais no smoke; o teste manual substitui a saída leve após a chamada real para injetar um número não suportado. Nenhum dataset do case, dado pessoal ou chave foi incluído.
- Verificações: em `ai-agent/`, `python -m pytest -q` passou com 373 testes; `python -m tests.test_genai_regression --output "$env:TEMP\git-or-treat-synthetic-regression-report.json"` aprovou 13/13 casos; `python -m ruff check .`, `python -m compileall -q app tests` e `git diff --check` passaram. Os testes focados do `QuestionOrchestrator` cobrem divergência no nível leve, número compatível em decimal e notação científica, falha persistente no forte, orçamento de chamadas e tratamento distinto de indisponibilidade. O ambiente usou pytest 9.0.3, acima da faixa declarada no extra `dev` (`pytest<9`).
- Reconciliação ou amostra manual: não houve Gold nem número real. O smoke test manual usou chamadas Gemini reais para `gemini-3.5-flash-lite` e `gemini-3.6-flash` e a fonte `synthetic.fixture`; a saída do primeiro adaptador foi substituída após a chamada por um rascunho controlado com `999`, mantendo uma referência válida, para provocar especificamente a divergência numérica. `POST /api/v1/questions` retornou HTTP 200, `answered`, `model_tier: strong`; o evento `escalated` registrou duas chamadas de modelo, e a resposta pública trouxe `420 unidades fictícias`, sem `999`. O teste confirma a execução real dos dois adaptadores e a escalada, mas não demonstra que um modelo produziria espontaneamente uma afirmação numérica sem suporte.
- Comando de reprodução do smoke test, dentro de `ai-agent/`, com `GENAI_GEMINI_API_KEY` disponível em `.env`: `python -m tests.manual_gemini_numeric_retry_smoke --strong-model gemini-3.6-flash --light-model gemini-3.5-flash-lite --run-live`. São duas chamadas reais e potencialmente faturáveis; o script exige `--run-live` e usa somente a fixture sintética.
- Critérios de aceite revisados e pendências: a validação cobre tokens numéricos explícitos do rascunho contra as observações selecionadas e não demonstra correção semântica de cálculos, porcentagens derivadas ou compatibilidade com Gold. IA-06 continua dependendo de identidade verificada, credencial somente leitura e prova integrada com Gold.
- Responsável/revisor: Codex (implementação, testes sintéticos e smoke test real com divergência injetada); revisão do PR por Guilherme pendente.

### 2026-10-19 — IA-01, IA-02, IA-03 e IA-06 — prova técnica de reuso do núcleo GenAI

- Estado anterior → novo estado: `Pendente` → `Pendente`; a prova usa exclusivamente perfis e fontes artificiais, sem números reconciliados com a Gold.
- Mudança observável para usuário/negócio: a mesma composição do núcleo atende perguntas sobre energia e clima artificial com vocabulários, métricas, unidades e escopos diferentes. API e chamada direta preservam fundamentação, ausência de evidência, recusa e erros controlados. Instâncias simultâneas não compartilham permissão, resultado, cache nem eventos indevidamente.
- Arquivos/commit/PR: `ai-agent/tests/weather_fixture.py`, `tests/test_reusable_core.py`, `tests/test_import_boundaries.py`, [guia de reuso](services/ai-agent-reuse.md), [guia do serviço](services/ai-agent.md) e [README do GenAI](../ai-agent/README.md); commits locais registrados nesta branch, sem PR aberto para este recorte.
- Dados usados: apenas medidas e localidades inventadas nas fixtures do Grid 360 e de clima; nenhum dataset do case ou dado pessoal real.
- Verificações: em `ai-agent/`, `python -m pytest -q` passou com 301 testes; `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` aprovou 13/13; Ruff e compilação passaram. `git diff --check` passou na raiz. A matriz de conformidade cobre sucesso, vazio, filtro sem suporte declarado, acesso negado, resposta inválida, campo sensível, limite, timeout, cancelamento e proveniência, além de cache/fallback, autorização de insight sintético e dois perfis. A revisão adicional cobre município desconhecido em minúsculas sem alargar o filtro, preservação de expressões conhecidas como “na classe residencial” e “no município de Olinda”, referência opaca no insight, limites do catálogo coerentes com plano/resposta e descarte de saída não fundamentada no cache.
- Reconciliação ou amostra manual: consumo artificial `420 unidades fictícias` e chuva artificial `12 mm fictícios` foram retornados por composições independentes sem edição de `app/agent/`. Esses valores não representam métricas reais nem decisões operacionais.
- Critérios de aceite revisados e pendências: IA-01/IA-02 exigem vocabulário e respostas sobre o Grid 360 oficial; IA-03 exige fonte Gold reproduzível; IA-06 exige identidade, executor e permissões somente leitura reais. A referência da fonte é exposta como ID opaco estável após validação; a reprodução operacional dependerá do vínculo mantido pelo adaptador real. O insight sintético verifica perfil/fonte/escopo de leitura, mas seus filtros e métrica enviados pelo cliente não provam autorização de uma consulta Gold. O contrato externo com Backend/Dados (4.1), esquema Gold e revisão de segurança permanecem pendentes. Reuso do núcleo não implica compatibilidade automática com qualquer banco ou regra de negócio.
- Responsável/revisor: Codex (implementação e verificação sintética); integração/revisão com Backend, Dados e Segurança pendentes.

### 2026-10-19 — IA-03 e IA-06 — rastreabilidade segura do núcleo GenAI sintético

- Estado anterior → novo estado: `Pendente` → `Pendente`; a trilha local não comprova consulta Gold nem auditoria durável.
- Mudança observável para usuário/negócio: perguntas e insights geram eventos internos por estágio com correlação, resultado, código, duração, quantidades, versões e fingerprints do plano e da referência, sem registrar texto da pergunta, histórico, exceções ou linhas. Recusas HTTP também preservam o ID de correlação. Se auditoria durável for exigida na composição, destino ausente ou com falha impede a execução antes da consulta.
- Arquivos/commit/PR: commit `df6fc04`, `ai-agent/app/ports/events.py`, `app/agent/planner.py`, orquestradores, `app/agent/composition.py`, `app/api/routes.py`, `app/main.py`, `app/schemas/responses.py`, `ai-agent/tests/test_safe_events.py`, `tests/test_core_composition.py` e [guia do serviço](services/ai-agent.md).
- Dados usados: perfil e fixtures sintéticas, referências e segredos artificiais nos testes; nenhum dado bruto ou pessoal real.
- Verificações: em `ai-agent/`, `python -m pytest -q` (259 passaram), `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` (13 casos, 0 falhas), `python -m ruff check .` e `python -m compileall -q app tests` passaram em 19/10/2026; `git diff --check` passou na raiz. Os testes cobrem sucesso, recusa, erros de fonte/modelo, cancelamento, fallback, sanitização da referência e falha de destino opcional/obrigatório.
- Reconciliação ou amostra manual: evento de falha sintética pode ser localizado pelo mesmo ID de correlação HTTP e pelo estágio, com código fixo; nenhuma evidência Gold foi reconciliada.
- Critérios de aceite revisados e pendências: IA-03 ainda exige fonte/consulta Gold reproduzível e IA-06 requer identidade verificada, credencial de banco somente leitura, controles reais e teste integrado. O destino padrão descarta eventos; `durable=True` é contrato de adaptador, não comprovação de persistência. Retenção, controle de acesso e coleta distribuída continuam pendentes.
- Responsável/revisor: Codex (implementação e testes sintéticos); revisão de integração com Backend/Dados e política de auditoria pendentes.

### 2026-10-18 — IA-01, IA-03, IA-04 e IA-06 — composição do núcleo GenAI sintético

- Estado anterior → novo estado: `Pendente` → `Pendente`; os testes comprovam composição e substituição de dependências, sem números reconciliados com Gold ou integração ao portal.
- Mudança observável para usuário/negócio: perguntas e insights passam por casos de uso compostos com perfil, política, fonte, modelo, limites e destino opcional de eventos injetados. A resposta sintética mantém fundamentação por IDs de observação e falhas controladas. A API preserva o contrato público `v1`.
- Arquivos/commit/PR: commit `7cad797`, `ai-agent/app/agent/composition.py`, `app/generation/prompts.py`, `app/ports/events.py`, `app/main.py`, orquestradores, adaptadores, `ai-agent/tests/test_core_composition.py`, [README do serviço](../ai-agent/README.md) e [guia do serviço](services/ai-agent.md).
- Dados usados: perfil e fixtures sintéticas do Grid 360, fonte/modelos falsos e cliente falso do Gemini; nenhum dataset ou banco Gold.
- Verificações: em `ai-agent/`, `python -m pytest -q` (251 passaram), `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` (13 casos, 0 falhas), Ruff, compilação e `git diff --check` passaram em 18/10/2026. Testes exercitam chamada direta e HTTP, substituição entre modelo falso/Gemini/fallback, recusa antes da fonte, insight injetado, falha do destino de eventos e importação do núcleo sem FastAPI, fixture ou SDK.
- Reconciliação ou amostra manual: resposta demonstrativa de consumo `420 unidades fictícias` resulta do mesmo plano e evidência aprovada com adaptadores de modelo distintos; não representa consumo real.
- Critérios de aceite revisados e pendências: IA-01 e IA-03 exigem catálogo Gold oficial e reconciliação; IA-04 exige insight com contexto autorizado no portal; IA-06 exige identidade verificada, executor somente leitura, controles do banco e prova integrada. O evento mínimo não é auditoria durável; detalhamento e política de falha pertencem a 4.12.
- Responsável/revisor: Codex (implementação e testes sintéticos); validação de integração com Backend/Dados e revisão do produto pendentes.

### 2026-10-18 — IA-06 — limites de execução e isolamento do cache no protótipo GenAI

- Estado anterior → novo estado: `Pendente` → `Pendente`; os controles assíncronos foram exercitados com fonte e modelo falsos, sem consulta Gold real.
- Mudança observável para usuário/negócio: o fluxo limita duração, chamadas e concorrência de fonte/modelo e retorna falha controlada quando o orçamento acaba. O cache opcional só reutiliza uma resposta após autorização e com identidade, permissões, plano, catálogo e evidência compatíveis. O fallback avança apenas após falha transitória.
- Arquivos/commit/PR: commit `9ae3326`, `ai-agent/app/agent/execution.py`, orquestradores, planner, adaptadores de cache/fallback/Gemini, configuração, testes em `ai-agent/tests/`, [README do serviço](../ai-agent/README.md) e [guia do serviço](services/ai-agent.md).
- Dados usados: fixtures e identidades sintéticas; nenhum dataset, credencial, pessoa real ou esquema Gold oficial.
- Verificações: em `ai-agent/`, `python -m pytest -q` (240 passaram), `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` (13 casos, 0 falhas), `python -m ruff check .` e `python -m compileall -q app tests` passaram em 18/10/2026; `git diff --check` passou na raiz. Testes controlados verificam fonte/modelo lentos, cancelamento, liberação de vagas, concorrência, isolamento por chamador, recusa antes de cache, limite de chamadas e parada do fallback em erro definitivo.
- Reconciliação ou amostra manual: duas identidades fictícias com a mesma pergunta/evidência causam gerações separadas; escopo negado não alcança o cache. Nenhuma medida de latência ou cancelamento foi feita contra o banco ou SDK real.
- Critérios de aceite revisados e pendências: IA-06 ainda exige autenticação real, permissões e credencial somente leitura no banco, limites do executor Gold, validação de eventual SQL e teste integrado. Cancelamento de coroutine não comprova interrupção de trabalho síncrono ou remoto; cada adaptador concreto precisa impor seu timeout e demonstrar limpeza de recursos.
- Responsável/revisor: Codex (implementação e verificação sintética); revisão de Backend, Dados e Segurança pendente para a fonte real.

### 2026-10-18 — IA-03, IA-04 e IA-06 — proteção de evidência e saída no protótipo GenAI

- Estado anterior → novo estado: `Pendente` → `Pendente` para os três requisitos; esta entrega protege o caminho sintético, sem validar dados Gold ou integração com o portal.
- Mudança observável para usuário/negócio: a resposta de pergunta usa apenas observações aprovadas da fonte e apresenta métrica, valor, unidade, período e referência. O texto quantitativo livre do modelo não é publicado. Insights locais usam IDs de observação válidos; em modo real sem identidade confiável, o contexto enviado pelo navegador não é tratado como evidência autorizada.
- Arquivos/commit/PR: `ai-agent/app/agent/evidence_guard.py`, orquestradores de pergunta e insight, perfil e contratos de evidência, adaptadores e testes de `ai-agent/tests/`; commit `8a72304` na branch de fundação GenAI.
- Dados usados: catálogos e fixtures artificiais de energia e clima, incluindo valores pessoais e instruções maliciosas fictícias nos testes; nenhum dado identificável real ou esquema Gold oficial.
- Verificações: em `ai-agent/`, `python -m pytest -q` (209 passaram), `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` (13 casos, 0 falhas), `python -m ruff check .` e `python -m compileall -q app tests` passaram em 18/10/2026. `tests/test_evidence_guard.py` cobre 17 casos; `git diff --check` passou na raiz.
- Reconciliação ou amostra manual: a proveniência vincula o resultado ao plano lógico e ao catálogo local; isso detecta incompatibilidades, mas não comprova que uma fonte externa executou fielmente o plano. Valores, fórmulas, qualidade e permissões Gold ainda exigem verificação independente.
- Critérios de aceite revisados e pendências: a fonte deve fornecer origem, referência, versão, recorte e unidade compatíveis; campos não classificados são descartados antes do modelo. IA-03 ainda exige amostra reproduzível da Gold; IA-04 exige insight na tela real; IA-06 exige autorização e leitura somente leitura na execução concreta. Limites de tempo, cache, fallback e observabilidade pertencem aos próximos checkpoints.
- Responsável/revisor: Codex (implementação sintética); revisão por Backend, Dados e Segurança pendente para integração real.

### 2026-10-18 — IA-06 — plano lógico de leitura no protótipo GenAI

- Estado anterior → novo estado: `Pendente` → `Pendente`; o plano sintético é um controle anterior à fonte, sem comprovar consulta Gold segura.
- Mudança observável para usuário/negócio: a fonte recebe um plano aprovado com métrica e filtros lógicos, unidade, período e limite. Filtro ou comparação sem representação no catálogo gera esclarecimento antes de consultar dados; a entrada não é simplificada silenciosamente.
- Arquivos/commit/PR: `ai-agent/app/schemas/read_plan.py`, `app/agent/read_plan.py`, planner, porta de evidência, adaptador sintético, testes em `ai-agent/tests/` e [guia do serviço](services/ai-agent.md); commit `17254ce` na branch de fundação GenAI.
- Dados usados: catálogos artificiais de energia e clima e fixtures sintéticas; nenhum dataset, dado pessoal ou esquema Gold oficial.
- Verificações: em `ai-agent/`, `python -m pytest -q` (189 passaram), `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` (13 casos, 0 falhas), `python -m ruff check .` e `python -m compileall -q app tests` passaram em 18/10/2026; `git diff --check` passou na raiz. Testes confirmam plano aprovado idêntico ao recebido pela fonte, dois catálogos, bloqueio de escrita, IDs/operadores/valores/grão/limite inválidos e escopo restrito.
- Reconciliação ou amostra manual: a fixture de consumo continua retornando 420 unidades fictícias e a regressão sintética preserva os 13 resultados; não houve reconciliação com Gold.
- Critérios de aceite revisados e pendências: IA-06 continua sem autenticação real, resolução de período e grão Gold, AST/dialeto para eventual SQL textual, execução com credencial somente leitura e prova no banco. O plano lógico aprovado não torna SQL arbitrário seguro.
- Responsável/revisor: Codex (implementação e verificação sintética); revisão dos contratos e limites reais por Backend e Engenharia de Dados pendente.

### 2026-10-18 — IA-06 — política de acesso sintética na GenAI

- Estado anterior → novo estado: `Pendente` → `Pendente`; a proteção demonstrativa é evidência técnica parcial, sem autorização Gold.
- Mudança observável para usuário/negócio: perguntas e insights em modo real sem identidade verificada são recusados antes de acessar fonte ou modelo. No modo local, um principal fictício permite somente leitura de métricas e dimensões autorizadas no catálogo sintético. O corpo da requisição não concede permissão.
- Arquivos/commit/PR: `ai-agent/app/schemas/access.py`, `app/agent/access.py`, `app/api/access.py`, planner, orquestradores, rotas, `ai-agent/tests/test_access_policy.py` e [guia do serviço](services/ai-agent.md); commit `87a8a16` na branch de fundação GenAI.
- Dados usados: perfil e fontes sintéticas; nenhum dataset, dado pessoal ou consulta Gold.
- Verificações: em `ai-agent/`, `python -m pytest -q` (171 passaram em 18/10/2026), `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` (13 casos, 0 falhas), `python -m ruff check .` e `python -m compileall -q app tests` passaram; `git diff --check` passou na raiz. Testes com spies cobrem falta/adulteração de escopo, a mesma pergunta sob duas permissões, escrita, dados pessoais, limite HTTP, histórico que alega permissão e ausência de nova consulta causada por texto de evidência.
- Reconciliação ou amostra manual: o teste HTTP confirma recusa sem identidade no modo real e rejeição de campo `trusted` no payload. Não houve comparação quantitativa com Gold.
- Critérios de aceite revisados e pendências: a política checa fonte, operação, métrica, dimensão e sensibilidade antes da porta de evidência; autenticação do portal, derivação de permissões oficiais, validação de consulta concreta, credencial somente leitura, proteção completa da saída e reconciliação com Gold continuam pendentes. IA-06 não está concluído.
- Responsável/revisor: Codex (implementação e verificação local); revisão de Backend, Segurança e Engenharia de Dados pendente para integração real.

### 2026-10-20 — revisão da evidência sintética e ativação explícita do acesso demonstrativo

- Estado anterior → novo estado: IA-01 e IA-06 permanecem `Pendente`; esta revisão melhora o protótipo e não comprova integração com Gold ou autenticação real.
- Mudança observável: observações multirregistro podem conservar período ISO e dimensão catalogada em cada linha; a resposta quantitativa identifica esses recortes. O principal fictício só é concedido quando `GENAI_ENVIRONMENT=local` e `GENAI_ENABLE_DEMO_ACCESS=true` forem definidos explicitamente.
- Arquivos: `ai-agent/app/agent/evidence_guard.py`, `app/agent/orchestrator.py`, `app/schemas/domain_profile.py`, `app/api/access.py`, `app/config.py`, `app/main.py`, testes de evidência e acesso e guia do serviço. `app/agent/grounding.py`, sem consumidores, foi removido.
- Dados usados: perfis e linhas inteiramente sintéticos; nenhum registro Gold ou dado pessoal.
- Verificações: em `ai-agent/`, `python -m pytest -q` passou com 309 testes; `python -m ruff check .`, `python -m compileall -q app tests` e `git diff --check` passaram. A suíte foi executada fora do sandbox porque nele os sockets locais necessários ao event loop do Windows ficam bloqueados.
- Critérios de aceite e pendências: período e dimensão só atravessam a fronteira se classificados e validados; valores livres não entram. A janela por frase ainda não prova que as competências retornadas pertencem ao intervalo, e a origem dos dados continua sintética. Validar contrato/permissões Gold antes de concluir IA-01 ou IA-06.

### 2026-10-18 — proposta de propriedade da consulta Gold pelo Backend

- Estado anterior → novo estado: requisitos funcionais permanecem `Pendente`; registrada uma proposta para revisão conjunta sobre a propriedade da consulta Gold.
- Mudança observável para usuário/negócio: nenhuma. O endpoint atual de IA no Backend continua sendo placeholder e não consulta dados Gold.
- Arquivos/commit: proposta em [ADR-0002](decisions/0002-genai-gold-query-owner.md); estado atual da rota descrito no guia do Backend.
- Dados usados: código e contratos atuais do Backend/GenAI, PRD e dicionário Gold; nenhum dado real ou pessoal.
- Verificações: inspeção do endpoint `/api/v1/ai/query` confirmou que valida nomes contra uma lista fixa e devolve `records: []`; o modelo `GoldIndicador` é o único modelo analítico encontrado. A comparação não demonstra consulta, autorização somente leitura ou catálogo Gold funcional.
- Reconciliação ou amostra manual: a proposta recomenda Backend como dono da execução para centralizar autorização e consulta para portal e agente; não fixa tabelas, métricas ou fórmulas ainda não aprovadas.
- Critérios de aceite revisados e pendências: proposta aguarda revisão de Backend e Engenharia de Dados. P-04, esquema/carga Gold e contrato entre serviços continuam abertos; nenhum requisito IA ou DE mudou de estado.
- Responsável/revisor: Codex (proposta); confirmação pelos responsáveis de Backend e Engenharia de Dados pendente.

### 2026-10-18 — fronteira interna de evidências da GenAI

- Estado anterior → novo estado: requisitos funcionais permanecem `Pendente`; o fluxo interno do agente passa a depender de uma porta de evidências implementada atualmente pelo adaptador sintético.
- Mudança observável para usuário/negócio: nenhuma mudança no contrato HTTP; a troca da implementação de evidências não altera a resposta pública.
- Arquivos/commit: `ai-agent/app/tools/evidence.py`, `ai-agent/app/tools/synthetic_analytics.py`, `ai-agent/app/agent/planner.py`, `ai-agent/app/agent/orchestrator.py`, `ai-agent/tests/` e [guia do serviço GenAI](services/ai-agent.md).
- Dados usados: somente cenários sintéticos versionados; nenhuma consulta Gold ou dado real/pessoal.
- Verificações: em `ai-agent/`, `python -m pytest -q` (118 passaram), `python -m ruff check app tests`, `python -m compileall -q app tests` e `git diff --check` passaram fora do sandbox. Dentro do sandbox Windows, o event loop trava ao criar o `socketpair` local em `socket.accept`, antes de executar a aplicação.
- Reconciliação ou amostra manual: `tests/test_evidence_api.py` envia pergunta a `POST /api/v1/questions` com uma fonte alternativa à fixture e confirma que resposta e referência vêm desse adaptador. O planner mantém esclarecimento antes da consulta, filtros corrigidos e proveniência.
- Critérios de aceite revisados e pendências: a porta é interna e provisória; não define schema, métricas, fórmulas nem contrato HTTP entre serviços e não executa SQL. A proposta 4.1 aguarda revisão de Backend e Engenharia de Dados; integração Gold e todos os requisitos funcionais de IA continuam pendentes.
- Responsável/revisor: Codex (implementação); revisão do contrato pelos responsáveis de Backend e Engenharia de Dados pendente.

### 2026-10-18 — limite de payload no contrato interno de evidências

- Estado anterior → novo estado: requisitos funcionais continuam `Pendente`; o contrato interno valida o tamanho e a estrutura da evidência antes de repassá-la ao modelo.
- Mudança observável para usuário/negócio: fonte que retorna mais de 100 registros ou uma resposta inválida recebe erro recuperável genérico antes da geração.
- Arquivos/commit: `ai-agent/app/tools/evidence.py`, `ai-agent/app/agent/planner.py`, testes de contrato/fluxo e guia do serviço GenAI.
- Dados usados: fixtures sintéticas e resultados artificiais, sem dataset, Gold ou dados pessoais.
- Verificações: em `ai-agent/`, `python -m pytest -q` (121 passaram), `python -m compileall -q app tests` e `python -m ruff check .` passaram; na raiz, `git diff --check` passou fora do sandbox Windows.
- Reconciliação ou amostra manual: teste cobre resultado com mais de 100 registros, metadado de referência ausente e erro público genérico; cenários existentes cobrem filtro não suportado e ausência de evidência.
- Critérios de aceite revisados e pendências: limite de payload e tratamento de contrato inválido estão cobertos; timeout, autorização por identidade confiável, allowlist do executor e auditoria/correlação da consulta Gold continuam pendentes de decisão e integração com Backend/Dados. Nenhum requisito IA/DE mudou de estado.
- Responsável/revisor: Codex; revisão da política de acesso e auditoria por Backend e Engenharia de Dados pendente.

### 2026-10-18 — contratos e tratamento de falhas do protótipo GenAI

- Estado anterior → novo estado: requisitos IA permanecem Pendente; os contratos internos e a fronteira de evidências do protótipo foram reforçados, sem integração com Gold.
- Mudança observável para usuário/negócio: o fluxo demonstrativo distingue recusa, ausência de evidência e indisponibilidade; saídas inválidas da fonte ou do modelo resultam em erro controlado, sem resposta quantitativa infundada.
- Arquivos/commits: contratos em ai-agent/app/schemas/, porta em ai-agent/app/ports/evidence.py, adaptador sintético, planner, orquestradores e testes em ai-agent/tests/; limites e dependências descritos em docs/services/ai-agent.md.
- Dados usados: fixtures sintéticas identificadas como demonstração e fontes falsas; nenhum dado Gold, pessoal ou bruto foi usado.
- Verificações: em ai-agent/, python -m pytest -q (148 passaram), python -m compileall -q app tests e python -m ruff check .; na raiz, git diff --check. Os testes incluem contratos, endpoints, falhas da fonte, recusa, concorrência e cancelamento com fontes falsas.
- Reconciliação ou amostra manual: as expectativas dos testes sintéticos são fixadas separadamente do código testado; não houve reconciliação numérica com Gold.
- Critérios de aceite revisados e pendências: nenhum requisito IA foi concluído. Permanecem necessários catálogo e métricas Gold aprovados, autorização efetiva, consulta somente leitura na fonte real, reconciliação e integração com backend e portal.
- Responsável/revisor: Codex (implementação e verificação local); revisão de Backend e Engenharia de Dados pendente para o contrato real.

### 2026-10-16 — IA-07 — protótipo de follow-up contextual

- Estado anterior → novo estado: `Pendente` → `Pendente`; o protótipo local cobre parte do comportamento, mas não conclui o diferencial no produto integrado.
- Mudança observável para usuário/negócio: a API pode receber até três turnos anteriores em cada pergunta. Uma continuação reconhecida herda a intenção completa mais recente da pessoa usuária e substitui geografia/classe quando explicitadas. Uma mensagem histórica ambígua pede esclarecimento sem reaproveitar uma intenção mais antiga. O histórico é transitório e não é armazenado; o safety gate examina todos os turnos enviados antes de ferramenta/modelo.
- Arquivos/commit/PR: implementação local ainda não commitada em `ai-agent/app/agent/interpreter.py`, `ai-agent/app/agent/planner.py`, `ai-agent/app/agent/orchestrator.py`; testes em `ai-agent/tests/test_interpreter.py`, `ai-agent/tests/test_question_flow.py` e adaptação do harness em `ai-agent/tests/test_genai_regression.py`; contratos descritos em `ai-agent/README.md` e `docs/services/ai-agent.md`.
- Dados usados: cenários sintéticos existentes, sem dataset, Gold ou dados pessoais; adaptadores falsos nos testes, sem chamada ao Gemini.
- Verificações: em `ai-agent/`, `python -m pytest -q` (80 passaram), `python -m compileall -q app tests` e `python -m ruff check .` passaram. Na raiz, `git diff --check` passou em 16/10/2026.
- Reconciliação ou amostra manual: teste HTTP confirma herança de consumo/período, correção de Olinda para Jaboatão, ausência de evidência quando a fixture não cobre o filtro, esclarecimento quando a última fala anterior é ambígua, bloqueio de instrução em turnos user/assistant e ausência de herança em chamada sem contexto.
- Critérios de aceite revisados e pendências: o comportamento sintético e os limites do parser lexical estão cobertos. IA-07 permanece `Pendente` até validar continuidade e isolamento na integração com backend/portal e os critérios de sessão definidos pela equipe; o contexto recebido pela API ainda não tem autenticação/autorização própria.
- Responsável/revisor: Codex (implementação e verificações locais); revisão humana dos critérios de sessão e do comportamento integrado pendente.

### 2026-10-16 — IA-08 — regressão sintética de perguntas e insights

- Estado anterior → novo estado: `Pendente` → `Pendente`; a avaliação local é evidência técnica parcial e não mede resultados reconciliados com Gold.
- Mudança observável para usuário/negócio: conjunto versionado passa a avaliar, além das perguntas conversacionais existentes, quatro resultados do endpoint de insight: hipótese fundamentada nos valores fornecidos, esclarecimento, recusa e insuficiência de série histórica.
- Arquivos/commit/PR: `ai-agent/tests/fixtures/genai_regression.json` (versão 2.0.0), `ai-agent/tests/test_genai_regression.py`, `ai-agent/reports/synthetic-regression-report.json`, README e guia do serviço. Implementação local ainda não commitada.
- Dados usados: fixtures artificiais marcadas como demonstração; adaptador fixo em todos os casos. Nenhum dataset real, chamada ao Gemini ou chave foi usado.
- Verificações: em `ai-agent/`, `python -m pytest -q` (86 passaram), `python -m compileall -q app tests`, `python -m ruff check .` e `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` (13 casos aprovados, 0 falhas); na raiz, `git diff --check` passou em 16/10/2026. Teste de repetibilidade confirmou que o relatório gerado com o mesmo código e fixtures tem conteúdo idêntico.
- Reconciliação ou amostra manual: os quatro casos de insight verificam estado HTTP, número de chamadas ao modelo, trecho esperado, referência e, quando aplicável, valor observado. O caso de insuficiência usa um total sintético sem série mensal e espera esclarecimento, não uma tendência inventada.
- Critérios de aceite revisados e pendências: cobertura sintética e relatório reproduzível atendem ao checkpoint técnico. IA-08 continua `Pendente` até um conjunto aprovado medir fundamentação e correção contra Gold; o adaptador fixo não avalia a qualidade real do Gemini.
- Responsável/revisor: Codex (implementação e verificações locais); revisão humana dos casos esperados e avaliação contra Gold pendentes.

### 2026-10-16 — preparação de WEB-01 a WEB-07 e IA-01 a IA-06 — skill de prototipação

- Estado anterior → novo estado: requisitos funcionais permanecem `Pendente`; skill própria criada como preparação documental.
- Mudança observável para usuário/negócio: instrução reutilizável para planejar e revisar o protótipo, com quatro páginas Figma e temas claro/escuro compartilhando componentes e tokens; direção visual inicial híbrida registrada em §9.3, com escolhas específicas ainda abertas.
- Arquivos/commit/PR: branch `feat/git-or-treat-figma`; [skill](../.agents/skills/git-or-treat-figma/SKILL.md), seus três guias de apoio, metadados Codex e adaptador Claude; [catálogo de ferramentas](agents/tooling.md#skill-própria-de-prototipação) e §9.3/§12 deste PRD. Sem publicação ou arquivo Figma criado nesta etapa.
- Dados usados: PRD, guias frontend/backend/IA e dicionário ainda sem esquema real; consulta às cinco referências oficiais em 16/10/2026, com a limitação de abertura de Motion Primitives documentada no guia. Nenhum dataset ou dado pessoal utilizado.
- Verificações: `python -X utf8 <pasta-da-skill-creator>/scripts/quick_validate.py .agents/skills/git-or-treat-figma` aprovou nome/frontmatter/estrutura; bloco Python do workflow `.github/workflows/quality.yml` executado localmente aprovou configurações, seis imports e links em 33 documentos; `python -m compileall -q .hooks` passou. Links internos da skill e correspondência do adaptador foram conferidos. `git diff --check` inicialmente detectou espaços finais no cabeçalho alterado, corrigidos antes da verificação final aprovada.
- Reconciliação ou amostra manual: teste de comportamento por subagente antes/depois da skill, sem escrita externa. Na revisão com a skill, o plano propôs quatro páginas com uma biblioteca e dois modos; distinguiu números do enunciado de achados e limitou paralelismo à análise, mantendo futura escrita coordenada no Figma. Uma ambiguidade sobre iniciar entrevista em pedidos preparatórios foi corrigida e revalidada.
- Critérios de aceite revisados e pendências: matriz cobre jornadas obrigatórias, estados alternativos e diferenciais selecionáveis. Essa revisão é documental; nenhuma integração, cálculo Gold, controle de acesso ou requisito funcional foi validado. Pendentes direção visual, dispositivo, diferenciais, plano/acesso e criação via Figma MCP, capturas e navegação do protótipo.
- Responsável/revisor: Codex (autoria e verificações locais); subagente de revisão comportamental; revisão humana do resultado e critérios funcionais pendente.

### 2026-10-16 — preparação de WEB-01 a WEB-07 e IA-01 a IA-06 — protótipo visual

- Estado anterior → novo estado: todos os requisitos funcionais permanecem `Pendente`; protótipo visual criado como referência adicional solicitada pela pessoa usuária.
- Mudança observável para usuário/negócio: quatro páginas Figma, 16 frames por tema, biblioteca compartilhada e jornadas conectadas para panorama, receita, UC, inspeções, ordens, operação e assistente. Paleta cacau/goiaba/pistache aprovada; backgrounds editáveis e transições nativas representados.
- Arquivos/commit/PR: branch `feat/git-or-treat-figma`; [registro visual](design/grid360-prototype.md), §9.3/§12 deste PRD, [guia frontend](services/frontend.md), [catálogo de ferramentas](agents/tooling.md) e README. [Arquivo Figma](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K); scripts/capturas temporários em `work/` não integram a entrega versionada e foram excluídos pelo `.gitignore`.
- Dados usados: cenários totalmente sintéticos, sem dataset ou dados pessoais. Receita demonstrativa R$ 80.000 → R$ 76.500; decomposição −8.000 + 5.000 − 500 = −3.500. Não são achados do diagnóstico real.
- Verificações: auditoria de leitura pelo Figma MCP em 16/10/2026 encontrou, por tema, 16/16 frames alcançáveis, 250 instâncias, 764 textos e zero destinos inexistentes, fontes ausentes, textos colapsados ou transbordamentos internos detectados. Capturas dos layouts principais e overlays inspecionadas; painel FEC corrigido e recapturado. Procedimento e contrastes medidos no registro visual. O bloco Python do workflow `.github/workflows/quality.yml`, executado localmente, aprovou configurações, seis imports compartilhados e links em 34 documentos; `git diff --check` passou.
- Reconciliação ou amostra manual: totais dos municípios e bairros demonstrativos conferidos; UC e suspeita de perdas usam identificadores distintos. Revisão corrigiu recortes sem detalhe, retorno dos filtros, fundamento por contexto, série FEC e vencimento fictício de fatura. O player carregou o panorama; sequência de cliques e alterações de variáveis no player ainda não foram validadas manualmente.
- Critérios de aceite revisados e pendências: cobertura visual dos requisitos obrigatórios, com estados alternativos e limites explícitos. Gold, API, persistência de ordens, segurança Text-to-SQL, teclado, responsividade e números reais não foram implementados ou comprovados. Diferenciais fora desta primeira versão.
- Responsável/revisor: Codex coordenou a escrita no Figma MCP; subagentes apoiaram componentes, jornadas e revisão documental. Revisão humana do protótipo e critérios funcionais pendente.

### 2026-10-17 — preparação visual de WEB-03, WEB-05 e WEB-07 — revisão de usabilidade e acessibilidade

- Estado anterior → novo estado: estados dos requisitos funcionais preservados; revisão delimitada do protótipo, sem nova conclusão funcional.
- Mudança observável: Apple HIG, Material Design 3 e WCAG 2.2 foram consultados e incorporados às referências da skill. No Figma, campos ganharam alinhamento inicial e altura de entrada de 48 unidades; foco ganhou contorno contrastante; carregamento ganhou texto próprio; navegação ganhou marcador de seleção e correção do item Operação; cancelamento passou a identificar a ordem e oferecer “Manter ordem”.
- Arquivos/commit: referências registradas no commit `213a5e7`, na branch `docs/prototype-reference-audit`; [fontes, elementos, evidências e limites](../.agents/skills/git-or-treat-figma/references/visual-references.md#aplicação-no-protótipo). O esclarecimento anterior em `docs/design/grid360-prototype.md` foi removido conforme solicitado; o registro desta revisão fica na skill. [Arquivo Figma](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K). Consulta e ajustes iniciados em 16/10, registro final em 17/10.
- Dados usados: conteúdo sintético já presente no protótipo; nenhum dado real, dataset ou credencial.
- Verificações: auditoria via Figma MCP encontrou 16/16 frames alcançáveis por tema, 251 instâncias, 765 textos e zero destinos inexistentes, fontes ausentes, textos colapsados ou transbordamentos internos. Os 150 alvos ON_CLICK por tema têm altura mínima 44 e largura mínima 109 unidades no canvas. Capturas dos componentes afetados e overlays dos dois temas inspecionadas; “Manter ordem” fecha sem alterar variável e “Cancelar ordem” mantém a simulação existente. Contraste do foco/superfície: 15,53:1 claro e 13,24:1 escuro.
- Reconciliação/revisão: teste documental da skill antes/depois demonstrou cobertura das fontes específicas, unidades e registro por critério. Comparação de propriedades e textos renderizados não encontrou divergências nos botões dos fluxos.
- Verificações documentais: `quick_validate.py .agents/skills/git-or-treat-figma` aprovou a skill; bloco Python do workflow de qualidade aprovou configurações, seis imports compartilhados e links em 34 documentos; `git diff --check` passou.
- Pendências: CSS px, teclado, Escape, leitor de tela, reflow, foco executável e navegação completa no player exigem testes específicos. A revisão parcial não comprova conformidade WCAG AA nem critérios funcionais do portal.
- Responsável/revisor: Codex coordenou consulta, alterações e verificações; subagente realizou o teste documental da skill. Revisão humana do comportamento executável pendente.

### 2026-10-17 — checkup de cobertura do protótipo contra o PRD

- Estado anterior → novo estado: requisitos funcionais e diferenciais permanecem `Pendente`; revisão da cobertura visual não muda seus estados.
- Mudança observável para usuário/negócio: matriz por ID separa o que está mostrado do que precisa ser confirmado para fechar o protótipo; inclui os caminhos mobile que a pessoa usuária informou que adicionará.
- Arquivos/commit/PR: [checkup e lista de fechamento](design/grid360-prototype.md#checkup-contra-o-prd--17102026); arquivo Figma e frames estão vinculados no registro visual.
- Dados usados: PRD, guias frontend/backend/IA, dicionário Gold ainda sem esquema real, registro visual e conteúdo sintético do protótipo. Nenhum dado real ou pessoal.
- Verificações: comparação requisito a requisito de WEB-01 a WEB-10 e IA-01 a IA-06 com a cobertura e limitações documentadas; player testado em 17/10/2026 nos modos claro/escuro, Receita, Inspeções, detalhe da suspeita e criação demonstrativa de ordem `OS-DEMO-001`.
- Reconciliação ou amostra manual: navegação e transição da fila para detalhe e criação de ordem foram observadas no player. A ordem é simulada e não persiste; os valores continuam sintéticos, sem Gold/API.
- Critérios de aceite revisados e pendências: frames cobrem as jornadas principais, mas faltam conferir por fluxo os estados alternativos, recorte de receita por classe, casos de ausência da UC, filtros/insight após alteração e ciclo completo/cancelamento de ordens. Mobile está em andamento pela pessoa usuária. Segurança da IA, reconciliação, acessibilidade executável e responsividade permanecem dependentes da aplicação. WEB-08 a WEB-10 seguem fora do escopo selecionado.
- Responsável/revisor: Codex; revisão humana do protótipo após a inclusão mobile pendente.

### 2026-10-17 — WEB-01 a WEB-07 e IA-01 a IA-06 — passada manual ampliada no player Figma

- Estado anterior → novo estado: requisitos funcionais permanecem `Pendente`; a passada verificou apenas a execução demonstrativa do protótipo.
- Mudança observável para usuário/negócio: foram percorridos filtros/estados do panorama, Receita, busca e detalhe de UC, inspeções, ações de ordem, operação DEC/FEC e exemplos do assistente em tema claro/escuro. A matriz registra o que foi visto e limitações por requisito em [checkup do protótipo](design/grid360-prototype.md#checkup-contra-o-prd--17102026).
- Arquivos/commit/PR: `docs/design/grid360-prototype.md` (registro dos cenários e resultado); sem edição do arquivo Figma.
- Dados usados: somente conteúdo sintético do protótipo; nenhum dataset ou dado pessoal.
- Verificações: navegação e cliques diretos no player autenticado em 17/10/2026; fluxo de receita e UC, estados de insuficiência/erro/recuperação, ordem `OS-DEMO-001`, detalhe DEC/FEC e assistente. Reiniciar retornou ao panorama.
- Reconciliação ou amostra manual: IA respondeu insuficiência sem inferir zero; UI distinguiu faturado de pago; UC mostrou ressalvas de GD/dados incompletos. Falha reproduzida: cancelar `OS-DEMO-001`, reabrir suas ações e atualizar o estado faz a ordem voltar visualmente a “Em análise”.
- Critérios de aceite revisados e pendências: a ordem cancelada deve permanecer terminal na simulação e o fluxo precisa ser repetido após correção. Filtros, busca e estados são exemplos estáticos; nada nesta passada comprova API, Gold, persistência, autorização ou cálculo real. Mobile não está no arquivo testado. Leitor de tela aparece desativado no player; acessibilidade executável e responsividade continuam pendentes.
- Responsável/revisor: Codex; correção e revisão humana do protótipo pendentes.

### 2026-10-17 — DE-01 — Bronze com reconciliação e captura de registros malformados

- Estado anterior → novo estado: `Pendente` → `Em validação`; a ingestão roda e a conta fecha, mas o PR #8 ainda não foi revisado e a reconciliação não registra o hash do arquivo de origem (§4.3).
- Mudança observável para usuário/negócio: a Bronze passa a devolver, por fonte, quantas linhas físicas de origem foram lidas, quantas viraram linha da tabela e quantas foram rejeitadas. Registro malformado deixa de ser descartado em silêncio: vai para `bronze.rejeitados` com o conteúdo bruto, e `bronze.reconciliacao` fecha a conta com `delta = 0`.
- Arquivos/commit/PR: `data-engineering/notebook/Landing_to_Bronze.ipynb` (reescrito, então `01_bronze.py`), `data-engineering/notebook/Bronze_perfilamento.ipynb` (colunas de auditoria no perfilamento e deduplicação restrita às colunas de negócio, então `02_perfilamento.py`), [ADR-0003](decisions/0003-reconciliacao-e-captura-de-registros-malformados.md), `docs/services/data-engineering.md` e este PRD; branch `feat/bronze`, PR #8 (ainda sem revisão).
- Dados usados (versão/fonte; sem anexar dados sensíveis): extração do case com as 8 fontes, no Volume `/Volumes/workspace/default/venergy`; dados brutos não versionados (`.gitignore`).
- Verificações: execução completa do notebook na Databricks Free Edition em 17/10/2026, sem erro. Contagens: unidades_consumidoras 46.461, medidores 51.812, ocorrencias_rede 180.000, geracao_distribuida 3.510, faturas 2.184.623, leituras 2.182.468, atendimentos 318.871, inspecoes 1.389 (abas 511 + 383 + 495). `bronze.reconciliacao` com `delta = 0` em todas as linhas; `atendimentos` sai como `SEM_BASE` e `inspecoes` com `linhas_arquivo = null` (esperado). Autoteste de registros malformados `OK` nos dois leitores (CSV 1 válida/2 rejeitadas; JSON 1 válida/1 rejeitada). `bronze.rejeitados` sem linhas. `python -m py_compile` local nos dois notebooks.
- Reconciliação ou amostra manual: `bronze.leituras` conferida contra a contagem física do Volume — 2.182.473 linhas menos 5 cabeçalhos = 2.182.468, igual à tabela. As demais fontes fecham por aritmética dentro do próprio notebook (§4.3).
- Critérios de aceite revisados e pendências: as 8 fontes estão em Delta com origem rastreável e os rejeitados são contados e isolados. Falta para `Concluído`: revisão do PR #8, hash/versão do arquivo na reconciliação (§4.3), decisão da Silver sobre a quarentena dos rejeitados e conferência de encoding/separador (hoje documentada, não automatizada).
- Responsável/revisor: juliatenoriocalado (implementação e execução na Databricks); revisão de pares pendente no PR #8.

### 2026-10-17 — DE-01 — perfilamento da Bronze: medição corrigida e cobertura completa

- Estado anterior → novo estado: DE-01 permanece `Em validação`; o perfilamento deixa de ser um relatório de tela e passa a ser artefato persistido, e as contagens passam a medir o mesmo que a Silver vai tratar.
- Mudança observável para usuário/negócio: o relatório de problemas vira a tabela Delta `quality.perfil_bronze` (113 linhas na execução), além da cópia em CSV no Volume; a gravação saiu de dentro de `try/except`, então falha de escrita falha à vista em vez de seguir sem insumo. Números inflados caíram: `valor_total` não numérico foi de 196.624 para 2, porque o perfil passou a normalizar moeda, vírgula decimal e sufixo em vez de chamar de podre o que é só formato. Data que não está em ISO deixou de ser contada como inválida e passou a ser contada como **ambígua**, que é uma decisão de negócio e não um defeito do dado.
- Arquivos/commit/PR: `data-engineering/notebook/Bronze_perfilamento.ipynb` (então `02_perfilamento.py`); branch `feat/bronze`, PR #8.
- Dados usados (versão/fonte; sem anexar dados sensíveis): extração do case com as 8 fontes, no Volume `/Volumes/workspace/default/venergy`; dados brutos não versionados (`.gitignore`).
- Verificações: execução completa na Databricks Free Edition em 17/10/2026, sem erro e sem nenhum aviso de coluna ausente nas 8 tabelas. Duplicata exata (linha idêntica nos campos de dado) passa a ser medida: 21.523 em `leituras`, 900 em `unidades_consumidoras`, 513 em `medidores`, 1 em `faturas` — antes dava 0 sempre, porque `_id_registro` é único por linha. Órfão passa a contar linha afetada, não só chave: `faturas` 32.285 linhas (31.705 UCs distintas), `leituras` 8.609. Negativo passa a ser checado em todo campo numérico, com exceção de `latitude`/`longitude` (46.460 cada, onde negativo é legítimo): 8.068 em `leitura_anterior` e 8.150 em `consumo_kwh`. Grafia divergente passa a rodar nas 20 colunas categóricas: 32 em `inspecoes.inspetor`, 9 em `medidores.modelo`, 5 em `classe`, 3 em `medidores.tipo`, 2 em `inspecoes.resultado`. `inspecoes._aba_origem`, que é coluna nossa, sai do perfil de dado e entra nas colunas de auditoria. Nulos aparecem em 8 colunas, concentrados em `medidores.data_ultima_manutencao` (51.812, 100%) e `medidores.data_retirada` (31.796, 61,37%). Datas ambíguas de dia/mês: 102.878 em `leituras.data_leitura` e 61.226 em `faturas.data_emissao`. `python -m py_compile` local no notebook.
- Reconciliação ou amostra manual: contagens por tabela conferidas contra a execução anterior na mesma base (2.184.623 faturas, 2.182.468 leituras, 318.871 atendimentos), sem divergência; a origem de cada número está impressa nas seções 2 a 9 do próprio notebook.
- Critérios de aceite revisados e pendências: falta para `Concluído`: (a) as contagens de data de `ocorrencias_rede` (`data_abertura`, `data_encerramento`) e `atendimentos` (`data_abertura`, `data_fechamento`) saíram infladas nesta execução — o conteúdo é timestamp e o leitor aceitava apenas data pura; a leitura foi corrigida no código e essas contagens serão refeitas na próxima execução; (b) decisão de negócio pendente sobre data ambígua de dia/mês (`11-05-2022`), que a Silver não pode resolver sozinha; (c) faturas não pagas com `data_pagamento` preenchida têm data no futuro em 61.333 de 61.335 linhas — investigar com o negócio antes de tratar como erro; (d) decisões B1 a B3 do dicionário de dados; (e) revisão do PR #8.
- Responsável/revisor: juliatenoriocalado (implementação e execução na Databricks); revisão de pares pendente no PR #8.

### 2026-10-18 — DE-01 — notebook no nome e no formato do bootcamp, com a justificativa da carga

- Estado anterior → novo estado: DE-01 permanece `Em validação`; os dois notebooks da Bronze passam ao `.ipynb` (formato exigido pelo documento de entrega da atividade, que também lista o `.yaml` do Workflow) e ao nome do padrão dela, e a estratégia de carga deixa de ser escolha implícita e ganha justificativa dentro do próprio notebook.
- Mudança observável para usuário/negócio: quem avaliar abre `data-engineering/notebook/Landing_to_Bronze.ipynb` e `data-engineering/notebook/Bronze_perfilamento.ipynb` — mesmo formato e mesma lógica de nome da atividade — e a revisão do PR #8 encontra na seção "Decisões desta versão" por que a carga é por sobrescrita e não por acréscimo. O comportamento da Bronze não muda: isto é empacotamento e documentação.
- Arquivos/commit/PR: `data-engineering/notebook/Landing_to_Bronze.ipynb` (era `01_bronze.py`) e `data-engineering/notebook/Bronze_perfilamento.ipynb` (era `02_perfilamento.py`), com os dois `.py` removidos — o Databricks não aceita dois notebooks com o mesmo nome no mesmo diretório, mesmo em extensões diferentes; a decisão 6 do notebook de ingestão documenta a carga por `overwrite`; branch `feat/bronze`, PR #8.
- Dados usados (versão/fonte; sem anexar dados sensíveis): extração do case com as 8 fontes, no Volume `/Volumes/workspace/default/venergy`; dados brutos não versionados (`.gitignore`).
- Verificações: a conversão foi conferida por round-trip — o `.py` reconstruído a partir de cada `.ipynb` é idêntico célula a célula ao original, nas 57 células (29 markdown, 28 de código). O conjunto de linhas de código tem **hash idêntico** ao da versão `.py` do commit anterior (453 linhas em `Landing_to_Bronze.ipynb`, 418 em `Bronze_perfilamento.ipynb`), ou seja, nenhuma linha de lógica mudou. JSON em `nbformat` 4.5 válido, ids de célula únicos, UTF-8 sem BOM, sem CRLF. `python -m py_compile` local OK nos dois antes da conversão.
- Reconciliação ou amostra manual: as duas únicas diferenças de conteúdo são as esperadas — o markdown do `Landing_to_Bronze.ipynb` foi de 214 para 224 linhas (as 10 da decisão 6 sobre `overwrite`) e o do `Bronze_perfilamento.ipynb` ficou idêntico (89 linhas).
- Critérios de aceite revisados e pendências: falta para `Concluído`: (a) confirmar no Databricks que os dois `.ipynb` abrem e executam — a conversão foi provada localmente, mas o ambiente que decide é o de lá; (b) recontar as 4 colunas de data de `ocorrencias_rede` e `atendimentos`; (c) decisão de negócio sobre data ambígua de dia/mês; (d) decisões B1 a B3 do dicionário de dados; (e) revisão do PR #8.
- Responsável/revisor: juliatenoriocalado (implementação); devolutiva de revisão de pares de 18/10/2026 endereçada neste commit (nome, formato e justificativa da carga).

### 2026-10-18 — DE-01 — Workflow do Databricks com as tarefas da Bronze

- Estado anterior → novo estado: DE-01 permanece `Em validação`; o pipeline da Bronze deixa de existir só como execução manual e passa a ter orquestração versionada no repositório, no lugar que o documento de entrega pede (`data-engineering/`, junto dos notebooks). O job nasce com as duas tarefas que existem hoje e recebe Silver e Gold como novos elos depois.
- Mudança observável para usuário/negócio: quem avaliar encontra em `data-engineering/configuracao/databricks/v-energy-grid-360.yaml` a definição do job `v-energy-grid-360` — `Landing_to_Bronze` e depois `Bronze_perfilamento`, nessa ordem porque o perfilador lê as tabelas que a ingestão acabou de gravar. A pergunta "com que frequência isso roda?" deixa de ter resposta só na conversa: o agendamento é mensal, dia 5, às 03:00 (America/Recife), com o motivo escrito no próprio arquivo — leituras e faturas são por competência, então rodar mais de uma vez no mês não traz dado novo, só custo. Reexecutar é seguro porque a Bronze é carregada por sobrescrita e reconciliada com `delta = 0`; é a mesma idempotência que motivou o `overwrite` e não o `append`, agora valendo como garantia operacional.
- Arquivos/commit/PR: `data-engineering/configuracao/databricks/v-energy-grid-360.yaml` — definição do job criado no workspace, com comentários de porquê; branch `feat/bronze`, PR #8.
- Dados usados (versão/fonte; sem anexar dados sensíveis): extração do case com as 8 fontes, no Volume `/Volumes/workspace/default/venergy`; dados brutos não versionados (`.gitignore`).
- Verificações: job criado e executado no Databricks com as duas tarefas concluídas — a execução `14313419965490` (18/10, 02:46) fechou em **21m 03s**, sendo 15m 22s de `Landing_to_Bronze` e 5m 39s de `Bronze_perfilamento`. A soma das partes dá 21m 01s contra 21m 03s de total: as tarefas rodaram **uma depois da outra**, e não em paralelo — se fossem concorrentes o total seria o da maior delas (15m 22s). A aba List da execução confirma o elo com `Depends on = Landing_to_Bronze` e `Run if dependencies = All succeeded`. O job rodou 4 vezes em 18/10 (02:34, 02:34, 02:36 e 02:46), todas bem-sucedidas — o que também exercita a idempotência da carga. As tarefas usam o compute serverless da Free Edition (`performance_target: PERFORMANCE_OPTIMIZED`), montagem que dispensa `.cache()` e que motivou exportar o YAML da UI em vez de escrevê-lo de cabeça. O output da ingestão repete o que a execução de 17/10 já havia mostrado: `AUTOTESTE registros malformados: OK`, `delta = 0` nas 8 tabelas (`atendimentos` sai `SEM_BASE`, esperado porque o JSON é indentado) e `bronze.rejeitados` vazia.
- Reconciliação ou amostra manual: o arquivo foi conferido contra o YAML exportado da UI depois de o agendamento ser armado, e a única diferença é o `run_if: ALL_SUCCESS` escrito por extenso — o export não repete essa linha porque o padrão do Databricks já é "All succeeded", e ela ficou explícita para a garantia não virar memória de quem lê. O cron é o do próprio job (`29 0 3 5 * ?`; o deslocamento de segundos dentro do minuto de 03:00 vem da UI). Uma primeira tentativa de agendamento foi corrigida: a UI aceitou "a cada 5 dias", o que seriam ~73 execuções por ano em vez de 12 — custo puro para um insumo mensal. Duas alternativas foram consideradas e registradas: o **gatilho de chegada de arquivo** no Volume (`On file arrival`, que a própria UI sugere), descartado porque no Dataset os arquivos entram em lote e cada chegada dispararia uma execução, enquanto o agendamento dispara uma vez no dia combinado; e transformar o arquivo em **bundle** instalável, descartado porque exigiria a CLI do Databricks e um `databricks.yml` na raiz, e o documento de entrega pede o yaml do Workflow, não a instalação automatizada.
- Critérios de aceite revisados e pendências: falta para `Concluído`: (a) importar/confirmar os dois `.ipynb` no Databricks; (b) recontar as 4 colunas de data de `ocorrencias_rede` e `atendimentos`; (c) decisão de negócio sobre data ambígua de dia/mês; (d) decisões B1 a B3 do dicionário de dados; (e) revisão do PR #8; (f) tarefas de Silver e Gold no Workflow, quando os notebooks existirem.
- Responsável/revisor: juliatenoriocalado (criação do job e execução no Databricks); revisão de pares pendente no PR #8.

### 2026-10-18 — preparação de WEB-01 a WEB-07 e IA-01 a IA-06 — arquitetura do frontend

- Estado anterior → novo estado: requisitos funcionais permanecem `Pendente`; fundação arquitetural preparada na branch `refactor/arquitetura-frontend`.
- Mudança observável: as sete áreas mantêm navegação e cabeçalho, agora com layout persistente e registro único de rotas. A indicação fixa e não verificada de API online foi retirada. As páginas continuam vazias; não foram construídos KPIs, gráficos ou integrações.
- Arquivos: `frontend/src/app`, `layouts`, `features`, `shared`, `styles`; configuração Tailwind/Vite, TypeScript estrito, testes e verificações na CI. Decisão e limites em [ADR-0001](decisions/0001-arquitetura-frontend.md) e [guia arquitetural](architecture/frontend.md).
- Dados usados: nenhum dataset ou dado de negócio; testes de infraestrutura usam respostas HTTP artificiais e rotas vazias. O provedor de consultas não dispara solicitações.
- Verificações: instalação reproduzível com `npm ci`; limites de importação, formatação, lint, dez testes de transporte/composição e tipos/build. O resultado final e a revisão de navegação ficam no [plano de execução](plans/2026-10-18-arquitetura-frontend.md).
- Pendências: alinhamento visual ao Figma, componentes visuais, contratos por domínio, filtros, dados reais, operações e IA. A arquitetura não comprova critérios de aceite funcionais, reconciliação com Gold ou conformidade WCAG AA.
- Responsável/revisor: Codex executou a fundação; revisão humana da branch pendente.

### 2026-10-18 — preparação visual de WEB-01 e navegação do portal — sidebar e topo do Panorama

- Estado anterior → novo estado: requisitos funcionais continuam `Pendente`; primeira fatia visual implementada na branch `feat/visual-frontend`, renomeada de `refactor/arquitetura-frontend`.
- Mudança observável: sidebar com marca e ícones Lucide do protótipo; topo do Panorama com título, subtítulo, decoração e alternância de tema. Menu mobile reproduz a navegação. O rodapé demonstrativo e a linha de atualização ilustrativa foram retirados conforme solicitação; filtros e todo o conteúdo de dados ficaram fora.
- Arquivos: `frontend/src/layouts/`, `frontend/src/shared/ui/`, `frontend/src/features/panorama/` e `frontend/src/styles/`; medidas, frames Figma e limites na [arquitetura do frontend](architecture/frontend.md).
- Dados usados: nenhum dataset, dado de negócio ou mock de produto. As imagens decorativas não representam métricas.
- Verificações: limites de importação, formatação, lint, dez testes e tipos/build; revisão visual e de navegação no Chrome headless com temas claro/escuro, desktop 1440 × 1024 e mobile 390 × 844, incluindo Escape, retorno de foco e ausência de consultas de negócio. Evidências locais ficam em `work/visual-frontend/`, ignorado pelo Git.
- Reconciliação e pendências: não aplicável a números nesta fatia. WEB-01/WEB-07 ainda exigem dados reais, filtros e evidência integrada; demais jornadas não foram implementadas. Revisão humana da aparência pendente.

### 2026-10-18 — preparação visual de WEB-02 a WEB-06 e IA-05 — textos superiores

- Estado anterior → novo estado: requisitos funcionais permanecem `Pendente`; títulos, subtítulos e contexto superior das outras seis áreas alinhados aos frames originais do Figma, nos dois temas.
- Mudança observável: textos de Receita, UC 360, Inspeções, Ordens, Operação e Assistente reproduzem o protótipo. UC 360 mostra Atendimento no topo; Inspeções mostra Perdas. Sidebar e Panorama preservados. O Assistente recebe a abertura textual em um painel central com superfície, borda e cantos do protótipo, sem exemplos, campo de envio ou funcionalidades de chat.
- Arquivos: `frontend/src/app/routes.ts`, `frontend/src/layouts/navigation.ts`, `frontend/src/layouts/AppLayout.tsx`, `frontend/src/features/assistente/AssistentePage.tsx` e teste de navegação existente. Frames claros consultados via Figma MCP: `15:331`, `15:582`, `15:773`, `16:640`, `16:735`, `16:991`, além do painel mobile `195:8810`; correspondentes escuros: `16:1296`, `16:1547`, `16:1738`, `16:1894`, `16:1989`, `16:2245`.
- Dados usados: nenhum dataset, mock de produto ou consulta. Não foram adicionados filtros, indicadores, tabelas, formulários ou respostas de IA.
- Verificações: formatação, fronteiras, lint, dez testes existentes e tipos/build; seis rotas conferidas no navegador em claro/escuro, desktop/mobile, sem conteúdo de negócio. Após correção do layout do Assistente, suas caixas foram comparadas com os metadados do Figma e coincidiram nos dois temas: painel desktop 960 × 800 px em x=352/y=104, mobile 358 × 752 px em x=16/y=76, além das posições do título e texto de apoio. A altura do painel foi adaptada à janela: 800 px é máximo no desktop e apenas o histórico pode rolar; janelas menores não exigem rolar a página até o futuro compositor. A revisão posterior fixou o bloco textual padrão em 810 px no desktop e comparou posições e quebras ao Figma em 24 casos via Playwright MCP. O zoom nativo de 80% a 400% cobre sete rotas nos dois temas; em altura de até 480 px, o Assistente compacta o cabeçalho interno para manter área de histórico. Capturas e medições locais em `work/visual-frontend/`. Reconciliação de dados não se aplica a esta alteração visual.
- Pendências e revisor: critérios funcionais e integrações continuam pendentes; revisão humana dos textos e interface pendente.

### 2026-10-18 — preparação visual de WEB-01 — fluxo de energia no Panorama

- Estado anterior → novo estado: requisito funcional permanece `Pendente`; decoração estática substituída por movimento SVG aprovado na conversa.
- Mudança observável: as duas linhas originais aparecem progressivamente; pulsos goiaba percorrem as trilhas e pontos próximos acendem em pistache. A entrada termina em cerca de 3,7 s, sem loop; passar o mouse após o repouso repete apenas os pulsos. Movimento reduzido mantém a composição estática. No desktop, o ornamento fica na faixa entre o texto de abertura e o alternador de tema, cresce responsivamente até 320 px e não altera as posições do texto e do botão. O mobile continua sem o ornamento.
- Arquivos: `frontend/src/features/panorama/PanoramaArtwork.tsx`, `panorama-artwork.css`; remoção dos dez SVGs decorativos substituídos. Referências e comportamento na [arquitetura do frontend](architecture/frontend.md#movimento-decorativo-do-panorama--18102026).
- Dados usados: nenhum dataset, mock de produto ou API. O efeito é apenas decorativo.
- Verificações: limites de importação, formatação, lint, dez testes existentes e tipos/build; Playwright MCP para duração finita, repouso, replay, movimento reduzido e comportamento nos dois temas/mobile; captura visual e deslocamento do pulso conferidos no navegador. Após o ajuste de composição, foram comparadas as posições do texto e do botão e o espaço do ornamento em 1440, 1280, 1024 e 390 px; build, lint, formatação e fronteiras passaram. Evidências locais em `work/visual-frontend/`.
- Pendências e revisor: revisão humana da animação pendente; requisitos funcionais de indicadores, filtros e IA não são concluídos por este efeito.

### 2026-10-18 — preparação visual do portal — favicon Grid360

- Requisitos funcionais permanecem `Pendente`. O ícone padrão do Vite foi substituído pelo símbolo da marca usado na sidebar, em `frontend/public/favicon.svg`, referenciado por `frontend/index.html`.
- O SVG adapta as cores à preferência clara/escura do navegador; não usa dados de negócio. Verificação: carregamento e renderização pelo Playwright MCP, formatação, lint, fronteiras, testes existentes e build. Revisão humana da identidade visual pendente.

### 2026-10-19 — DE-01 — falhas explícitas na ingestão Bronze

- Estado anterior → novo estado: `Em validação` → `Em validação`; a correção local ainda não foi executada no Databricks.
- Mudança observável para usuário/negócio: o notebook encerra a tarefa com erro se o autoteste de parse falhar, se as três abas esperadas de inspeções mudarem, se a quarentena não fechar com as rejeições registradas ou se a reconciliação de alguma fonte divergir. O Workflow não inicia o perfilamento quando a ingestão falha.
- Arquivos/commit/PR: `data-engineering/notebook/Landing_to_Bronze.ipynb`, `data-engineering/notebook/Bronze_perfilamento.ipynb`, `data-engineering/evidencias/workflow/workflow-graph.png`, `data-engineering/README.md`, `data-engineering/configuracao/databricks/v-energy-grid-360.yaml` e este PRD; alteração registrada em commits locais na worktree baseada em `origin/feat/bronze`, sem publicação nesta etapa.
- Dados usados (versão/fonte; sem anexar dados sensíveis): nenhum dado real foi lido nesta correção; as verificações locais usaram estados sintéticos de falha.
- Verificações: em 19/10/2026, o JSON do notebook foi lido e as 15 células de código Python foram compiladas localmente; a execução isolada das células confirmou `RuntimeError` para autoteste `FALHA` e reconciliação com `delta = 2`/`INVESTIGAR`, `ValueError` para abas incompletas, e continuidade normal com reconciliação `OK` tanto sem rejeições quanto com rejeições capturadas. Não houve reexecução do Job Databricks.
- Reconciliação ou amostra manual: o cenário sintético com `leituras` divergente foi usado apenas para verificar a sinalização da falha; as contagens reais de 18/10/2026 permanecem como evidência da última execução do Job.
- Critérios de aceite revisados e pendências: a falha agora bloqueia a tarefa dependente, mas uma divergência descoberta ao fim da ingestão pode ocorrer após sobrescrita de tabelas Bronze; publicação atômica, reconciliação por arquivo/aba, hash/versão dos arquivos e rastreio até a linha original continuam pendentes. Validar os caminhos de sucesso e falha no Databricks antes de concluir DE-01.
- Responsável/revisor: Codex (alteração e verificações locais); revisão humana e execução no Databricks pendentes.

### 2026-10-19 — DE-01 — reconciliação por origem, rastro até a linha e publicação por lote

- Estado anterior → novo estado: `Em validação` → `Em validação`; a implementação está pronta e **executada no Databricks em 19/10/2026**, com o PR #8 em revisão. Os quatro pontos que a revisão de pares do PR #8 pediu — reconciliação por arquivo/aba, rastreio até a linha original, hash/versão do arquivo e publicação por lote — estavam listados como pendência na entrada anterior deste PRD e passam a estar no código.
- Mudança observável para usuário/negócio: `bronze.reconciliacao` deixa de ter uma linha por tabela e passa a ter uma linha por **origem** (5 arquivos simples/faturas, 5 arquivos anuais de leitura, `atendimentos.json` e as 3 abas de inspeção — 14 origens, mais a linha do autoteste), cada uma com lidas, rejeitadas, gravadas, delta e status, então dá para ver qual ano ou qual aba encolheu em vez de só o total da tabela. Cada registro ganha `_ordem_na_origem`, que auxilia a busca na origem (a posição física só é garantida no Excel); `bronze.arquivos_lote` guarda nome, tamanho, data de modificação e SHA-256 de cada arquivo do lote, provando qual versão entrou; e a Bronze publicada só começa a ser trocada depois de autoteste, quarentena e reconciliação fecharem. A troca é tabela a tabela: falha antes dela preserva o lote anterior, mas falha no meio pode deixar mistura; `bronze.controle_lote` registra `EM_ANDAMENTO`/`PUBLICADO` e os consumidores precisam bloquear leitura até o lote atual estar publicado.
- Arquivos/commit/PR: `data-engineering/notebook/Landing_to_Bronze.ipynb`, `data-engineering/notebook/Bronze_perfilamento.ipynb` (coluna nova na lista de auditoria do perfil), `data-engineering/README.md`, `data-engineering/decisoes-tecnicas.md` (D39–D42 e R34–R40 fecham a Bronze; as seções da Silver acompanham a doc e serão usadas no próximo PR), `docs/services/data-engineering.md`; branch `feat/bronze`, PR #8. O `Bronze_to_Silver.ipynb` fica para o PR da Silver.
- Dados usados (versão/fonte; sem anexar dados sensíveis): extração do case com as 8 fontes, no Volume `/Volumes/workspace/default/venergy`; dados brutos não versionados (`.gitignore`). A execução de 19/10/2026 leu os arquivos reais; nenhum dado foi anexado ao commit.
- Verificações: em 19/10/2026, a ingestão rodou na Databricks Free Edition: **15 linhas** em `bronze.reconciliacao` (14 origens + a linha do autoteste), `delta = 0` em todas as 14 origens, `AUTOTESTE_OK`, `bronze.controle_lote` com o lote em `PUBLICADO` e `bronze.arquivos_lote` com os arquivos do lote e SHA-256 calculado. O `Bronze_perfilamento` rodou em **Run All** e regravou `quality.perfil_bronze`. Verificações locais: `python -m py_compile` OK nos dois notebooks, nenhum CRLF, UTF-8 sem BOM e `check_docs.py` com 36 documentos e 0 links locais quebrados.
- Reconciliação ou amostra manual: a reconciliação por origem fechou com `delta = 0` nas 14 origens; `bronze.arquivos_lote` guarda a identidade dos 12 arquivos do lote e `bronze.controle_lote` registra o lote em `PUBLICADO`. A conferência da Silver (§13) fica para o PR da Silver.
- Critérios de aceite revisados e pendências: (a) execução da ingestão e conferência das 14 origens com `delta = 0`, `PUBLICADO` e SHA-256: **feito em 19/10/2026**; falta para `Concluído`: (b) decisão de negócio sobre data ambígua de dia/mês; (c) decisões B1 a B3 do dicionário de dados; (d) posição física garantida nos CSVs/JSON; (e) revisão do PR #8. A cascata de órfãos (D38) foi decidida em 19/10/2026 conforme `data-engineering/decisoes-tecnicas.md`; a implementação pertence ao PR da Silver. A execução da Silver e os blocos 13.1b a 13.1d ficam no PR da Silver.
- Responsável/revisor: juliatenoriocalado (implementação); revisão de pares do PR #8 endereçada nesta alteração e execução da Bronze no Databricks concluída.

### 2026-10-19 — DE-01/DE-02 — validação de largura CSV e perfil incompleto explícito

- Estado anterior → novo estado: DE-01 `Em validação` → `Em validação`; DE-02 permanece `Pendente`.
- Mudança observável: antes de ler cada CSV, a Bronze confere a quantidade de campos com o cabeçalho e bloqueia o lote com contagem e linhas de exemplo se houver divergência. O autoteste usa dois registros de largura incorreta para verificar esse bloqueio. O perfilador registra `NAO_EXECUTADA` em `quality.perfil_bronze` quando uma coluna esperada falta. O limite da ordem de leitura em CSV/JSON passa a ser declarado corretamente.
- Arquivos/branch: `data-engineering/notebook/Landing_to_Bronze.ipynb`, `data-engineering/notebook/Bronze_perfilamento.ipynb`, `data-engineering/decisoes-tecnicas.md`, `docs/decisions/0003-reconciliacao-e-captura-de-registros-malformados.md`, `data-engineering/README.md` e este PRD; `feat/bronze`, sem commit nesta etapa.
- Dados usados: nenhum arquivo real do case foi aberto localmente. A guarda é baseada no contrato de CSV e nos registros sintéticos do autoteste; a execução histórica de 19/10/2026 precede esta alteração.
- Verificações locais (script auxiliar não versionado): as células Python dos dois notebooks compilaram; com arquivos sintéticos, a guarda aceitou campos delimitados entre aspas e bloqueou duas linhas com larguras incorretas, informando linhas 3 e 4. O perfil registrou `NAO_EXECUTADA` uma única vez para uma coluna ausente consultada duas vezes. `git diff --check` não apontou erro. A execução completa no Databricks, a contagem real por origem e o tempo adicional da varredura CSV continuam pendentes. Para a publicação por lote, também falta comprovar uma falha induzida durante a troca seguida de reexecução e implementar no consumidor a leitura somente quando o lote atual estiver `PUBLICADO`.
- Reconciliação e pendências: a guarda evita que o Spark complete campos ausentes ou descarte excedentes silenciosamente. A reconciliação do JSON continua `SEM_BASE`, pois `objetos_interpretados` vem do próprio parser. A localização física CSV/JSON e a execução Databricks desta versão ainda precisam de evidência antes de concluir DE-01.
- Responsável/revisor: Codex (correção local); execução Databricks e revisão humana pendentes.

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


### 2026-10-19 — preparação de WEB-05 e WEB-11 — refatoração da base existente do backend

- Estado anterior → novo estado: `Pendente` → `Pendente`; a extração estrutural e os testes não concluem as jornadas integradas ou os controles de negócio.
- Mudança observável: os contratos HTTP existentes das ordens e da IA foram preservados, agora com schemas de entrada/saída explícitos. As rotas de ordens delegam consultas, gravações e rollback a um serviço que recebe a mesma sessão SQLAlchemy. A declaração de `Base` foi separada do engine, preservando `core.database.Base`, conexão PostgreSQL, pooling, `SessionLocal`, `get_db`, modelos e esquema existentes.
- Arquivos/branch: `feat/backend-base-operacional`; `backend/app/schemas/`, `backend/app/services/inspections.py`, `backend/app/db/`, imports dos modelos, `backend/alembic/env.py`, testes de inspeções/IA/banco/health/migrações, Docker/CI, [README do backend](../backend/README.md) e [guia do serviço](services/backend.md). O loader mantém seu esqueleto e agora descreve que não carrega dados nem implementa idempotência.
- Dados usados: apenas ordens artificiais e bancos SQLite descartáveis de teste; nenhum dataset, Gold, dado pessoal ou banco de desenvolvimento foi utilizado. O CI foi configurado com PostgreSQL 16 descartável e credenciais sintéticas para o teste dedicado de migração e persistência ORM.
- Verificações locais: em `backend/`, `./venv/Scripts/python.exe -m pytest -q` — 16 passaram, 1 ignorado por ausência de `TEST_POSTGRES_URL`, 1 aviso de depreciação httpx/Starlette; `./venv/Scripts/python.exe -m compileall -q app tests scripts alembic` — sucesso. `git diff --check` passou e os links locais dos quatro documentos alterados foram conferidos. A execução exige acesso ao interpretador instalado fora do sandbox. O teste PostgreSQL e o workflow remoto ainda não foram executados nesta etapa; o daemon Docker local estava indisponível.
- Reconciliação/amostra: testes HTTP exercitam criação, leitura, atualização, filtro de status, 404 e validação com persistência em SQLite. Falhas reais de INSERT/UPDATE por triggers verificam recuperação da mesma Session; a retirada temporária do rollback fez o teste falhar com `PendingRollbackError`, e sua restauração fez o teste passar. Alembic foi exercitado em upgrade/downgrade SQLite; o health foi testado com conexão disponível e indisponível, preservando o contrato atual.
- Critérios de aceite e pendências: autorização, transições, histórico, idempotência e paginação das ordens continuam pendentes de decisões e implementação; rotas analíticas/IA permanecem placeholders, sem consulta Gold ou reconciliação numérica. WEB-05 e WEB-11 seguem `Pendente`. A separação de código não comprova acesso somente leitura da IA, segurança para uso público ou validade de métricas.
- Responsável/revisor: dois implementadores GPT-6 Luna high e revisão independente GPT-6.1 Sol high; revisão integrada sem achados críticos/importantes remanescentes após reforço do teste de rollback na mesma Session. Sincronização Trello pendente porque o MCP não está conectado nesta sessão.

### 2026-10-20 — DEV-01 — contratos analíticos e consulta sintética integrada

- Estado anterior → novo estado: WEB-01 a WEB-07 e IA-01 a IA-06 permanecem `Pendente`. A preparação DEV-01 atende seu critério local de consulta frontend → API → fonte sintética, sem concluir requisitos funcionais do case.
- Mudança observável: a rota interna `/dev/contratos` permite consultar indicadores com período/filtros, conferir unidades e procedência de demonstração e distinguir zero, vazio, parcial e indisponibilidade. Rotas analíticas de receita, UC, fila e continuidade possuem schemas e validações HTTP; ordens operacionais e contratos de IA existentes são preservados.
- Arquivos/branch: `dev01`, baseada em `origin/develop` no commit `d59f7f2`; `backend/app/schemas/analytics.py`, `backend/app/repositories/analytics.py`, `backend/app/synthetic/fixtures.py`, serviços/rotas analíticos e testes separados por jornada; `frontend/src/features/dev-contracts/`, roteador e testes; [plano e linhagem dos oito commits](plans/2026-10-20-dev01-plan.md#linhagem-dos-commits), [desenho](design/2026-10-20-dev01-design.md), [contratos](contracts/analytics-api.md), [ADR-0004](decisions/0004-contratos-analiticos-e-fonte-sintetica.md) e guias afetados. Commit/push da branch autorizados após a revisão, sem merge para `develop` nesta etapa.
- Dados usados: somente o lote fictício determinístico `dev01-v1`, com cinco UCs; nenhum dataset real, credencial ou esquema físico Gold foi utilizado. `ANALYTICS_SOURCE=synthetic` é obrigatório para ativar a demonstração; o padrão retorna 503, sem fallback silencioso.
- Verificações em 20/10/2026: em `backend/`, `./venv/Scripts/python.exe -m pytest -q` — 44 passaram, 1 teste PostgreSQL ignorado por ausência de `TEST_POSTGRES_URL`, 1 aviso preexistente httpx/Starlette; `./venv/Scripts/python.exe -m compileall -q app tests scripts` — sucesso. Em `frontend/`, `npm.cmd run check:boundaries`, `npm.cmd run format:check`, `npm.cmd run lint`, `npm.cmd test` (29 testes) e `npm.cmd run build` — sucesso. Configurações, seis imports de instruções e links locais em 43 documentos Markdown conferidos pelo auxiliar local `work/dev01/verify_docs.py`; `git diff --check` aprovado, sem dados brutos ou assinaturas comuns de segredo nos arquivos alterados/novos. Ambiente local: Python 3.11.9, FastAPI 0.150.0 e Pydantic 2.14.1; Python 3.12/PostgreSQL do CI ainda sem execução nesta branch.
- Reconciliação/amostra manual: navegador real sem interceptação da API mostrou BRL 182 faturados, BRL 170 pagos por competência da fatura, 170 kWh faturados e subtotal conhecido de 407 kWh medidos, parcial. Olinda/janeiro mostrou zero disponível; Paulista, ausência; AL-03/fevereiro, leitura indisponível. Uma falha real de conexão foi recuperada pelo botão de nova tentativa. Conferidos temas claro/escuro e viewport móvel sem transbordamento horizontal; o preview de produção redirecionou `/dev/contratos` para `/panorama`. Procedimento reproduzível no catálogo; capturas locais não versionadas em `work/dev01/`.
- Critérios de aceite e pendências: revisados contratos, contexto analítico, estados, coerência das referências, isolamento da fonte e fórmulas provisórias. Revisão do controlador corrigiu comparação de meses ausentes, distinção de nulo/vazio, competência vazia, schemas OpenAPI de erro, coerência de pagamento parcial e proveniência da API restrita a demonstração, com regressões que falharam antes das correções. Um repositório de teste injetado confirmou que `is_demo: false` pode atravessar a API; não implementa nem conecta a Gold. O protótipo Figma atual foi consultado para Panorama nos dois temas e jornadas Receita, UC e Operação; a página de diagnóstico não substitui a implementação dessas telas. Parecer local aprovado para commit/push no escopo DEV-01. Adaptador Gold, homologação de métricas, UI final, integração IA e reconciliação ponta a ponta com dados reais continuam pendentes.
- Responsável/revisor: dois implementadores GPT-6 Luna/high (backend e frontend), revisão integrada pelo controlador. Sincronização Trello pendente: a nova tentativa de leitura do [quadro indicado](https://trello.com/b/eD8tWRha) pelo MCP retornou `not found or no access`; nenhum cartão foi alterado.

### 2026-10-20 — preparação de WEB-05 e WEB-11 — base Docker Hardened com zlib corrigida

- Estado anterior → novo estado: `Pendente` → `Pendente`; correção da dependência da imagem e validação de compatibilidade, sem conclusão dos requisitos funcionais.
- Mudança observável: backend mantém Python 3.12 e usa `dhi.io/python:3.12-alpine3.24-dev`, base mantida pela Docker que já contém zlib `1.3.2-r1`. Removida a atualização corretiva via `RUN apk add`. O CI constrói a imagem e executa `pip check` e a suíte nela com PostgreSQL 16 descartável; login DHI opcional por secrets. `requirements.txt`, contratos e regras de negócio preservados.
- Arquivos/branch: `dev01`; `backend/Dockerfile`, `.github/workflows/quality.yml`, `backend/README.md`, [ADR-0005](decisions/0005-backend-python312-alpine.md), índice de decisões, guia do backend e este PRD. Comandos reproduzíveis no [README](../backend/README.md#imagem-docker).
- Dados usados: fixtures sintéticas existentes, ordem artificial para teste HTTP e banco PostgreSQL descartável `*_test`; nenhum dataset, Gold ou banco de desenvolvimento.
- Verificações em 20/10/2026: build com `--pull --no-cache` passou; `pip check` e imports de FastAPI, SQLAlchemy, Psycopg binário e componentes nativos do Uvicorn passaram. Python 3.12.15 e zlib `1.3.2-r1` confirmados tanto na base quanto na imagem construída. A suíte com `docker run --rm --network <rede-descartavel> -e TEST_POSTGRES_URL=<URL-descartavel> git-or-treat-backend:dhi-check python -m pytest -q` passou com 45 testes, sem skips, e um aviso preexistente httpx/Starlette.
- Reconciliação/amostra: o teste HTTP real exercita saúde com `database=connected`, OpenAPI, KPI sintético BRL 182 e criação/atualização/listagem de ordem artificial usando PostgreSQL descartável. A amostra valida compatibilidade e persistência; não reconcilia Gold.
- Segurança: `docker scout cves registry://dhi.io/python:3.12-alpine3.24-dev --platform linux/amd64 --format packages` apresentou 0 críticas, 0 altas, 0 médias e 0 baixas na base `de73484b502d`. A análise da imagem final `da80696bd174` com `docker scout cves local://git-or-treat-backend:dhi-check --platform linux/amd64 --format packages` apontou 0 críticas, 0 altas, 1 média e 0 baixas; CVE-2026-85091 ausente. O alerta médio restante é CVE-2026-13346 em pip 26.1.2; não foi suprimido. As análises de registry consideram atestações/VEX disponíveis.
- Acesso ao registry: pull local com configuração Docker vazia funcionou. A documentação DHI orienta login; `DHI_USERNAME` e `DHI_TOKEN` podem ser configurados no GitHub caso a autenticação seja exigida. Nenhuma credencial foi criada, solicitada ou versionada nesta entrega.
- Critérios de aceite e pendências: base oficial já corrigida encontrada e adotada, conforme preferência da pessoa usuária. Execução remota do workflow, plataformas além de `linux/amd64` e o alerta médio do pip permanecem pendentes. WEB-05/WEB-11 e integração Gold mantêm suas pendências funcionais. Nenhuma migração foi alterada. Commit e push em `dev01` autorizados pela pessoa usuária após as verificações locais.
- Responsável/revisor: implementação e verificações locais por Codex; revisão independente GPT-6 Astra/high sem achados críticos ou importantes. A descrição antiga do CI no guia de ferramentas, apontada na revisão, foi sincronizada. HTTP real na imagem final, `compileall`, sintaxe YAML/shell do workflow, links em 44 documentos e `git diff --check` passaram. O revisor conferiu o diff e as fontes; a execução Docker foi verificada pelo implementador. Sincronização Trello pendente: leitura anterior do quadro retornou `not found or no access`; nenhum cartão foi alterado.

### 2026-10-20 — preparação de WEB-01, WEB-03, WEB-05 a WEB-07 e WEB-11 — ajustes da revisão DEV-01

- Estado anterior → novo estado: requisitos funcionais permanecem `Pendente`; correções de robustez e aderência aos contratos existentes, sem integração Gold ou conclusão das jornadas.
- Mudança observável: ciclo Alembic recusa banco com resíduos antes de alterar objetos, limpa as próprias migrações após falha e compara esquema/modelos com tipos/defaults. PostgreSQL é validado com usuário de migração sem superusuário. Nova revisão `7c4a2b1e9d60` adiciona defaults de inserção aos timestamps de ordens; upgrade/downgrade preservam registros. Enum continua armazenado pelos nomes em inglês, mantendo os valores da API em português; nenhuma trigger de UPDATE foi introduzida.
- Correções analíticas: continuidade valida alimentador vazio com 422 e usa cobertura temporal explícita de janeiro–fevereiro de 2025. Janela externa produz DEC/FEC nulos e estado indisponível; janela parcial usa somente a interseção e informa limitações; zero conhecido é preservado. Cobertura espacial permanece separada. Busca/projeção/paginação de UC foram movidas ao serviço, preservando o contrato HTTP.
- Correções frontend: recorte aplicado fica na URL validada/normalizada; formulário mantém rascunho local. Link/reload e histórico restauram consulta/campos, URL inválida bloqueia HTTP e pode ser corrigida, atualização com cache é anunciada e aplicação por Enter preserva foco. A rota continua exclusiva de desenvolvimento.
- Arquivos/branch: `dev01`; testes de migração/analítica, nova revisão Alembic, modelos de timestamps, serviços/repositório/fonte sintética, endpoints de continuidade/UC, feature `dev-contracts`, testes React, workflow e script de preparação PostgreSQL. [README backend](../backend/README.md), [contratos](contracts/analytics-api.md), [guia backend](services/backend.md) e [arquitetura frontend](architecture/frontend.md) sincronizados. Os arquivos locais `.env` não foram alterados.
- Dados usados: fixtures `dev01-v1`, registros artificiais para migração e PostgreSQL 16 temporário sem volumes de desenvolvimento. Nenhum dataset/Gold ou dado pessoal real. Cobertura temporal adicionada como metadado interno da fonte; fórmulas e valores de controle sintéticos preservados.
- Verificações: backend `python -m pytest -q` passou com **69 testes**, sem skips, com PostgreSQL descartável e papel sem superusuário; a mesma suíte passou na imagem Python 3.12 construída com `docker build -f backend/Dockerfile -t git-or-treat-backend:review-check .`. `python -m compileall -q app tests scripts alembic` passou. Frontend: **45 testes**, fronteiras modulares, lint, tipos/build e formatação aprovados. Regressões falharam antes das respectivas correções; testes de caracterização da busca UC permaneceram verdes antes/depois da extração.
- Reconciliação/amostra manual: navegador com API real sintética confirmou BRL 182, BRL 170, 170 kWh e 407 kWh parcial; Olinda/janeiro manteve zero disponível; Paulista manteve ausência. Reload/voltar/avançar restauraram os recortes; mês inválido não disparou HTTP, e a correção recuperou a consulta. Refetch com resposta temporariamente retida manteve o dado cacheado e anunciou atualização. Enter no botão e no campo preservou foco após a correção. Desktop claro 1440 × 1024 e mobile escuro 390 × 844 sem transbordamento horizontal; capturas locais em `work/dev01-adjustments/`, ignorado pelo Git.
- Controle HTTP de continuidade: alimentador vazio retornou 422; AL-01/janeiro de 2030 retornou indisponível com DEC/FEC nulos; AL-01/dezembro de 2024 a janeiro de 2025 retornou parcial com DEC 1 h/UC e FEC 0,5; AL-02/janeiro de 2025 manteve DEC/FEC zero disponíveis. São controles sintéticos, não indicadores homologados.
- Critérios e pendências: integração/reconciliação Gold, fórmulas oficiais, autorização e ciclo completo de ordens continuam pendentes. O teste de drift não cobre automaticamente toda mudança de CHECK/enum. Atualização por SQL direto continua responsável por `updated_at`. Workflow remoto ainda não executado nesta entrega; o aviso preexistente Starlette/httpx permanece, sem alteração de dependências.
- Responsável/revisor: implementação coordenada por Codex, com frentes independentes de backend analítico e frontend. Revisão independente não encontrou problemas críticos/importantes; apontou perda de foco na submissão, corrigida com duas regressões e conferência no navegador. Sincronização Trello pendente: o MCP retornou recurso não encontrado ou sem acesso ao quadro indicado; nenhum cartão foi alterado.

### 2026-10-20 — DEV-01 — sincronização com develop e resolução do conflito do PR #27

- Arquivos/branch: integração de `origin/develop` em `df0b34c` na `dev01`; conflitos resolvidos no índice de decisões e no guia do backend. As ADRs de contratos analíticos e imagem Docker foram renumeradas para 0004 e 0005, com links atualizados, preservando os IDs 0002 e 0003 já presentes em `develop`.
- Critérios: contratos sintéticos implementados e propostas de integração GenAI/Gold permanecem distintos; as propostas continuam pendentes de revisão. A sincronização não conclui os requisitos WEB/IA nem comprova reconciliação com Gold.
- Verificações locais na árvore combinada: backend `python -m pytest -q` com PostgreSQL 16 descartável e papel sem superusuário: **69 testes aprovados**, sem skips, no host e na imagem Docker Python 3.12 reconstruída; `pip check` e compilação aprovados. Frontend: **45 testes aprovados**, lint, fronteiras em 36 arquivos, formatação, tipos e build aprovados. GenAI: **373 testes aprovados**, lint/compilação e regressão sintética **13/13** aprovados. Gate de documentação/configuração: 46 documentos, seis imports e 29 links/âncoras das skills válidos. Sem dados reais ou chamadas de modelo real.
- Publicação: commit/push na `dev01` autorizados para atualizar o [PR #27](https://github.com/GuilhermeRangel1/git-or-treat/pull/27); o resultado remoto deve ser conferido na execução do workflow vinculada ao PR. Evidências de Trello serão entregues à pessoa usuária, pois o quadro não estava acessível pelo MCP nesta sessão.

### 2026-10-21 — DEV-03 — início da exploração demonstrativa da receita

- Estado: WEB-02, WEB-07 e ENT-01 permanecem `Pendente`; esta entrada registra preparação e implementação iniciada, sem comprovar aceite funcional ou diagnóstico Gold.
- Autorização e organização: desenho/plano aprovados pela pessoa usuária para execução por dois subagentes GPT-6 Luna/high, com revisão de padrões e requisitos nesta sessão. Branch `dev03`, base `ebccc238bcec502bfa7a1b36ff32e01b0c6c4567`.
- Definições: [ADR-0006](decisions/0006-exploracao-demonstrativa-receita.md), [contrato Receita 1.1.0](contracts/revenue-dev03.md), [desenho](design/2026-10-21-dev03-design.md) e [plano](plans/2026-10-21-dev03-plan.md). Comparação mensal dos extremos demonstrativos, cinco UCs para percentual, cobertura explícita, preço observado distinto de homologação e reconciliação por receita/variação. As janelas anuais e métricas reais continuam dependentes da Gold.
- Baseline informado pelos implementadores: backend Python 3.11.9, `python -m pytest -q` com 68 aprovados/1 PostgreSQL ignorado e compilação aprovada; alvo Python 3.12 e gate PostgreSQL seguem sem execução local. Frontend: 45 testes, lint, fronteiras e build aprovados; `format:check` já falha em nove arquivos existentes antes da implementação, registrado em relatório local. Estes resultados não são validação da DEV-03.
- Fontes: somente código/contratos e referências Figma de Receita clara `15:331` e escura `16:1296`, consultadas pelo implementador frontend em modo de leitura. Nenhum dataset real ou esquema físico Gold presumido.
- Pendências: implementar/revisar as fatias, executar API/tela reais e registrar resultados independentes antes do aceite. Trello: consulta MCP em 21/10/2026 ao quadro indicado retornou recurso não encontrado ou sem acesso; nenhum cartão foi alterado.

### 2026-10-21 — DEV-03 — exploração sintética da receita implementada e revisada

- Estado anterior → novo estado: WEB-02, WEB-07 e ENT-01 permanecem `Pendente`. A exploração demonstrativa DEV-03 atende seu critério local de recortes/retorno consistente; ainda não demonstra as janelas anuais, integração Gold ou diagnóstico final do case.
- Mudança observável: `/receita` consulta a API, apresenta série, valores inicial/final, deltas absoluto/percentual, decomposição preço-volume e agrupamentos município/bairro/classe. Filtros base e refinamentos ficam na URL; Total preserva o contexto aplicado. A tabela mostra receita inicial/final e variação por grupo, soma conhecida dos recortes e estado do fechamento; grupos não comparáveis e diferença não atribuída são identificados. Base pequena, cobertura incompleta, denominador zero, vazio e erro possuem tratamento próprio. Preço observado é identificado em BRL/kWh e distinguido de reajuste homologado indisponível. Totalizadores legados permanecem no contrato HTTP, sem apresentação na tela. A pedido da pessoa usuária, foi removido o painel dedicado de método, cobertura e limitações; avisos necessários permanecem junto aos indicadores, e a API mantém os dados estruturados de qualidade/cobertura/reconciliação sem duplicá-los em `metadata.limitations`. A série mensal ganhou escala em BRL, marcadores de competência, preenchimento visual, animação curta e tooltip por hover/foco com mês e faturamento; movimento reduzido desativa as animações.
- Arquivos/branch: `dev03`, base `ebccc238bcec502bfa7a1b36ff32e01b0c6c4567`. Serviço `backend/app/services/revenue_analytics.py`, rota/schema/repositório/fixtures analíticos e testes HTTP; `frontend/src/features/receita/` e regressões do roteador; [contrato](contracts/revenue-dev03.md), [ADR-0006](decisions/0006-exploracao-demonstrativa-receita.md), [plano](plans/2026-10-21-dev03-plan.md), guias e [relatório reproduzível de evidências/revisão](plans/2026-10-21-dev03-evidence.md). O commit da branch fixa os arquivos revisados.
- Dados usados: lote fictício determinístico `dev03-v1`, dez UCs e 16 faturas, atualização `2026-10-21T00:00:00Z`. Fonte sintética ativada explicitamente; nenhum dataset, credencial, dado pessoal ou esquema físico Gold presumido. Demais envelopes analíticos preservam 1.0.0; somente Receita evoluiu para 1.1.0.
- Verificações: backend `venv/Scripts/python.exe -m pytest -q`: **100 aprovados, 1 PostgreSQL ignorado**; `compileall` aprovado na revisão. Frontend: **65 testes aprovados**, incluindo 20 de Receita; fronteiras em 45 arquivos, formatação, lint, tipos/build aprovados. Fechamento dos recortes na interface verificado em cenário completo e parcial. Validação de documentação/configurações e `git diff --check` registradas no relatório. Host Python 3.11.9; Python 3.12/PostgreSQL/CI remoto continuam sem execução nesta entrega.
- Reconciliação/amostra: auditoria independente de 21 consultas HTTP em sete universos e três agrupamentos, mais vazio, conferiu faturas versus extremos/grupos/deltas. Total janeiro–fevereiro: BRL 800 → 927, Δ +127 (+15,88%); efeitos +136,99 −8,53 −1,46 e ajuste zero. Residencial 620 → 725; Recife/Residencial 620 → 645. Paulista mostra zero financeiro conhecido; Olinda/Comercial vazio; março ausente mantém lacuna. Regressões de subcentavos garantem deltas entre snapshots publicados, ajuste explícito e exposição de divergência de soma das linhas.
- Jornada e visual: navegador real percorreu município/bairro/classe e retorno, inclusive filtros base de município/bairro, histórico e reload. Falha real de conexão e nova tentativa preservaram contexto sem fallback. Build de produção com API explícita exibiu Receita; `/dev/contratos` permaneceu excluído. Frames Figma de Receita clara/escura consultados e comparados com desktop 1440 × 1024; mobile 390 × 844 e largura 768 sem transbordamento global. Escape, Fechar e Aplicar restauram foco; capturas locais ignoradas em `work/dev03/`. Ampliação nativa do navegador não auditada.
- Critérios e revisão: esta sessão revisou padrões das skills locais e requisitos, corrigindo desconhecido convertido em zero, cobertura nula, arredondamento oculto entre grupos, delta publicado, fidelidade visual, overflow mobile, retorno de foco e conteúdo fora do escopo (totalizadores agregados removidos da UI; mantidos no contrato DEV-01). Exploração sintética aprovada sem achados importantes abertos nesse escopo. Adaptador/reconciliação Gold → banco → API → portal, métricas/janelas homologadas, demais telas WEB-07 e diagnóstico ENT-01 permanecem pendentes.
- Responsável/revisor: dois implementadores GPT-6 Luna/high, revisão integrada pelo controlador conforme autorização. Trello pendente: MCP retornou recurso não encontrado ou sem acesso ao quadro indicado; nenhum cartão foi alterado. Sem PR, merge ou publicação de produto nesta etapa.

### 2026-10-21 — DEV-03 — B4: classificação analítica no serviço

- Estado: WEB-02, WEB-07 e ENT-01 permanecem `Pendente`; refatoração da demonstração sintética, sem mudança do contrato 1.1.0.
- Mudança: a rota de Receita delega a classificação de disponibilidade a `revenue_metadata_status` em `backend/app/services/revenue_analytics.py`. Foram preservados o vazio, o período único e o envelope parcial para universo conhecido com coberturas indisponíveis.
- Evidência: `backend/tests/test_revenue_dev03.py` acrescenta um controle HTTP para as quatro coberturas indisponíveis. `venv/Scripts/python.exe -m pytest -q tests/test_revenue_dev03.py`: 33 aprovados; suíte backend completa: 101 aprovados, 1 PostgreSQL ignorado. `git diff --check` aprovado. Detalhes no [registro da DEV-03](plans/2026-10-21-dev03-evidence.md).
- Dados/revisão: somente fonte sintética `dev03-v1` e fixtures artificiais de contrato; implementação por GPT-6 Luna/high e revisão do controlador. Gold, Python 3.12 e PostgreSQL seguem pendentes. Trello: a tentativa de leitura do quadro pelo MCP expirou; sincronização pendente.

### 2026-10-21 — DEV-03 — B1: destinos de retorno centralizados

- Estado: WEB-02, WEB-07 e ENT-01 permanecem `Pendente`; contratos e aparência preservados.
- Mudança: `revenueRefinementDestination` em `frontend/src/features/receita/revenue-filters.ts` fornece o mesmo destino para `href` e clique dos links Total/Município em `ReceitaPage.tsx`. Total remove somente refinamentos; Município remove o bairro e mantém classe independente, filtros base, competências e agrupamento.
- Evidência: regressões em `ReceitaPage.test.tsx` conferem destinos literais, filtros base geográfico/classe, histórico e consistência entre endereço e clique. Em `frontend/`: `npm.cmd test` → 67 aprovados; `check:boundaries` → 45 arquivos; `format:check`, `lint` e `build` aprovados. Documentação e `git diff --check` aprovados; ver [registro da DEV-03](plans/2026-10-21-dev03-evidence.md).
- Dados/revisão: somente respostas artificiais de contrato; implementação GPT-6 Luna/high e revisão do controlador. A jornada de navegador não foi repetida por ausência de navegador conectado; testes de interação e evidência anterior não equivalem a nova execução com Gold. Sincronização Trello pendente após timeout do MCP.

### 2026-10-21 — DEV-03 — B5: cálculo compartilhado dos recortes

- Estado: WEB-02, WEB-07 e ENT-01 permanecem `Pendente`; sem mudanças de métrica, fonte ou JSON 1.1.0.
- Mudança: `backend/app/services/revenue_analytics.py` compartilha contexto filtrado e cálculo de cobertura/comparação. Faturas e leituras são particionadas por grupo uma vez; os grupos deixam de montar série/acumulados/opções completos, e a reconciliação reutiliza a comparação agregada. Foram removidos a recursão de `build_revenue` e seu controle privado sem outros consumidores.
- Evidência: suíte backend completa → 101 aprovados, 1 PostgreSQL ignorado; `compileall` de `app`, `tests` e `scripts` aprovado. Comparação independente contra `bbb59d2`: 10.080 combinações de resultados/erros idênticas, com fonte sintética normal, sem cobertura, faturamento incompleto e universo vazio, seis janelas e três agrupamentos. Documentação e `git diff --check` aprovados; detalhes no [registro da DEV-03](plans/2026-10-21-dev03-evidence.md).
- Dados/revisão: somente fixtures artificiais; implementação GPT-6 Luna/high, revisão de código e comparação diferencial pelo controlador. Controles HTTP de Decimal, arredondamento, base pequena, ausência, mix e reconciliação preservados. Acesso Gold por consultas no PostgreSQL continua evolução futura, condicionado ao dicionário aprovado. Limites de navegador, Python 3.12/PostgreSQL e sincronização Trello permanecem os registrados nesta rodada.

### 2026-10-21 — DEV-03 — finais de linha reproduzíveis no Windows

- Estado: requisitos funcionais permanecem `Pendente`; ajuste de ferramentas, sem mudança de comportamento do produto.
- Causa e correção: com `core.autocrlf=true` e sem atributos, o checkout podia produzir CRLF enquanto o Prettier esperava LF. `.gitattributes` fixa LF apenas no frontend, com detecção automática de binários; `frontend/.prettierrc.json` explicita a mesma política. O README orienta atualizar checkouts existentes sem descartar trabalho local nem mudar a configuração global do Git.
- Evidência: Prettier 3.9.10 aceitou o conteúdo LF e rejeitou o mesmo conteúdo CRLF antes da correção de checkout. `git cat-file --filters` com `core.autocrlf=true` passou a produzir LF; `git check-attr` confirmou os atributos. `npm.cmd run format:check`, validação documental e `git diff --check` aprovados. Doze arquivos locais foram normalizados, sem diferenças lógicas no índice; não houve reformatação em massa de código. Revisão pelo controlador; ver [evidências](plans/2026-10-21-dev03-evidence.md).

### 2026-10-21 — DEV-03 — comparação financeira independente da energia

- Estado: WEB-02, WEB-07 e ENT-01 permanecem `Pendente`; correção sintética, sem definições Gold ou mudança na estrutura JSON 1.1.0.
- Mudança: `backend/app/services/revenue_analytics.py` preserva delta em BRL, percentual elegível e reconciliação financeira quando o valor faturado está completo, mesmo com energia incompleta. Delta em kWh depende da energia; preço observado e decomposição exigem as duas bases comparáveis pertinentes. O snapshot financeiro conhecido com energia ausente é parcial; a precedência do envelope é preservada.
- Evidência: `backend/tests/test_revenue_dev03.py` cobre energia sem cobertura, energia nula, lacuna energética intermediária e energia completa com receita incompleta. Controle: BRL 500 → 550 mantém delta +50 e +10%, com fechamento em BRL e preço-volume indisponível. Receita HTTP: 37 testes aprovados; backend completo: 105 aprovados, 1 PostgreSQL ignorado; `compileall app tests`, documentação e `git diff --check` aprovados.
- Decisão/revisão: [ADR-0006](decisions/0006-exploracao-demonstrativa-receita.md), [contrato](contracts/revenue-dev03.md), [desenho](design/2026-10-21-dev03-design.md) e [evidências](plans/2026-10-21-dev03-evidence.md) sincronizados. Implementação GPT-6 Luna/high, revisão do controlador. Navegador/Gold/Python 3.12/PostgreSQL e sincronização Trello permanecem pendentes nos termos registrados.

### 2026-10-21 — DEV-03 — alimentador por URL e rejeição de escalares repetidos

- Estado: WEB-02, WEB-07 e ENT-01 permanecem `Pendente`; fonte sintética e estrutura dos contratos preservadas.
- Correção: o frontend descartava `alimentador`, embora a API já suportasse esse filtro. Agora ele atravessa parser, consulta HTTP, chave de cache e aplicação do formulário, com identificação no contexto efetivo e sem novo seletor. A validação rejeita duplicatas de qualquer chave bruta, além de alimentador vazio/longo; reaplicar filtros remove duplicatas e recupera links inválidos.
- Evidência: testes públicos de `ReceitaPage.test.tsx` conferem AL-01 → AL-02, preservação ao aplicar Município, contexto da API, bloqueio sem fetch e recuperação de links repetidos. Frontend: 75 aprovados; Receita: 30 aprovados; fronteiras em 45 arquivos, formatação, lint e build aprovados. Após o ajuste final da fonte do contexto, Receita/build/formatação/lint repetidos e aprovados. Documentação e `git diff --check` aprovados; ver [evidências](plans/2026-10-21-dev03-evidence.md).
- Arquivos/revisão: página, formulário, filtros e testes em `frontend/src/features/receita/`; [desenho](design/2026-10-21-dev03-design.md) e [contrato](contracts/revenue-dev03.md) sincronizados. Implementação GPT-6 Luna/high, revisão do controlador. Nenhum ajuste global de responsividade; a integração do layout da DEV-02 permanece separada.

### 2026-10-21 — DEV-03 — retorno explícito pelos níveis de recorte

- Estado: WEB-02, WEB-07 e ENT-01 permanecem `Pendente`; navegação sintética revisada sem mudança no esquema da API.
- Mudança: Total remove todos os refinamentos; Município remove bairro e classe refinados; Bairro remove a classe refinada. Filtros base de município/bairro/classe/alimentador, competências e agrupamento permanecem. O segmento Bairro torna-se link quando há classe refinada abaixo dele; a transformação centralizada fornece o mesmo destino para endereço e clique. Esta política substitui a retenção intermediária de classe refinada do B1 anterior.
- Evidência: testes públicos da página verificam os três destinos, endereços literais, histórico, classe/alimentador base e indicação do bairro atual. Frontend: 77 aprovados; fronteiras em 45 arquivos; formatação, lint e build aprovados. Checagem adicional com parser/decoder reais e API sintética em memória: quatro consultas HTTP 200 preservaram filtros efetivos, três URLs repetidas foram bloqueadas antes do transporte e chamada direta repetida retornou 422. Documentação e `git diff --check` aprovados.
- Decisão/revisão: [contrato](contracts/revenue-dev03.md#estado-no-navegador), [desenho](design/2026-10-21-dev03-design.md), [ADR-0006](decisions/0006-exploracao-demonstrativa-receita.md) e [evidências](plans/2026-10-21-dev03-evidence.md) sincronizados. Implementação GPT-6 Luna/high, revisão do controlador. Ampliação responsiva da DEV-02 não alterada; fonte sintética continua explícita. O relato local de 404 não motivou troca de rota: a API desta branch foi exercitada com sucesso; fonte não configurada tem resposta 503 no contrato.

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

### 2026-10-21 — WEB-01 e WEB-07 — correções da integração Panorama

- Estado: WEB-01 corrigido de `Concluído` demonstrativo para `Em validação`; WEB-07 permanece `Pendente` no conjunto das jornadas. Fixtures não satisfazem a reconciliação Gold exigida pelo aceite.
- Mudança observável: o frontend usa exclusivamente `/api/v1/panorama`, valida JSON e filtros efetivos, encaminha cancelamento e mostra falha com nova tentativa. Removido fallback silencioso. Corrigidos campos nulos de comparação, conversão kWh/GWh, filtros ofertados sem cobertura e texto que inferia perdas/inadimplência das diferenças entre grandezas. Série respeita o mês escolhido e inclui competência parcial; ausência de comparação não vira base zero.
- Arquivos: `backend/app/services/panorama.py`, `backend/app/api/v1/endpoints/panorama.py`, `backend/tests/test_panorama.py`, `frontend/src/shared/analytics/`, `frontend/src/shared/ui/MetricCard.tsx`, `frontend/src/shared/filters/FilterBar.tsx`, `frontend/src/features/panorama/`; contratos, ADR-0006 e guias sincronizados. Alterações existentes preservadas, sem commit nesta sessão.
- Dados: exclusivamente fixtures sintéticas já existentes, separadas da Gold; controles abril/março de 2024. Dicionário Gold continua sem campos reais homologados.
- Verificações: `backend/venv/Scripts/python.exe -m pytest -q` em `backend/`: 79 aprovados, 1 ignorado (PostgreSQL), com aviso de depreciação Starlette/httpx. Em `frontend/`, `npm test`: 58 aprovados em 6 arquivos; lint, fronteiras e build aprovados. Testes executados fora do sandbox após bloqueio de temporários/execução. `git diff --check` sem erros. `npm run format:check` global falha em 50 arquivos fora do conjunto formatado nesta correção; mantidos para evitar reformatação ampla. Arquivos frontend editados nesta sessão formatados com Prettier.
- Evidência e limites: HTTP TestClient cobre fonte desabilitada 503, entrada inválida 422, filtros, controles, ausência de comparação e série temporal. Testes React cobrem erro/retentativa, JSON inválido e null da API. Navegador integrado não alcançou o servidor local (timeout em localhost e 127.0.0.1), impedindo revisão visual integrada. Figma MCP não disponível e acesso web ao arquivo falhou; usados registros locais dos frames `15:164`/`16:1129`, sem afirmar nova comparação visual. Não houve reconciliação Gold.
- Pendências: homologar métricas e carregar Gold; validar manualmente os dois temas e responsividade contra o Figma; resolver formatação global. Trello não sincronizado porque seu MCP não está conectado. Responsável: Codex; revisão humana pendente.
- Smoke HTTP adicional: com `ANALYTICS_SOURCE=synthetic` e Uvicorn local, `GET /api/v1/panorama?competencia=2024-04&municipio=Recife` retornou R$ 38.000 faturados e 620 UCs, confirmados por `Invoke-RestMethod`. Este teste não substitui a revisão visual ou a reconciliação Gold.


### 2026-10-22 — DEV-02 / WEB-01 e WEB-07 — ajustes da revisão do Panorama

- Estado anterior → novo: WEB-01 permanece `Em validação`; WEB-07 permanece `Pendente` para o conjunto das jornadas. Esta revisão atende à fatia demonstrativa DEV-02, dependente da fundação DEV-01, sem comprovar integração Gold nem adicionar insight de IA.
- Mudança observável: filtros inválidos da URL ficam explícitos por campo e bloqueiam a consulta até correção/restauração; recarga e voltar/avançar preservam o contexto. Maio parcial mantém totais e série, com comparação indisponível; percentual nulo não aparece como 0%. Conversão de energia corrigida para 1 GWh = 1.000.000 kWh.
- Apresentação: filtros em duas colunas no mobile, quatro KPIs principais antes da série e quatro complementares depois; fonte sintética e atualização no topo. Série com escala vertical, valores nas barras, detalhes fora do contêiner de rolagem acessíveis por teclado e tabela alternativa. Competência parcial identificada também na série/tabela.
- Arquivos: `backend/app/services/panorama.py`, `backend/tests/test_panorama.py`, `frontend/src/features/panorama/`, `frontend/src/shared/filters/`, `frontend/src/shared/ui/MetricCard.tsx`, `ContentState.tsx`, `Select.tsx` e hooks/fixture analíticos. ADR-0006 corrigida: oito métricas e calendário 2024 são escolhas demonstrativas da implementação, não imposições do PRD/Figma. Guias frontend/backend sincronizados.
- Dados e reconciliação: API real local com `ANALYTICS_SOURCE=synthetic`, lote `Lote Gold 2024.04-sintetico-v1`. Abril total R$ 76.500 contra R$ 80.000 = −4,38%; Recife R$ 38.000; maio total R$ 31.000 e Recife R$ 22.000, ambos parciais com referências e variações nulas. Nenhuma dessas evidências representa reconciliação com Gold.
- Verificações: backend `venv/Scripts/python.exe -m pytest -q` → 133 aprovados, 2 ignorados (PostgreSQL indisponível com Docker desligado), aviso preexistente Starlette/httpx. Frontend `npm test -- --reporter=dot` → 75 aprovados em 9 arquivos; lint, limites de importação (54 arquivos), build/tipos e formatação dos arquivos alterados aprovados. `npm run format:check` global sinaliza 49 arquivos não alterados nesta revisão; formatação global permanece pendente para evitar misturar mudanças fora da DEV-02.
- Jornada manual: navegador com frontend Vite e API FastAPI locais, SQLite em memória sem dados operacionais; Recife modifica números, sobrevive à recarga e ao voltar/avançar; maio mostra aviso e mantém totais parciais sem percentuais; URL com `comparacao=bad` mostra erro e restauração. Tabela e detalhes do gráfico por teclado conferidos. Reflow em 320, 390, 768 e 1920 px sem rolagem horizontal da página; rolagem local da série preservada; temas claro/escuro inspecionados. Em 390 px, os campos de período/comparação e município/classe estão alinhados em duas linhas.
- Referência técnica: TanStack Query 5 (`@tanstack/react-query` declarado ^5.104.4); documentação oficial consultada via Context7 em 22/10/2026, guia [Disabling/Pausing Queries](https://tanstack.com/query/latest/docs/framework/react/guides/disabling-queries), para bloqueio declarativo de consulta inválida. Nenhuma dependência nova ou alteração de arquitetura.
- Pendências/revisão: revisão humana do PR, reconciliação Gold e formatação global; testes PostgreSQL não executados nesta rodada por indisponibilidade do Docker. Trello não sincronizado porque o MCP não está conectado. Revisor humano: a definir pelo time.


### 2026-10-22 — DEV-02 / WEB-01 e WEB-07 — faixa de resumo dos filtros

- Estado: WEB-01 permanece `Em validação`; WEB-07 permanece `Pendente` no conjunto das jornadas. Ajuste restrito ao frontend, usando as capturas do protótipo fornecidas pela pessoa usuária como referência visual; sem alterar backend, dados, períodos ou adicionar insights de IA.
- Mudança: faixa com competência, competência de comparação, território e classe; botão “Ajustar filtros” expande os campos existentes. Edição continua aplicada automaticamente na URL e na consulta. “Fechar ajustes” ou Escape recolhem os controles; Escape devolve foco ao botão. Filtros inválidos na abertura mantêm os campos expostos para correção. Os períodos mostrados são os reais da fixture 2024, não os exemplos anuais do desenho.
- Arquivos: `frontend/src/shared/filters/FilterBar.tsx`, `FilterBar.test.tsx` e adaptação da interação em `frontend/src/features/panorama/PanoramaPage.test.tsx`.
- Verificações: `npm test -- --reporter=dot` → 77 testes aprovados em 10 arquivos; `npm run lint`, `npm run check:boundaries` (55 arquivos), `npm run build` e Prettier nos três arquivos alterados aprovados. Backend não alterado; não houve necessidade de repetir sua suíte.
- Jornada manual: frontend Docker com API sintética real; resumo desktop em 1440 px, ajuste para Recife com R$ 38.000, fechamento por Escape; mobile 390 e 320 px, painel aberto/fechado sem rolagem horizontal da página. Temas claro e escuro inspecionados. Em 390 px a faixa fechada mede 196 px de altura, com resumo em duas colunas e botão abaixo.
- Pendências: revisão humana e reconciliação Gold permanecem; nenhuma imagem do enunciado adicionada ao repositório. Trello não sincronizado: MCP não conectado. Revisor humano: a definir pelo time.

- Ajuste solicitado na mesma revisão: removida do topo a linha de demonstração sintética/lote e última atualização. Metadados continuam no contrato e lote nos detalhes das métricas; a omissão visual foi solicitada pela pessoa usuária e não altera a origem dos dados ou conclui o aceite Gold.
