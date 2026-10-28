# Dicionário de dados Gold

**Estado:** os sete CSVs Gold v1 foram disponibilizados localmente em 27/10/2026. O [contrato físico observado](contracts/gold-csv-v1.md) orienta a carga provisória ao banco; não homologa as métricas. Este dicionário canônico continua pendente de definição e revisão pela engenharia de dados durante DE-08. O documento `dicionario_gold.md` da branch Gold é uma referência em elaboração e contém divergências em relação aos CSVs.

Os [contratos de consumo DEV-01](contracts/analytics-api.md) e as definições de suas fixtures sintéticas são propostas de aplicação, separadas deste dicionário Gold. Sua existência não comprova nomes de colunas, fórmulas ou granularidades do dataset. A integração futura deve revisar os pontos provisórios indicados no catálogo antes de apresentar métricas reais.

## Modelo de tabela Gold

| Campo | Descrição |
| --- | --- |
| Nome e finalidade | Quem usa e qual pergunta atende |
| Granularidade | Uma linha representa exatamente o quê |
| Chave primária/única | Comprovação de unicidade |
| Chaves de relação | Cardinalidade e vigência temporal |
| Fonte Bronze/Silver | Arquivos, abas e colunas de origem |
| Atualização | Frequência, competência e data do lote |
| Tratamentos | Filtros, deduplicação, imputação, quarentena |
| Limitações | Cobertura, nulos, uso indevido a evitar |

## Modelo de métrica

| Campo | Descrição |
| --- | --- |
| Nome e definição | Significado para o negócio |
| Fórmula | Numerador, denominador, sinais e arredondamento |
| Unidade | R$, kWh, horas/UC, interrupções/UC, %, contagem etc. |
| Granularidade e filtros | Competência, UC, classe, geografia, alimentador |
| Fonte | Tabelas e colunas Gold |
| Reconciliação | Consulta/cálculo de controle e resultado |
| Limites | Divisão por zero, base pequena, faltantes, estimativas |

## Métricas a definir

- Receita residencial e comercial; valor faturado versus pago.
- Energia consumida, energia faturada e preço médio efetivo.
- Decomposição preço-volume e contribuição por recorte.
- UCs ativas, UCs com GD, queda de consumo.
- Suspeita/prioridade de inspeção e energia potencialmente recuperável.
- DEC e FEC simplificados por alimentador/período.
- Indicadores de atendimento e satisfação, se exibidos.

Uma métrica só pode alimentar portal, IA ou apresentação final depois de ter fórmula e validação registradas aqui.

O contrato das vistas Silver que poderão alimentar a Gold — grão, chave, cobertura, linhagem e limites de uso — está no [guia do serviço de engenharia de dados](services/data-engineering.md#contrato-de-entrada-da-gold). Ele não substitui as definições e provas por métrica exigidas neste dicionário.
