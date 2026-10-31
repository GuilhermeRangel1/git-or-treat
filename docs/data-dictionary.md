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

## Documentação atual — Gold CSV v2

A referência de aceite é **Gold CSV v2**, com quinze projeções analíticas no schema
`gold_v2`, mais o pacote cadastral restrito separado. O contrato físico e de exportação
está em [gold-csv-v2.md](contracts/gold-csv-v2.md); definições de negócio, grão,
chaves, fórmulas, nulidade e limitações estão no [dicionário Gold detalhado](dicionario_gold.md), implementado no notebook
[Silver_to_gold](../data-engineering/notebook/Silver_to_gold.ipynb). O pacote local e
a prontidão são documentados em [gold-readiness.md](gold-readiness.md) e
[gold-catalog.md](gold-catalog.md).

O conteúdo dentro do bloco histórico abaixo explica a versão v1 e não define critérios,
fórmulas, populações, chaves ou aceite da v2. Para os requisitos atuais, prevalecem o
PRD e os documentos v2 indicados acima. O envelope de contratos internos pode manter
versão própria sem alterar a versão do esquema dos dados.

## Métricas e cobertura v2

| Tema | Definição corrente v2 | Limite de uso |
| --- | --- | --- |
| Receita e faturamento | Total de faturas elegíveis, com parcelas separadas por presença de leitura; a ausência de leitura não exclui uma fatura. | Faturamento não significa recebimento ou pagamento. |
| Consumo | Leituras observadas, inclusive em UC/mês sem fatura; ausência de consumo é preservada como nula. | Consumo medido não é energia efetivamente faturada. |
| Preço observado | Receita dividida pelo consumo da mesma base comparável, com fatura e todas as leituras observadas válidas. | Não é tarifa homologada; decomposição por janelas tem estados e cobertura próprios. |
| Ticket médio | Receita sobre UCs faturadas em cada mês do recorte, como razão de somas das parcelas mensais. | O denominador representa UC-mês faturada, não UCs distintas no período inteiro. |
| Consumo médio por UC | Consumo medido sobre UCs com leitura em cada mês, como razão de somas. | Não usa UCs faturadas como denominador. |
| DEC/FEC | Numeradores de interrupção divididos pelas UCs do alimentador no cadastro atual; grão alimentador/competência. | Indicadores simplificados; linhas ausentes não significam zero e os valores não se somam entre alimentadores/meses. |
| Atendimento | Contagem por protocolo e média de notas individuais; atendimento mensal projeta `data_abertura` em UTC, enquanto acumulados não inventam datas. | Nota zero é válida; notas ausentes continuam ausentes. Atendimento mensal exige controles e cobertura do recorte. |
| Cobertura | `cobertura_dominios` e C14/C15 distinguem reconciliação da extração, estados de cobertura e disponibilidade por domínio. | Declaração de extração não certifica completude externa, conformidade ou semântica de negócio. |

O resumo acima não substitui as definições coluna a coluna do dicionário detalhado,
nem os controles independentes e o estado oficial do PRD. Medidas não existentes ou
não demonstradas na v2 — como valor recebido e energia efetivamente faturada — não
podem ser inferidas de campos próximos.

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
