# Dicionário de dados — camada Gold

**Escopo:** contrato conceitual e regras implementadas nas sete tabelas analíticas Gold, nos quatro históricos por UC e na tabela de controle `controle_gold`. O documento descreve código e evidências disponíveis; não substitui a validação física do Delta, aceite do portal/IA ou homologação regulatória.

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
| `consumo_mensal_uc` | Uma UC e competência com fatura e leitura correspondentes | `id_uc`, `competencia` | Faturas e leituras da Silver |
| `faturas_uc` | Uma fatura emitida vinculada a uma Unidade Consumidora | `id_fatura` | Faturas da Silver (`silver_publicada.faturas`) |
| `medidor_uc` | Um medidor de energia e seu histórico de vínculo por UC | `id_medidor` | Medidores da Silver (`silver_publicada.medidores`) |
| `atendimentos_uc` | Um protocolo de atendimento detalhado por Unidade Consumidora | `protocolo` | Atendimentos da Silver (`silver_publicada.atendimentos`) |
| `ocorrencias_uc` | Um registro de ocorrência da rede elétrica vinculado à Unidade Consumidora | `id_ocorrencia`, `id_uc` | Ocorrências da Silver (`silver_publicada.ocorrencias_rede`) |
| `controle_gold` | Registro de uma execução Gold concluída pelo notebook | `run_id_gold` identifica a execução; não há teste de unicidade explícito para essa tabela | Metadados da execução e dos controles Silver |

As onze primeiras tabelas de negócio compõem o contrato candidato de exportação `gold-csv-v2`, ainda dependente de migração/carga v2 no Backend e validação do Job real. `controle_gold` é uma tabela operacional de linhagem e não está na lista de exportação do notebook.

## Regras compartilhadas e limites

- **Fonte e lote:** a Gold lê as vistas `silver_publicada.*` e consulta `silver.controle_publicacao` e `silver.controle_silver`. O notebook aceita `AMBIENTE` igual a `prod`, `dev` ou `test`; a execução em `prod` exige controles físicos e Silver com status `CONCLUIDO`. Os modos `dev`/`test` têm caminho de linhagem sintética quando os controles não estão disponíveis.
- **Cadastro:** os fluxos mostrados descartam UCs sem `id_uc` e identificadores iniciados por `TESTE`. A fila constrói sua base com `dropDuplicates(id_uc)`; o diagnóstico e a rede também fazem verificações de unicidade em suas bases. O cadastro é uma fotografia atual: classe, município, bairro, alimentador, status e GD não comprovam sua vigência histórica.
- **Receita e consumo:** faturas e leituras são agregadas separadamente por UC e competência e depois unidas por `inner join` para a construção de `diagnostico_receita`, `consumo_receita_bairro` e `consumo_mensal_uc` (usando somente pares UC/mês presentes nas duas fontes). **As projeções `faturas_uc`, `medidor_uc`, `atendimentos_uc` e `ocorrencias_uc` são exceções a esse acoplamento:** a `faturas_uc` preserva o histórico de faturas no grão individual de `id_fatura` independentemente de leitura na competência; a `medidor_uc` registra o parque de medição e seus vínculos de instalação/retirada no grão individual de `id_medidor`; a `atendimentos_uc` preserva o histórico completo de chamados no grão de `protocolo`; e a `ocorrencias_uc` preserva o histórico isolado de eventos da rede no grão de `id_ocorrencia` e `id_uc`, mantendo a fidelidade observada na origem sem cruzamentos forçados ou perda de registros.
- **GD:** `Sim` significa que há pelo menos uma linha da UC em `geracao_distribuida`; a regra atual não considera vigência nem comprova geração, injeção ou compensação em uma competência. `Não` é atribuído quando a junção não encontra essa linha.
- **Privacidade:** a projeção final de `fila_inspecao` e `visao_360_uc` não inclui CPF/CNPJ, nome, endereço, CEP, coordenadas ou metadados internos da Silver. `id_uc` continua sendo identificador de unidade: a ausência desses campos não torna o conjunto automaticamente anônimo.
- **Publicação:** validar no schema de preparo antes da promoção; produção, desenvolvimento e teste têm destinos separados. Recuperar falhas capturadas e impedir execuções concorrentes; não há transação multi-tabela.
- **Ausência e zero:** verifique a regra específica de cada tabela. Algumas contagens são preenchidas com zero quando uma junção não encontra registro; isso não demonstra, por si só, cobertura completa da fonte. Uma linha ausente em `indicadores_dec_fec` ou `ocorrencias_uc` não prova ausência de interrupções.

## 1. `diagnostico_receita`

**Finalidade:** explorar receita faturada e consumo medido por recorte comercial.
**Grão e chave de verificação:** (`competencia`, `municipio`, `classe_consumo`, `subgrupo_tarifario`, `bandeira_tarifaria`, `possui_gd`). O teste geral exige chave não nula e única; se uma dimensão estiver nula, essa validação falha, mesmo que o agrupamento Spark aceite nulos.
**Fontes:** `silver_publicada.faturas`, `leituras`, `unidades_consumidoras` e `geracao_distribuida`.

| Coluna | Tipo conceitual / unidade | Definição |
| --- | --- | --- |
| `competencia` | texto `YYYY-MM` | Mês de referência comum às faturas e leituras. |
| `municipio` | texto | Município do cadastro atual da UC. |
| `classe_consumo` | texto | `classe` do cadastro atual. |
| `subgrupo_tarifario` | texto | Subgrupo do cadastro atual. |
| `bandeira_tarifaria` | texto | Primeira bandeira não nula da UC/mês; se houver mais de uma bandeira distinta para a mesma UC/mês, o notebook falha. Se a coluna de origem estiver ausente, é criada nula. |
| `possui_gd` | texto: `Sim`/`Não` | Presença de linha de GD para a UC, sem vigência temporal. |
| `qtd_ucs_distintas_faturadas_no_mes` | inteiro / UCs | Contagem distinta de UCs no grupo após o `inner join` de faturas e leituras. |
| `soma_faturamentos_mensais` | inteiro / faturas | Soma das contagens de faturas por UC/mês no grupo; não é necessariamente igual à contagem de UCs. |
| `consumo_total_kwh` | número / kWh | Soma do consumo das leituras agregadas das UCs/mês elegíveis. |
| `receita_total_reais` | decimal / R$ | Soma de `valor_total` das faturas das UCs/mês elegíveis; não é receita paga. |
| `ticket_medio_reais_por_uc` | número / R$/UC | Média da receita agregada por UC/mês no grupo. |
| `consumo_medio_kwh_por_uc` | número / kWh/UC | Média do consumo agregado por UC/mês no grupo. |
| `tarifa_media_efetiva` | número / R$/kWh | Receita total dividida pelo consumo total, se o consumo for não nulo e diferente de zero; caso contrário, nulo. É preço observado, não tarifa homologada. |

**Exemplos de categorias:** `classe_consumo` usa grafias como `COMERCIAL`, `INDUSTRIAL`, `PODER PUBLICO`, `RESIDENCIAL` e `RURAL`; `subgrupo_tarifario`, `A4`, `B1`, `B2` e `B3`; e `bandeira_tarifaria`, `AMARELA`, `VERDE`, `VERMELHA P1` e `VERMELHA P2`. São exemplos de valores da origem, não um domínio fechado imposto pela Gold.

**Cobertura:** o cadastro entra por `left join`; faturas com leitura mas sem cadastro permanecem na base intermediária, sujeitas às validações das dimensões. A Gold não estima valores para pares sem leitura ou sem fatura.

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
| `duracao_total_interrupcoes_horas` | número / horas | Soma de `duracao_min / 60` para as ocorrências incluídas. |
| `DEC` | número / horas por UC | `duracao_total_interrupcoes_horas / total_ucs_alimentador`. |
| `FEC` | número / interrupções por UC | `frequencia_total_interrupcoes / total_ucs_alimentador`. |

**Filtros e limites:** exige UC, ocorrência e data de abertura não nulas; verifica unicidade do par UC–ocorrência e rejeita duração negativa. A atribuição usa o cadastro atual e não prova vigência histórica. A tabela parte das ocorrências agregadas: não cria automaticamente linhas para alimentadores/mês sem ocorrência. O teste geral rejeita denominador inválido e DEC/FEC nulos ou negativos. Estes indicadores são simplificados e não constituem apuração ou conformidade regulatória oficial.

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
| `data_ligacao` | data | Data de ligação cadastrada. |
| `status` | texto | Status cadastral da UC. |
| `possui_geracao_solar` | texto: `Sim`/`Não` | Presença de linha de GD; o nome da coluna não prova geração ou compensação mensal. |
| `total_inspecoes_realizadas` | inteiro / inspeções | Contagem distinta de `id_inspecao` com UC e ID não nulos; zero quando não há agregado associado. |
| `total_inspecoes_irregulares` | inteiro / inspeções | Contagem distinta cujo `resultado` é exatamente `IRREGULARIDADE CONFIRMADA`; outros valores não entram nessa contagem. |
| `media_consumo_historico` | número / kWh por leitura | Média de `consumo_kwh` das leituras não nulas da UC; não é necessariamente média mensal. Nula se não houver leitura válida associada. |
| `prioridade_inspecao` | texto | Categoria produzida pela hierarquia abaixo. |

**Prioridade, na ordem aplicada:**

1. `ALTA - HISTORICO IRREGULAR`: há inspeção com resultado exatamente `IRREGULARIDADE CONFIRMADA`.
2. `REVISAR - SEM HISTORICO DE CONSUMO`: não há média de consumo disponível.
3. `ALTA - CONSUMO ZERO`: média de consumo igual a zero e `possui_geracao_solar = Não`.
4. `MEDIA - NUNCA INSPECIONADO`: não se enquadrou acima e não há inspeções realizadas.
5. `BAIXA`: demais casos.

Prioridade indica uma regra de triagem; não é diagnóstico de fraude. O mapeamento de outros resultados de inspeção deve ser confirmado com a origem antes de ampliá-lo.

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
| `data_ligacao` | data | Data de ligação cadastrada. |
| `status` | texto | Status cadastral da UC. |
| `possui_gd` | texto: `Sim`/`Não` | Presença de linha de GD, sem vigência temporal. |
| `total_chamados_callcenter` | inteiro / protocolos | Contagem distinta de protocolos associados; zero quando não há agregado associado. |
| `media_satisfacao_atendimento` | número / nota | Média de `nota_satisfacao` dos atendimentos válidos; pode ser nula. |
| `total_interrupcoes_sofridas` | inteiro / ocorrências | Contagem distinta de IDs de ocorrência por UC; zero quando não há agregado associado. |
| `duracao_total_interrupcoes_horas` | número / horas | Soma das durações das ocorrências associadas divididas por 60; preenchida com zero quando o agregado é nulo. |
| `media_consumo_historico` | número / kWh por leitura | Média das leituras não nulas associadas à UC; pode ser nula e não equivale necessariamente a média mensal. |

**Limite:** esta tabela não contém nome, endereço, histórico de faturas, medidores ou registros individuais de atendimento/interrupção. Esses dados não podem ser deduzidos da presença desta tabela; a jornada do portal deve usar fontes adequadas para cada detalhe.

## 5. `consumo_receita_bairro`

**Finalidade:** analisar receita e consumo por bairro, município, classe e competência.
**Grão e chave:** (`competencia`, `municipio`, `bairro`, `classe_consumo`), validados como não nulos e únicos.
**Fontes:** faturas e leituras pré-agregadas por UC/mês, com cadastro associado por `left join`.

| Coluna | Tipo conceitual / unidade | Definição |
| --- | --- | --- |
| `competencia` | texto `YYYY-MM` | Mês de referência da fatura e leitura agregadas. |
| `municipio` | texto | Município do cadastro; ausência recebe `Não informado`. |
| `bairro` | texto | Bairro do cadastro; ausência recebe `Não informado`. |
| `classe_consumo` | texto | Classe do cadastro; ausência recebe `Não informado`. |
| `consumo_total_kwh` | número / kWh | Soma do consumo das UCs/mês elegíveis no recorte. |
| `receita_total_reais` | decimal / R$ | Soma do faturamento das UCs/mês elegíveis no recorte. |
| `qtd_ucs_distintas_faturadas_no_mes` | inteiro / UCs | Contagem distinta das UCs elegíveis no recorte. |

**Limite:** os nomes `Não informado` representam ausência de dimensão cadastral; não são um município, bairro ou classe reais. A fonte é a interseção entre faturas e leituras, e os recortes devem ser reconciliados com `diagnostico_receita` no mesmo lote.

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

**Interpretação:** `false` na flag também pode representar comparação indisponível; consulte as médias e contagens de meses antes de concluir que não houve queda. A variação usa leituras, enquanto as tabelas financeiras usam a interseção de leituras e faturas.

## 7. `consumo_mensal_uc`

**Finalidade:** série por unidade e competência para consumo e receita.
**Grão e chave:** (`id_uc`, `competencia`), com não nulidade e unicidade verificadas.
**Fontes:** faturas e leituras agregadas por UC/mês, unidas por `inner join`.

| Coluna | Tipo conceitual / unidade | Definição |
| --- | --- | --- |
| `id_uc` | texto | Identificador da unidade. |
| `competencia` | texto `YYYY-MM` | Mês de referência comum às duas fontes. |
| `consumo_kwh` | número / kWh | Soma do consumo das leituras da UC/mês, arredondada a duas casas. |
| `receita_reais` | decimal / R$ | Soma de `valor_total` das faturas da UC/mês, arredondada a duas casas. |

**Limite:** não há linha para UC/mês que exista somente em faturas ou somente em leituras. A tabela informa valor faturado, não valor pago, e não contém as dimensões territoriais; qualquer junção adicional precisa preservar o grão.

## 8. `faturas_uc`

**Grão e população:** Uma fatura por `id_fatura`; todas as faturas aceitas na Silver, independentemente de leitura pareada.

| Coluna | Tipo / unidade | Definição |
| --- | --- | --- |
| `id_fatura`, `id_uc` | string | Fatura e UC associada; chaves obrigatórias. |
| `mes_referencia` | string YYYY-MM | Competência de faturamento. |
| `data_emissao`, `data_vencimento`, `data_pagamento` | date | Datas Silver saneadas por flags; vencimento futuro é válido. Pagamento inconclusivo fica nulo. |
| `valor_energia`, `tributos`, `valor_total` | decimal(20,2) / R$ | Valores cobrados; não demonstram valor efetivamente pago. |
| `bandeira_tarifaria`, `status` | string | Categorias observadas; status não comprova quitação. |
| `flag_paga`, `flag_tem_pagamento` | boolean | Status/data declarados na fonte; não constituem confirmação financeira. |
| `flag_valor_inconsistente`, `flag_data_pagamento_inconclusiva`, `flag_paga_sem_data_valida`, `flag_pagamento_antes_emissao`, `flag_pagamento_sentinela`, `flag_pagamento_futuro` | boolean | Sinais Silver preservados; impedem interpretar ausência/inconsistência como pagamento comprovado. |
| `data_processamento_gold` | timestamp UTC | Referência temporal única da execução Gold. |

Fonte: `silver_publicada.faturas`. Emissão sentinela/futura e pagamento sinalizado ficam nulos; vencimento só é anulado por flag de sentinela. Não calcula pagamento parcial, valor em aberto ou energia faturada. Não é necessário haver leitura na competência.

## 9. `medidor_uc`

**Grão e população:** Um registro por `id_medidor`, vinculado a `id_uc`; exclui UC nula ou com prefixo TESTE.

| Coluna | Tipo / unidade | Definição |
| --- | --- | --- |
| `id_medidor`, `id_uc` | string | Chaves obrigatórias; medidor único na fonte elegível. |
| `modelo`, `tipo`, `status` | string | Atributos observados do equipamento. |
| `data_instalacao`, `data_retirada` | date | Datas observadas, nulas quando flags Silver indicam sentinela ou futuro; retirada anterior à instalação reprova o lote. |
| `flag_instalacao_sentinela`, `flag_instalacao_futura`, `flag_retirada_sentinela`, `flag_retirada_futura` | boolean | Preservam o motivo de saneamento da data. |
| `ingestao_data` | timestamp UTC | Referência temporal única Gold. |

Fonte: `silver_publicada.medidores`. Não aplica corte arbitrário por ano, não fabrica transferências e não identifica medidor ativo apenas por retirada nula. Seleção do instalado na data de referência e sobreposições continuam dependentes de regra aprovada. Manutenção não é publicada nesta projeção.

## 10. `atendimentos_uc`

**Grão e população:** Um protocolo por `protocolo`; exclui UC nula ou com prefixo TESTE.

| Coluna | Tipo / unidade | Definição |
| --- | --- | --- |
| `protocolo`, `id_uc` | string | Protocolo único e UC obrigatória. |
| `canal`, `assunto`, `subassunto` | string | Classificações observadas. |
| `data_abertura`, `data_fechamento` | timestamp UTC | Datas nulas quando a flag Silver correspondente indica futuro. |
| `nota_satisfacao` | double / pontos | Nota inválida ou negativa fica nula; ausência não é zero. |
| `qtd_tratativas` | inteiro | Contagem da fonte, não quantidade de chamados. |
| `primeira_acao`, `ultima_acao` | string | Resumo da primeira/última ação; não substitui todas as tratativas. |
| `_abertura_futura`, `_fechamento_futura`, `_nota_negativa`, `_nota_invalida` | boolean | Flags de qualidade Silver mantidas com seus nomes físicos; metadados técnicos para o Backend, não autorização de exposição ao modelo. |
| `ingestao_data` | timestamp UTC | Referência temporal única Gold. |

Fonte: `silver_publicada.atendimentos`. As interações de `atendimentos_historico` não são exportadas por esta tabela. Nenhum join com faturas ou ocorrências altera a contagem de protocolos.

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

Fonte: `silver_publicada.ocorrencias_rede`. Exclui evento sem UC vinculável, ID nulo ou `_id_uc_ausente` diferente de falso; reconcilia a população elegível. Linha ausente não comprova zero interrupções. Não cruza fatos financeiros e não demonstra continuidade regulatória.

## 12. `controle_gold` — linhagem da execução

O notebook gera um registro de controle ao final das verificações e usa `append` quando a tabela já existe. Não é uma das 11 tabelas do CSV de exportação. Uma falha anterior a essa etapa não garante um registro de falha nesta tabela.

| Coluna | Tipo declarado | Definição |
| --- | --- | --- |
| `run_id_gold` | `string` | ID da execução Gold, com data/hora UTC e sufixo aleatório. |
| `run_id_silver` | `string` | Identificador da execução Silver usada. |
| `lote_bronze_silver` | `string` | Identificador do lote Bronze informado pela linhagem Silver. |
| `status_silver` | `string` | Estado Silver registrado para a execução. |
| `silver_lineage_status` | `string` | Identifica se a linhagem veio de controle físico ou do caminho sintético. |
| `status_gold` | `string` | `CONCLUIDO` quando o registro final é criado. |
| `tabelas_geradas` | `string` | Lista textual das onze tabelas verificadas. |
| `ambiente` | `string` | `prod`, `dev` ou `test`. |
| `processado_em` | `timestamp` | Instante UTC usado para o registro. |

Esses campos têm nulabilidade física `False`. Gold valida onze candidatos em schema exclusivo, promove para `gold` em produção (`gold_dev`/`gold_test` nos demais ambientes) e registra o controle dentro do bloco de recuperação de falhas capturadas. Não há transação única entre tabelas: o Job deve executar sem concorrência e os consumidores devem aguardar sucesso. Falha abrupta ou falha no RESTORE exige recuperação operacional antes do consumo.

## Exportação e verificações

O exportador exige o controle produtivo mais recente, sem empate temporal, com linhagem física Silver concluída, identidade completa e conjunto exato das onze tabelas. O `run_id` opcional só confirma o controle; nunca o substitui. As versões Delta são fixadas e verificadas novamente antes de liberar o manifesto.

Cada tentativa grava em `/Volumes/workspace/gold/gold_export_volume/export_csv/<run_id_gold>/<export_id>/`, em onze subpastas, sem sobrescrever exportações anteriores. CSV: cabeçalho, separador `;`, UTF-8, aspas, datas ISO, timestamps UTC com microssegundos e offset, decimais com escala preservada; `\N` é nulo, distinto de string vazia (o marcador literal é reservado). Cada CSV é relido com o schema original e comparado como multiconjunto completo. O manifesto é criado somente após reconciliação e revalidação de controle/versões. Pasta sem manifesto é tentativa incompleta e não deve ser carregada.

O manifesto `gold-csv-v2` contém as onze tabelas, contagens, schemas físicos, versões Delta, execução Gold e origem Silver/Bronze. É um contrato candidato: o carregador atual `gold-csv-v1` rejeita este conjunto e não foi alterado; a migração/carga v2 e os consumidores ainda precisam ser integrados. Não adaptar o snapshot histórico v1 silenciosamente.

Os testes Gold conferem chaves, população elegível, finanças e todos os grupos DEC/FEC, com tolerância explícita para somas em ponto flutuante. Datas e ausências seguem as regras acima; a existência do código não comprova execução sobre o lote real. O exportador requer Gold → exportação serializados, pois verificações de versão não substituem uma transação multi-tabela ou um bloqueio de execução.

### Rastreabilidade e reconciliação por execução

IDs de execução, contagens, distribuições e totais apurados pertencem ao manifesto e às evidências do lote no ambiente autorizado. Esses resultados não são constantes do modelo e não integram este dicionário.

Diferenças entre exportações devem ser investigadas para o mesmo lote e grão completo: `competencia`, `municipio`, `bairro` e `classe_consumo`. Comparar chaves exclusivas, repetidas ou ausentes; a quantidade de nomes distintos de bairro, isoladamente, não explica diferenças de linhas.

A reconciliação deve conferir receita e energia entre as tabelas pertinentes, no total e por competência, e registrar as exclusões dos vínculos com a Silver. Controles de estrutura não substituem essa conferência semântica.

## Conferência no Databricks antes de homologar

Para cada uma das onze tabelas e para `controle_gold`:

1. Consultar `DESCRIBE TABLE` ou `printSchema` e registrar tipos físicos, precisão decimal e nulabilidade.
2. Conferir as colunas publicadas com este dicionário e verificar chaves, nulos, contagens e relações entre tabelas para o mesmo lote.
3. Reconciliar receita e energia com as fontes Silver, incluindo os pares que ficaram fora do `inner join`, e registrar a evidência para o lote efetivo.
4. Conferir DEC/FEC, janelas e população em amostras independentes; identificar competências sem linha, denominadores e limites do cadastro atual.
5. Comparar esquema, contagens e agregados de Gold, CSV e banco local; verificar os arquivos de cada diretório, o lote e as condições de reexecução.
6. Revisar permissões e uso de identificadores no portal/IA. Só alterar o estado de DE-08 após revisão humana e evidências correspondentes; este dicionário documenta o contrato, não conclui o requisito.
