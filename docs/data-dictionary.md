# Referências da camada Gold

As definições atuais das tabelas e métricas estão no [dicionário detalhado da Gold](dicionario_gold.md).
O contexto histórico abaixo registra a disponibilização inicial dos CSVs v1; as descrições
sobre o estado do dicionário naquele momento foram substituídas pela documentação atual.

<details>
<summary>Contexto histórico da integração CSV v1 — 27/10/2026</summary>

# Dicionário de dados Gold

**Estado:** os sete CSVs Gold v1 foram disponibilizados localmente em 27/10/2026. O [contrato físico observado](contracts/gold-csv-v1.md) orienta a carga provisória ao banco; não homologa as métricas. Este dicionário canônico continua pendente de definição e revisão pela engenharia de dados durante DE-08. O documento `dicionario_gold.md` da branch Gold é uma referência em elaboração e contém divergências em relação aos CSVs.

Os [contratos de consumo DEV-01](contracts/analytics-api.md) e as definições de suas fixtures sintéticas são propostas de aplicação, separadas deste dicionário Gold. Sua existência não comprova nomes de colunas, fórmulas ou granularidades do dataset. A integração futura deve revisar os pontos provisórios indicados no catálogo antes de apresentar métricas reais.


</details>

## Documentação atual

Este documento reúne as referências para consumir a camada Gold. As definições das
sete tabelas analíticas e de `controle_gold` estão no
[dicionário detalhado da Gold](dicionario_gold.md): finalidade, granularidade, chaves,
fontes, unidades, fórmulas, tratamento de ausências e limites de interpretação.

O [contrato físico observado dos CSVs v1](contracts/gold-csv-v1.md) descreve o lote
recebido para carga no banco. Ele deve ser consultado junto ao dicionário e ao manifesto
do lote efetivamente utilizado. Uma contagem registrada para outro lote não define a
quantidade obrigatória de registros das tabelas Gold.

## Métricas e cobertura

| Tema | Conteúdo implementado e documentado | Limite de uso |
| --- | --- | --- |
| Receita | Receita faturada, ticket médio e preço médio efetivo em `diagnostico_receita`, com recortes em `consumo_receita_bairro` e `consumo_mensal_uc` | Não representa receita paga; usa pares UC/mês com fatura e leitura correspondentes. |
| Consumo | Consumo medido e médias das leituras; comparação entre janelas em `variacao_consumo_uc` | Não equivale a uma medida independente de energia faturada. |
| Cadastro e GD | Atributos atuais por UC e presença de registro de geração distribuída | Não comprova vigência histórica, geração ou compensação mensal; status cadastral não deve ser convertido implicitamente em população ativa. |
| Inspeção | Hierarquia de prioridade em `fila_inspecao` | Prioridade orienta triagem; não confirma fraude nem quantifica energia recuperável. |
| Continuidade | DEC/FEC internos simplificados por alimentador e competência | Usa cadastro atual como denominador e publica grupos com ocorrência; não comprova conformidade regulatória oficial. |
| Atendimento | Contagem de protocolos e média de satisfação agregadas em `visao_360_uc` | Não fornece histórico individual de protocolos ou tratativas; observe as regras de notas e de cobertura das fontes. |

As fórmulas e regras por coluna estão no dicionário detalhado. Ao acrescentar métricas,
registre ali definição, grão, fonte, unidade, tratamento de nulos e divisão por zero,
arredondamento e limites. O aceite dos requisitos e as evidências de execução permanecem
no [PRD](PRD.md).

## Relação com os contratos da aplicação

Os [contratos de consumo DEV-01](contracts/analytics-api.md) e suas fixtures sintéticas
descrevem a interface da aplicação. A integração com a Gold deve mapear explicitamente
esses contratos para as colunas e fórmulas documentadas e reconciliar o lote carregado
com a fonte antes de apresentar métricas reais. O contrato da aplicação não altera
automaticamente a semântica das tabelas Gold.

O [contrato de entrada Silver](services/data-engineering.md#contrato-de-entrada-da-gold)
define grãos, chaves, cobertura, linhagem e limites das vistas `silver_publicada.*`
usadas pelo notebook Gold. Consulte-o para rastrear a origem das métricas e a população
excluída em cada etapa.
