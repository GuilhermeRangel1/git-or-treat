# Dicionário de dados — camada Gold

**Escopo:** contrato conceitual e regras implementadas nas quinze projeções analíticas/históricas, no cadastro de titular restrito e na tabela de controle `controle_gold`. O documento descreve código e evidências disponíveis; não substitui a validação física do Delta, aceite do portal/IA ou homologação regulatória.

**Fontes:** `data-engineering/notebook/Silver_to_gold.ipynb`, notebook de exportação, contrato Silver em `docs/services/data-engineering.md`, PR #36 e manifestos/CSV locais disponíveis.

**Como ler os tipos:** as tabelas abaixo indicam o tipo **conceitual** ou o tipo explicitamente construído no código. Precisão e escala de decimais, nulabilidade física do Delta e tipos herdados da Silver precisam ser confirmados com `DESCRIBE TABLE` ou `printSchema` na execução escolhida. Uma coluna verificada por `assert_no_nulls` pode continuar com metadado físico `nullable=true` no Spark; isso não invalida a verificação dos valores daquele lote.

## Visão geral

| Tabela Gold | Uma linha representa | Chave verificada no notebook | Origem principal |
| --- | --- | --- | --- |
| `diagnostico_receita` | Uma combinação de competência, município, classe, subgrupo, bandeira e GD | Essas seis dimensões | Faturas, leituras, UCs e GD da Silver |
| `indicadores_dec_fec` | Um alimentador com ocorrências em uma competência | `id_alimentador`, `competencia` | Ocorrências e cadastro de UCs da Silver |
| `fila_inspecao` | Uma UC da base cadastral usada para priorização | `id_uc` | UCs, inspeções, atendimentos, leituras e GD da Silver |
| `visao_360_uc` | Uma UC da base cadastral com indicadores agregados | `id_uc` | UCs, atendimentos, ocorrências, leituras e GD da Silver |
| `consumo_receita_bairro` | Uma combinação de competência, município, bairro e classe | Essas quatro dimensões | Faturas, leituras e cadastro da Silver |
| `variacao_consumo_uc` | Uma UC comparada entre duas janelas fixas | `id_uc` | Leituras mensais e `visao_360_uc` |
| `consumo_mensal_uc` | Uma UC e competência observada em fatura ou leitura | `id_uc`, `competencia` | Faturas e leituras da Silver |
| `faturas_uc` | Uma fatura emitida vinculada a uma Unidade Consumidora | `id_fatura` | Faturas da Silver (`silver_publicada.faturas`) |
| `medidor_uc` | Um medidor de energia e seu histórico de vínculo por UC | `id_medidor` | Medidores da Silver (`silver_publicada.medidores`) |
| `atendimentos_uc` | Um resumo estruturado por protocolo de atendimento | `protocolo` | Atendimentos da Silver (`silver_publicada.atendimentos`) |
| `ocorrencias_uc` | Um registro de ocorrência da rede elétrica vinculado à Unidade Consumidora | `id_ocorrencia`, `id_uc` | Ocorrências da Silver (`silver_publicada.ocorrencias_rede`) |
| `gd_uc` | Um cadastro de GD observado por UC | `id_uc` | `silver_publicada.geracao_distribuida` |
| `tratativas_uc` | Uma posição original do histórico de um protocolo | `protocolo`, `posicao_historico` | `silver_publicada.atendimentos_historico` |
| `gold_cadastro.cadastro_titular_uc` | Nome atual de exibição para atendimento autorizado | `id_uc` | Cadastro Silver; schema e exportação restritos |
| `cobertura_dominios` | Um domínio, competência e recorte global ou de alimentador | `dominio`, `competencia`, `recorte` | Observações da Silver fixada e declarações autorizadas do mesmo lote |
| `decomposicao_receita` | Um recorte município/bairro/classe e duas janelas explícitas | Município, bairro, classe e quatro competências das janelas | Série mensal UC e dimensões do mesmo snapshot; cobertura certificada |
| `controle_gold` | Registro de uma execução Gold concluída pelo notebook | `run_id_gold` identifica a execução; não há teste de unicidade explícito para essa tabela | Metadados da execução e dos controles Silver |

As quinze projeções analíticas/históricas compõem o contrato candidato de exportação `gold-csv-v2`, ainda dependente de migração/carga v2 no Backend e validação do Job real. O cadastro pessoal usa pacote separado obrigatório [gold-cadastro-v1](contracts/gold-cadastro-v1.md), fora do catálogo GenAI. `controle_gold` é uma tabela operacional de linhagem e não está na lista de exportação do notebook.

## Regras compartilhadas e limites

- **Fonte e lote:** a Gold lê as vistas `silver_publicada.*` e consulta `silver.controle_publicacao` e `silver.controle_silver`. O notebook aceita `AMBIENTE` igual a `prod`, `dev` ou `test`; a execução em `prod` exige controles físicos e Silver com status `CONCLUIDO`. Os modos `dev`/`test` têm caminho de linhagem sintética quando os controles não estão disponíveis.
- **Cadastro:** os fluxos mostrados descartam UCs sem `id_uc` e identificadores iniciados por `TESTE`. A base cadastral da fila, do diagnóstico e da rede tem unicidade por UC verificada; duplicatas não são resolvidas escolhendo um cadastro arbitrário. O cadastro é uma fotografia atual: classe, município, bairro, alimentador, status e GD não comprovam sua vigência histórica.
- **Receita e consumo:** decisão de implementação autorizada pela pessoa usuária em 30/10/2026 para a evolução candidata v2 (#49): publicar faturamento total, com leitura e sem leitura separadamente. Faturas e leituras são agregadas no próprio grão UC/mês e unidas por `full outer join`; a ausência de uma fonte não elimina os fatos da outra. A tarifa observada usa somente pares com fatura e todas as leituras observadas válidas; não usa faturamento sem leitura. O histórico individual de faturas permanece independente de leitura. Essa evolução exige adaptação explícita do consumidor v1 antes da carga; não representa homologação dos resultados reais pelo time.
- **GD:** `Sim` significa que há pelo menos uma linha da UC em `geracao_distribuida`; a regra atual não considera vigência nem comprova geração, injeção ou compensação em uma competência. `Não` é atribuído quando a junção não encontra essa linha.
- **Privacidade:** a projeção final de `fila_inspecao` e `visao_360_uc` não inclui CPF/CNPJ, nome, endereço, CEP, coordenadas ou metadados internos da Silver. `id_uc` continua sendo identificador de unidade: a ausência desses campos não torna o conjunto automaticamente anônimo.
- **Publicação:** validar no schema de preparo antes da promoção; produção, desenvolvimento e teste têm destinos separados. Recuperar falhas capturadas e impedir execuções concorrentes; não há transação multi-tabela.
- **Ausência e zero:** verifique a regra específica de cada tabela. Algumas contagens são preenchidas com zero quando uma junção não encontra registro; isso não demonstra, por si só, cobertura completa da fonte. Uma linha ausente em `indicadores_dec_fec` ou `ocorrencias_uc` não prova ausência de interrupções.

## 1. `diagnostico_receita`

**Finalidade:** analisar faturamento total, sua decomposição por presença de leitura e consumo medido por recorte comercial.
**Grão e chave de verificação:** (`competencia`, `municipio`, `classe_consumo`, `subgrupo_tarifario`, `bandeira_tarifaria`, `possui_gd`).
**Fontes:** faturas, leituras, unidades consumidoras e geração distribuída da Silver publicada; as fontes de fatura e leitura são agregadas separadamente por UC/mês antes da junção.

| Coluna | Tipo conceitual / unidade | Definição |
| --- | --- | --- |
| `competencia`, `municipio`, `classe_consumo`, `subgrupo_tarifario`, `bandeira_tarifaria`, `possui_gd` | texto | Competência e dimensões do cadastro atual; dimensões ausentes são rotuladas `Não informado`. GD significa presença cadastral, sem vigência histórica. |
| `receita_total_reais` | decimal / R$ | Soma do valor total das faturas elegíveis, independentemente de leitura; não é receita recebida. |
| `receita_com_leitura_reais` | decimal / R$ | Faturas de UC/mês com pelo menos uma leitura observada; não atesta validade de todas as leituras. |
| `receita_sem_leitura_reais` | decimal / R$ | Faturas de UC/mês sem leitura observada. Nas linhas com faturamento, as parcelas com e sem leitura somam o total. |
| `consumo_total_kwh` | número / kWh | Soma das leituras com consumo presente; pode incluir UC/mês sem fatura. |
| `receita_base_comparavel_reais` | decimal / R$ | Faturamento somente de UC/mês com fatura e todas as leituras observadas válidas. |
| `consumo_base_comparavel_kwh` | número / kWh | Consumo dos mesmos pares UC/mês da receita comparável. |
| `qtd_ucs_distintas_faturadas_no_mes` | inteiro / UCs | Contagem distinta de UCs com fatura no recorte. |
| `qtd_ucs_com_leitura` | inteiro / UCs | Contagem distinta com ao menos uma leitura observada, ainda que parcial ou inválida. |
| `soma_faturamentos_mensais` | inteiro / faturas | Soma das contagens de faturas por UC/mês; não equivale a UCs distintas. |
| `qtd_leituras_observadas`, `qtd_leituras_validas` | inteiro / leituras | Contagens da origem; diferença entre elas sinaliza leitura ausente/inválida. |
| `ticket_medio_reais_por_uc` | número / R$/UC | Média do faturamento agregado por UC/mês entre os valores não nulos. |
| `consumo_medio_kwh_por_uc` | número / kWh/UC | Média do consumo agregado por UC/mês entre os valores não nulos. |
| `tarifa_media_efetiva` | número / R$/kWh | Receita comparável dividida pelo consumo comparável, quando o denominador é positivo; preço observado, não tarifa homologada. |

**Limites:** ausência de uma fonte permanece nula; não equivale a zero. Leitura observada não significa leitura válida. As dimensões vêm do cadastro atual, não de um histórico temporal; nenhuma métrica certifica fechamento mensal, energia efetivamente faturada ou pagamento. A base comparável é a única elegível para análises preço-volume.

**Exemplos de categorias:** `classe_consumo` usa grafias da origem como `COMERCIAL`, `INDUSTRIAL`, `PODER PUBLICO`, `RESIDENCIAL` e `RURAL`; exemplos não formam um domínio fechado imposto pela Gold.

## 2. `indicadores_dec_fec`

**Finalidade:** indicadores internos simplificados de continuidade por alimentador e mês.
**Grão e chave:** (`id_alimentador`, `competencia`).
**Fontes:** `ocorrencias_rede` e `unidades_consumidoras`; a competência vem de `data_abertura` da ocorrência.

| Coluna | Tipo conceitual / unidade | Definição |
| --- | --- | --- |
| `id_alimentador` | texto | Alimentador associado pelo cadastro atual da UC. |
| `municipio` | texto | Município associado ao alimentador pelo cadastro; mais de um município distinto para o mesmo alimentador faz o notebook falhar. |
| `competencia` | texto `YYYY-MM` | Mês da abertura das ocorrências incluídas. |
| `total_ucs_alimentador` | inteiro / UCs | Contagem distinta de UCs do cadastro atual no alimentador, excluídas as UCs de teste. É um denominador cadastral, não uma população histórica mensal. |
| `ucs_interrompidas` | inteiro / UCs | UCs distintas com ocorrência no alimentador e mês. |
| `frequencia_total_interrupcoes` | inteiro / pares UC–ocorrência | Contagem distinta de (`id_uc`, `id_ocorrencia`); uma UC com ocorrências diferentes pode contribuir mais de uma vez. |
| `duracao_total_interrupcoes_horas` | número / horas | Soma de `duracao_min / 60` quando todas as ocorrências do grupo têm duração válida; nula se qualquer duração estiver ausente ou sinalizada como incompatível. Zero exige durações válidas iguais a zero. |
| `DEC` | número / horas por UC | `duracao_total_interrupcoes_horas / total_ucs_alimentador`. |
| `FEC` | número / interrupções por UC | `frequencia_total_interrupcoes / total_ucs_alimentador`. |

**Filtros e limites:** exige UC, ocorrência e data de abertura não nulas; verifica unicidade do par UC–ocorrência e rejeita duração negativa. A atribuição usa o cadastro atual e não prova vigência histórica. A tabela parte das ocorrências agregadas: não cria automaticamente linhas para alimentadores/mês sem ocorrência. O teste geral rejeita denominador inválido, FEC nulo e métricas negativas. DEC é nulo quando a duração total é desconhecida; a frequência permanece disponível. A reconciliação rejeita somas parciais tratadas como completas e exige a mesma ausência de duração e DEC entre origem e agregado. Estes indicadores são simplificados e não constituem apuração ou conformidade regulatória oficial.

## 3. `fila_inspecao`

**Finalidade:** apresentar atributos e prioridades para triagem de UCs.
**Grão e chave:** uma linha por `id_uc`; o notebook verifica unicidade e ausência de nulos em `id_uc`, `municipio`, `bairro`, `alimentador` e `prioridade_inspecao`.
**Fontes:** cadastro, inspeções, atendimentos, leituras e GD da Silver. Os agregados de atendimento são construídos no processamento, mas não são projetados na tabela final da fila.

| Coluna | Tipo conceitual / unidade | Definição |
| --- | --- | --- |
| `id_uc` | texto | Identificador da unidade consumidora. |
| `municipio` | texto | Município do cadastro atual. |
| `bairro` | texto | Bairro do cadastro atual. |
| `uf` | texto | Unidade federativa do cadastro. |
| `classe` | texto | Classe do cadastro atual. |
| `subgrupo` | texto | `subgrupo_tarifario` da Silver, renomeado na projeção. |
| `alimentador` | texto | Alimentador do cadastro atual. |
| `data_ligacao` | data | Data de ligação cadastrada. Valores anteriores a 1950-01-01 saem nulos na Gold (D62); a Silver preserva o original. |
| `status` | texto | Status cadastral da UC. |
| `possui_geracao_solar` | texto: `Sim`/`Não` | Presença de linha de GD; o nome da coluna não prova geração ou compensação mensal. |
| `total_inspecoes_realizadas` | inteiro / inspeções | Contagem distinta de `id_inspecao` com UC e ID não nulos; zero quando não há agregado associado. |
| `total_inspecoes_irregulares` | inteiro / inspeções | Contagem distinta cujo `resultado` é exatamente `IRREGULARIDADE CONFIRMADA`; outros valores não entram nessa contagem. |
| `media_consumo_historico` | número / kWh por leitura | Média de `consumo_kwh` das leituras não nulas da UC; não é necessariamente média mensal. Nula se não houver leitura válida associada. |
| `prioridade_inspecao` | texto | Categoria produzida pela hierarquia abaixo. |
| `motivo_prioridade` | texto | Primeira condição atendida na mesma hierarquia da prioridade; explica a triagem, não estima recuperação. |
| `ordem_prioridade_inspecao` | inteiro nullable | Ordem da categoria: 1 `ALTA - HISTORICO IRREGULAR`, 2 `ALTA - CONSUMO ZERO`, 3 `MEDIA - NUNCA INSPECIONADO`, 4 `BAIXA`. Nulo em `REVISAR - SEM HISTORICO DE CONSUMO`, que é um caso à parte. |
| `posicao_fila_inspecao` | inteiro não nulo | Posição única na fila, de 1 a N. Ordena por `ordem_prioridade_inspecao` (nulos por último), depois mais `total_inspecoes_irregulares`, depois maior `media_consumo_historico` (nulos por último) e, por fim, `id_uc`. É ordem de triagem, não estimativa de recuperação nem a prioridade escolhida para a ordem de serviço. |

**Prioridade, na ordem aplicada:**

1. `ALTA - HISTORICO IRREGULAR`: há inspeção com resultado exatamente `IRREGULARIDADE CONFIRMADA`.
2. `REVISAR - SEM HISTORICO DE CONSUMO`: não há média de consumo disponível.
3. `ALTA - CONSUMO ZERO`: média de consumo igual a zero e `possui_geracao_solar = Não`.
4. `MEDIA - NUNCA INSPECIONADO`: não se enquadrou acima e não há inspeções realizadas.
5. `BAIXA`: demais casos.

`motivo_prioridade` repete a precedência das regras e registra a primeira condição atendida. Prioridade e motivo indicam uma regra de triagem; não são diagnóstico de fraude nem estimativa de energia recuperável. O mapeamento de outros resultados de inspeção deve ser confirmado com a origem antes de ampliá-lo. A Silver tem `inspecoes.kwh_recuperado` como histórico; o estudo abaixo avalia referências médias históricas candidatas, sem atribuí-las a outra UC. WEB-04 ainda exige decisão explícita de escopo, aceite do método e resultado no lote real.

A regra `ALTA - CONSUMO ZERO` permanece parte do contrato mesmo em exportações sem casos nessa categoria. A ausência de casos não demonstra que a categoria seja inalcançável.

## 4. `visao_360_uc`

**Finalidade:** reunir atributos cadastrais e indicadores agregados por UC.
**Grão e chave:** `id_uc`; o notebook também exige `municipio`, `bairro` e `alimentador` não nulos.
**Fontes:** cadastro, atendimentos, ocorrências, leituras e GD da Silver.

| Coluna | Tipo conceitual / unidade | Definição |
| --- | --- | --- |
| `id_uc` | texto | Identificador da unidade consumidora. |
| `municipio` | texto | Município do cadastro atual. |
| `bairro` | texto | Bairro do cadastro atual. |
| `uf` | texto | Unidade federativa do cadastro. |
| `classe` | texto | Classe de consumo atual. |
| `subgrupo` | texto | `subgrupo_tarifario` renomeado. |
| `alimentador` | texto | Alimentador do cadastro atual. |
| `data_ligacao` | data | Data de ligação cadastrada. Valores anteriores a 1950-01-01 saem nulos na Gold (D62); a Silver preserva o original. |
| `status` | texto | Status cadastral da UC. |
| `possui_gd` | texto: `Sim`/`Não` | Presença de linha de GD, sem vigência temporal. |
| `total_chamados_callcenter` | inteiro / protocolos | Contagem distinta de protocolos associados; zero quando não há agregado associado. Reconciliada por UC com `atendimentos_uc`. |
| `media_satisfacao_atendimento` | número / nota | Média de `nota_satisfacao` dos atendimentos válidos; pode ser nula. |
| `total_interrupcoes_sofridas` | inteiro / ocorrências | Contagem distinta de IDs de ocorrência elegíveis por UC; zero quando não há agregado associado. Reconciliada por UC com `ocorrencias_uc`. |
| `duracao_total_interrupcoes_horas` | número / horas | Soma das durações válidas das ocorrências associadas divididas por 60; nula quando alguma duração é desconhecida. Zero é usado quando a UC não tem ocorrências, ou todas as durações observadas são zero. |
| `media_consumo_historico` | número / kWh por leitura | Média das leituras não nulas associadas à UC; pode ser nula e não equivale necessariamente a média mensal. |

**Controle:** os totais de chamados e interrupções são reconciliados por UC com `atendimentos_uc` e `ocorrencias_uc`. A elegibilidade de ocorrências usa a mesma flag `_id_uc_ausente = false` nas projeções resumida e detalhada.

**Limite:** esta tabela não contém nome, endereço, histórico de faturas, medidores ou registros individuais de atendimento/interrupção. Esses dados não podem ser deduzidos da presença desta tabela; a jornada do portal deve usar fontes adequadas para cada detalhe.

## 5. `consumo_receita_bairro`

**Finalidade:** analisar faturamento total, parcelas com/sem leitura e consumo medido por competência, município, bairro e classe.
**Grão e chave:** (`competencia`, `municipio`, `bairro`, `classe_consumo`), não nulos e únicos.
**Fontes:** faturas e leituras agregadas por UC/mês, associadas ao cadastro atual por `left join`; fatos das duas fontes são preservados independentemente.

| Coluna | Tipo conceitual / unidade | Definição |
| --- | --- | --- |
| `competencia`, `municipio`, `bairro`, `classe_consumo` | texto | Competência e dimensões do cadastro; dimensões ausentes são `Não informado`. |
| `receita_total_reais` | decimal / R$ | Soma de faturas elegíveis, sem afirmar pagamento. |
| `receita_com_leitura_reais` | decimal / R$ | Faturamento em UC/mês com pelo menos uma leitura observada. |
| `receita_sem_leitura_reais` | decimal / R$ | Faturamento em UC/mês sem leitura observada. |
| `consumo_total_kwh` | número / kWh | Soma de leituras com consumo presente, inclusive sem fatura. |
| `receita_base_comparavel_reais` | decimal / R$ | Receita dos pares UC/mês com fatura e leituras observadas integralmente válidas. |
| `consumo_base_comparavel_kwh` | número / kWh | Consumo dos mesmos pares que compõem a receita comparável. |
| `qtd_ucs_distintas_faturadas_no_mes`, `qtd_ucs_com_leitura` | inteiro / UCs | Contagens distintas de UCs faturadas e com leitura observada, respectivamente. |
| `soma_faturamentos_mensais`, `qtd_leituras_observadas`, `qtd_leituras_validas` | inteiro / registros | Contagens de faturas e leituras de origem por recorte. |

**Limites:** grupo apenas de leitura mantém receita nula; grupo com fatura sem membro de uma parcela usa zero nessa parcela. Total e componentes devem reconciliar. Ausência cadastral recebe `Não informado`; o consumo e a receita não comprovam cobertura completa nem pagamento.

## 6. `variacao_consumo_uc`

**Finalidade:** comparar o consumo mensal médio de cada UC entre dois períodos fixos.
**Grão e chave:** `id_uc`; população de referência herdada de `visao_360_uc`.
**Fontes:** `gold_visao_360` e leituras pré-agregadas por UC e mês.

**Janelas inclusivas:** P1 = julho/2022 a junho/2023; P2 = julho/2025 a junho/2026. Cada média usa as competências com consumo não nulo disponíveis na janela; o código não exige 12 meses completos.

| Coluna | Tipo conceitual / unidade | Definição |
| --- | --- | --- |
| `id_uc` | texto | Identificador da unidade. |
| `municipio` | texto | Município da Visão 360; ausência recebe `Não informado`. |
| `bairro` | texto | Bairro da Visão 360; ausência recebe `Não informado`. |
| `possui_gd` | texto: `Sim`/`Não` | Presença de linha de GD; sem vigência histórica. |
| `consumo_medio_inicial` | número / kWh por mês observado | Média de `consumo_uc_mes` em P1, arredondada a duas casas; pode ser nula. |
| `meses_com_leitura_p1` | inteiro / meses | Número de competências distintas com consumo não nulo em P1; zero se não houver agregado. |
| `consumo_medio_final` | número / kWh por mês observado | Média de `consumo_uc_mes` em P2, arredondada a duas casas; pode ser nula. |
| `meses_com_leitura_p2` | inteiro / meses | Número de competências distintas com consumo não nulo em P2; zero se não houver agregado. |
| `variacao_kwh` | número / kWh | Média final menos inicial, calculada antes do arredondamento de exibição e arredondada a duas casas; nula se uma média estiver ausente. |
| `variacao_pct` | número / % | `(média final − média inicial) / média inicial × 100`, arredondada a duas casas; nula quando a média inicial não é positiva ou a final está ausente. |
| `queda_consumo_superior_30_pct` | booleano | Verdadeiro quando a variação percentual **bruta** é estritamente menor que −30%; comparações sem valor viram `false`. Uma queda exatamente de 30% não atende à regra. |

**Interpretação:** `false` na flag também pode representar comparação indisponível; consulte as médias e contagens de meses antes de concluir que não houve queda. A variação usa leituras; os agregados de receita e consumo preservam as duas fontes independentemente.

## 7. `consumo_mensal_uc`

**Finalidade:** série mensal por UC para faturamento, consumo observado e comparação restrita à base elegível.
**Grão e chave:** (`id_uc`, `competencia`), não nulos e únicos.
**Fontes:** faturas e leituras agregadas separadamente por UC/mês e unidas com `full outer join`.

| Coluna | Tipo conceitual / unidade | Definição |
| --- | --- | --- |
| `id_uc` | texto | Identificador da unidade consumidora. |
| `competencia` | texto `YYYY-MM` | Mês observado em pelo menos uma das fontes. |
| `consumo_kwh` | número / kWh | Soma do consumo observado; pode existir sem fatura. |
| `receita_reais` | decimal / R$ | Faturamento total; nulo quando não há fatura. Não é valor pago. |
| `receita_com_leitura_reais` | decimal / R$ | Valor faturado quando há ao menos uma leitura observada; zero se há fatura sem leitura; nulo sem fatura. |
| `receita_sem_leitura_reais` | decimal / R$ | Valor faturado quando não há leitura observada; zero se há fatura com leitura; nulo sem fatura. |
| `receita_base_comparavel_reais` | decimal / R$ | Faturamento somente se existe fatura, leitura e todas as leituras observadas têm consumo válido; caso contrário nulo. |
| `consumo_base_comparavel_kwh` | número / kWh | Consumo da mesma UC/mês elegível à base comparável; caso contrário nulo. |
| `tem_fatura`, `tem_leitura` | booleano | Indicam presença de registro em cada fonte; não significam completude mensal. |
| `qtd_faturas` | inteiro / faturas | Quantidade de faturas observadas na UC/mês; zero sem fatura. |
| `qtd_leituras_observadas`, `qtd_leituras_validas` | inteiro / leituras | Registros observados e com consumo presente; a diferença sinaliza incompletude. |

**Limites:** a linha existe se a UC/mês está em pelo menos uma fonte; não se fabricam meses sem observação. Uma leitura observada pode ser inválida, e presença de linha não comprova fechamento ou cobertura completa da competência. Ausência permanece nula onde a medida não existe; não é zero conhecido.

## 8. `faturas_uc`

**Grão e população:** uma linha por `id_fatura`; preserva as faturas elegíveis mesmo quando não há leitura pareada.

| Coluna | Tipo / unidade | Definição |
| --- | --- | --- |
| `id_fatura`, `id_uc` | texto | Identificador da fatura e UC associada; chaves obrigatórias. |
| `mes_referencia` | texto `YYYY-MM` | Competência da fatura. |
| `data_emissao`, `data_vencimento`, `data_pagamento` | date | Datas saneadas conforme flags Silver; vencimento futuro é válido e pagamento inconclusivo fica nulo. |
| `valor_energia`, `tributos`, `valor_total` | decimal(20,2) / R$ | Valores cobrados; não demonstram pagamento efetivo. |
| `bandeira_tarifaria`, `status` | texto | Valores declarados na origem; status não comprova quitação. |
| `valor_em_aberto_reais` | decimal(20,2) / R$ | Indicação derivada do status e flags; não é saldo contábil nem suporta pagamento parcial. Casos conflitantes/inconclusivos ou valor inválido ficam nulos. |
| `situacao_pagamento_analitica` | texto | Categoria que preserva status declarado, sinais conflitantes e incerteza. |
| `flag_paga`, `flag_tem_pagamento`, `flag_valor_inconsistente`, `flag_data_pagamento_inconclusiva`, `flag_paga_sem_data_valida`, `flag_pagamento_antes_emissao`, `flag_pagamento_sentinela`, `flag_pagamento_futuro`, `flag_emissao_sentinela`, `flag_emissao_futura`, `flag_vencimento_sentinela`, `flag_valor_negativo` | booleano | Sinais de qualidade da Silver preservados para interpretação e auditoria; não são confirmação de recebimento. |
| `data_processamento_gold` | timestamp UTC | Instante de referência único da execução Gold. |

Fonte: `silver_publicada.faturas`. O saldo indicativo não calcula pagamentos parciais; status `PAGA` com data válida pode gerar zero declarado, não confirmação financeira. Não é necessário haver leitura na competência.

## 9. `medidor_uc`

**Grão e população:** um registro por `id_medidor`, vinculado a `id_uc`; exclui UC nula ou com prefixo `TESTE`.

| Coluna | Tipo / unidade | Definição |
| --- | --- | --- |
| `id_medidor`, `id_uc` | texto | Chaves obrigatórias; medidor único entre as linhas elegíveis. |
| `modelo`, `tipo`, `status` | texto | Atributos observados do equipamento. |
| `data_instalacao`, `data_retirada` | date | Datas nulas quando flags Silver indicam sentinela/futuro; retirada anterior à instalação reprova o lote. |
| `flag_instalacao_sentinela`, `flag_instalacao_futura`, `flag_retirada_sentinela`, `flag_retirada_futura` | booleano | Preservam a razão do saneamento. |
| `ingestao_data` | timestamp UTC | Instante de referência único Gold. |
| `situacao_na_referencia` | texto | `INSTALADO`, `RETIRADO` ou `INDETERMINADO`, calculado por medidor. Não colapsa sobreposições nem seleciona um equipamento único por UC. |

Fonte: `silver_publicada.medidores`. Não aplica corte arbitrário por ano e não fabrica transferências. Provisoriamente, instalação válida sem retirada registrada é classificada como `INSTALADO`; ausência de retirada não prova atividade e precisa de validação conjunta. Manutenção não é publicada nesta projeção.

## 10. `atendimentos_uc`

**Grão e população:** Um resumo estruturado por `protocolo`; exclui UC nula ou com prefixo TESTE.

| Coluna | Tipo / unidade | Definição |
| --- | --- | --- |
| `protocolo`, `id_uc` | string | Protocolo único e UC obrigatória. |
| `canal`, `assunto`, `subassunto` | string | Classificações observadas. |
| `data_abertura`, `data_fechamento` | timestamp UTC | Datas nulas quando a flag Silver correspondente indica futuro. |
| `nota_satisfacao` | double / pontos | Nota inválida ou negativa fica nula; ausência não é zero. |
| `qtd_tratativas` | inteiro | Quantidade de tratativas por protocolo; reconciliada com a contagem de linhas em `atendimentos_historico`. Não é quantidade de chamados. |
| `_abertura_futura`, `_fechamento_futura`, `_nota_negativa`, `_nota_invalida` | boolean | Flags de qualidade Silver mantidas com seus nomes físicos; metadados técnicos para o Backend, não autorização de exposição ao modelo. |
| `ingestao_data` | timestamp UTC | Referência temporal única Gold. |

Fonte: `silver_publicada.atendimentos`. Texto descritivo de ações das tratativas não é exportado; esses campos ficam fora até que seu conteúdo e tratamento sejam classificados e aprovados. A tabela mantém `qtd_tratativas`, mas não exporta o histórico completo. Nenhum join com faturas ou ocorrências altera a contagem de protocolos.

## 11. `ocorrencias_uc`

**Grão e população:** Uma ocorrência vinculada à UC por `(id_ocorrencia, id_uc)`.

| Coluna | Tipo / unidade | Definição |
| --- | --- | --- |
| `id_ocorrencia`, `id_uc` | string | Chave composta obrigatória na projeção; duplicidade na fonte reprova o lote. |
| `alimentador`, `tipo`, `causa` | string | Atributos observados do evento. |
| `data_abertura`, `data_encerramento` | timestamp UTC | Datas futuras pela flag ou pela referência Gold ficam nulas. |
| `duracao_min` | numérico / minutos | Duração inválida, negativa ou ausente permanece nula; não imputa zero. |
| `flag_duracao_incompativel`, `flag_abertura_futura`, `flag_encerramento_futuro` | boolean | Sinais de qualidade Silver preservados. |
| `ingestao_data` | timestamp UTC | Referência temporal única Gold. |

Fonte: `silver_publicada.ocorrencias_rede`. Exclui evento sem UC vinculável, ID nulo ou `_id_uc_ausente` diferente de falso; reconcilia a população elegível. O notebook exige schema exato e chave composta sem nulos ou duplicidades, e confere a contagem por UC com a visão 360. Linha ausente não comprova zero interrupções. Não cruza fatos financeiros e não demonstra continuidade regulatória.

## 12. `gd_uc`

Uma linha por UC com GD na Silver publicada; UC nula ou de teste é excluída. Potência inválida, duplicidade ou UC órfã bloqueiam a projeção. UC sem registro de GD não gera linha artificial.

| Campo | Tipo Spark / unidade | Regra |
| --- | --- | --- |
| `id_uc` | `string` | Chave não nula e única. |
| `potencia_kwp` | `double` / kWp | Valor observado; nulo permanece nulo e zero não vira ausência. Negativo, NaN e infinito são recusados. Não equivale a kW de geração instantânea. |
| `data_conexao` | `date` | Nula para conexão futura ou sentinela; não inventa vigência. |
| `modalidade` | `string` | Categoria observada da Silver; não comprova que a fonte é solar. |
| `flag_conexao_futura`, `flag_conexao_sentinela` | `boolean` | Motivo do saneamento; flags nulas são tratadas como falsas, com comparação adicional à data de referência. |
| `data_processamento_gold` | `timestamp` UTC | Instante de referência da execução. |

Não exporta a média de injeção como geração mensal nem constrói série temporal inexistente. A API deve mapear a unidade explicitamente; não renomear silenciosamente kWp para kW. O modelo atual `GenerationDetail` precisa ser evoluído para representar ausência e data/modalidade.

## 13. `tratativas_uc`

Uma linha por `(protocolo, posicao_historico)`, vinculada à UC do protocolo. Preserva todas as posições dos protocolos elegíveis; protocolos sem tratativas conservam zero em `atendimentos_uc`, sem linha artificial neste histórico. Chaves órfãs/duplicadas, posições não contíguas ou divergência com `qtd_tratativas` bloqueiam a projeção. `sequencia` repetida não multiplica chamados nem serve como chave.

| Campo | Tipo Spark | Regra |
| --- | --- | --- |
| `protocolo`, `id_uc` | `string` | Chaves/vínculo obrigatórios; protocolo deve existir no resumo publicado. |
| `posicao_historico` | `int` | Posição original de 1 em diante; ordenação estável do histórico. |
| `sequencia_origem` | `int` | Sequência observada, podendo repetir ou ser nula; nula quando sinalizada como inválida na Silver. |
| `data_tratativa` | `timestamp` UTC | Nula quando ausente, inválida ou posterior à referência Gold. |
| `acao_categoria` | `string` | Somente correspondência integral com `ABERTURA`, `ENCERRAMENTO`, `TRANSFERENCIA`, `RETORNO`, `ATUALIZACAO`; ausente vira `AUSENTE_NA_ORIGEM`, demais textos viram `CONTEUDO_RESTRITO`. |
| `canal` | `string` | Correspondência integral com `TELEFONE`, `WHATSAPP`, `EMAIL`, `CHAT`, `PRESENCIAL`, `APP`, `SITE`, `OUVIDORIA`, `CALL CENTER`; demais valores viram `NAO_CLASSIFICADO`. |
| `flag_data_invalida`, `flag_data_futura`, `flag_sequencia_invalida` | `boolean` | Distinguem as limitações das datas/sequência; não há imputação de data. |
| `data_processamento_gold` | `timestamp` UTC | Instante de referência da execução. |

As listas são regras técnicas explícitas de divulgação mínima, não um domínio homologado de todos os eventos da origem. Texto livre de ação/canal não é copiado nem tratado como anonimizado por regex. A posição e a existência do evento são preservadas mesmo quando seu conteúdo é restrito. O portal deve informar essa restrição; conteúdo integral exigiria política e entrega específica. Agregar chamados por `atendimentos_uc`, nunca contar linhas de tratativas como protocolos.

## 14. Cadastro restrito do titular

`gold_cadastro.cadastro_titular_uc`: nome atual de exibição, sem CPF/CNPJ ou referência de cliente fabricada. O [contrato cadastral](contracts/gold-cadastro-v1.md) define os quatro campos, nulos/conflitos, ligação por UC, pacote separado e obrigações de acesso. O nome não integra a visão agregada, a fila ou o catálogo da IA.

## 15. `cobertura_dominios`

Grão: `(dominio, competencia, recorte)`. Gera grade mensal, incluindo competências sem registros e alimentadores sem eventos. Contagem zero isolada não certifica cobertura; o [contrato de cobertura](contracts/gold-cobertura-v1.md) define declarações, estados, janela e obrigações dos consumidores.

| Campo | Tipo Spark | Definição |
| --- | --- | --- |
| `dominio`, `competencia`, `recorte` | `string` | Chave não nula e única. Domínios: consumo, faturamento, atendimentos, ocorrencias, medidores e gd. Recorte `DOMINIO` ou `ALIMENTADOR:<id>` para ocorrências. |
| `natureza_temporal` | `string` | `COMPETENCIA`, `ABERTURA`, `INSTALACAO_CADASTRAL` ou `CONEXAO_CADASTRAL`. Cadastros atuais não certificam vigência histórica mensal. |
| `estado_cobertura` | `string` | `NAO_CERTIFICADA` por padrão; `FECHADO`, `PARCIAL` ou `AUSENTE` somente com declaração válida vinculada ao lote. |
| `qtd_registros` | `bigint` | Contagem de registros elegíveis por mês no snapshot Silver fixado; não é filtrada pelo corte da evidência externa. Não representa valor de consumo/receita. |
| `qtd_sem_competencia` | `bigint` | Registros elegíveis sem atribuição temporal válida no domínio/recorte, repetidos na grade para sinalizar a limitação. Não somar essa coluna entre meses. Impede fechamento do recorte. |
| `zero_registros_confirmado` | `boolean` | Verdadeiro somente quando o recorte/mês está fechado e a contagem de registros é zero. Não preenche medidas nulas com zero. |
| `data_corte_evidencia` | `timestamp` UTC | Corte declarado pela evidência externa, distinto da referência do snapshot observado. Nulo sem declaração. |
| `referencia_evidencia` | `string` | Referência opaca, sem dados pessoais/segredos; nula sem declaração. Não é certificação automática do fornecedor. |
| `motivo` | `string` | `SEM_EVIDENCIA_DE_COBERTURA`, `ZERO_REGISTROS_DECLARADO`, `FECHADO_DECLARADO`, `PARCIAL_DECLARADO` ou `AUSENTE_DECLARADO`. |
| `origem_janela` | `string` | `EXPLICITA` ou `LIMITES_OBSERVADOS_NAO_CERTIFICADOS`. Sem janela explícita não extrapola ausência além dos extremos observados. |
| `run_id_silver`, `lote_bronze_silver` | `string` | Identidade da origem fixada, igual à exigida das declarações. |
| `data_processamento_gold` | `timestamp` UTC | Referência usada nas observações do snapshot. Não se confunde com o corte da evidência externa. |

Datas futuras/sentinelas e datas ausentes não geram competência artificial. Leituras/faturas são observadas independentemente; eventos usam a competência de abertura. O recorte por alimentador usa o cadastro atual. Não somar contagens globais e por alimentador; são níveis distintos. Declarações sobrepostas, fora da janela, contraditórias com fatos ou entre domínio/alimentador são recusadas.

Os meses não são fechados automaticamente por número de linhas, calendário ou presença de competências consecutivas. Medidor/GD não aceitam fechamento histórico com base no cadastro atual. Sem declarações aprovadas, a tabela é um controle de observação não certificado, pronto para receber a evidência real posteriormente.

## 16. `controle_gold` — linhagem da execução

O notebook gera um registro de controle ao final das verificações e usa `append` quando a tabela já existe. Não integra as quinze tabelas do CSV analítico nem o pacote cadastral. Uma falha anterior a essa etapa não garante um registro de falha nesta tabela.

| Coluna | Tipo declarado | Definição |
| --- | --- | --- |
| `run_id_gold` | `string` | ID da execução Gold, com data/hora UTC e sufixo aleatório. |
| `run_id_silver` | `string` | Identificador da execução Silver usada. |
| `lote_bronze_silver` | `string` | Identificador do lote Bronze informado pela linhagem Silver. |
| `status_silver` | `string` | Estado Silver registrado para a execução. |
| `silver_lineage_status` | `string` | Identifica se a linhagem veio de controle físico ou do caminho sintético. |
| `status_gold` | `string` | `CONCLUIDO` quando o registro final é criado. |
| `tabelas_geradas` | `string` | Lista textual das quinze tabelas analíticas verificadas. |
| `tabelas_restritas_geradas` | texto | Inventário separado `cadastro_titular_uc`; promovido no schema cadastral sob a mesma execução. |
| `ambiente` | `string` | `prod`, `dev` ou `test`. |
| `processado_em` | `timestamp` | Instante UTC usado para o registro. |

Esses campos têm nulabilidade física `False`. Gold valida quinze candidatos analíticos e o cadastro restrito em schema exclusivo, promove as projeções analíticas para `gold` em produção (`gold_dev`/`gold_test` nos demais ambientes) e o cadastro para `gold_cadastro` (com sufixo de ambiente fora de produção) e registra o controle dentro do bloco de recuperação de falhas capturadas. Não há transação única entre tabelas: o Job deve executar sem concorrência e os consumidores devem aguardar sucesso. Falha abrupta ou falha no RESTORE exige recuperação operacional antes do consumo.

O controle registra `tabelas_geradas` (quinze projeções analíticas) e `tabelas_restritas_geradas` (`cadastro_titular_uc`). Ambos só recebem conclusão após a promoção de todos os candidatos; a recuperação de falhas capturadas inclui o schema cadastral. Não há transação multi-tabela.

## Exportação e verificações

O exportador exige o controle produtivo mais recente, sem empate temporal, com linhagem física Silver concluída, identidade completa e conjunto exato das quinze tabelas analíticas e inventário cadastral separado. O `run_id` opcional só confirma o controle; nunca o substitui. As versões Delta são fixadas e verificadas novamente antes de liberar o manifesto.

Cada tentativa grava em `/Volumes/workspace/gold/gold_export_volume/export_csv/<run_id_gold>/<export_id>/`, em quinze subpastas analíticas, sem sobrescrever exportações anteriores. CSV: cabeçalho, separador `;`, UTF-8, aspas, datas ISO, timestamps UTC com microssegundos e offset, decimais com escala preservada; `\N` é nulo, distinto de string vazia (o marcador literal é reservado). Cada CSV é relido com o schema original e comparado como multiconjunto completo. O manifesto é criado somente após reconciliação e revalidação de controle/versões. Pasta sem manifesto é tentativa incompleta e não deve ser carregada.

O manifesto `gold-csv-v2` contém as quinze tabelas analíticas, contagens, schemas físicos, versões Delta, execução Gold e origem Silver/Bronze. É um contrato candidato: o carregador atual `gold-csv-v1` rejeita este conjunto e não foi alterado; a migração/carga v2 e os consumidores ainda precisam ser integrados. Não adaptar o snapshot histórico v1 silenciosamente.

O [contrato candidato v2](contracts/gold-csv-v2.md) descreve o pacote e suas incompatibilidades com v1. O manifesto emite `data_processamento_gold` com offset UTC e `status_gold=CONCLUIDO` obtido do controle validado; a exportação rejeita IDs manuais, de reserva e datas impossíveis nos identificadores de origem. `export_id` identifica somente a tentativa de exportação, não a publicação local gerada pelo Backend.

Os testes Gold conferem chaves, população elegível, finanças e todos os grupos DEC/FEC, com tolerância explícita para somas em ponto flutuante. Datas e ausências seguem as regras acima; a existência do código não comprova execução sobre o lote real. O exportador requer Gold → exportação serializados, pois verificações de versão não substituem uma transação multi-tabela ou um bloqueio de execução.

### Rastreabilidade e reconciliação por execução

IDs de execução, contagens, distribuições e totais apurados pertencem ao manifesto e às evidências do lote no ambiente autorizado. Esses resultados não são constantes do modelo e não integram este dicionário.

Diferenças entre exportações devem ser investigadas para o mesmo lote e grão completo: `competencia`, `municipio`, `bairro` e `classe_consumo`. Comparar chaves exclusivas, repetidas ou ausentes; a quantidade de nomes distintos de bairro, isoladamente, não explica diferenças de linhas.

A reconciliação deve conferir receita e energia entre as tabelas pertinentes, no total e por competência, e registrar as exclusões dos vínculos com a Silver. Controles de estrutura não substituem essa conferência semântica.

## Conferência no Databricks antes de homologar

Para cada projeção analítica, para o cadastro restrito e para `controle_gold`:

1. Consultar `DESCRIBE TABLE` ou `printSchema` e registrar tipos físicos, precisão decimal e nulabilidade.
2. Conferir as colunas publicadas com este dicionário e verificar chaves, nulos, contagens e relações entre tabelas para o mesmo lote.
3. Reconciliar receita e energia com as fontes Silver, incluindo as parcelas com e sem leitura e as leituras sem fatura, e registrar a evidência para o lote efetivo.
4. Conferir DEC/FEC, janelas e população em amostras independentes; identificar competências sem linha, denominadores e limites do cadastro atual.
5. Comparar esquema, contagens e agregados de Gold, CSV e banco local; verificar os arquivos de cada diretório, o lote e as condições de reexecução.
6. Revisar permissões e uso de identificadores no portal/IA. Só alterar o estado de DE-08 após revisão humana e evidências correspondentes; este dicionário documenta o contrato, não conclui o requisito.

Na entrega completa, cadastro e pacote analítico são obrigatórios e mantêm destinos separados. O manifesto analítico inclui `cadastro_export_id`/`cadastro_schema_version`; o cadastro inclui `analytic_export_id`/`analytic_schema_version`. Validar as duas referências e o sucesso do Job antes da carga; falha capturada remove manifestos da tentativa atual.


## Diagnóstico preço-volume no notebook — preparação de 30/10/2026

`preparar_base_preco_volume` associa `consumo_mensal_uc` às dimensões UC/mês da mesma execução fixada da Silver. Rejeita chave duplicada ou vínculo ausente antes da junção. `decompor_preco_volume` recebe essa base e a cobertura do mesmo lote, com duas janelas explícitas ordenadas e sem sobreposição. Exige `run_id_silver_esperado` e `lote_bronze_silver_esperado` e recusa cobertura com identidade ausente ou divergente. Essas expectativas vêm do snapshot fixado no chamador do notebook; a rotina não autentica DataFrames arbitrários nem substitui os controles de `read_silver`.

A base comum é formada pelas mesmas UCs no recorte. Os meses são pareados pela posição na janela (com janelas de 12 meses começando no mesmo mês, o mesmo mês do ano); um par vale quando há fatura e leituras integralmente válidas nos dois meses. A UC entra na base comum com ao menos seis pares válidos e consumo pareado positivo nas duas janelas. Para cada UC calcula, sobre os meses pareados, P=R/Q, efeito volume P0ΔQ, preço observado Q0ΔP e interação ΔPΔQ; só depois soma os efeitos por recorte. Entradas/saídas de faturamento no recorte ficam separadas, assim como variações sem leitura e demais parcelas fora da base pareada, inclusive os meses sem par válido de uma UC comum. A decomposição considera os registros aceitos pela Silver; os rejeitados por qualidade ficam registrados à parte na declaração de cobertura. A identidade desses sete componentes deve reconciliar a variação total, com tolerância max(0,000001 real, |ΔR total| × 10⁻⁹). Não arredonda antes da reconciliação.

**Por que seis pares.** O mínimo é metade da janela de 12 meses e o mesmo piso proposto por Dados para a pergunta de GD com queda de consumo (ao menos seis meses com leitura por janela). A versão anterior exigia os 24 meses válidos e deixava quase todas as UCs fora da base comum: cada mês inválido eliminava a UC inteira, o que não representa a população. Seis é uma escolha de Dados, não um valor otimizado estatisticamente. Fica no parâmetro `MIN_PARES_PRECO_VOLUME` e deve ser revisto se a sensibilidade no lote real mostrar que a participação da base comum muda muito entre pisos próximos. A receita e o consumo de cada UC comum usam exatamente os mesmos pares de meses, e os demais meses permanecem registrados em sem leitura e em outros fora da base, mantendo a reconciliação com a variação total.

Requer cobertura global FECHADO de consumo/faturamento em todos os meses e nenhuma observação sem competência. Sem isso, retorna `COBERTURA_NAO_CERTIFICADA` e valores derivados nulos. Sem UC elegível, retorna `SEM_BASE_COMUM`, efeitos de preço/volume nulos e contribuições de composição identificadas quando a cobertura é certificada. Valores não finitos, presença financeira inconsistente ou falha de reconciliação interrompem o cálculo. Os contadores de base comum, entradas/saídas e UCs observadas acompanham os resultados. São contagens por recorte: uma UC com mudança de dimensão pode aparecer em mais de um recorte, portanto não somar esses contadores para inferir UCs únicas globais.

As dimensões cadastrais são atuais; a rotina não cria histórico de vigência. Entradas/saídas no recorte não comprovam ligação/desligamento, e preço observado pode refletir alterações de componentes da fatura ou composição interna da UC. Não é tarifa homologada, kWh faturado, receita recebida ou comprovação causal.

O resultado é materializado e exportado quando os quatro parâmetros `PRECO_VOLUME_INICIO_P0`, `PRECO_VOLUME_FIM_P0`, `PRECO_VOLUME_INICIO_P1`, `PRECO_VOLUME_FIM_P1` estão preenchidos. Sem parâmetros publica tabela vazia tipada, identificada como `NAO_CONFIGURADA` no controle/manifesto; preenchimento parcial falha. Essa 15ª projeção participa da promoção e exportação. Aprovação do método e integração dos consumidores permanecem pendentes.

### Confirmações da origem necessárias ao fechamento

| Medida/regra | Evidência existente | Confirmação necessária | Tratamento atual |
| --- | --- | --- | --- |
| Energia faturada | Dados confirmou no [PR #73](https://github.com/GuilhermeRangel1/git-or-treat/pull/73#issuecomment-6508822736) que o consumo não é energia faturada. | Disponibilidade de kWh faturado por fatura ou regra formal de vínculo/ equivalência com a medição. | Não usar consumo medido ou valor monetário como energia faturada. |
| Valor recebido | [Issue #49](https://github.com/GuilhermeRangel1/git-or-treat/issues/49#issuecomment-6383232977) exige regra validada; status e data não bastam. | Valor de pagamentos por fatura, ou confirmação do significado de quitação integral, parciais, estornos e ajustes. | Não derivar receita recebida de `valor_total`. |
| Sentinela e saldo aberto | D15/D55 e [issue #48](https://github.com/GuilhermeRangel1/git-or-treat/issues/48#issuecomment-6383184517) mantêm a incerteza. | Significado dos valores sentinela por status e condições em que a ausência de pagamento permite saldo integral. | Manter saldo nulo nos casos inconclusivos; não interpretar sentinela como quitação. |
| Fechamento mensal | Ausência de lacunas é proposta no [PR #71](https://github.com/GuilhermeRangel1/git-or-treat/pull/71#issuecomment-6509043466); isso não certifica completude da origem. | Declarações por domínio/período/recorte vinculadas ao run/lote e evidência de origem. | Cobertura não certificada até receber declaração válida. |
| Energia recuperável | [Issue #47](https://github.com/GuilhermeRangel1/git-or-treat/issues/47#issuecomment-6383151816) exige método, horizonte, intervalo e incerteza. | Definir a medida-alvo e validar metodologia; entender o período/método de `kwh_recuperado` histórico; obter decisão explícita se média histórica for aceita como alternativa ao cálculo por UC. | Estudo candidato produz referências médias históricas com validação temporal; campos por UC permanecem nulos até aceite de escopo. Sem homologação presumida. |

A conferência das discussões em 30/10/2026 não localizou aprovação adicional dessas regras. A recomendação de seis meses do PR #71 é específica da pergunta de GD nas janelas fixas; não autoriza fechamento mensal ou mudança de regra geral. Essas confirmações não foram presumidas e precisam ser registradas antes de alterar a semântica dos indicadores.


### Contrato físico de `decomposicao_receita`

Chave: `municipio`, `bairro`, `classe_consumo`, `inicio_p0`, `fim_p0`, `inicio_p1`, `fim_p1`. Na configuração ativa, a chave é não nula e única; a tabela não contém `id_uc` nem dados pessoais. Sem configuração a tabela existe com esse schema e zero linhas, para limpar a análise anterior sob a mesma política de publicação.

| Campos | Tipo Spark | Definição |
| --- | --- | --- |
| `municipio`, `bairro`, `classe_consumo` | string | Recorte da análise; dimensões do cadastro atual. |
| `inicio_p0`, `fim_p0`, `inicio_p1`, `fim_p1` | string | Limites inclusivos YYYY-MM, com janelas ordenadas e sem sobreposição. |
| `qtd_ucs_base_comum`, `qtd_ucs_entrantes`, `qtd_ucs_saintes`, `qtd_ucs_observadas` | bigint | Contagens não negativas por recorte; não são somáveis para inferir UCs globais entre recortes. |
| `faturamento_p0_reais`, `faturamento_p1_reais` | double / R$ | Faturamento nos períodos sob cobertura certificada, sem arredondamento intermediário. |
| `efeito_volume_reais`, `efeito_preco_observado_reais`, `efeito_interacao_reais` | double / R$ | Soma dos efeitos calculados por UC comum; nulos sem base comum ou certificação. |
| `variacao_entradas_reais`, `variacao_saidas_reais` | double / R$ | Contribuições de entrada/saída de faturamento no recorte, não prova de ativação/desativação. |
| `variacao_sem_leitura_fora_base_reais`, `variacao_outros_fora_base_reais` | double / R$ | Contribuições restantes, sem dupla contagem das entradas/saídas. |
| `variacao_faturamento_total_reais`, `residuo_reconciliacao_reais` | double / R$ | Diferença de faturamento e resíduo da soma dos sete componentes; tolerância numérica documentada acima. |
| `estado_decomposicao` | string | `CALCULADA_BASE_COMUM`, `SEM_BASE_COMUM` ou `COBERTURA_NAO_CERTIFICADA`. Sem certificação todas as medidas double são nulas. |
| `metodo` | string | `PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3`; cálculo candidato, sem homologação tarifária. |
| `run_id_silver`, `lote_bronze_silver` | string | Identidades fixadas da origem, conferidas na exportação. |
| `data_processamento_gold` | timestamp | Referência dos dados da análise, igual a `preco_volume_referencia`; não é o horário de conclusão do Job. |

O controle Gold acrescenta `preco_volume_configuracao_json`, `preco_volume_referencia` e `limitacoes_medidas_json` (strings não nulas). O manifesto leva os objetos validados `preco_volume_configuracao`/`limitacoes_medidas` e a referência UTC. O estado da configuração, os estados das linhas e a contagem devem ser interpretados juntos. Nenhum deles certifica valor pago, energia faturada ou estimativa de recuperação.

## Regras operacionais e estudo de recuperação — 30/10/2026

### Fatura declarada em aberto

`valor_fatura_declarada_em_aberto_reais` (`decimal(20,2)`, R$, grão fatura) conserva o valor nominal quando `status` normalizado é `EM ABERTO` e o valor é utilizável. Não é recebimento nem saldo contábil. Mesmo com data sentinela/conflitante, o valor da fatura declarada fica consultável, acompanhado dos sinais de qualidade. O campo de saldo indicativo anterior permanece nulo nos casos inconclusivos. Nenhuma regra inventa pagamentos parciais, estornos ou quitação comprovada.

### Cobertura e bairro

A cobertura passa a distinguir `natureza_certificacao=EXTRACAO`, `FECHAMENTO_CONTABIL` ou `NAO_CERTIFICADA`; `reconciliacao_extracao_json` registra o inventário e contagens por intervalo. Regras e limites estão no contrato de cobertura. Um hash declarado não verifica o arquivo por si só. A decomposição passa a ter grão município/bairro/classe/quatro limites de janela; `bairro` vem do cadastro atual, sem reconstruir mudança histórica de endereço. Efeitos são de preço observado e consumo medido, nunca de tarifa homologada ou kWh faturado.

### Média histórica de recuperação por inspeção

`estudar_recuperacao` usa somente `id_inspecao`, `id_uc`, `data`, `resultado` e `kwh_recuperado` da Silver fixada. Exclui identificação/data inválida, futuro, resultado desconhecido, alvo ausente/não finito/negativo e `SEM IRREGULARIDADE` com valor diferente de zero. Não imputa zero em alvo ausente. Uma inspeção só conhece irregularidades elegíveis da mesma UC em dias anteriores; inspeções no mesmo dia não conhecem os resultados umas das outras.

O método candidato `MEDIA_GLOBAL_COM_GRUPOS_OPCIONAIS_V2` calcula primeiro uma média global e testa, separadamente, médias para UCs com e sem irregularidade confirmada anterior à data da inspeção. Só entram inspeções concluídas com `IRREGULARIDADE CONFIRMADA` ou `SEM IRREGULARIDADE`; o valor registrado de recuperação precisa ser finito e não negativo, e `SEM IRREGULARIDADE` só é compatível com zero. Alvo ausente ou conflitante é contado como exclusão, nunca convertido em zero. A atribuição do grupo considera apenas inspeções elegíveis anteriores; registros do mesmo dia não revelam o resultado uns dos outros.

As datas inteiras são divididas cronologicamente em treino (60%), calibração (20%) e teste (20%), sem separar um mesmo dia. Os critérios atualmente codificados são candidatos, não limiares homologados: pelo menos 100 observações no total, 20 em cada partição, 20 por grupo em cada partição, cobertura de pelo menos 80%, MAE de teste não maior que a média prevista e viés absoluto de até 25% da média. A média global pode ser liberada se passar esses critérios. Uma média por grupo só substitui a global para aquele grupo quando também reduz em pelo menos 5% o MAE na calibração, comparado à média global treinada; se um grupo falhar, isso não bloqueia uma média global válida nem o outro grupo. A seleção do grupo usa calibração; todos os critérios de erro e cobertura são conferidos no teste temporal reservado, sem reajustar o modelo no teste.

O intervalo é a média do treino ± o quantil conformal nominal de 90% dos erros absolutos da calibração, com limite inferior truncado em zero. A cobertura observada no teste é apenas retrospectiva: não garante cobertura futura, independência entre inspeções da mesma UC ou validade sob mudança de população. O histórico contém apenas UCs inspecionadas e pode ter viés de seleção. A referência global pode aparecer como contexto em toda a fila; referências por grupo exigem histórico elegível da UC. Essa apresentação não calcula previsões individuais para unidades nunca inspecionadas. Os cortes, mínimos e limites de erro precisam de revisão com Dados/Produto e validação no lote real; o código não transforma esses valores provisórios em aprovação de negócio.

A fila publica a referência histórica em cinco campos próprios:

| Campo | Tipo | Significado |
| --- | --- | --- |
| `media_historica_recuperacao_kwh_por_inspecao` | double / kWh por inspeção | Média do treino da referência aprovada na validação temporal. |
| `intervalo_historico_recuperacao_inferior_kwh` | double / kWh por inspeção | Limite inferior do intervalo calibrado para um resultado de inspeção. |
| `intervalo_historico_recuperacao_superior_kwh` | double / kWh por inspeção | Limite superior do mesmo intervalo. |
| `referencia_media_historica_recuperacao` | string nullable | `global`, `0` (sem irregularidade elegível anterior) ou `1` (com irregularidade elegível anterior); nulo sem referência. |
| `estado_media_historica_recuperacao` | string não nula | `DISPONIVEL_REFERENCIA_HISTORICA` ou `SEM_REFERENCIA_VALIDADA`. |

A referência global, quando passa os critérios, é repetida em toda a fila como contexto histórico. Uma média por grupo substitui essa referência apenas nas UCs com histórico elegível correspondente, com identificações válidas e dados até a data de referência; ausência de inspeção não é imputada como grupo `0`. Sem referência global válida, só os grupos validados recebem valores. Valores ausentes permanecem nulos e zeros observados continuam distintos de ausência. Consumidores devem mostrar “Média histórica de kWh recuperados por inspeção” e a referência usada. O intervalo descreve dispersão de resultados individuais de inspeções; não é intervalo de confiança da média, nem garantia de recuperação para uma UC. Não somar essas médias/limites entre UCs: são referências compartilhadas.

Os campos `energia_estimada_recuperavel_kwh`, `intervalo_recuperacao_inferior_kwh` e `intervalo_recuperacao_superior_kwh` permanecem nulos. Quando há referência histórica disponível, `estado_estimativa_recuperacao=ESTIMATIVA_UC_INDISPONIVEL`; os estados de insuficiência/reprovação continuam explícitos quando o estudo não passa. A média histórica autorizada nesta implementação não constitui aceite do WEB-04 como estimativa individual.

`validacao_recuperacao_json` registra método, alvo, referência, cortes, contagens, exclusões, avaliações e `parametros_candidatos`, com `interpretacao=MEDIA_HISTORICA_POR_INSPECAO` e `aceite_web04=PENDENTE`. `publicacao_media_historica` reconcilia as contagens com/sem referência publicada; `aplicacao_fila.com_estimativa` permanece zero. O relatório se repete por UC: não somar suas contagens. Gold e exportador verificam a coincidência dos campos históricos com a referência identificada, a nulabilidade, finitude, estado e contagens, além de impedir preenchimento dos campos individuais.

A prioridade existente é preservada. Os limites estatísticos são provisórios e exigem revisão com Dados/Produto e execução no lote real. A issue #47 ainda exige decisão explícita de escopo/aceite caso a referência histórica seja adotada como alternativa ao requisito de estimativa por UC; o código não conclui WEB-04.

O manifesto registra a limitação global de recuperação como `ESTIMATIVA_HISTORICA_CONDICIONAL`; os estados e o relatório por UC determinam se há valor publicável. Essa classificação não transforma uma validação sintética em aceite do método no lote real.
