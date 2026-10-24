# Dicionário de Dados — Camada Gold

Este documento descreve a estrutura, esquemas de dados, mascaramentos de privacidade (LGPD) e regras de negócio aplicadas às tabelas da **Camada Gold**.

---

## 1. Visão 360 da Unidade Consumidora (`visao_360_uc`)

Tabela consolidada ao nível de Unidade Consumidora (`id_uc`), agregando dados cadastrais, consumo histórico, interrupções, atendimento e geração distribuída.

>  **LGPD / Mascaramento:** Os campos `cpf_cnpj` e `nome_titular` passam por mascaramento/anonimização na formação da tabela para proteção de dados sensíveis.

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `id_uc` | `string` | Sim | Identificador único da Unidade Consumidora. |
| `cpf_cnpj` | `string` | Sim | Documento do titular (**Mascarado - LGPD**). |
| `nome_titular` | `string` | Sim | Nome completo do titular (**Mascarado - LGPD**). |
| `_cpf_cnpj_conflitante` | `boolean` | Sim | Flag de auditoria para divergências cadastrais de documento. |
| `_nome_titular_conflitante` | `boolean` | Sim | Flag de auditoria para divergências cadastrais do nome. |
| `logradouro` | `string` | Sim | Endereço da UC. |
| `numero` | `string` | Sim | Número do imóvel. |
| `bairro` | `string` | Sim | Bairro do imóvel. |
| `municipio` | `string` | Sim | Município de localização. |
| `uf` | `string` | Sim | Estado (Unidade Federativa). |
| `cep` | `string` | Sim | Código de Endereçamento Postal. |
| `classe` | `string` | Sim | Classe de consumo (ex.: Residencial, Comercial, Industrial). |
| `subgrupo_tarifario` | `string` | Sim | Subgrupo tarifário (ex.: B1, B3, A4). |
| `alimentador` | `string` | Sim | Código do alimentador elétrico associado. |
| `data_ligacao` | `date` | Sim | Data de ligação/ativação da UC. |
| `status` | `string` | Sim | Status operacional da UC (ex.: Ativo, Desligado). |
| `latitude` | `double` | Sim | Coordenada geográfica (latitude). |
| `longitude` | `double` | Sim | Coordenada geográfica (longitude). |
| `_geo_invalida` | `boolean` | Sim | Flag indicando inconsistência geográfica. |
| `_ligacao_futura` | `boolean` | Sim | Flag para datas de ligação inconsistentes/futuras. |
| `_ligacao_sentinela` | `boolean` | Sim | Flag para valores padrões/sentinela de ligação. |
| `_arquivo_origem` | `string` | Sim | Metadado de lineage: nome do arquivo de origem. |
| `_ordem_na_origem` | `long` | Sim | Metadado de lineage: número da linha na origem. |
| `_lote_id` | `string` | Sim | Identificador do lote do ingestion. |
| `_id_registro` | `long` | Sim | Identificador do registro no pipeline. |
| `_data_processamento` | `timestamp` | Sim | Timestamp de execução do pipeline. |
| `_run_id` | `string` | Sim | ID da execução do pipeline. |
| `possui_gd` | `string` | Sim | Indicador se possui Geração Distribuída (`Sim` / `Não`). |
| `total_chamados_callcenter` | `long` | Sim | Total acumulado de atendimentos/chamados via callcenter. |
| `media_satisfacao_atendimento` | `double` | Sim | Nota média de satisfação obtida em atendimentos (CSAT). |
| `total_interrupcoes_sofridas` | `long` | Sim | Total de interrupções de energia associadas à UC. |
| `duracao_total_interrupcoes_horas` | `double` | Sim | Duração acumulada das interrupções sofridas (em horas). |
| `media_consumo_historico` | `double` | Sim | Média histórica do consumo de energia em kWh. |

---

## 2. Diagnóstico de Receita (`diagnostico_receita`)

Tabela agregada por competência e segmentações operacionais para diagnóstico financeiro, volumes de consumo e cálculo de tarifa efetiva.

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `competencia` | `string` | Sim | Mês e ano de referência (`YYYY-MM`). |
| `municipio` | `string` | Sim | Nome do município. |
| `classe_consumo` | `string` | Sim | Classificação do consumidor. |
| `subgrupo_tarifario` | `string` | Sim | Subgrupo tarifário de enquadramento. |
| `bandeira_tarifaria` | `string` | Sim | Bandeira tarifária vigente no faturamento. |
| `possuo_gd` | `string` | Sim | Indicador de presença de Geração Distribuída. |
| `qtd_ucs_distintas_faturadas_no_mes` | `long` | Sim | Contagem distinta de UCs faturadas na combinação. |
| `soma_faturamentos_mensais` | `long` | Sim | Total acumulado de episódios de faturamento. |
| `consumo_total_kwh` | `double` | Sim | Consumo de energia somado em kWh. |
| `receita_total_reais` | `decimal(38,2)` | Sim | Soma da receita faturada em R$. |
| `ticket_medio_reais_por_uc` | `decimal(34,6)` | Sim | Valor médio faturado por UC (`receita_total / ucs_distintas`). |
| `consumo_medio_kwh_por_uc` | `double` | Sim | Consumo médio mensal por UC (`consumo_total / ucs_distintas`). |
| `tarifa_media_efetiva` | `double` | Sim | Valor médio pago por kWh (`receita_total / consumo_total`). |

---

## 3. Fila de Inspeção de Fraudes (`fila_inspecao`)

Tabela direcionada ao time de campo e modelos de GenAI / Machine Learning para priorização de vistorias e combate a perdas não técnicas.

>  **LGPD / Mascaramento:** Os campos `cpf_cnpj` e `nome_titular` passam por mascaramento.

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `id_uc` | `string` | Sim | Identificador único da UC. |
| `cpf_cnpj` | `string` | Sim | Documento do titular (**Mascarado - LGPD**). |
| `nome_titular` | `string` | Sim | Nome do titular (**Mascarado - LGPD**). |
| `logradouro` | `string` | Sim | Endereço da UC. |
| `numero` | `string` | Sim | Número do imóvel. |
| `bairro` | `string` | Sim | Bairro. |
| `municipio` | `string` | Sim | Município. |
| `uf` | `string` | Sim | Estado. |
| `cep` | `string` | Sim | CEP. |
| `classe` | `string` | Sim | Classe de consumo. |
| `subgrupo_tarifario` | `string` | Sim | Subgrupo tarifário. |
| `alimentador` | `string` | Sim | Código do alimentador elétrico. |
| `data_ligacao` | `date` | Sim | Data de ativação. |
| `status` | `string` | Sim | Status da UC. |
| `latitude` | `double` | Sim | Coordenada (latitude). |
| `longitude` | `double` | Sim | Coordenada (longitude). |
| `media_consumo_historico` | `double` | Sim | Média histórica de consumo (kWh). |
| `total_inspecoes_realizadas` | `long` | Sim | Quantidade prévia de inspeções em campo. |
| `total_inspecoes_irregulares` | `long` | Sim | Quantidade de inspeções que confirmaram fraude/anomalia. |
| `total_chamados_callcenter` | `long` | Sim | Total de atendimentos do cliente. |
| `media_satisfacao_atendimento` | `double` | Sim | Média da nota de atendimento. |
| `possui_geracao_solar` | `string` | Sim | Indicador de presença de sistema fotovoltaico/GD. |
| `prioridade_inspecao` | `string` | Sim | Score/Nível de prioridade para vistoria de campo (ex.: `Alta`, `Média`, `Baixa`). |

---

## 4. Indicadores de Qualidade da Rede (`indicadores_dec_fec`)

Tabela consolidada com os indicadores regulatórios da ANEEL calculados ao nível de alimentador elétrico e município por competência.

| Nome da Coluna | Tipo de Dado | Permite Nulo | Descrição / Regra de Negócio |
| :--- | :--- | :--- | :--- |
| `id_alimentador` | `string` | Sim | Código identificador do alimentador de distribuição. |
| `municipio` | `string` | Sim | Município atendido pelo alimentador. |
| `competencia` | `string` | Sim | Mês e ano de referência (`YYYY-MM`). |
| `total_ucs_alimentador` | `long` | Sim | Quantidade total de clientes/UCs conectadas ao alimentador. |
| `ucs_interrompidas` | `long` | Sim | Total de clientes afetados por descontinuidade de suprimento. |
| `frequencia_total_interrupcoes` | `long` | Sim | Soma de eventos de interrupção no período. |
| `duracao_total_interrupcoes_horas` | `double` | Sim | Soma das durações dos desligamentos em horas. |
| `DEC` | `double` | Sim | **Duração Equivalente de Interrupção por Unidade Consumidora** (Horas). |
| `FEC` | `double` | Sim | **Frequência Equivalente de Interrupção por Unidade Consumidora** (Vezes). |
