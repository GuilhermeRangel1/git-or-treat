# Contrato candidato dos CSVs Gold v2

Preparação de DE-04/DE-06/DE-08, em 30/10/2026. Descreve o produtor em [Exportacao_Gold_SQLite.ipynb](../../data-engineering/notebook/Exportacao_Gold_SQLite.ipynb). Não habilita a carga nem altera o [contrato histórico v1](gold-csv-v1.md). O Backend e a GenAI ainda precisam implementar e validar a compatibilidade antes do consumo.

## Origem e pacote

O produtor lê `gold.controle_gold`, seleciona a conclusão mais recente sem empate de instante e exige ambiente produtivo, Silver concluída, linhagem física, identificação completa e inventário das quatorze tabelas. A execução Gold e a exportação precisam ser serializadas. O exportador fixa as versões Delta e revalida controle e versões antes de liberar o manifesto; não oferece uma transação distribuída entre as tabelas.

Os identificadores seguem `GOLD_<YYYYMMDDTHHMMSSZ>_<8 hex minúsculos>` para Gold e `<YYYYMMDDTHHMMSSZ>_<8 hex minúsculos>` para Silver/Bronze. O produtor valida também a data/hora contida neles; valores manuais, de reserva ou com data impossível impedem a exportação.

Cada tentativa fica em `export_csv/<run_id_gold>/<export_id>/`, com uma pasta por tabela e exatamente um `manifest.json` final. A pasta da tentativa não é reutilizada. Diretório sem manifesto final ou com arquivos faltantes não é um pacote válido. `_SUCCESS` não é uma tabela nem substitui os controles.

## Inventário e grãos

| Pasta | Chave de negócio | Observação |
| --- | --- | --- |
| `diagnostico_receita` | competência, município, classe, subgrupo, bandeira e GD | Faturamento total elegível e parcelas com/sem leitura; base comparável separada. |
| `indicadores_dec_fec` | alimentador e competência | Indicadores simplificados; ausência de linha não comprova zero. |
| `fila_inspecao` | UC | Snapshot de triagem; não é ordem operacional. |
| `visao_360_uc` | UC | Cadastro atual e agregados; não substitui os históricos. |
| `consumo_mensal_uc` | UC e competência | Série independente por fonte, faturamento com/sem leitura, base comparável, flags de presença e contagens de observações. |
| `consumo_receita_bairro` | competência, município, bairro e classe | Mesmos universos independentes e parcelas do diagnóstico financeiro. |
| `variacao_consumo_uc` | UC | Janelas fixas documentadas; não é comparação mensal arbitrária. |
| `faturas_uc` | fatura | Independente da presença de leitura. |
| `medidor_uc` | medidor | Vínculo observado; não inventa transferências ou seleção de medidor ativo. |
| `atendimentos_uc` | protocolo | Resumo do chamado; não conserva todas as tratativas. |
| `ocorrencias_uc` | ocorrência e UC | Duração em minutos, datas/horários e flags de qualidade. |
| `gd_uc` | UC | Potência em kWp, conexão, modalidade e qualidade; não é série mensal de geração. |
| `tratativas_uc` | protocolo e posição original | Eventos estruturados, sem texto livre pessoal; sequência não é chave. |
| `cobertura_dominios` | domínio, competência e recorte | Grade mensal observada e estados certificados apenas por declaração de origem do mesmo lote. |

As projeções candidatas acrescentam `motivo_prioridade` à fila, `valor_em_aberto_reais` e `situacao_pagamento_analitica` às faturas, e `situacao_na_referencia` aos medidores. O saldo de fatura é derivado do status declarado e das flags Silver, não é confirmação contábil e não modela pagamento parcial; casos conflitantes/inconclusivos ficam sem valor. A situação do medidor é calculada por linha e não elimina sobreposições. O histórico `tratativas_uc` preserva as posições e as classificações divulgáveis, reconciliadas por protocolo; seu conteúdo livre não é exportado. A tabela `atendimentos_uc` conserva campos estruturados por protocolo e `qtd_tratativas`, reconciliada com a contagem no histórico Silver, mas exclui `acao`, `primeira_acao` e `ultima_acao`, que podem conter texto descritivo sem classificação de privacidade. Os totais de chamados e interrupções da `visao_360_uc` também são reconciliados por UC com `atendimentos_uc` e `ocorrencias_uc`; o agregado de interrupções e a projeção detalhada aplicam a mesma elegibilidade `_id_uc_ausente = false`, e o notebook exige schema exato e chave composta válida para `ocorrencias_uc`. A estimativa de energia recuperável continua fora do schema até haver método aprovado.

Os nomes físicos das colunas, tipos, medidas e limitações estão no [dicionário Gold](../dicionario_gold.md). O schema Spark de cada tabela também é registrado no manifesto para conferência. O exportador compara o conjunto e a quantidade de nomes de coluna de cada tabela com o inventário explícito do contrato candidato e interrompe a tentativa se houver campo faltante, extra ou duplicado. A ordem física do cabeçalho é preservada no CSV, mas não altera a autorização do schema. O manifesto registra também os tipos físicos observados. A aprovação final dos tipos, precisão, nulabilidade e nomes pelo Backend continua pendente; o schema declarado pelo arquivo não autoriza automaticamente campos novos nem amplia acesso.

O nome de exibição do titular fica em `gold_cadastro.cadastro_titular_uc`, fora deste inventário e do schema analítico. O pacote obrigatório da entrega completa [gold-cadastro-v1](gold-cadastro-v1.md) tem destino restrito e referencia a mesma execução e a tentativa analítica. A GenAI não pode consumir esse cadastro. O controle produtivo contém `tabelas_restritas_geradas=cadastro_titular_uc`, mas os nomes das pessoas nunca entram em manifestos.

Os complementos têm tipos físicos explicitamente validados pelo produtor e exportador: `id_uc`/protocolo/categorias como `string`, posições/sequência como `int`, potência como `double`, conexão como `date`, flags como `boolean` e instantes como `timestamp` UTC. Nulos permitidos e grãos estão no dicionário. Schema físico Spark pode ter `nullable=true` mesmo onde a chave recebe verificação de não nulidade; o consumidor deve impor a restrição lógica correspondente.

`cobertura_dominios` integra o mesmo pacote e a mesma publicação, com schema/tipos e contagem de linhas no manifesto. Os campos e o envelope de declarações opcionais estão no [contrato de cobertura](gold-cobertura-v1.md). Zero de registros observado não confirma completude: sem evidência válida, o estado permanece `NAO_CERTIFICADA`. `data_corte_evidencia` qualifica a declaração; `qtd_registros` conta o snapshot fixado. Não confundir esses universos em consultas com corte intramensal.

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
| `cadastro_export_id`, `cadastro_schema_version` | Referência obrigatória à tentativa cadastral da mesma entrega, com versão `gold-cadastro-v1`. Não contém nomes de pessoas. |
| `tabelas_exportadas` | Inventário completo, sem repetição. |
| `controles_tabelas` | Por tabela: `registros`, `versao_delta` e `schema` Spark. |
| `formato_csv` | Opções de codificação, separador, aspas, nulo, datas e timestamps usadas pelo produtor. |
| `responsavel` | Identificação funcional da equipe produtora. |

Os dois pacotes são obrigatórios: o destino cadastral é verificado antes de iniciar a escrita, e nenhum manifesto é liberado antes da reconciliação dos quinze conjuntos. O cadastro é publicado primeiro e o manifesto analítico por último, com referências cruzadas. Falhas capturadas removem os manifestos novos da tentativa; falha abrupta exige recuperação e o consumidor deve exigir sucesso do Job e os dois manifestos compatíveis. Não há atomicidade entre Volumes.

O manifesto é serializado antes de abrir o arquivo temporário. Só após escrita completa o produtor o renomeia para `manifest.json`. Erros capturados removem o temporário; a semântica de renomeação no Volume e o Job integral ainda precisam de validação no ambiente final. Controles e schema não autenticam o produtor; transferência e acesso devem ser autorizados.

## Diferenças que o consumidor precisa tratar

| Fronteira | v1 existente | Candidato v2 |
| --- | --- | --- |
| Inventário | Sete tabelas. | Quatorze tabelas analíticas/históricas, incluindo GD e tratativas estruturadas; cadastro pessoal em pacote separado. |
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
- A infraestrutura de cobertura mensal está implementada; as declarações de completude continuam dependentes da evidência de origem. Receita e inspeções mantêm suas definições pendentes; cadastro, tratativas e GD precisam de carga/consumidores autorizados. Quatorze tabelas não encerram automaticamente a [issue 75](https://github.com/GuilhermeRangel1/git-or-treat/issues/75).

A evolução autorizada de faturamento total e consumo independente altera também os schemas e o significado dos agregados em relação ao contrato v1. Os consumidores precisam mapear as parcelas, a base comparável e as contagens de qualidade; não basta aceitar colunas extras mantendo a fórmula anterior de tarifa.

Para #49, as projeções financeiras agregam cada fonte no grão UC/mês antes do `full outer join`. Faturamento com leitura observada não significa que todas as leituras sejam válidas. A base comparável inclui apenas UC/mês com fatura e todas as leituras observadas válidas; é a única base elegível para tarifa observada e análises preço-volume. Leituras sem fatura permanecem no consumo medido. Uma ausência dos dois lados na reconciliação é aceita como ausência; ausência comparada a zero ou a outro valor é divergência. Nenhuma dessas regras declara cobertura mensal completa nem calcula energia efetivamente faturada, valor recebido ou tarifa homologada.
