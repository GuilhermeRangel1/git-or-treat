# Dicionário de Dados — Camada Gold

Este documento descreve a estrutura, esquemas de dados, e regras de negócio aplicadas às tabelas da **Camada Gold**.

---

## 1. Visão 360 da Unidade Consumidora (`visao_360_uc`)

**Objetivo:** Consolidar métricas operacionais, comerciais, de atendimento ao cliente e interrupções ao nível de Unidade Consumidora (UC), servindo como base analítica para o portal do atendente (WEB-03) e modelos de IA.  
**Granularidade:** Unidade Consumidora (`id_uc`).  
**Regras de Governança e Privacidade (LGPD):** 
* **PII Zero (Minimização Estrita):** Remoção completa de dados pessoais (`cpf_cnpj` e `nome_titular`) para anonimização total da camada analítica.
* **Privacidade Territorial:** Descarte de dados de endereço detalhado (`logradouro`, `cep`) e coordenadas geográficas (`latitude`, `longitude`).
* **Saneamento de Controle:** Exclusão de metadados técnicos de ETL (`_lote_id`, `_run_id`, `_geo_invalida`).

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `id_uc` | `string` | Não | Chave primária: Identificador técnico único da Unidade Consumidora. |
| `municipio` | `string` | Não | Município de localização da UC. |
| `bairro` | `string` | Não | Bairro de localização da UC. |
| `uf` | `string` | Sim | Unidade Federativa (ex: `PE`). |
| `classe` | `string` | Sim | Categoria de consumo da UC (ex: Residencial, Comercial, Industrial). |
| `subgrupo` | `string` | Sim | Subgrupo tarifário de enquadramento (ex: B1, B3). |
| `alimentador` | `string` | Não | Código/Identificador do alimentador elétrico ao qual a UC está conectada. |
| `data_ligacao` | `date` | Sim | Data de ligação inicial do fornecimento de energia na UC. |
| `status` | `string` | Sim | Status operacional da UC (ex: Ativa, Desligada). |
| `possui_gd` | `string` | Sim | Indicador de presença de Geração Distribuída (`Sim` / `Não`). |
| `total_chamados_callcenter` | `bigint` | Sim | Quantidade total de chamados de atendimento registrados pelo cliente no call center. |
| `media_satisfacao_atendimento` | `double` | Sim | Média das notas de satisfação atribuídas pelo cliente nos atendimentos. |
| `total_interrupcoes_sofridas` | `bigint` | Sim | Soma de ocorrências de falta de energia/interrupções que afetaram a UC. |
| `duracao_total_interrupcoes_horas` | `double` | Sim | Duração acumulada total das interrupções sofridas pela UC em horas. |
| `media_consumo_historico` | `double` | Sim | Média histórica do consumo de energia faturado em kWh. |

---

## 2. Diagnóstico de Receita e Variação Tarifária (`diagnostico_receita`)

**Objetivo:** Atender ao pedido da Diretoria Comercial explicando variações no volume faturado e o impacto na receita por município, classe de consumo, subgrupo e presença de geração distribuída (GD).  
**Granularidade:** Competência (Mensal), Município, Classe de Consumo, Subgrupo Tarifário, Bandeira Tarifária e Possui GD.  
**Origem dos Dados (Silver):** `silver.faturas`, `silver.leituras`, `silver.unidades_consumidoras` e `silver.geracao_distribuida`.  
**Regras de Negócio e Segurança:** 
* Filtro de registros sintéticos: Exclusão de faturamentos de teste (`id_uc NOT LIKE 'TESTE%'`).
* Eliminação de ambiguidade volumétrica: Distinção clara entre quantidade de UCs distintas e o acúmulo de faturas no mês.

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `competencia` | `string` | Sim | Ano e mês de referência do faturamento (formato `YYYY-MM`). |
| `municipio` | `string` | Sim | Nome do município correspondente. |
| `classe_consumo` | `string` | Sim | Categoria da unidade consumidora (ex: Residencial, Comercial, Industrial). |
| `subgrupo_tarifario` | `string` | Sim | Subgrupo tarifário de enquadramento (ex: B1, B3). |
| `bandeira_tarifaria` | `string` | Sim | Bandeira tarifária aplicada no período (ex: Verde, Amarela, Vermelha). |
| `possui_gd` | `string` | Sim | Indicador de presença de Geração Distribuída (GD Solar). |
| `qtd_ucs_distintas_faturadas_no_mes` | `bigint` | Sim | Contagem distinta de Unidades Consumidoras faturadas no período mensal. |
| `soma_faturamentos_mensais` | `bigint` | Sim | Total acumulado de faturas/faturamentos processados na competência. |
| `consumo_total_kwh` | `double` | Sim | Soma do consumo total de energia em kWh no mês. |
| `receita_total_reais` | `decimal(38,2)` | Sim | Valor total da receita faturada em reais (R$). |
| `ticket_medio_reais_por_uc` | `decimal(34,6)` | Sim | Valor médio faturado por UC (`receita_total_reais` / `qtd_ucs_distintas_faturadas_no_mes`). |
| `consumo_medio_kwh_por_uc` | `double` | Sim | Consumo médio em kWh por unidade consumidora. |
| `tarifa_media_efetiva` | `double` | Sim | Tarifa média efetiva praticada (`receita_total_reais` / `consumo_total_kwh`). |

---

## 3. Fila de Inspeção e Risco de Perdas Não Técnicas (`fila_inspecao`)

**Objetivo:** Consolidar indicadores de risco e anomalias de consumo por Unidade Consumidora (UC) para direcionamento e priorização das equipes de fiscalização de campo no combate a fraudes e furtos de energia (perdas não técnicas).  
**Granularidade:** Unidade Consumidora (`id_uc`).  
**Regras de Governança e Privacidade (LGPD):** 
* **Saneamento Cadastral:** Remoção na origem de UCs fictícias de teste (`id_uc` iniciando com `TESTE`) e documentos zerados/nulos.
* **PII Zero (Minimização Estrita):** Eliminação total dos dados pessoais (`cpf_cnpj` e `nome_titular`), além de endereços detalhados (`logradouro`, `cep`) e coordenadas geográficas, garantindo consumo analítico e de IA 100% anonimizado via chave técnica (`id_uc`).
* **Hierarquia de Priorização (`prioridade_inspecao`):**
  1. `ALTA - HISTORICO IRREGULAR`: `total_inspecoes_irregulares > 0`
  2. `REVISAR - SEM HISTORICO DE CONSUMO`: `media_consumo_historico IS NULL`
  3. `ALTA - CONSUMO ZERO`: `possui_geracao_solar = 'Não'` AND `media_consumo_historico = 0`
  4. `MEDIA - NUNCA INSPECIONADO`: `total_inspecoes_realizadas = 0`
  5. `BAIXA`: Demais cenários de operação regular.

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `id_uc` | `string` | Não | Chave primária: Identificador técnico único da Unidade Consumidora. |
| `municipio` | `string` | Não | Município de localização da UC. |
| `bairro` | `string` | Não | Bairro de localização da UC. |
| `uf` | `string` | Sim | Unidade Federativa (ex: `PE`). |
| `classe` | `string` | Sim | Categoria de consumo da UC (ex: Residencial, Comercial, Industrial). |
| `subgrupo` | `string` | Sim | Subgrupo tarifário de enquadramento (ex: B1, B3). |
| `alimentador` | `string` | Não | Código/Identificador do alimentador elétrico ao qual a UC está conectada. |
| `data_ligacao` | `date` | Sim | Data de ligação inicial do fornecimento de energia na UC. |
| `status` | `string` | Sim | Status operacional da UC (ex: Ativa, Desligada). |
| `possui_geracao_solar` | `string` | Sim | Indicador de presença de Geração Distribuída Solar (`Sim` / `Não`). |
| `total_inspecoes_realizadas` | `bigint` | Sim | Quantidade total de vistorias de campo executadas na UC. |
| `total_inspecoes_irregulares` | `bigint` | Sim | Quantidade de vistorias onde foram confirmadas fraudes ou irregularidades. |
| `media_consumo_historico` | `double` | Sim | Média histórica do consumo de energia faturado em kWh. |
| `prioridade_inspecao` | `string` | Não | Métrica de decisão: Classificação do nível de risco da UC (`ALTA - HISTORICO IRREGULAR`, `REVISAR - SEM HISTORICO DE CONSUMO`, `ALTA - CONSUMO ZERO`, `MEDIA - NUNCA INSPECIONADO`, `BAIXA`). |

---

## 4. Indicadores Operacionais e Regulação ANEEL (`indicadores_dec_fec`)

**Objetivo:** Calcular os indicadores regulatórios operacionais de Duração Equivalente de Interrupção por Unidade Consumidora (**DEC**) e Frequência Equivalente de Interrupção por Unidade Consumidora (**FEC**) segundo as normas do PRODIST Módulo 8 da ANEEL.  
**Granularidade:** Alimentador (`id_alimentador`), Município (`municipio`) e Competência (`competencia`).  
**Regras de Negócio e Tratamento de Dados:** 
* **Filtro de Segurança / Qualidade (N2):** Exclusão das UCs fictícias de teste (`id_uc` iniciando com `TESTE`), garantindo a base real de 45.000 UCs no denominador para evitar subestimação dos indicadores operacionais.
* **Fórmulas Oficiais:**
  * **DEC:** `DEC` = `duracao_total_interrupcoes_horas` / `total_ucs_alimentador`
  * **FEC:** `FEC` = `frequencia_total_interrupcoes` / `total_ucs_alimentador`

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `id_alimentador` | `string` | Sim | Identificador único do alimentador elétrico. |
| `municipio` | `string` | Sim | Nome do município atendido pelo alimentador. |
| `competencia` | `string` | Sim | Ano e mês de referência do indicador (formato `YYYY-MM`). |
| `total_ucs_alimentador` | `bigint` | Sim | Denominador: Quantidade total de UCs ativas vinculadas ao alimentador (sem UCs sintéticas de teste). |
| `ucs_interrompidas` | `bigint` | Sim | Quantidade de unidades consumidoras impactadas por interrupções no período. |
| `frequencia_total_interrupcoes` | `bigint` | Sim | Soma do número total de ocorrências de interrupção registradas no alimentador. |
| `duracao_total_interrupcoes_horas` | `double` | Sim | Soma total da duração das interrupções em horas no alimentador. |
| `DEC` | `double` | Sim | Indicador DEC (horas/UC): Duração equivalente de interrupção por unidade consumidora. |
| `FEC` | `double` | Sim | Indicador FEC (interrupções/UC): Frequência equivalente de interrupção por unidade consumidora. |

---

## 5. Consumo e Receita por Bairro e Mês (`consumo_receita_bairro`)

**Objetivo:** Permitir que agentes de IA e aplicações de backend respondam a consultas de desempenho territorial (ex: *"Qual bairro teve maior receita no mês?"*) de forma otimizada, eliminando a necessidade de varrer séries temporais individuais de UCs.  
**Granularidade:** Competência (`competencia`), Município (`municipio`), Bairro (`bairro`) e Classe de Consumo (`classe_consumo`).  
**Origem dos Dados (Silver):** Cruzamento da base de faturamento e leituras válidas com a base cadastral de UCs.  
**Auditoria e Conciliação Financeira:** Aprovada com 100% de conciliação (R$ 0,00 de divergência) contra a tabela `diagnostico_receita` no valor total de R$ 591.560.472,66.

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `competencia` | `string` | Sim | Mês e ano de referência do faturamento (formato `YYYY-MM`). |
| `municipio` | `string` | Sim | Nome do município associado à UC. |
| `bairro` | `string` | Sim | Nome do bairro associado à UC. |
| `classe_consumo` | `string` | Sim | Categoria da unidade consumidora (ex: Residencial, Comercial, Industrial). |
| `consumo_total_kwh` | `double` | Sim | Soma do consumo em kWh faturado na combinação de mês/bairro/classe. |
| `receita_total_reais` | `decimal(38,2)` | Sim | Soma da receita faturada em Reais (R$) na combinação de mês/bairro/classe. |
| `qtd_ucs_distintas_faturadas_no_mes` | `bigint` | Sim | Contagem distinta de Unidades Consumidoras únicas faturadas na combinação. |

---

## 6. Variação de Consumo por UC (`variacao_consumo_uc`)

**Objetivo:** Permitir que agentes de IA e modelos analíticos identifiquem variações temporais e anomalias de consumo individualizado (ex: *"Quais UCs com geração distribuída apresentaram queda de consumo superior a 30%?"*).  
**Granularidade:** Unidade Consumidora (`id_uc`).  
**Cobertura Base:** 45.000 Unidades Consumidoras (100% da rede ativa).  
**Janelas Temporais de Análise:**
* **Período Inicial (P1):** Média de consumo mensal de `2022-07` a `2023-06` (12 meses).
* **Período Final (P2):** Média de consumo mensal de `2025-07` a `2026-06` (12 meses).
* **Fórmulas e Regras de Negócio:**
  * **Variação Absoluta:** `variacao_kwh` = `consumo_medio_final` - `consumo_medio_inicial`
  * **Variação Percentual:** `variacao_pct` = ((`consumo_medio_final` - `consumo_medio_inicial`) / `consumo_medio_inicial`) * 100
* **Tratamento de Nulos:** Indicador `variacao_pct` mantido como `NULL` quando não há histórico de leitura em ambos os períodos (P1 e P2). Havendo ao menos 1 mês com medição em cada janela, o indicador é calculado sobre a média dos meses disponíveis.

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `id_uc` | `string` | Não | Chave primária: Identificador técnico único da Unidade Consumidora. |
| `municipio` | `string` | Sim | Município de localização da UC. |
| `bairro` | `string` | Sim | Bairro de localização da UC. |
| `possui_gd` | `string` | Sim | Indicador de presença de Geração Distribuída (`Sim` / `Não`). |
| `consumo_medio_inicial` | `double` | Sim | Média mensal de consumo em kWh no Período Inicial (P1: `2022-07` a `2023-06`). |
| `meses_com_leitura_p1` | `bigint` | Sim | Quantidade de meses com leituras válidas registradas no Período Inicial (P1). |
| `consumo_medio_final` | `double` | Sim | Média mensal de consumo em kWh no Período Final (P2: `2025-07` a `2026-06`). |
| `meses_com_leitura_p2` | `bigint` | Sim | Quantidade de meses com leituras válidas registradas no Período Final (P2). |
| `variacao_kwh` | `double` | Sim | Variação absoluta de consumo em kWh ($\text{P2} - \text{P1}$). |
| `variacao_pct` | `double` | Sim | Variação percentual de consumo ($\%$). Mantido como `NULL` na ausência de histórico. |
| `queda_consumo_superior_30_pct` | `boolean` | Sim | Flag de decisão (`True` / `False`): `True` se a variação percentual for menor ou igual a `-30.0%`. |

---

## 7. Consumo e Receita Mensal por Unidade Consumidora (`consumo_mensal_uc`)

**Objetivo:** Armazenar a série histórica temporal granular de consumo (kWh) e receita (R$) por Unidade Consumidora e competência. Serve como camada intermediária para alimentar a Visão 360° e permitir que agentes de GenAI respondam a consultas de histórico faturado sem reprocessamentos pesados.  
**Granularidade / Chave Primária:** Unidade Consumidora e Competência (`id_uc`, `competencia`).  
**Regras de Negócio e Enriquecimento:**
* **Junção de Fontes:** `INNER JOIN` entre faturas e leituras pré-agregadas por UC e mês, garantindo alinhamento financeiro total com a tabela `diagnostico_receita`.
* **Padronização Monetária e Volumétrica:** Métrica `receita_reais` padronizada em duas casas decimais com precisão decimal estrita.

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `id_uc` | `string` | Não | Chave primária parte 1: Identificador técnico único da Unidade Consumidora. |
| `competencia` | `string` | Não | Chave primária parte 2: Ano e mês de referência da fatura (formato `YYYY-MM`). |
| `consumo_kwh` | `double` | Sim | Volume total de consumo em kWh faturado na UC na competência. |
| `receita_reais` | `decimal(31,2)` | Sim | Valor total da receita faturada em reais (R$) para a UC no mês. |


