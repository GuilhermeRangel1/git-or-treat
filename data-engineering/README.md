# Engenharia de dados — Bronze, Silver e Gold

Os notebooks versionados cobrem ingestão, perfilamento, Silver, Gold e exportação.
O Job `v-energy-grid-360` encadeia cinco tarefas
([YAML versionado](configuracao/databricks/v-energy-grid-360.yaml)) e cada uma já foi executada no
Databricks; o run limpo de ponta a ponta e o print do Workflow serão registrados no PRD. Na Bronze, valores ausentes,
duplicatas, datas ambíguas e vínculos inconsistentes são medidos e preservados;
tratamento e decisão de negócio pertencem à Silver. O contrato completo está no
[PRD](../docs/PRD.md) e no [guia do serviço](../docs/services/data-engineering.md).

## Arquivos

| Arquivo | Papel |
| --- | --- |
| [`Landing_to_Bronze.ipynb`](notebook/Landing_to_Bronze.ipynb) | Ingestão, rejeitados, reconciliação por origem e publicação |
| [`Bronze_perfilamento.ipynb`](notebook/Bronze_perfilamento.ipynb) | Inventário, achados e relações por arquivo/aba |
| [`Bronze_to_Silver.ipynb`](notebook/Bronze_to_Silver.ipynb) | Silver: limpeza, tipos, chaves, quarentena, reconciliação e portão de qualidade |
| [`Silver_to_gold.ipynb`](notebook/Silver_to_gold.ipynb) | Construção e validações das tabelas Gold a partir da Silver publicada |
| [`Exportacao_Gold_SQLite.ipynb`](notebook/Exportacao_Gold_SQLite.ipynb) | Exportação das sete tabelas Gold em CSV para um Volume |

O scanner grava JSONL de preparo **somente no Volume autorizado**. Cada
registro aceito mantém o conteúdo bruto, arquivo, ordinal e linha física inicial
e final. Registros de largura CSV ou sintaxe inválida vão para
`bronze.rejeitados` com motivo; não são limpos nem descartados em silêncio.
O array `atendimentos.json` é contado objeto a objeto antes da leitura Spark.
Após publicação bem-sucedida, o notebook remove o schema de preparo e os JSONL
temporários; em falha, eles ficam disponíveis para diagnóstico.

## Publicação

Cada execução recebe `_lote_id` próprio e um schema de preparo isolado. O
conjunto de hashes dos arquivos forma `_versao_origem`; `lote_origem` pode ser
fornecido pelo Job e não substitui o hash. O livro `bronze.reconciliacao`
registra origem, lidos, aceitos, rejeitados, duplicatas detectadas e delta.
`bronze.arquivos_lote` guarda a identidade dos arquivos.

Após validar todas as fontes, a carga acrescenta o lote às tabelas Delta de
`bronze_hist`. As vistas `bronze.*` filtram o único `lote_ativo` de
`bronze.controle_publicacao`. Mudar esse ponteiro publica o conjunto; uma
falha antes da troca deixa visível o lote anterior. Reexecutar a mesma origem
cria histórico de execução, sem duplicar linhas na vista publicada. A primeira
execução migra as tabelas Bronze anteriores para o histórico e precisa ocorrer
em janela controlada, com conferência das tabelas legadas.

O perfilador lê o lote publicado e grava `quality.perfil_bronze`,
`quality.inventario_bronze`, `quality.achados_bronze`,
`quality.relacoes_bronze` e `quality.distribuicoes_bronze` para categorias
selecionadas. `quality.achados_bronze` também registra padrões de data, fuso e
pontuação em colunas numéricas por arquivo/aba; isso descreve a pontuação sem
assumir se vírgula ou ponto representa decimal ou milhar. `NAO_EXECUTADA` indica coluna ou vínculo ausente;
zero só é usado quando a checagem foi feita e nada foi encontrado. Nomes e valores pessoais não são exportados como exemplos. `tipo_bronze`
indica o tipo armazenado no Delta, sem afirmar significado de negócio: os campos
CSV/Excel ficam como texto e o JSON mantém sua estrutura aninhada com os tipos
físicos lidos pelo parser. `_registro_bruto` preserva a representação original
do objeto JSON.

## Silver

`Bronze_to_Silver.ipynb` lê o lote **ativo** da Bronze (`bronze.controle_publicacao`) em `bronze_hist`, com o
`_lote_id` fixado no início. A versão atual prepara as tabelas por execução, reconcilia as saídas, grava o histórico
em `silver_hist` e expõe o run selecionado por `silver.controle_publicacao` nas vistas `silver_publicada.*`.
`silver.controle_silver` registra o estado da execução. Parâmetros: `catalog` (padrão `workspace`) e
`lote_bronze` opcional. Rode `Landing_to_Bronze` e `Bronze_perfilamento` antes: a Silver exige o perfil,
a reconciliação e as identidades de arquivo do mesmo lote.

Datas ambíguas de leitura e emissão permanecem em quarentena (opção B); a seção 13 mede por arquivo
e competência evidências de ordem e consistência das datas inequívocas para análise posterior (opção C),
sem inferir datas na publicação.
Medidores com instalação ambígua ficam em quarentena, e leituras dependentes recebem
`medidor_em_quarentena` como bloqueio em cascata (opção A). A quarentena preserva o payload integral,
inclusive `_registro_bruto`; registros aceitos preservam os metadados técnicos de linhagem.
Conflitos de CPF/CNPJ ou nome de titular ficam nulos e sinalizados na UC. Data futura e
`9999-12-31` são preservadas, sem presumir quitação nem interpretar a sentinela como data real.

- Todo registro que não entra na Silver vai para a quarentena da execução, com motivo, origem, lote e valor de
  controle; seu histórico permanece em `silver_hist.quarentena`.
- As tratativas de `atendimentos_historico` preservam `posicao_historico` (posição no array JSON, a partir de 1),
  além do localizador do protocolo na Bronze; `sequencia` não é usada como chave de linhagem.
- A conta fecha por tabela, arquivo/aba, competência e classe quando aplicável (`bronze = aceitos + quarentenados`),
  em R$ (faturas) e kWh (leituras), e ponta a ponta com os rejeitados do parse da Bronze.
- Se qualquer invariante falhar, o notebook **falha** e não troca o ponteiro de publicação. A Gold deve consultar
  `silver_publicada.*` e conferir que `silver.controle_publicacao` aponta para execução `CONCLUIDO` do lote desejado.
- Estado: a execução mais recente no Databricks é a Silver `20261026T225331Z_c738405b` (lote Bronze
  `20261026T220920Z_9168e7ab`, `CONCLUIDO`), dentro do run completo do Job de 26/10/2026, que precisou de uma
  retomada (repair run) da tarefa da Silver. O roteiro somente leitura `validacao_silver_v1` foi executado sobre ela
  (32 verificações, 0 falhas). A evidência anterior (run `20261024T035426Z_c5ba30e0`: bairros, cronologia de datas,
  classes, valores impossíveis e amostra independente) está no PRD, na entrada de 24/10/2026. O reparo de encoding de
  `bairro` (D61) já valia nessa execução. DE-02 e DE-03 mantêm o estado registrado no PRD.
  Decisões D46–D62 e §11.2–11.4 de [`decisoes-tecnicas.md`](decisoes-tecnicas.md).

## Gold e exportação

`Silver_to_gold.ipynb` usa `workspace.silver_publicada` como fonte de dados e
consulta os controles de publicação e execução da Silver. Ele lê o widget
`AMBIENTE`, aceitando `dev`, `test` ou `prod`; para o Job de entrega, configure
explicitamente `AMBIENTE=prod` e confira o valor no Workspace. Em `dev` e
`test`, o notebook admite execução sintética em condições previstas no código.
O catálogo `workspace` está definido no próprio notebook.

O notebook gera `diagnostico_receita`, `indicadores_dec_fec`, `fila_inspecao`,
`visao_360_uc`, `consumo_mensal_uc`, `consumo_receita_bairro` e
`variacao_consumo_uc`, além do registro `gold.controle_gold`. A fila e a Visão
360 projetam as colunas finais sem CPF/CNPJ, nome, endereço ou metadados internos.
Os indicadores DEC/FEC são simplificados e não comprovam conformidade regulatória.

`Exportacao_Gold_SQLite.ipynb` verifica a existência das sete tabelas e grava
CSV com cabeçalho e separador `;` no Volume
`/Volumes/workspace/gold/gold_export_volume/export_csv`. Cada tabela é gravada
em um diretório próprio, com sobrescrita; a exportação não executa a carga no
banco local nem comprova sua reconciliação. Antes de gravar, o notebook exige que a última execução `CONCLUIDO`
de `gold.controle_gold` seja do ambiente `prod` e falha se não for. Depois dos CSVs, grava o `manifest.json`
no mesmo Volume, com ambiente, lote da Gold, `run_id_silver`, `lote_bronze_silver` e os horários de processamento
e de exportação. Uma falha de escrita ainda pode deixar uma exportação parcial. Cada diretório de tabela traz
também arquivos de controle do Spark (`_committed_*`, `_started_*`); o carregador do backend lê só `*.csv`. Confirme o catálogo, o destino e as
permissões do Volume antes de executar e não versione os CSVs do case.

A Gold oficial é `GOLD_20261027T014656Z_81c5530b` (Silver `20261026T225331Z_c738405b`, ambiente `prod`),
executada isoladamente no Job em 26/10/2026. O roteiro somente leitura `validacao_gold_v4` foi executado sobre
ela, com 0 falhas, e confere a reconciliação Silver × Gold, as colunas das tabelas por UC e o encoding. Os controles
de referência C01–C12 (PR #60) foram recalculados em Spark SQL sobre as tabelas Delta, sem divergência. As
verificações finais da Gold ocorrem depois de gravações das tabelas; uma falha não garante que a versão anterior
permaneça publicada.
O teste de DEC recalcula a amostra da Silver, mas usa um alimentador e um mês
fixos e não valida toda a tabela nem o FEC.

## Executar no Databricks

1. Coloque a extração autorizada no Volume informado por `raw`. Não adicione
   arquivos do case ao Git.
2. Importe os notebooks no Workspace e confira o Job `v-energy-grid-360`: a ordem
   necessária é `Landing_to_Bronze` → `Bronze_perfilamento` → `Bronze_to_Silver`
   → `Silver_to_gold` → `Exportacao_Gold_SQLite`. Configure as dependências,
   os caminhos do seu Workspace e os parâmetros aplicáveis, incluindo
   `AMBIENTE=prod` para a Gold oficial. O YAML versionado registra as cinco
   tarefas, com os caminhos do Workspace de origem; o agendamento está comentado (proposta, não ativada).
3. Rode o Job manualmente e confira as 12 identidades de arquivo e as 14 origens
   reconciliadas (cinco CSVs
   simples/faturas, cinco leituras, JSON e três abas), além das oito tabelas de
   dados, rejeitados, arquivos, controle e perfil.
4. Compare a contagem lógica da origem com aceitos + rejeitados por arquivo/aba.
   Confira hash, linhas físicas de exemplos autorizados, uma falha induzida e
   uma reexecução da mesma versão. Registre IDs dos runs, comandos e resultados
   no Registro de progresso do PRD antes de concluir DE-01.
5. Confira a execução da Silver e suas vistas publicadas; execute a versão atual
   da Gold com o parâmetro adequado e revise os controles e a reconciliação.
   Execute a exportação somente após validar as saídas, confira os CSVs e registre
   as evidências. A carga no banco local é uma etapa separada do notebook de
   exportação; registre o processo e os resultados de reconciliação utilizados.

O YAML versionado registra a configuração do Job de cinco tarefas, sem agendamento ativo. Confira os valores
e a configuração atual no Workspace antes de executar os notebooks.

## Estratégia de agendamento (proposta, não ativada)

Execução mensal, no dia 5, às 03:00 (America/Recife). Decisão do time pendente.

- O insumo é mensal por natureza: leituras e faturas são por competência; rodar mais de uma vez no mês não traria
  dado novo, só custo.
- O dia 5 dá folga para o fechamento da competência anterior chegar íntegro.
- Reexecutar é seguro: a Bronze é carregada por sobrescrita e reconciliada em `bronze.reconciliacao` com
  `delta = 0`, então um rerun reconstrói o mesmo resultado em vez de duplicar linhas.
- Descartado: gatilho de chegada de arquivo (`On file arrival`), porque no dataset os arquivos entram em lote e
  cada chegada dispararia uma execução. Se a origem passar a depositar arquivo solto, este é o caminho.
- Não aplicar a sugestão automática "On table update" do Databricks: a própria Silver atualiza as tabelas de
  controle, e o Job dispararia a si mesmo.

## Evidência anterior

![Workflow com as duas tarefas concluídas](evidencias/workflow/workflow-graph.png)

O run `14313419965490` de 18/10/2026 terminou em `Succeeded` em 21m 03s e
comprovou o encadeamento das duas tarefas **na versão anterior**. O print do Workflow de cinco tarefas será
acrescentado depois do run limpo de ponta a ponta. Ele não
valida o scanner, as vistas, o perfil por origem nem a migração desta mudança.
