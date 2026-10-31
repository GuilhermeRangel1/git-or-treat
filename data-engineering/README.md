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
| [`Exportacao_Gold_SQLite.ipynb`](notebook/Exportacao_Gold_SQLite.ipynb) | Exportação candidata v2 de quinze tabelas analíticas Gold em CSV para um Volume |

O [contrato candidato CSV v2](../docs/contracts/gold-csv-v2.md) reúne as diferenças de inventário, manifesto, tipos e nulos que precisam de compatibilização com o Backend. Essa preparação não ativa a carga ou o consumo v2.

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
  `20261026T220920Z_9168e7ab`, `CONCLUIDO`), dentro do run do Job de 26/10/2026 (quatro das cinco tarefas, sem Exportacao_Gold), que precisou de uma
  retomada (repair run) das tarefas Bronze_to_SilvereSilver_to_gold. O roteiro somente leitura `validacao_silver_v1` foi executado sobre ela
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

O notebook gera quinze projeções analíticas: as sete tabelas iniciais, os
quatro históricos (`faturas_uc`, `medidor_uc`, `atendimentos_uc`,
`ocorrencias_uc`) e `gd_uc`, `tratativas_uc`, `cobertura_dominios` e
`decomposicao_receita`. Também
gera `controle_gold` e o cadastro restrito `gold_cadastro.cadastro_titular_uc`.
As fontes publicadas são materializadas e conferidas por execução/lote. Os
candidatos são validados em schema próprio antes da promoção; dev/test não
sobrescrevem a Gold produtiva. DEC/FEC permanecem indicadores simplificados.

Na semântica candidata v2, faturas e leituras são pré-agregadas por UC/mês e preservadas como populações independentes. O diagnóstico e o recorte territorial separam faturamento com e sem leitura; a série mensal conserva receita, consumo, flags e contagens de observações. A tarifa observada usa somente pares com fatura e leituras integralmente válidas. Isso não comprova cobertura completa, energia efetivamente faturada, valor pago ou tarifa homologada. O saldo em aberto individual é um valor indicativo derivado do status e das flags, não um saldo contábil nem inclui pagamentos parciais; situações inconclusivas ficam nulas. O consumidor v1 ainda não aceita o contrato v2.

A fila também publica `motivo_prioridade`, alinhado à primeira regra de triagem aplicada; isso não estima energia recuperável por si só. O estudo candidato separado compara a média global de kWh registrados por inspeção com médias históricas opcionais por grupo, usando treino, calibração e teste temporais. As referências aprovadas pelos critérios internos são publicadas em campos próprios de média histórica, intervalo, origem global/grupo e estado; os campos de estimativa individual continuam nulos. O aceite do WEB-04 segue pendente. Método e critérios provisórios estão descritos no dicionário e ainda exigem revisão de Dados/Produto e validação no lote real. `faturas_uc` expõe situação declarada e saldo indicativo por fatura, mantendo nulo quando status/flags conflitam ou são inconclusivos. `medidor_uc` preserva vínculo e datas e inclui uma situação temporal candidata por registro; sobreposições permanecem separadas. A regra de status/saldo e a vigência dos medidores também permanecem sujeitas à validação de Dados/Produto.

O exportador exige controle produtivo com as quinze tabelas analíticas e fixa versões Delta.
Cada tentativa grava em
`/Volumes/workspace/gold/gold_export_volume/export_csv/<run_id_gold>/<export_id>/`.
CSV usa UTF-8, separador `;`, aspas duplicadas, datas ISO, timestamps UTC e nulo
explícito distinto de texto vazio. Os CSVs são relidos e comparados antes de
publicar o manifesto por arquivo temporário. Falhas deixam tentativa sem
manifesto válido e preservam exportações anteriores. Não consumir pastas sem
manifesto completo e validado; não misturar arquivos de tentativas diferentes.

O contrato candidato `gold-csv-v2` exige migração/carga v2 no Backend; o carregador
v1 atual deve rejeitá-lo. Confira campos, populações e limites no
[dicionário Gold](../docs/dicionario_gold.md). Não versione os CSVs do case.

Gold → exportação devem executar em sequência, sem Jobs concorrentes. Não há
transação entre quinze tabelas analíticas; falha abrupta na promoção exige recuperação antes
de exportar. A evidência histórica do PR #36 não valida estas alterações: o Job
atual e a reconciliação até o banco ainda precisam de execução autorizada.

Evidência histórica: a Gold oficial `GOLD_20261027T014656Z_81c5530b` (Silver `20261026T225331Z_c738405b`) foi conferida em 26/10/2026 pelos roteiros `validacao_gold_v4` e controles C01–C12 do PR #60, sem divergências reportadas. Essa validação é da versão anterior e não cobre as alterações candidatas desta branch (novas projeções analíticas, cadastro restrito e publicação em dois manifestos). O Job atual e a reconciliação até o consumidor ainda precisam de validação autorizada.

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


### Complementos da visão 360 e nome restrito — 30/10/2026

O notebook Gold publica `gd_uc` com potência em kWp, conexão/modalidade e flags, e `tratativas_uc` no grão `(protocolo, posicao_historico)`. O histórico preserva eventos e datas disponíveis, divulga apenas categorias/canais da lista explícita e sinaliza os demais conteúdos como restritos. Sequência repetida não é erro de chave; ausência de data não é preenchida. Chaves, vínculos, contagens por protocolo e tipos são verificados antes da promoção.

O nome de exibição fica somente em `gold_cadastro.cadastro_titular_uc`, com schema de preparo separado, nulo quando ausente/conflitante e sem documentos pessoais. Não integra as quinze tabelas do pacote analítico nem o contexto GenAI. A exportação cadastral é obrigatória na entrega completa (`exportar_cadastro_restrito=sim`, único valor aceito), requer Volume cadastral provisionado e gera manifesto `gold-cadastro-v1` com vínculo à mesma tentativa analítica. Permissões reais, migração, carga e mapeamento do nome pelo Backend/portal precisam ser feitos pelos consumidores; o leitor analítico não recebe acesso ao cadastro.

Detalhes e critérios do consumidor: [contrato cadastral restrito](../docs/contracts/gold-cadastro-v1.md).

O processamento do cadastro requer `CADASTRO_RESTRITO_VALIDADO=sim` e schemas cadastrais de publicação/preparo existentes e validados pelo operador. O notebook não cria esses schemas nem concede acessos.


### Controle mensal de cobertura — 30/10/2026

`cobertura_dominios` registra domínios/competências e ocorrências por alimentador, com contagens observadas, lacunas, referência temporal e estado de cobertura. Janela explícita pelos parâmetros `COBERTURA_INICIO`/`COBERTURA_FIM`; sem eles usa limites observados sem certificar seus extremos. Declarações opcionais `COBERTURA_DECLARACOES_JSON` exigem identidade de origem, referência de evidência e corte com offset. Sem declaração, o estado é `NAO_CERTIFICADA`; linha ausente não vira zero confirmado. Cadastros GD/medidor não certificam histórico mensal, e declarações contraditórias entre domínio/alimentador são recusadas.

A contagem representa o snapshot fixado; `data_corte_evidencia` representa o corte da evidência externa, podendo ser anterior à referência da observação em meses parciais. O consumidor não pode apresentar essa contagem como total naquele corte. O exportador inclui o controle como 14ª tabela analítica, com tipos e contagem no manifesto. Definições e limites: [contrato de cobertura](../docs/contracts/gold-cobertura-v1.md).

A exportação completa verifica o destino cadastral antes de gravar e exige os dezesseis conjuntos reconciliados. Os manifestos são publicados em sequência (cadastro e analítico), com referências cruzadas e recuperação de falhas capturadas; o consumidor exige sucesso do Job e ambos os manifestos. Nenhuma transação entre Volumes é presumida.


### Preço-volume exportável — preparação de 30/10/2026

A 15ª projeção analítica `decomposicao_receita` registra a comparação de duas janelas por município/bairro/classe. Configurar as quatro competências `PRECO_VOLUME_INICIO_P0`, `PRECO_VOLUME_FIM_P0`, `PRECO_VOLUME_INICIO_P1`, `PRECO_VOLUME_FIM_P1`. Sem configuração, publica tabela vazia tipada e estado `NAO_CONFIGURADA`; isso elimina a possibilidade de reutilizar silenciosamente a análise anterior. Com configuração, a disponibilidade depende da cobertura e da base comum observada, sinalizadas nas linhas.

A tabela participa do preparo, qualidade, promoção/recuperação e releitura CSV. O controle/manifesto inclui configuração, referência dos dados e limitações das medidas. A referência dos dados é distinta do horário de conclusão Gold. A entrega completa tem 15 projeções analíticas e um cadastro restrito, em dois pacotes. Método, campos e limites: [dicionário Gold](../docs/dicionario_gold.md#diagnóstico-preço-volume-no-notebook--preparação-de-30102026) e [contrato v2](../docs/contracts/gold-csv-v2.md). O consumidor precisa atualizar carga/mapeamento; esta implementação não conclui aceites com dados reais.

### Regras complementares candidatas — 30/10/2026

Faturas distinguem valor nominal declarado em aberto de saldo indicativo e recebimento. Cobertura v2 distingue extração reconciliada de fechamento contábil, com contagens por intervalo e referência ao inventário; nenhuma certificação é criada automaticamente por haver linhas. A decomposição inclui bairro na mesma base UC/mês.

A fila publica médias históricas de recuperação por inspeção, com intervalo calibrado, referência global/grupo e estado explícito. A referência global é compartilhada na fila; grupos com ganho de calibração e validação temporal usam sua própria média apenas onde há histórico elegível. Ausência permanece nula. As médias não devem ser somadas entre UCs e o intervalo representa dispersão por inspeção, não precisão da média ou garantia de recuperação da UC. Os campos de estimativa individual permanecem nulos. O dicionário e o contrato candidato v2 descrevem o novo schema; execução real, adaptação dos consumidores e aceite do WEB-04 ainda são necessários.
