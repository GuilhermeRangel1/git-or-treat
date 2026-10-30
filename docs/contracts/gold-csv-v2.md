# Contrato candidato dos CSVs Gold v2

Preparação de DE-04/DE-06/DE-08, em 30/10/2026. Descreve o produtor em [Exportacao_Gold_SQLite.ipynb](../../data-engineering/notebook/Exportacao_Gold_SQLite.ipynb). Não habilita a carga nem altera o [contrato histórico v1](gold-csv-v1.md). O Backend e a GenAI ainda precisam implementar e validar a compatibilidade antes do consumo.

## Origem e pacote

O produtor lê `gold.controle_gold`, seleciona a conclusão mais recente sem empate de instante e exige ambiente produtivo, Silver concluída, linhagem física, identificação completa e inventário das onze tabelas. A execução Gold e a exportação precisam ser serializadas. O exportador fixa as versões Delta e revalida controle e versões antes de liberar o manifesto; não oferece uma transação distribuída entre as tabelas.

Os identificadores seguem `GOLD_<YYYYMMDDTHHMMSSZ>_<8 hex minúsculos>` para Gold e `<YYYYMMDDTHHMMSSZ>_<8 hex minúsculos>` para Silver/Bronze. O produtor valida também a data/hora contida neles; valores manuais, de reserva ou com data impossível impedem a exportação.

Cada tentativa fica em `export_csv/<run_id_gold>/<export_id>/`, com uma pasta por tabela e exatamente um `manifest.json` final. A pasta da tentativa não é reutilizada. Diretório sem manifesto final ou com arquivos faltantes não é um pacote válido. `_SUCCESS` não é uma tabela nem substitui os controles.

## Inventário e grãos

| Pasta | Chave de negócio | Observação |
| --- | --- | --- |
| `diagnostico_receita` | competência, município, classe, subgrupo, bandeira e GD | Faturamento total elegível e parcelas com/sem leitura; base comparável separada. |
| `indicadores_dec_fec` | alimentador e competência | Indicadores simplificados; ausência de linha não comprova zero. |
| `fila_inspecao` | UC | Snapshot de triagem; não é ordem operacional. |
| `visao_360_uc` | UC | Cadastro atual e agregados; não substitui os históricos. |
| `consumo_mensal_uc` | UC e competência | Série independente por fonte, flags de presença e contagens de observações. |
| `consumo_receita_bairro` | competência, município, bairro e classe | Mesmos universos independentes e parcelas do diagnóstico financeiro. |
| `variacao_consumo_uc` | UC | Janelas fixas documentadas; não é comparação mensal arbitrária. |
| `faturas_uc` | fatura | Independente da presença de leitura. |
| `medidor_uc` | medidor | Vínculo observado; não inventa transferências ou seleção de medidor ativo. |
| `atendimentos_uc` | protocolo | Resumo do chamado; não conserva todas as tratativas. |
| `ocorrencias_uc` | ocorrência e UC | Duração em minutos, datas/horários e flags de qualidade. |

As projeções candidatas acrescentam `motivo_prioridade` à fila, `valor_em_aberto_reais` e `situacao_pagamento_analitica` às faturas, e `situacao_na_referencia` aos medidores. O saldo de fatura é derivado do status declarado e das flags Silver, não é confirmação contábil e não modela pagamento parcial; casos conflitantes/inconclusivos ficam sem valor. A situação do medidor é calculada por linha e não elimina sobreposições. A estimativa de energia recuperável continua fora do schema até haver método aprovado.

Os nomes físicos das colunas, tipos, medidas e limitações estão no [dicionário Gold](../dicionario_gold.md). O schema Spark de cada tabela também é registrado no manifesto para conferência. O consumidor precisa de um esquema esperado versionado: o schema declarado pelo arquivo não pode autorizar automaticamente colunas novas ou ampliar acesso.

## Codificação e fidelidade

- CSV UTF-8, separador `;`, cabeçalho em cada parte e aspas duplas; aspas internas duplicadas. Quebras de linha dentro de campos exigem leitura multiline.
- `nullValue` é o marcador literal `\N`; string vazia permanece vazia. O produtor rejeita uma string cujo conteúdo inteiro seja esse marcador reservado. O leitor v1, que interpreta vazio como nulo, não é compatível com essa representação.
- Datas usam `yyyy-MM-dd`; timestamps usam `yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX`, com sessão e serialização em UTC. Não reinterpretar timestamps como datas ou como hora local sem offset.
- Precisão decimal e tipos são preservados na releitura explícita do CSV. Valores monetários dos históricos usam `decimal(20,2)` conforme a projeção; esse tipo não deve ser confundido com o armazenamento histórico `Numeric(38,2)` do Backend v1.
- O produtor compara os registros nas duas direções com `exceptAll`, preservando multiplicidades. Uma diferença impede o manifesto final. Tabela vazia pode ser legítima conforme os controles; não substituir ausência de arquivo por tabela vazia.

## Manifesto emitido

| Campo | Conteúdo |
| --- | --- |
| `schema_version` | `gold-csv-v2`. |
| `ambiente` | `prod`, após validação do controle. |
| `run_id`, `lote` | Mesma execução Gold efetivamente validada. |
| `run_id_silver`, `lote_bronze_silver` | Linhagem declarada no controle da mesma execução. |
| `data_processamento_gold` | Instante do controle Gold, com offset UTC; não é a data da carga local. |
| `status_gold` | `CONCLUIDO`, proveniente do controle validado. |
| `data_exportacao_csv` | Instante UTC da emissão do manifesto. |
| `export_id` | Identificador da tentativa de exportação; não é publicação no banco local. |
| `tabelas_exportadas` | Inventário completo, sem repetição. |
| `controles_tabelas` | Por tabela: `registros`, `versao_delta` e `schema` Spark. |
| `formato_csv` | Opções de codificação, separador, aspas, nulo, datas e timestamps usadas pelo produtor. |
| `responsavel` | Identificação funcional da equipe produtora. |

O manifesto é serializado antes de abrir o arquivo temporário. Só após escrita completa o produtor o renomeia para `manifest.json`. Erros capturados removem o temporário; a semântica de renomeação no Volume e o Job integral ainda precisam de validação no ambiente final. Controles e schema não autenticam o produtor; transferência e acesso devem ser autorizados.

## Diferenças que o consumidor precisa tratar

| Fronteira | v1 existente | Candidato v2 |
| --- | --- | --- |
| Inventário | Sete tabelas. | Onze tabelas, incluindo os quatro históricos. |
| Nulos CSV | Campo vazio representa nulo. | Marcador reservado distinto de string vazia. |
| Manifesto | Campos extras recusados. | Novos campos de tentativa, schemas, versões e formato. |
| Processamento | Exige `data_processamento_gold`. | Produtor agora emite o mesmo nome; o nome antigo `data_processamento` não é emitido. |
| Identidade da publicação | Parser Backend e `GoldBatchRef` GenAI aceitam somente v1. | Compatibilidade v2 ainda não implementada. |
| Banco | Snapshot físico v1 e migrações existentes. | Exige migração e mapeamento explícitos, sem editar silenciosamente o snapshot histórico. |

A carga deve preservar as garantias existentes de publicação transacional, idempotência, auditoria, identidade e conservação de ordens. O formato final da referência v2 precisa ser acordado nos dois serviços; o exportador não fabrica `publication_id` nem altera envelopes GenAI.

## Pendências para aprovação e aceite

- Aprovação conjunta do inventário e dos novos campos, tipos, nulos e limites do manifesto; conferir tamanho máximo antes de alterar o limite v1 de 64 KiB.
- Validação estrita de identidade, schema, controles, partes CSV e versão pelo consumidor, com falha preservando o lote válido anterior.
- Execução real de escrita/releitura CSV, controle de concorrência e comparação com a publicação aprovada na origem.
- Reconciliação da mesma exportação no banco, na API e no portal/GenAI. Os testes do produtor não comprovam essas etapas.
- Complementos de cobertura, receita, cadastro, tratativas, GD e inspeções continuam sujeitos às definições e à disponibilidade da origem. Onze tabelas não encerram automaticamente a [issue 75](https://github.com/GuilhermeRangel1/git-or-treat/issues/75).

A evolução autorizada de faturamento total e consumo independente altera também os schemas e o significado dos agregados em relação ao contrato v1. Os consumidores precisam mapear as parcelas, a base comparável e as contagens de qualidade; não basta aceitar colunas extras mantendo a fórmula anterior de tarifa.

Para #49, as projeções financeiras agregam cada fonte no grão UC/mês antes do `full outer join`. Faturamento com leitura observada não significa que todas as leituras sejam válidas. A base comparável inclui apenas UC/mês com fatura e todas as leituras observadas válidas; é a única base elegível para tarifa observada e análises preço-volume. Leituras sem fatura permanecem no consumo medido. Uma ausência dos dois lados na reconciliação é aceita como ausência; ausência comparada a zero ou a outro valor é divergência. Nenhuma dessas regras declara cobertura mensal completa nem calcula energia efetivamente faturada, valor recebido ou tarifa homologada.
