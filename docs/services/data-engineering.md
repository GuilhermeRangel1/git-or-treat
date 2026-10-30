# Serviço: engenharia de dados

**Escopo:** DE-01 a DE-09 do [PRD](../PRD.md). **Estado:** há registros de execução da Bronze e da Silver no Databricks; a Silver `20261024T035426Z_c5ba30e0` terminou `CONCLUIDO` em 24/10/2026, com zero falhas. A branch `feat/gold` contém os notebooks de Gold e exportação. O PR #36 registra a execução da Gold na versão `c95bfc3`; em 27/10/2026, a pessoa usuária confirmou que execução, reconciliação e Workflow já foram validados. Os identificadores e resultados dessa validação mais recente ainda devem ser vinculados ao PRD. O YAML versionado registra uma configuração anterior, com duas tarefas da Bronze. **Tecnologia exigida:** Databricks, PySpark e tabelas Delta para Bronze/Silver/Gold.

## Responsabilidade

Converter oito conjuntos legados em tabelas Gold confiáveis para portal, IA e diagnóstico. A fonte bruta deve permanecer reprocessável e rastreável. A Silver resolve qualidade e relacionamento. A Gold publica métricas com granularidade explícita. O Workflow reproduz tudo e exporta Gold em CSV para banco local.

## Entradas

`unidades_consumidoras.csv`, cinco CSVs de `leituras/`, `faturas.csv`, `medidores.csv`, `ocorrencias_rede.csv`, `atendimentos.json`, `geracao_distribuida.csv` e as três abas de `inspecoes.xlsx`. Volumes, semântica e cuidado com aproximações estão no PRD §4. A extração virá de `.zip` na plataforma da atividade; não assumir caminhos ou esquema até recebê-la.

### Inventário de descoberta ao receber o `.zip`

Para cada arquivo/aba, registrar tamanho, período aparente, encoding, delimitador/separador, quantidade física e lógica de registros, colunas/caminhos JSON, tipo físico armazenado e padrões observados de parseabilidade,
nulos, duplicatas e valores fora de domínio. A Bronze não converte os campos brutos para
inferir tipos semânticos. Separar erro de leitura do arquivo de erro de regra de negócio. O JSON de atendimento e o Excel de inspeção exigem cuidado especial: uma lista aninhada ou uma aba auxiliar pode mudar o grão e inflar contagens. Documentar o que cada aba representa antes de fazer união.

Montar um mapa de relacionamento **com chaves verificadas**, cobrindo UC, cliente, medidor, competência, fatura, ocorrência, chamado e inspeção. Registrar cardinalidade e vigência temporal. Para fontes sem chave suficiente, explicitar a limitação do fluxo dependente em vez de criar join por semelhança de texto.

## Contrato por camada

| Camada | Deve preservar/publicar | Checagem de saída |
| --- | --- | --- |
| Bronze | Conteúdo original, arquivo/aba de origem, lote de origem, versão/hash, execução, momento de ingestão e rejeições de parse separadas | Contagem de registros lógicos contra aceitos + rejeitados por fonte, checksum e acesso ao trecho bruto; nenhuma correção silenciosa |
| Silver | Tipos, datas, chaves, categorias e medidas padronizadas; regras de deduplicação e exceções documentadas | Nulos, duplicatas, órfãos, intervalos impossíveis e reconciliação por fonte/período |
| Gold | Tabelas para indicadores, receita, UC, inspeção e continuidade, com dimensão de tempo/geografia/classe | Chaves e granularidade declaradas; agregações reproduzíveis; dicionário completo |

### Invariantes de qualidade por transição

- **Bronze:** reprocessar o mesmo lote deve conservar o conteúdo e permitir localizar arquivo/aba/registro de origem. Quando um formato não for interpretável, contar e isolar a falha sem alterar silenciosamente o restante. O perfil registra, por arquivo/aba, padrões observados de data, fuso e pontuação numérica sem inferir decimal versus milhar.
- **Silver:** toda regra que remove, substitui ou agrega registros precisa de contagem antes/depois e motivo. A soma de aceitos, quarentenados e rejeitados deve reconciliar com a entrada adequada ao grão, por arquivo/aba, competência e classe quando aplicável. A versão em preparo não substitui as vistas publicadas antes da validação.
- **Silver:** datas ambíguas de leitura/emissão permanecem em quarentena (B), enquanto o diagnóstico C mede evidências por arquivo sem inferir datas; medidor com instalação ambígua fica em quarentena, e leituras dependentes são bloqueadas com `medidor_em_quarentena` (A); CPF/CNPJ ou nome conflitante não é escolhido por completude; data registrada ou futura não comprova quitação, e `9999-12-31` é preservada sem uso como data real. Rejeitados preservam payload integral em `silver_hist.quarentena._registro`; aceitos carregam metadados técnicos de linhagem. Consulte D36–D38 e D48–D60 em [decisões técnicas](../../data-engineering/decisoes-tecnicas.md). A evidência de 24/10 está no PRD; a pessoa usuária confirmou que execução, reconciliação e Workflow foram validados e os identificadores mais recentes devem ser registrados.
- **Gold:** publicar uma métrica apenas depois de declarar grão, chave, fórmula e população. Verificar que joins não multiplicam receita/energia e que recortes geográficos/classes somam ao total quando compõem uma partição válida.
- **Exportação:** carregar CSVs Gold em banco local de modo repetível; segunda carga do mesmo lote não duplica linhas ou valores. Comparar contagem, chave e amostras de agregados em ambos os lados.

### Contrato de entrada da Gold

A Gold deve ler apenas `silver_publicada.*` depois de conferir uma única linha `silver.controle_publicacao` para `chave = 'silver'`, com `run_ativo`, `lote_ativo` e estado `CONCLUIDO` correspondente em `silver.controle_silver`. A mesma execução e o mesmo lote devem aparecer em todas as tabelas consumidas; tabelas de preparo, `silver_hist` e quarentena não são entrada de métricas. Antes de liberar exportação, conferir permissões efetivas: somente operadores autorizados podem ler Bronze, histórico, quarentena e campos pessoais da Silver. Não conceder acesso direto da aplicação ou da IA a esses objetos.

| Vista Silver | Grão e chave para consumo | Limite para agregação |
| --- | --- | --- |
| `unidades_consumidoras` | Uma UC por `id_uc` aceito | Cadastro atual não prova titularidade ou classe histórica; CPF/CNPJ, nome, endereço, CEP e coordenadas são excluídos da projeção Gold/CSV, sem hash ou mascaramento (D20). |
| `medidores` | Um medidor por `id_medidor` aceito | Datas ambíguas de instalação ficam fora; não inferir troca ou vigência não observada. |
| `leituras` | Uma leitura por `id_leitura` aceito | `consumo_kwh` soma no grão de leitura; datas ambíguas e vínculos bloqueados ficam fora, flags de vigência e leitura decrescente seguem para avaliação. |
| `faturas` | Uma fatura por `id_fatura` aceito | `valor_total` é R$ decimal com duas casas; competência e classe não tornam fatura única por UC. Status ou data isolada não comprovam pagamento; sentinela não é data real. |
| `geracao_distribuida` | Uma linha por `id_uc` aceito | Potência instalada e média de injeção não provam geração/compensação por competência. |
| `ocorrencias_rede` | Uma ocorrência por `id_ocorrencia` aceito | Duração e UC afetada não bastam para DEC/FEC regulatório; investigar `_duracao_incompativel`. |
| `atendimentos` | Um protocolo por `protocolo` aceito | `qtd_tratativas` não é número de protocolos; nota inválida fica nula e sinalizada. |
| `atendimentos_historico` | Uma tratativa por `(protocolo, posicao_historico)` | `sequencia` do JSON não é chave confiável; não somar chamados após explodir tratativas. |
| `inspecoes` | Uma inspeção por `id_inspecao` aceito, com `_aba_origem` | Resultado desconhecido continua explícito; inspeção histórica não é ordem operacional criada no portal. |

Toda linha aceita mantém `_arquivo_origem`, `_ordem_na_origem`, `_lote_id` e `_id_registro`; inspeções mantêm `_aba_origem` e tratativas mantêm `posicao_historico`. Esses campos são para auditoria, não dimensões de negócio. A população excluída e os motivos são recuperáveis no histórico da quarentena por execução; cobertura e impacto devem acompanhar qualquer métrica publicada. Juntar fatos pela UC antes de agregar pode multiplicar valores, portanto agregar cada fato no próprio grão e só depois unir os resultados. O dicionário Gold descreve as onze saídas candidatas; o aceite DE-08 depende de validar os schemas e limitações no lote autorizado.

### Implementação Gold e exportação disponíveis na branch

`Silver_to_gold.ipynb` lê somente as vistas `silver_publicada.*`, materializando cada fonte com `localCheckpoint(eager=True)` e conferindo execução/lote antes/depois. O checkpoint corta a dependência lazy do ponteiro Silver; perda dos blocos interrompe a execução e requer refazer o Job inteiro. Não há fallback para `silver_hist`. Referência da API Spark: [DataFrame.localCheckpoint](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.localCheckpoint.html); disponível desde Spark 2.3, sem pressupor uma versão específica do Runtime ainda não validado.

São sete tabelas analíticas e quatro históricos por UC, descritos no [dicionário](../dicionario_gold.md). Preparo isolado e recuperação de falhas capturadas preservam candidatos até a validação; não há atomicidade entre onze tabelas. Configurar uma execução por vez e Gold → exportação sequenciais. Falha abrupta exige conferência/recuperação antes de exportar. Não inferir pagamento comprovado, valor em aberto ou medidor ativo sem evidência suficiente.

`Exportacao_Gold_SQLite.ipynb` prepara o contrato candidato `gold-csv-v2`: exige controle produtivo validado das onze tabelas, fixa versões Delta, grava em diretório exclusivo por tentativa, relê CSVs com os tipos originais e só libera manifesto após reconciliar registros e revalidar identidade/versões. CSVs usam UTC, precisão decimal e nulo explícito. O parâmetro `run_id` só pode confirmar o lote do controle. Tentativa sem manifesto não é publicação válida; repetir exportação cria outra tentativa sem apagar a anterior.

O Backend atual aceita sete tabelas no contrato v1 e rejeita v2. Migração, carga v2 e integração API/portal/GenAI continuam entregas separadas; não copiar dados reais para o repositório nem concluir DE-06/WEB-03 por esta preparação. A execução do Job real e a reconciliação até o banco ainda precisam de evidência autorizada.

## Pontos críticos de modelagem

- **UC e tempo:** distinguir cadastro atual de histórico, troca de medidor, múltiplas faturas e múltiplos atendimentos. Nunca unir fatos crus por UC e somar valores antes de controlar cardinalidade.
- **Receita:** distinguir faturado e pago, competência e vencimento, tarifa homologada e preço efetivo. A decomposição preço-volume deve fechar com o total, inclusive termo de interação conforme método escolhido.
- **Inspeção:** separar suspeita, ordem operacional e resultado de fiscalização. `inspecoes.xlsx` é entrada histórica; ordens novas do portal são dados operacionais do backend.
- **Rede:** documentar numerador, denominador, abrangência e período do DEC/FEC simplificado. A fórmula não deve ser descrita como apuração regulatória oficial.
- **GD:** medir apenas o que os campos permitem. Potência instalada isolada não prova energia gerada ou abatida por competência.

## Workflow e atualização

O Job deve mostrar dependências explícitas entre ingestão, tratamento, Gold e exportação, com parâmetros de ambiente/lote, status observável, logs úteis e falha que interrompe publicação de dados inválidos. Testar uma execução completa e uma reexecução do mesmo lote. Se uma etapa falhar, registrar quais saídas permanecem válidas e como retomar sem mistura de versões.

O YAML versionado em [`v-energy-grid-360.yaml`](../../data-engineering/configuracao/databricks/v-energy-grid-360.yaml) registra uma configuração anterior com `Landing_to_Bronze` → `Bronze_perfilamento` e caminhos do Workspace de origem. O run `14313419965490` (21m 03s, `Succeeded`) comprova essa versão anterior das duas tarefas. A pessoa usuária confirmou que o Workflow também foi validado; o identificador e os detalhes dessa validação ainda devem ser associados ao PRD, e o YAML versionado deve refletir a configuração efetivamente executada. A evidência histórica está no [README do módulo](../../data-engineering/README.md#evidência-anterior).

O case fornece uma extração única e pede que o time proponha agendamento para uma operação futura. A periodicidade, a janela de chegada das fontes, o tratamento de atrasos/retificações e o custo da atualização são decisões a justificar após inspecionar o material. Não apresentar uma simulação de agenda como integração de produção existente.

Agenda proposta para essa operação futura: **mensal, dia 5, às 03:00 (America/Recife)** — o insumo é mensal por natureza; o dia 5 dá folga ao fechamento. A configuração exportada registra o agendamento da versão anterior do Workflow; a proposta operacional precisa ser confirmada para a operação futura. A versão nova prepara cada execução em schema próprio, preserva lotes em `bronze_hist` e muda uma linha em `bronze.controle_publicacao` para selecionar o lote exposto pelas vistas `bronze.*`. A janela real de chegada continua desconhecida.

## Dependências e decisões pendentes

| Decisão | Depende de | Documento de saída |
| --- | --- | --- |
| Chaves e mudanças históricas de UC/medidor | Perfil do cadastro, leituras e medidores | Dicionário Gold e, se material, ADR |
| Regra de faturas duplicadas/canceladas | Campos e distribuição reais das faturas | Relatório de qualidade e definição de receita |
| Modelo Gold | Perguntas do portal, IA e diagnóstico; grãos disponíveis | Dicionário e contrato de exportação |
| DEC/FEC simplificado | Ocorrências, vínculo com UC/alimentador e denominador temporal | Fórmula, amostra manual e limites |
| Agenda do Workflow | Periodicidade definida (mensal, dia 5, 03:00, America/Recife); a janela operacional e o atraso das fontes continuam não fornecidos pelo case | [Agenda proposta](../../data-engineering/README.md#agenda-proposta) |

## Entregáveis futuros

1. Notebooks PySpark ou equivalente versionado, parâmetros e instruções de execução.
2. Atualização e validação da definição YAML/JSON do Databricks Workflow com dependências Bronze → perfilamento → Silver → Gold → exportação e parâmetros do Job; o YAML versionado registra apenas as duas tarefas da Bronze.
3. Relatório de perfil e qualidade por origem, decisões de tratamento e testes automatizados se DE-09 for perseguido.
4. CSVs Gold exportados no ambiente de execução, esquema e processo de carga ao banco local; dados reais não entram no Git sem autorização.
5. [Dicionário de dados](../dicionario_gold.md) preenchido a partir do dataset real.

## Aceite do serviço

Rodar a extração completa de ponta a ponta e comparar contagens, chaves e métricas em cada transição. Exercitar reexecução sem duplicação. Demonstrar pelo menos um cálculo manual por métrica crítica e uma falha de qualidade detectada. Registrar comandos, Job run e resultados no PRD; concluir os IDs separadamente.


## Integração local dos CSVs v1 — 27/10/2026

As sete exportações da `feat/gold` foram recebidas localmente e têm um [contrato físico provisório](../contracts/gold-csv-v1.md), observado nos cabeçalhos. O backend implementa carga transacional/repetível para tabelas próprias `gold_*`, com validação CSV → banco. Isso não homologa fórmulas, não prova reconciliação Delta → CSV e não corrige a publicação antecipada ou o exportador da branch Gold. O dicionário canônico DE-08, manifesto de execução Gold e adaptação dos consumidores permanecem pendentes. Este adendo atualiza apenas a disponibilidade da carga local; evidências históricas anteriores continuam delimitadas às versões executadas.

### Atualização da entrada local — preparação GENAI-01, 28/10/2026

A carga Backend agora exige o manifesto de origem e vincula sua linhagem à publicação local. A versão ausente do exportador atual requer argumento explícito `--schema-version gold-csv-v1`; a carga não substitui IDs ausentes por valores de reserva. No PostgreSQL, as relações analíticas locais ficam no schema `gold`, sem alterar os nomes/colunas exportados. Veja [contrato](../contracts/gold-csv-v1.md#origem-e-publicação) e [runbook](../contracts/gold-load-dev12.md#preparação-para-genai-01-schema-origem-e-publicação). Controles de contagens, chaves e somas da origem para o mesmo lote ainda são necessários para comprovar Delta → CSV → banco; esta preparação não modifica notebooks nem homologa métricas.
