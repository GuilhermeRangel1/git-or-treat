# Contrato cadastral restrito da UC

Produtor: [Silver_to_gold](../../data-engineering/notebook/Silver_to_gold.ipynb) e [exportador](../../data-engineering/notebook/Exportacao_Gold_SQLite.ipynb). Finalidade: preencher `UCProfile.customer_name` na visão do atendente, a partir do nome de exibição solicitado em 30/10/2026. A revisão da D20 está nas [decisões de Dados](../../data-engineering/decisoes-tecnicas.md#93-exclusão-de-dados-pessoais-na-projeção-gold-d20-decidido).

## Projeção e limites

`workspace.gold_cadastro.cadastro_titular_uc` tem uma linha por `id_uc` elegível da Silver publicada. Em `dev`/`test`, usa `gold_cadastro_dev`/`gold_cadastro_test`. O preparo usa schema cadastral exclusivo `gold_cadastro_preparo` (sufixo `_dev`/`_test` conforme ambiente), com tabela candidata de nome exclusivo por execução. Ambos os schemas cadastrais devem existir previamente; o notebook não os cria.

| Campo | Tipo Spark | Obrigatoriedade lógica | Regra |
| --- | --- | --- | --- |
| `id_uc` | `string` | Não nulo e único | Liga o cadastro à unidade; não é identificador de cliente. |
| `nome_exibicao_titular` | `string` | Pode ser nulo | Nome atual da Silver, com espaços nas extremidades removidos; sem transformação em chave ou identificador. |
| `situacao_identificacao` | `string` | Não nulo | `DISPONIVEL`, `AUSENTE_NA_ORIGEM` ou `CONFLITO_NA_ORIGEM`. Conflito tem precedência e mantém nome nulo. |
| `data_processamento_gold` | `timestamp` | Não nulo | Mesmo instante de referência das demais projeções. |

Exclui UC nula ou de teste. Não contém CPF/CNPJ, endereço, coordenadas, hash de documento ou referência fictícia de cliente. Não prova titularidade histórica. A origem não fornece uma chave de cliente/contrato independente da UC nesta projeção: `customer_reference` deve continuar nulo, sem agrupar nomes iguais como uma pessoa.

## Pré-condição da produção do cadastro

Provisionar previamente os schemas de publicação e preparo com permissões exclusivas e configurar o Job com `CADASTRO_RESTRITO_VALIDADO=sim` após conferir ACLs. O padrão é `nao`: o notebook interrompe antes de ler/projetar nomes. Também recusa schema cadastral ausente; não cria um namespace que possa herdar acesso amplo sem essa preparação.

Esse parâmetro é uma declaração operacional de pré-condição, não uma prova automática de ACL. Revisar privilégios herdados e testar os papéis continua obrigatório no ambiente de implantação. Não habilitar a opção para contornar a configuração de acesso.

## Exportação separada

O pacote analítico [gold-csv-v2](gold-csv-v2.md) nunca inclui esta tabela. A entrega completa exige também o cadastro: `exportar_cadastro_restrito=sim` é o padrão e o único valor aceito. Configuração antiga com `nao` falha antes de exportar. Provisionar o Volume exclusivo `workspace.gold_cadastro.cadastro_export_volume`; o exportador verifica o acesso antes de criar as pastas das tentativas ou gravar CSVs.

Destino: `/Volumes/workspace/gold_cadastro/cadastro_export_volume/export_csv/<run_id_gold>/<export_id>/`. O notebook não cria esse Volume automaticamente. Ausência de acesso ou de provisionamento interrompe a exportação restrita. Falha cadastral interrompe a entrega completa. Nenhum manifesto novo é liberado antes da validação dos dezesseis conjuntos. Arquivos parciais ficam em tentativa isolada, sem serem confundidos com uma entrega válida.

O CSV usa as mesmas regras de UTF-8, `;`, aspas, UTC e marcador de nulo `\N` do contrato analítico. Tipos e conjunto exato de colunas são verificados; campos adicionais, inclusive documentos, são recusados. A releitura deve conservar o multiconjunto completo antes do manifesto.

O manifesto `gold-cadastro-v1` contém `restrito=true`, `finalidade=identificacao_titular_atendimento`, `ambiente`, `run_id`, `run_id_silver`, `lote_bronze_silver`, `data_processamento_gold`, `status_gold`, `data_exportacao_csv`, `export_id`, `analytic_export_id`, `analytic_schema_version`, `tabelas_exportadas`, `controles_tabelas` e `formato_csv`. Não contém nomes de pessoas. O único item de `tabelas_exportadas` é `cadastro_titular_uc`; `controles_tabelas` registra seu schema físico, contagem e versão Delta.

## Conclusão dos dois pacotes

Após reconciliar os dezesseis conjuntos e revalidar controle/versões, o exportador publica o manifesto cadastral e depois o analítico, com referências cruzadas. Sucesso só é anunciado após ambos. Falha capturada durante essa publicação remove os manifestos da tentativa atual; exportações anteriores não são removidas. Se a remoção falhar, a execução informa a necessidade de bloquear/recuperar a tentativa.

Não há transação entre os dois Volumes. Interrupção abrupta pode deixar manifesto parcial: o consumidor deve exigir o sucesso do Job e conferir ambos os manifestos e suas referências antes de aceitar a entrega. A publicação transacional no banco continua responsabilidade do carregador.

## Obrigações do consumidor e do operador

- Conferir que `run_id`, origem Silver/Bronze e processamento coincidem com o pacote analítico selecionado; `analytic_export_id` deve apontar àquela tentativa, não apenas a um lote com prefixo semelhante; os campos `cadastro_export_id` e `cadastro_schema_version` do manifesto analítico devem coincidir com o pacote cadastral. Rejeitar versão desconhecida, schema inesperado, arquivo ausente ou cadastro de outra publicação.
- Importar em schema cadastral separado do schema analítico `gold`, por papel de carga próprio, preservando idempotência e publicação válida anterior. Não editar `gold_v1.py` para aceitar este pacote.
- O papel analítico `venergy_gold_reader` e o serviço GenAI não podem ler o schema/Volume cadastral. O Backend deve consultar o nome por um papel restrito e aplicar autorização individual de atendimento. Nenhum nome entra no contexto de planejamento/síntese, catálogo, evidência ou auditoria textual da IA.
- Provisionar e conferir permissões também no catálogo e nos schemas de preparo, pois privilégios herdados podem ampliar acesso; separar schemas não comprova sozinho o controle de acesso. Os notebooks não concedem permissões nem demonstram ACLs do ambiente real.
- Mapear `nome_exibicao_titular` disponível para `customer_name`. Ausência ou conflito gera valor nulo e explicação específica na seção cadastral; falha de carga/consulta gera indisponibilidade da integração. Não substituir por nome sintético ou tratar ausência de pacote como ausência de titular na origem.

Esta entrega prepara o produtor; migração, carga, autorização e mapeamento da API/portal permanecem entregas dos consumidores. A projeção não conclui o WEB-03 nem atende por si só ao pedido mais amplo de referência de cliente e endereço do DEV13.2 U03.
