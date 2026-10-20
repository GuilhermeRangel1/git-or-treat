# ADR-0001 — Reconciliação da ingestão e captura de registros malformados na Bronze

**Data:** 2026-10-17

**Estado:** proposta

**IDs do PRD afetados:** DE-01

## Contexto

O [PRD](../PRD.md) exige que a Bronze preserve o bruto de forma rastreável, que "diferenças de parse e rejeições sejam contadas e explicadas" (§6.1, DE-01) e que cada ingestão tenha um livro de reconciliação por fonte e lote (§4.3). Isso obriga a isolar as linhas malformadas e a provar quantas linhas físicas de origem viraram linha da tabela.

Dois fatos do ambiente limitam as opções:

1. O runtime usado na atividade é a Databricks Free Edition sobre Spark Connect. Nele, uma opção não suportada tende a ser ignorada em silêncio, sem erro visível.
2. A opção `badRecordsPath` — o mecanismo natural para gravar rejeitados em arquivo lateral — foi testada com corrupção certa por construção e **gravou 0 bytes**. Somado a isso, `mode` não pode ser combinado com `badRecordsPath` ("If 'badRecordsPath' is specified, 'mode' is not allowed to set"), o que inviabiliza o `overwrite` das tabelas.

## Opções consideradas

1. **`badRecordsPath` (arquivo lateral de rejeitados).** Mantém a tabela da fonte só com válidos e grava os ruins fora do Delta. Descartada: comprovadamente ineficaz neste runtime (0 bytes com corrupção certa) e incompatível com `mode=overwrite`.
2. **Coluna de corrupção (`columnNameOfCorruptRecord` → `_corrupt_record`).** O registro malformado vira o valor de uma coluna e permanece na própria linha. Tudo fica dentro do Delta, permite separar válidos e rejeitados em memória e não conflita com `mode`.
3. **Validação fora do Spark (reler o arquivo com `csv`/Python no driver).** Foi descartada para fazer todo o parse. A revisão de 19/10/2026 a usa apenas para conferir a quantidade de campos por registro, em fluxo contínuo e com memória constante; o Spark continua responsável pela ingestão.

## Decisão

Adotar a opção 2, com as seguintes regras de contrato:

- CSV usa schema explícito 100% string; JSON usa schema inferido para preservar a estrutura aninhada e acrescenta `_corrupt_record` sem duplicá-la. Ambos usam `columnNameOfCorruptRecord="_corrupt_record"`. Antes da leitura Spark, a largura do CSV é validada pelo cabeçalho; divergência interrompe o lote com contagem e linhas de exemplo.
- Linha com `_corrupt_record` nulo é válida e vai para a tabela da fonte; as demais vão para `bronze.rejeitados`, com o conteúdo bruto preservado.
- `rejeitadas` é sempre derivada por aritmética (`total lido − gravadas`), **nunca** de `count()` sobre o DataFrame filtrado por `_corrupt_record` (o Spark Connect recusa essa expressão).
- Cada tabela registra uma linha em `bronze.reconciliacao` com `linhas_lidas`, `gravadas`, `rejeitadas` e `delta = linhas_dados − gravadas − rejeitadas`; `delta ≠ 0` é falha declarada, não ruído.
- `bronze.leituras` é reconciliada contra a contagem **física** de linhas do Volume (`spark.read.text`), não contra a contagem do parser, para que a verificação seja independente.
- Um **autoteste** roda a cada execução. Na revisão de 19/10/2026, dois registros CSV com largura divergente precisam ser bloqueados antes do Spark; um CSV íntegro produz uma linha válida e nenhuma rejeição; o JSON produz uma linha válida e uma rejeitada. Se o mecanismo falhar, o lote não é publicado. A guarda de largura acrescenta uma leitura sequencial de cada CSV; validar seu custo no Databricks.

## Consequências e verificação

- `bronze.rejeitados` e `bronze.reconciliacao` passam a fazer parte do contrato da camada. A quarentena dos rejeitados é decisão da Silver e segue em aberto.
- A tabela da fonte perde a equivalência "linha física = linha da tabela": `_id_registro` é o id técnico do lote. `_ordem_na_origem` depende do particionamento do Spark e não garante a linha física em CSV/JSON; somente no Excel vem do índice da aba. O rastreio usa arquivo, hash e valores brutos, e a posição física CSV/JSON continua pendente em DE-01.
- `atendimentos` fecha como `SEM_BASE` (array JSON identado: não há contagem de linhas físicas comparável) e `inspecoes` fecha com `linhas_arquivo = null` (origem XLSX, lida por `pandas`).
- A lacuna histórica de hash/versão foi resolvida em 19/10/2026 por `bronze.arquivos_lote` (SHA-256 quando o Volume permite leitura no driver).
- Se o runtime voltar a suportar `badRecordsPath` com gravação confiável, esta decisão deve ser revista; o contrato de reconciliação pode ser mantido trocando apenas o mecanismo de captura.
- Verificação histórica: execução completa do notebook em 17/10/2026 — `delta = 0` em todas as tabelas, autoteste `OK` nos dois leitores e `bronze.rejeitados` sem linhas. A guarda de largura de 19/10/2026 ainda precisa de execução no Databricks. A distinção de largura segue a documentação oficial do Apache Spark 3.5.6: https://spark.apache.org/docs/3.5.6/sql-data-sources-csv.html#data-source-option.
