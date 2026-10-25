# Engenharia de dados — Bronze

Escopo desta entrega: DE-01 e perfil descritivo da Bronze. Valores ausentes,
duplicatas, datas ambíguas e vínculos inconsistentes são medidos e preservados;
tratamento e decisão de negócio pertencem à Silver. O contrato completo está no
[PRD](../docs/PRD.md) e no [guia do serviço](../docs/services/data-engineering.md).

## Arquivos

| Arquivo | Papel |
| --- | --- |
| [`Landing_to_Bronze.ipynb`](notebook/Landing_to_Bronze.ipynb) | Ingestão, rejeitados, reconciliação por origem e publicação |
| [`Bronze_perfilamento.ipynb`](notebook/Bronze_perfilamento.ipynb) | Inventário, achados e relações por arquivo/aba |
| [`Bronze_to_Silver.ipynb`](notebook/Bronze_to_Silver.ipynb) | Silver: limpeza, tipos, chaves, quarentena, reconciliação e portão de qualidade |

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
- Estado: a versão atual foi executada no Databricks com o dataset real em 24/10/2026 (run
  `20261024T035426Z_c5ba30e0`, lote Bronze `20261021T223955Z_f875fb45`, `CONCLUIDO`, 0 falhas de invariante, 19 min 25 s).
  A evidência de qualidade (bairros, cronologia de datas, classes, valores impossíveis e amostra independente) está
  registrada no PRD (entrada de 24/10/2026) e pode ser reproduzida com o roteiro somente leitura `validacao_silver_v1`.
  O Job `v-energy-grid-360` já tem as quatro tarefas montadas (Landing_to_Bronze, Bronze_perfilamento, Bronze_to_Silver
  e Silver_to_gold), mas a tarefa Gold ainda aponta para uma versão antiga e será trocada pela versão final antes do run
  completo. O YAML versionado ainda reflete só as duas tarefas da Bronze e será exportado depois desse run.
  DE-02 e DE-03 permanecem em validação até o run final.
  Decisões D46–D60 e §11.2–11.4 de [`decisoes-tecnicas.md`](decisoes-tecnicas.md).

## Executar no Databricks

1. Coloque a extração autorizada no Volume informado por `raw`. Não adicione
   arquivos do case ao Git.
2. Importe os notebooks no Workspace e configure ou atualize o Job `v-energy-grid-360`
   na interface do Databricks, com `Landing_to_Bronze` antes de `Bronze_perfilamento`.
   O YAML versionado registra o Workflow existente e mantém os caminhos exportados
   do Workspace de origem; ajuste os caminhos na interface para os notebooks do seu
   Workspace. Se necessário, defina os parâmetros `catalog`, `raw` e `lote_origem`
   nas tarefas do Job.
3. Rode o Job manualmente e confira as 12 identidades de arquivo e as 14 origens
   reconciliadas (cinco CSVs
   simples/faturas, cinco leituras, JSON e três abas), além das oito tabelas de
   dados, rejeitados, arquivos, controle e perfil.
4. Compare a contagem lógica da origem com aceitos + rejeitados por arquivo/aba.
   Confira hash, linhas físicas de exemplos autorizados, uma falha induzida e
   uma reexecução da mesma versão. Registre IDs dos runs, comandos e resultados
   no Registro de progresso do PRD antes de concluir DE-01.

O YAML versionado registra a configuração de execução existente, incluindo o
compute serverless e o agendamento. Confira esses valores no Workspace antes de
executar a versão atual do notebook.

## Evidência anterior

![Workflow com as duas tarefas concluídas](evidencias/workflow/workflow-graph.png)

O run `14313419965490` de 18/10/2026 terminou em `Succeeded` em 21m 03s e
comprovou o encadeamento das duas tarefas **na versão anterior**. Ele não
valida o scanner, as vistas, o perfil por origem nem a migração desta mudança.
