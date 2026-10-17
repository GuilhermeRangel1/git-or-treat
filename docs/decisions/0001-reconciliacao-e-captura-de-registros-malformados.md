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
3. **Validação fora do Spark (reler o arquivo com `csv`/Python no driver).** Não depende do runtime para contar malformados. Descartada: cria uma segunda fonte de verdade, não escala para ~2,2 mi de linhas e duplicaria a lógica de parsing.

## Decisão

Adotar a opção 2, com as seguintes regras de contrato:

- Toda leitura de CSV/JSON usa **schema explícito 100% string** e `columnNameOfCorruptRecord="_corrupt_record"`. Como o schema é explícito, a inferência do JSON não duplica a coluna de corrupção.
- Linha com `_corrupt_record` nulo é válida e vai para a tabela da fonte; as demais vão para `bronze.rejeitados`, com o conteúdo bruto preservado.
- `rejeitadas` é sempre derivada por aritmética (`total lido − gravadas`), **nunca** de `count()` sobre o DataFrame filtrado por `_corrupt_record` (o Spark Connect recusa essa expressão).
- Cada tabela registra uma linha em `bronze.reconciliacao` com `linhas_lidas`, `gravadas`, `rejeitadas` e `delta = linhas_dados − gravadas − rejeitadas`; `delta ≠ 0` é falha declarada, não ruído.
- `bronze.leituras` é reconciliada contra a contagem **física** de linhas do Volume (`spark.read.text`), não contra a contagem do parser, para que a verificação seja independente.
- Um **autoteste** roda a cada execução, com corrupção certa por construção (CSV 1 válida/2 rejeitadas; JSON 1 válida/1 rejeitada). Se o mecanismo parar de funcionar, a execução avisa que `rejeitadas = 0` não é garantia de dataset limpo.

## Consequências e verificação

- `bronze.rejeitados` e `bronze.reconciliacao` passam a fazer parte do contrato da camada. A quarentena dos rejeitados é decisão da Silver e segue em aberto.
- A tabela da fonte perde a equivalência "linha física = linha da tabela": `_id_registro` é o id técnico do lote, não o número da linha no arquivo. O rastreio da linha bruta se dá por `_arquivo_origem` e pelo `_corrupt_record` guardado em `bronze.rejeitados`.
- `atendimentos` fecha como `SEM_BASE` (array JSON identado: não há contagem de linhas físicas comparável) e `inspecoes` fecha com `linhas_arquivo = null` (origem XLSX, lida por `pandas`).
- Lacuna conhecida frente ao §4.3: a reconciliação registra o **nome** do arquivo de origem, mas ainda não o **hash/versão** do arquivo ingerido.
- Se o runtime voltar a suportar `badRecordsPath` com gravação confiável, esta decisão deve ser revista; o contrato de reconciliação pode ser mantido trocando apenas o mecanismo de captura.
- Verificação: execução completa do notebook em 17/10/2026 — `delta = 0` em todas as tabelas, autoteste `OK` nos dois leitores e `bronze.rejeitados` sem linhas.
