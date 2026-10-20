# Serviço: engenharia de dados

**Escopo:** DE-01 a DE-09 do [PRD](../PRD.md). **Estado:** Bronze implementada e executada na Databricks Free Edition (17/10/2026; a versão com publicação por lote rodou em 19/10/2026) e o Workflow `v-energy-grid-360` criado em 18/10/2026 com as duas tarefas da Bronze encadeadas (PR #8 em revisão); Silver implementada e em validação (em PR separado); Gold e exportação ainda não existem. **Tecnologia exigida:** Databricks, PySpark e tabelas Delta para Bronze/Silver/Gold.

## Responsabilidade

Converter oito conjuntos legados em tabelas Gold confiáveis para portal, IA e diagnóstico. A fonte bruta deve permanecer reprocessável e rastreável. A Silver resolve qualidade e relacionamento. A Gold publica métricas com granularidade explícita. O Workflow reproduz tudo e exporta Gold em CSV para banco local.

## Entradas

`unidades_consumidoras.csv`, cinco CSVs de `leituras/`, `faturas.csv`, `medidores.csv`, `ocorrencias_rede.csv`, `atendimentos.json`, `geracao_distribuida.csv` e as três abas de `inspecoes.xlsx`. Volumes, semântica e cuidado com aproximações estão no PRD §4. A extração virá de `.zip` na plataforma da atividade; não assumir caminhos ou esquema até recebê-la.

### Inventário de descoberta ao receber o `.zip`

Para cada arquivo/aba, registrar tamanho, período aparente, encoding, delimitador/separador, quantidade física e lógica de registros, colunas/caminhos JSON, tipos inferidos, nulos, duplicatas e valores fora de domínio. Separar erro de leitura do arquivo de erro de regra de negócio. O JSON de atendimento e o Excel de inspeção exigem cuidado especial: uma lista aninhada ou uma aba auxiliar pode mudar o grão e inflar contagens. Documentar o que cada aba representa antes de fazer união.

Montar um mapa de relacionamento **com chaves verificadas**, cobrindo UC, cliente, medidor, competência, fatura, ocorrência, chamado e inspeção. Registrar cardinalidade e vigência temporal. Para fontes sem chave suficiente, explicitar a limitação do fluxo dependente em vez de criar join por semelhança de texto.

## Contrato por camada

| Camada | Deve preservar/publicar | Checagem de saída |
| --- | --- | --- |
| Bronze | Conteúdo original, arquivo/aba de origem, lote, momento de ingestão e rejeições de parse separadas | Contagens e checksums por fonte quando possível; nenhuma correção silenciosa |
| Silver | Tipos, datas, chaves, categorias e medidas padronizadas; regras de deduplicação e exceções documentadas | Nulos, duplicatas, órfãos, intervalos impossíveis e reconciliação por fonte/período |
| Gold | Tabelas para indicadores, receita, UC, inspeção e continuidade, com dimensão de tempo/geografia/classe | Chaves e granularidade declaradas; agregações reproduzíveis; dicionário completo |

### Invariantes de qualidade por transição

- **Bronze:** reprocessar o mesmo lote deve conservar o conteúdo e permitir localizar arquivo/aba/registro de origem. Quando um formato não for interpretável, contar e isolar a falha sem alterar silenciosamente o restante.
- **Silver:** toda regra que remove, substitui ou agrega registros precisa de contagem antes/depois e motivo. A soma de aceitos, quarentenados e rejeitados deve reconciliar com a entrada adequada ao grão.
- **Gold:** publicar uma métrica apenas depois de declarar grão, chave, fórmula e população. Verificar que joins não multiplicam receita/energia e que recortes geográficos/classes somam ao total quando compõem uma partição válida.
- **Exportação:** carregar CSVs Gold em banco local de modo repetível; segunda carga do mesmo lote não duplica linhas ou valores. Comparar contagem, chave e amostras de agregados em ambos os lados.

## Pontos críticos de modelagem

- **UC e tempo:** distinguir cadastro atual de histórico, troca de medidor, múltiplas faturas e múltiplos atendimentos. Nunca unir fatos crus por UC e somar valores antes de controlar cardinalidade.
- **Receita:** distinguir faturado e pago, competência e vencimento, tarifa homologada e preço efetivo. A decomposição preço-volume deve fechar com o total, inclusive termo de interação conforme método escolhido.
- **Inspeção:** separar suspeita, ordem operacional e resultado de fiscalização. `inspecoes.xlsx` é entrada histórica; ordens novas do portal são dados operacionais do backend.
- **Rede:** documentar numerador, denominador, abrangência e período do DEC/FEC simplificado. A fórmula não deve ser descrita como apuração regulatória oficial.
- **GD:** medir apenas o que os campos permitem. Potência instalada isolada não prova energia gerada ou abatida por competência.

## Workflow e atualização

O Job deve mostrar dependências explícitas entre ingestão, tratamento, Gold e exportação, com parâmetros de ambiente/lote, status observável, logs úteis e falha que interrompe publicação de dados inválidos. Testar uma execução completa e uma reexecução do mesmo lote. Se uma etapa falhar, registrar quais saídas permanecem válidas e como retomar sem mistura de versões.

Existe hoje o job `v-energy-grid-360` com as duas tarefas da Bronze encadeadas (`Landing_to_Bronze` → `Bronze_perfilamento`, o elo em `depends_on` + `run_if: ALL_SUCCESS`), definido em [`data-engineering/configuracao/databricks/v-energy-grid-360.yaml`](../../data-engineering/configuracao/databricks/v-energy-grid-360.yaml) e comprovado em execução na Free Edition (run `14313419965490`, 21m 03s, `Succeeded`). A evidência com identificação da execução e resultado está no [README do módulo](../../data-engineering/README.md#execução-comprovada).

O case fornece uma extração única e pede que o time proponha agendamento para uma operação futura. A periodicidade, a janela de chegada das fontes, o tratamento de atrasos/retificações e o custo da atualização são decisões a justificar após inspecionar o material. Não apresentar uma simulação de agenda como integração de produção existente.

Agenda proposta para essa operação futura: **mensal, dia 5, às 03:00 (America/Recife)** — o insumo é mensal por natureza (leituras e faturas são por competência), o dia 5 dá folga para o fechamento chegar íntegro, e a reexecução é segura porque a Bronze é **publicada por lote** (ingestão em `bronze_stg`, troca de `bronze.*` só no fim, com `bronze.controle_lote`) e reconciliada com `delta = 0`, de modo que uma competência retificada entra no lugar da anterior em vez de acumular e uma falha antes da publicação deixa o lote anterior inteiro. A janela real de chegada das fontes continua desconhecida, porque o case não a informa.

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
2. Definição YAML/JSON do Databricks Workflow com dependências Bronze → Silver → Gold → exportação (**já existe com as duas tarefas da Bronze**; os demais elos entram quando os notebooks existirem).
3. Relatório de perfil e qualidade por origem, decisões de tratamento e testes automatizados se DE-09 for perseguido.
4. CSVs Gold exportados no ambiente de execução, esquema e processo de carga ao banco local; dados reais não entram no Git sem autorização.
5. [Dicionário de dados](../data-dictionary.md) preenchido a partir do dataset real.

## Aceite do serviço

Rodar a extração completa de ponta a ponta e comparar contagens, chaves e métricas em cada transição. Exercitar reexecução sem duplicação. Demonstrar pelo menos um cálculo manual por métrica crítica e uma falha de qualidade detectada. Registrar comandos, Job run e resultados no PRD; concluir os IDs separadamente.
