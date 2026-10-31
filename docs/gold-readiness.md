# Prontidão da Gold por capacidade

**Cartão:** GENAI-02. **Código:** `ai-agent/app/readiness/`. **Fronteira pública:** `evaluate_readiness(PublicationFacts)`. **Natureza:** avaliador puro com operação interna autenticada. Observação Backend e consulta conversacional são etapas de integração separadas.

## Responsabilidades e caminho previsto

O Backend observa sua publicação validada e fornece fatos de tabela, resultados aprovados de controle e cobertura do recorte. O avaliador existente, puro e sem I/O, devolve códigos por capacidade. O coordenador, catálogo e consumidores deverão usar o relatório antes da consulta. A fábrica GenAI injeta o avaliador na operação autenticada `POST /api/v1/internal/gold-readiness`. O chat público ainda não chama essa operação. Não existe acesso a banco no núcleo GenAI.

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

GENAI-02 permanece em andamento até essas dependências serem comprovadas. A operação interna usa o ponto de composição existente; o Backend ainda deve fornecer os fatos observados e consumir o relatório antes da consulta. O contrato público de chat e os estados dos requisitos IA não mudam nesta preparação.
