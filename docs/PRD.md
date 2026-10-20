# PRD — V-Energy Grid 360

**Versão:** 1.3 documental · **Data:** 16/10/2026 · **Estado da implementação:** parcial — fundação e primeira fatia visual concluídas; requisitos funcionais pendentes

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
- Arquivos/commit/PR: `data-engineering/notebook/Landing_to_Bronze.ipynb` (reescrito, então `01_bronze.py`), `data-engineering/notebook/Bronze_perfilamento.ipynb` (colunas de auditoria no perfilamento e deduplicação restrita às colunas de negócio, então `02_perfilamento.py`), [ADR-0001](decisions/0001-reconciliacao-e-captura-de-registros-malformados.md), `docs/services/data-engineering.md` e este PRD; branch `feat/bronze`, PR #8 (ainda sem revisão).
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
- Arquivos/branch: `data-engineering/notebook/Landing_to_Bronze.ipynb`, `data-engineering/notebook/Bronze_perfilamento.ipynb`, `data-engineering/decisoes-tecnicas.md`, `docs/decisions/0001-reconciliacao-e-captura-de-registros-malformados.md`, `data-engineering/README.md` e este PRD; `feat/bronze`, sem commit nesta etapa.
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
