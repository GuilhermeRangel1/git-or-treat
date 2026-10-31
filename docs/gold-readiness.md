# Prontidão da Gold por capacidade

**Cartão:** GENAI-02. **Código:** `ai-agent/app/readiness/`. **Fronteira pública:** `evaluate_readiness(PublicationFacts)`. **Natureza:** avaliador puro com operação interna e observador Backend executáveis para C14/C15. Há prova privada em SQLite com pacote real e HTTP local, além de prova em PostgreSQL 16 descartável com papel restrito; homologação no destino e consulta conversacional permanecem limites separados.

## Responsabilidades e caminho previsto

O Backend observa sua publicação validada e fornece fatos de tabela, resultados aprovados de controle e cobertura do recorte. O avaliador existente, puro e sem I/O, devolve códigos por capacidade. O coordenador, catálogo e consumidores deverão usar o relatório antes da consulta. A fábrica GenAI injeta o avaliador na operação autenticada `POST /api/v1/internal/gold-readiness`. O Backend observa o banco por `observe_attendance_readiness` e usa `evaluate_attendance_readiness` para chamar a GenAI; a CLI operacional descrita abaixo executa esse caminho. O chat público ainda não chama essa operação. Não existe acesso a banco no núcleo GenAI.

Os diagnósticos privados produzidos por `scripts/gold_coverage.py` nos controles C14/C15 são evidências de conferência; não são uma autorização automática nem um envelope de publicação confiável. Sua aprovação e vinculação ao lote cabem ao servidor responsável. Nenhuma entrada desta API interna deve vir diretamente do navegador.

## Versões e migração

- `gold-readiness-v1` preserva a matriz histórica de sete tabelas, a lista `approved_controls` e as decisões anteriores, como compatibilidade explícita. Continua o default legado `READINESS_VERSION`; o consumidor novo precisa informar v2.
- `gold-readiness-v2` reconhece as quinze tabelas analíticas do dicionário atual e exige resultados de controle vinculados ao lote. O cadastro restrito de titular e `controle_gold` ficam fora do inventário.
- Publicação `gold-csv-v2` não pode ser avaliada como prontidão v1. O esquema CSV e a versão de prontidão são conceitos distintos; uma referência válida não certifica a carga.
- Fatos v2 não podem ser enviados em envelope v1, e v2 rejeita a lista legada `approved_controls`. Mudança de consumidor exige envio explícito da versão e dos fatos novos; não converter uma lista de controles aprovados em resultados aprovados de outro lote.
- O relatório preserva a versão de prontidão recebida. Rollback exige voltar a um par consumidor/contrato compatível, sem fallback silencioso de Gold v2 para prontidão v1.

## Entrada v2

`PublicationFacts` contém identificação atual/esperada (`GoldBatchRef` compartilhado com evidências), `backend_reachable`, `tables`, `control_results` e `coverage`, além da versão explícita. Sem contagens de negócio, registros ou identificadores pessoais.

- `TableFacts`: presença, existência de linhas, referência de publicação e competências observadas. Tabela ausente não tem linhas/publicação; tabela sem linhas não tem competências. Flags booleanas são estritas; períodos inválidos ou duplicados são rejeitados.
- `ControlFacts`: referência de publicação, `status` (`passed`, `failed`, `pending`, `unavailable`) e `approved` booleano estrito, falso por padrão. Aprovação sem resultado passado não libera a capacidade; resultado passado sem aprovação também não. Resultado de outro lote bloqueia somente as capacidades dependentes.
- `CoverageFacts`, por capacidade: publicação, períodos solicitados, observados, fechados, zero confirmado e presença de registros sem competência, informada por booleano estrito obrigatório (sem presumir falso por omissão). O Backend deriva esses fatos da cobertura e das definições validadas para a métrica/recorte, preservando AUSENTE/PARCIAL/NAO_CERTIFICADA como períodos não fechados. Não inferir fechamento pelo calendário, continuidade dos meses ou presença de registros.

O mês solicitado deve existir nos fatos de `cobertura_dominios`, mesmo para eventos datados por abertura. Um período solicitado deve estar fechado e observado, ou ter zero explicitamente confirmado. Zero confirmado exige fechamento e não pode coincidir com registros observados. Registros sem competência bloqueiam a análise temporal. Para tabelas com coluna de competência, os períodos solicitados também devem constar dos fatos observados da tabela. Uma lacuna fora do recorte solicitado não bloqueia uma pergunta por outro recorte válido.

Apenas a capacidade mensal de atendimento admite tabela de eventos vazia com zero confirmado para todo o recorte; a tabela de cobertura precisa existir e conter linhas. Ausência da tabela nunca confirma zero. O avaliador não produz um número zero de negócio: apenas informa prontidão para consulta autorizada.

## Estados do lote

Precedência: Backend indisponível → `unavailable`; publicação atual/tabelas presentes sem referência → `invalid`; referência esperada divergente → `stale`; tabelas com referências distintas → `mixed`; nenhuma linha → `empty`; alguma das quinze fontes do inventário v2 ausente/vazia → `partial` (v1 mantém o inventário legado requerido); demais casos → `ready`.

Os quatro primeiros bloqueiam todas as capacidades. `ready` descreve disponibilidade de inventário, não aprovação de todas as medidas. Nos demais casos, a avaliação é por capacidade; um lote `partial` pode sustentar capacidades independentes. Um resultado `available` não substitui autenticação, validação de plano, controles de execução ou grounding.

## Matriz v2 e limites semânticos

| Capacidade | Fontes principais | Controles / limite |
| --- | --- | --- |
| `faturamento.receita` | `diagnostico_receita` | C01/C02/C04 e cobertura do recorte |
| `faturamento.receita_bairro` | `consumo_receita_bairro` | C12/C13 e cobertura do recorte |
| `consumo.mensal_uc` | `consumo_mensal_uc` | C03/C10 e cobertura do recorte |
| `interrupcoes.dec_fec` | `indicadores_dec_fec` | C11 e cobertura do recorte; não somar razões |
| `atendimento.uc_acumulado` | `visao_360_uc`, `atendimentos_uc` | C14 aprovado e passado no mesmo lote; sem competência inventada |
| `atendimento.mensal` | `atendimentos_uc`, `cobertura_dominios` | C14/C15 aprovados e passados, cobertura fechada do recorte |
| `faturamento.preco_volume` | `decomposicao_receita` | definição pendente para exposição da medida candidata; presença não homologa tarifa |
| `faturamento.faturas_em_aberto` | `faturas_uc` | fonte existe; liberação semântica/controles da capacidade ainda pendentes; valor indicativo não é saldo contábil |
| `apoio.medidor_uc` | `medidor_uc` | fonte existe; regra e controles da capacidade ainda pendentes; ausência de retirada não prova atividade |
| `apoio.energia_recuperavel` | `fila_inspecao` | definição pendente; média histórica não é estimativa individual; campos por UC permanecem nulos |
| `interrupcoes.uc_acumulado` | `visao_360_uc`, `ocorrencias_uc` | controle/definição da capacidade ainda pendentes |
| `consumo.variacao_uc` | `variacao_consumo_uc` | C08/C09; interpretação das janelas ainda pendente para a capacidade |
| `apoio.fila_inspecao` | `fila_inspecao` | C06/C07; aprovação da interpretação dos rótulos ainda pendente |

Definição pendente permanece bloqueada, mesmo com controles passados. As pendências são da capacidade consumidora, não uma declaração de ausência das tabelas ou de falta de implementação do produtor. Os detalhes canônicos estão no [dicionário](dicionario_gold.md) e nos contratos [de cobertura](contracts/gold-cobertura-v1.md) e [de consulta](contracts/genai-query-execution.md).

## Evidência e continuação

Os testes pela função pública usam fatos controlados, sem provedor, banco ou dados pessoais. Validam versões, controles, cobertura, zero/ausência, isolamento de capacidades, lote misto/antigo e rejeição de entradas inválidas. Não comprovam identidade/hash do CSV, reconciliação Silver/Gold, agregados persistidos ou mesmo lote no portal.

GENAI-02 permanece em andamento até essas dependências serem comprovadas. A ligação ao runtime deve usar o ponto de composição existente e dados observados no Backend; não basta importar este módulo em testes. O contrato público de chat e os estados dos requisitos IA não mudam nesta preparação.


## Operação executável e prova privada

`backend/scripts/check_gold_readiness.py` é um consumidor operacional interno: lê a publicação v2 carregada, recalcula C14 e C15 sobre os fatos persistidos, envia somente metadados/estados ao serviço GenAI e confere a publicação novamente depois da resposta. Não envia UCs, protocolos, médias ou valores financeiros. A saída operacional omite referência do lote e períodos. O recorte é global de atendimento; não autoriza reutilizar os mesmos fatos para uma pergunta filtrada por UC, município ou classe.

Configure `GOLD_READINESS_DATABASE_URL` com credencial de leitura e `AI_AGENT_BASE_URL`/`AI_AGENT_SERVICE_API_TOKEN` com a conexão interna. Execute `python scripts/check_gold_readiness.py --period YYYY-MM --approve-control C14 --approve-control C15`, repetindo `--period` quando necessário. As flags são aceite explícito das regras pelo operador, não forçam resultado passado nem fecham meses. Sem flags de aceite os resultados continuam não aprovados. Não passe credenciais na linha de comando. Banco deve estar migrado até `goldv2000002`; PostgreSQL usa a view mínima `gold.publicacao_linhagem` para ler somente IDs Silver/Bronze, sem acesso ao manifesto operacional completo ou ao cadastro pessoal.

No PostgreSQL a observação usa `REPEATABLE READ READ ONLY`, timeout de SQL limitado ao saldo (até 5 s) e publicação revalidada fora do snapshot. A conexão da CLI limita aquisição e conexão a 5 s; outros chamadores devem fornecer engine com limites equivalentes. Leitura/banco e HTTP consomem prazo total de 35 s no serviço. Cancelamento de thread não substitui cancelamento SQL; o SQL conserva timeout no servidor. SQLite local usa `query_only` e restaura o estado da conexão, sem comprovar isolamento/permissões PostgreSQL.

A operação GenAI exige token configurado mesmo no modo local; ausência não herda a dispensa da demonstração. A fábrica injeta o mesmo avaliador já testado, sem novo orquestrador ou chamada ao LLM. Corpo inválido ou token incorreto é recusado. A implantação deve manter esta rota na rede privada; o proxy público e o navegador não a usam.

A verificação privada opt-in `tests/test_gold_readiness_real.py` usa `GOLD_CSV_V2_DIR`, `GOLD_READINESS_TEST_URL` e `GOLD_READINESS_TEST_TOKEN`. Importa as quinze tabelas pelo importador real em banco temporário, pede avaliação por HTTP e confere a identidade preservada e os estados de atendimento. A execução local passou sem provedor de IA; o atendimento acumulado foi liberado e o mensal permaneceu indisponível por cobertura não certificada. Nenhum dataset ou credencial integra o teste no repositório. O banco temporário é removido ao final.

A regressão com papel restrito passou em PostgreSQL 16 descartável no Docker, incluindo a migração da view de linhagem e os bloqueios de escrita e de acesso fora do escopo. Ainda permanecem a conferência no PostgreSQL de destino, a incorporação ao coordenador de perguntas/insights, o mesmo lote no portal e os controles dos outros domínios. A conclusão da ligação C14/C15 não conclui GENAI-02 integralmente ou IA-01/03/04/06.


## Controles dos quatro domínios na publicação v2

A CLI aceita `--scope domains` para usar `evaluate_domain_readiness` e `observe_domain_readiness`. O escopo padrão `attendance` preserva a operação anterior. Ambas as operações reutilizam a mesma coordenação, referência, prazo e snapshot; não há outro banco ou executor na GenAI. Flags `--approve-control` continuam aceites explícitos do operador e não são preenchidas a partir da aprovação histórica do relatório CSV.

A versão de prontidão permanece `gold-readiness-v2`: o envelope não muda, mas o observador passa a preencher controles já previstos. A compatibilidade v1 e os controles candidatos do relatório histórico permanecem preservados. Os IDs abaixo identificam a família do controle; estas verificações internas complementam o controle de origem e **não substituem seus valores de referência ou sua aprovação externa**.

| Controle | Verificação adicional sobre a publicação carregada |
| --- | --- |
| C01 | Reconcilia consumo medido e receita da série UC/mês com o diagnóstico por competência. Não chama consumo medido de energia faturada. |
| C02 | Reconcilia os mesmos valores por competência e classe cadastral atual. |
| C03 | Confere presença dos pares UC/mês e coerência de flags/contagens de faturas e leituras observadas. Não presume que toda linha tenha as duas fontes. |
| C04 | Reconcilia os mesmos valores por competência e município cadastral atual; ausência cadastral usa `Não informado`. |
| C10 | Confere tipos/ausências da população de médias históricas e consumo mensal. Não compara média por leitura com média mensal; a distribuição de nulos e a ausência de série continuam evidências a conferir contra a origem. |
| C11 | Reconcilia eventos, duração e UCs distintas com numeradores, denominador cadastral e fórmulas DEC/FEC, sem somar razões nem preencher duração desconhecida. Indicadores continuam esparsos nos meses sem ocorrência. |
| C12 | Reconcilia diagnóstico e bairro em consumo, receita e UCs faturadas por mês, condicionado também à reconciliação da série. |
| C13 | Detecta bairros que diferem somente por caixa, acentos, espaços extras ou mojibake latin-1/UTF-8. |

Receita é faturamento, não recebimento; a conferência considera as fontes presentes independentemente, preserva ausência de medida e não fabrica zero. Contagens conciliam exatamente; diferenças em consumo e receita nos agregados usam tolerância absoluta de 0,01 na unidade publicada para acomodar representação numérica/centavos, sem tolerância por percentual. C11 usa 0,0001 para duração/razões em ponto flutuante. Essas tolerâncias técnicas não aprovam metodologia de negócio nem completude da origem. Médias históricas por leitura não são recalculáveis a partir da média de somas mensais.

Cobertura de faturamento/consumo é confrontada com as contagens de faturas/leituras observadas da série. Mês com medida inteiramente nula não vira período utilizável só porque a extração está fechada. Cobertura de ocorrências é confrontada com eventos e precisa ser conferida também para cada alimentador cadastral; fechamento global não se propaga aos alimentadores. São necessários mesmo lote/linhagem, mês fechado, corte posterior ao mês e não futuro e referência de evidência. Extração exige JSON de reconciliação íntegro, sem exclusões da origem, preservando quarentena separada; esse JSON não prova sozinho o inventário do fornecedor. Falha mantém o mês fora dos períodos fechados, mesmo com controle numérico passado.

A saída continua apenas com estados e metadados técnicos. Cadastro pessoal, medidas, UCs, protocolos e alimentadores não são devolvidos. Esta etapa ainda não entrega catálogo/perguntas/insights Gold nem prova o mesmo lote no portal; C05/C06/C07/C08/C09 e definições consumidoras pendentes não são aprovados por consequência.

As reconciliações agrupam a série mensal e os eventos no SQL do Backend antes da comparação. Os joins são apenas com a chave única de UC do cadastro; faturas e eventos não são unidos entre si. Agregações e leitura do resultado continuam no mesmo snapshot, com teto SQL de 5 s e orçamento total de 35 s; não há aumento de prazo para esconder custo da conferência.


Verificação desta ampliação: Backend Docker/PostgreSQL 16 com agregados não vazios e leitor restrito, 847 testes passaram/8 skips; GenAI completa, 3.407 passaram/4 skips; operação HTTP, 24 passaram. Prova privada `--scope domains` pelo serviço Backend e GenAI HTTP passou com o pacote real, mantendo mesma referência e o prazo. Isso comprova execução e proteções, não homologa automaticamente resultados contra a Silver nem libera todas as capacidades. A primeira tentativa excedeu o orçamento e foi recusada; as agregações SQL corrigiram o custo sem aumentar o limite.
