# Matriz de cobertura — Melhoria Geral do Chatbot V-Energy

Esta matriz descreve o que o catálogo e a admissão F1 declaram suportar na branch em que a bateria nova será construída. Ela separa capacidade semântica, fonte e condições de aceitação; uma métrica no catálogo não prova que a rota consegue consultá-la no lote atual.

## Capacidades Gold v2

| Métrica | Fonte e grão | Operação admitida no contrato | Recortes e limites que os casos devem cobrir |
| --- | --- | --- | --- |
| `billing.revenue` | `diagnostico_receita` (competência, município, classe, subgrupo, bandeira, GD); fontes bairro/UC quando autorizadas | Soma; total, série mensal, agrupamento, comparação e ranking quando dimensões/períodos forem compatíveis | Município, classe, subgrupo, bandeira, GD explicitamente solicitado; distinguir faturado de pago. Receita inclui faturas sem leitura. |
| `energy.consumption` | `diagnostico_receita`; também fonte por bairro e UC, cada qual com seu próprio grão | Soma; total, série mensal, agrupamento, comparação e ranking quando autorizados | Município, classe, bairro e dimensões da fonte. GD só como filtro explícito. Distinguir medido de faturado. |
| `billing.average_ticket` | `diagnostico_receita` / `consumo_receita_bairro` | Razão de somas; `SUM(receita)/SUM(qtd_ucs_distintas_faturadas_no_mes)`, arredondada a 2 casas | Não usar média das médias nem agrupar em dimensão que replique o denominador. R$/UC faturada no mês. |
| `billing.effective_tariff` | Receita e consumo comparáveis na mesma população, nas fontes autorizadas | Razão de somas; `SUM(receita_base_comparavel)/SUM(consumo_base_comparavel)`, arredondada a 4 casas | Rotular como preço observado em R$/kWh, nunca tarifa homologada. Não misturar populações ou parcelas sem leitura. |
| `energy.average_consumption_per_uc` | `diagnostico_receita` / `consumo_receita_bairro` | Razão de somas; `SUM(consumo_total_kwh)/SUM(qtd_ucs_com_leitura)` | kWh/UC com leitura. Não usar média simples de médias. Município/classe/bairro apenas no grão que preserve os componentes. |
| `network.equivalent_interruption_duration` (DEC) | `indicadores_dec_fec`, por alimentador e competência | Leitura por grão no contrato anterior; soma ponderada de numeradores com denominador contado uma vez por alimentador elegível no contrato F1 v12 | Competências completas, numerador válido e denominador positivo constante por alimentador. Não somar nem tirar média simples dos índices publicados. Estado observado não certificado deve permanecer explícito. |
| `network.equivalent_interruption_frequency` (FEC) | `indicadores_dec_fec`, por alimentador e competência | Igual ao DEC, usando numerador de frequência | Mesmas condições do DEC; validar separadamente valores, população elegível e aviso de cobertura. |
| `service.attendance` | `atendimentos_uc`, um protocolo por abertura; mês em UTC | Contagem de protocolos; operação `total` | Intervalo UTC, protocolo distinto conforme contrato, cobertura mensal e controle. Não contar tratativas como atendimentos. |
| `service.satisfaction` | `atendimentos_uc`, um protocolo por abertura | Média de `nota_satisfacao` não nula; operação `average` | Zero é nota válida; nulo é ausência de nota. Cobertura mensal e controle precisam passar. |
| `service.accumulated_attendance` | `visao_360_uc`, por UC | Soma do histórico publicado; operação `accumulated_total` | Período histórico desconhecido. Não apresentar como intervalo temporal nem como histórico completo certificado. |
| `service.accumulated_satisfaction` | `atendimentos_uc`, por protocolo | Média das notas individuais não nulas; `accumulated_average` | Período do histórico desconhecido; não calcular média de médias por UC. |
| `billing.price_volume` | `decomposicao_receita`, por município/bairro/classe e quatro limites de janela | Ler decomposição publicada; não recalcular método no prompt | Exigir janela única, estado calculado, linhagem compatível, população e identidade financeira reconciliadas. Não inferir causalidade. A disponibilidade da janela pedida deve ser verificada em cada snapshot/staging. |
| `network.interruption_events` | `ocorrencias_uc`, grão ocorrência/UC | Contagem distinta de ocorrência | Controle/cobertura podem bloquear o acesso. Não confundir ocorrências com DEC/FEC nem executar quando readiness negar. |
| `energy.gd_units` | `variacao_consumo_uc`, um registro por UC no lote | Contagem distinta de UC com `possui_gd='Sim'`; `snapshot_total` | Retrato cadastral do lote; não implica vigência histórica, origem solar ou geração. Filtro municipal somente com cobertura autorizada. A pergunta de contagem passou pela rota autenticada com Gemini e SQL independente (CTL-005). |
| `energy.gd_consumption_drop` | `variacao_consumo_uc`, uma linha por UC | Contagem de flag `queda_consumo_superior_30_pct=true`; `snapshot_total` | GD cadastrada e ao menos 6 meses lidos em cada janela fixa jul/2022–jun/2023 e jul/2025–jun/2026; queda estritamente maior que 30%. C08/C09 reconciliam flag e componentes; a pergunta passou pela rota autenticada com Gemini e SQL independente (CTL-006). Não atribuir causalidade à GD. |
| `customer.units_by_class` (C05) | `visao_360_uc`, retrato atual, uma linha por UC | `snapshot_total` / `count_distinct`; filtro por classe ou agrupamento por classe | Contar `id_uc` distinta pela classe atual. Sem período histórico. Validada na rota autenticada para todas as classes e para o filtro residencial contra SQL independente. |
| `inspection.units_by_priority` (C06/C07) | `fila_inspecao`, retrato atual, uma linha por UC | `snapshot_total` / `count_distinct`; filtro por prioridade ou agrupamento por prioridade | Prioridade é triagem, não ocorrência confirmada. “Consumo zero” aponta somente para `ALTA - CONSUMO ZERO`; categoria ausente na publicação é zero válido, não “sem histórico”. Validada por agrupamento, filtro e comparação SQL independente. |

## Operações transversais

| Operação | Situação observada no contrato/código | Como avaliar |
| --- | --- | --- |
| Total e série mensal | Admitidas para métricas temporais quando a fonte, a cobertura e a granularidade permitem | Conferir os meses retornados, lacunas, total e interpretação de “ano”. |
| Agrupamento | SQL estruturado tem operações `grouped_total`; dimensões precisam existir no grão da fonte | Comparar grupos e soma dos grupos com o total do mesmo recorte; detectar perda/duplicação de população. |
| Comparação entre dois períodos | Operação `comparison`; exige períodos compatíveis e validação específica da métrica | Conferir ordem dos períodos, delta, percentual, base zero e população comparável. |
| Ranking | Operação `ranking`; agrega toda a população antes de ordenar e limitar | Conferir direção, limite, desempate e cálculo do delta antes do ranking. |
| Continuidade entre mensagens | O plano recebe contexto conversacional e pode preservar ou substituir dimensões/períodos | Criar casos independentes de manter, trocar, remover e corrigir filtro; garantir isolamento de conversas. |
| Consulta composta / JOIN | Não há autorização genérica para combinar fatos crus; joins permanecem bloqueados | Aceitar só composição tipada com fontes e grãos reconciliados. A pergunta de consumo e receita deve testar comparação paralela por dimensão, sem JOIN cru nem causalidade. |
| Ambiguidade, falta de cobertura e bloqueio | Saídas distintas: esclarecimento, sem dados, não suportado, negado por controle, fonte indisponível | Exigir que cada estado correto seja distinguido e que esclarecimento/recusa não execute SQL. |

## Prontidão e evidências para pontuar os casos

- O catálogo da branch declara `gold-catalog-v2`, schema `gold_v2` e perfil Gold v2. A publicação ativa observada para esta revisão é `GOLD_20261103T173853Z_76c37784` (`gold-csv-v2`).
- A conta de leitura usada para calcular referências não tem `SELECT` em `gold_v2.cobertura_dominios`; isso limita a conferência direta dos metadados de cobertura. Após provisionar somente `id_uc` e `prioridade_inspecao` para a fila e habilitar C05–C07 no ambiente local do Docker (09/11/2026), seis consultas cobrindo C05–C09 passaram pela rota autenticada com Gemini e SQL independente. Os dois casos C08/C09 já tinham perguntas mapeadas; C05–C07 exigiram os quatro casos novos. CTL-003 teve um 502 transitório e passou na repetição, ocorrência que deve permanecer separada como falha de provedor em avaliações de estabilidade. A readiness mantém `partial`: 9 de 14 capacidades ficam disponíveis; as restantes continuam indisponíveis por cobertura incompleta ou fonte/definição ausente. Essas aprovações são configuração local; não alteram política nem estado dos dados.
- A Gold v2 local está carregada pelo compose com o lote `GOLD_20261103T173853Z_76c37784`, usando os CSVs e o manifesto disponíveis. O lote contém decomposição preço-volume para jul/2022–jun/2023 contra jul/2025–jun/2026, mas não contém jul/2024–jun/2025 contra jul/2025–jun/2026. Portanto, a consulta à publicação pode funcionar para janelas nela presentes; a análise específica proposta ainda depende de CSV/manifesto com a janela faltante e de recarga da staging.
- A especificação dos 15 casos diagnósticos iniciais tem SQL/gabaritos independentes. A revisão semântica foi ampliada para os 230 casos; cada uma das 17 métricas do catálogo tem pelo menos dez casos individuais (170 perguntas individuais no total; ticket médio tem 11 e MGC-006 avalia DEC e FEC conjuntamente). Isso não constitui baseline Gemini.

### Diversidade do rascunho MGC (09/11/2026)

- As consultas individuais incluem recortes observados na Gold v2 por bairro, subgrupo tarifário, bandeira e GD, além de município/classe/competência. MGC-041 acrescenta uma borda real de razão de somas indisponível por denominador zero. Os gabaritos independentes dos 219 casos com SQL esperado foram calculados e reconciliados com o snapshot Gold indicado. A baseline Gemini ainda não foi executada.
- Nos recortes mensais escolhidos para receita e razões de somas, a publicação contém linhas e denominadores positivos; isso evita cenários vazios acidentais, mas não substitui a reconciliação numérica caso a caso.
- Atendimento e satisfação individuais usam uma competência mensal, como exige o contrato F1. Os três casos antes escritos como consultas anuais foram trocados por competências mensais de anos diferentes, todas presentes na cobertura temporal da publicação. Duas perguntas anuais foram preservadas na categoria de limites e segurança como pedidos que devem ser marcados como não suportados na F1 e encerrados sem SQL.
- MGC-006 consulta um alimentador explícito em seis competências sem agrupamento, formato admitido pelo F1 v12. A rota pública sob perfil admin retornou DEC 0,5385047281 h/UC e FEC 0,2996453901 ocorrências/UC, conciliados com o SQL independente, e preservou o aviso de cobertura observada não certificada.
- A solicitação original de agrupar DEC/FEC por todos os alimentadores foi mantida como MGC-210, caso negativo: o contrato atual não admite esse agrupamento, portanto o comportamento esperado é explicar o limite e não gerar SQL.
- Auditoria dirigida somente leitura no lote ativo: 48 competências/7.600 linhas em `diagnostico_receita`; nenhum empate mensal por município ou município/classe em consumo/receita; oito grupos município/classe/mês com zero UCs com leitura; nenhum município ou município/classe com base zero nas janelas anuais de MGC-015. MGC-041 cobre um exemplo real: IGARASSU/PODER PUBLICO/2023-06, uma linha, zero leitores e consumo NULL. Não inferir que esses achados valem para grãos ou métricas não auditados.
- O conjunto semântico de 230 foi revisado; MGC-015 tem oráculo independente de comparação com disclosure obrigatório de decomposição ausente. Os 20 casos adicionais MGC-211–230 exercitam as métricas cadastrais por classe e fila/prioridade, com oráculos numéricos. A baseline Gemini completa não foi executada.

### Atualização da revisão semântica (09/11/2026)

- A revisão dos 230 registros contra o contrato F1 v12 está detalhada em [REVISAO_SEMANTICA_MELHORIA_GERAL_CHATBOT.md](REVISAO_SEMANTICA_MELHORIA_GERAL_CHATBOT.md). Isso confirma coerência do enunciado com a intenção e o estado esperado, não a precisão numérica da rota.
- MGC-162 agora é um limite explícito: o contrato não admite ranking por variação percentual; a expectativa é recusa sem SQL. MGC-175–184 agora registram as operações analíticas pretendidas.
- A divisão separa 186 diagnósticos e 44 holdout por famílias semânticas, sem família atravessando o split. Os 230 casos e seus oráculos estão congelados; a baseline Gemini permanece pendente.

### Resultado da checagem de prontidão (09/11/2026)

Execução interna somente leitura pelo Backend, com `scope=domains`, `requested_periods=["2026-06"]` e as aprovações locais restauradas do ambiente de demonstração (C01–C04 e C08–C15); `readiness_version=gold-readiness-v2`, `lot_state=partial`. Nove das 14 capacidades estavam disponíveis. A primeira tentativa omitiu aprovações e não representa o runtime restaurado; a execução abaixo é a referência atual:

| Capacidade | Estado observado | Motivos retornados |
| --- | --- | --- |
| `faturamento.receita` | disponível | — |
| `faturamento.receita_bairro` | disponível | — |
| `faturamento.preco_volume` | disponível para decomposições publicadas | A janela jul/2024–jun/2025 não existe no lote; não responde à proposta específica |
| `faturamento.faturas_em_aberto` | indisponível | `table_missing`, `definition_pending` |
| `consumo.mensal_uc` | disponível | — |
| `consumo.variacao_uc` | disponível | — |
| `interrupcoes.dec_fec` | indisponível para aceite certificado | `coverage_incomplete`; pode existir resultado observado com aviso, sem certificação Gold |
| `interrupcoes.uc_acumulado` | indisponível | `coverage_incomplete` |
| `atendimento.uc_acumulado` | disponível | — |
| `apoio.fila_inspecao` | disponível para contagem distinta por prioridade | C06/C07 passaram na rota Gemini/Gold e SQL independente; leitura limitada a `id_uc` e `prioridade_inspecao`; prioridade não confirma ocorrência |
| `cadastro.ucs_por_classe` | disponível para contagem distinta por classe | C05 passou para todas as classes e para residencial, com Gemini e SQL independente |
| `apoio.medidor_uc` | indisponível | `table_missing`, `definition_pending` |
| `apoio.energia_recuperavel` | indisponível | `table_missing`, `definition_pending` |
| `atendimento.mensal` | disponível | — |

As aprovações locais de controle foram restauradas para reproduzir o ambiente de demonstração usado nas validações anteriores. Isso remove a configuração reduzida do container local, não altera controle técnico, grants ou políticas de autorização. Disponibilidade de capacidade e resposta ponta a ponta foram observadas para a configuração local; DEC/FEC segue sem cobertura certificada e a decomposição da janela específica continua ausente.

Uma pergunta foi verificada visualmente no Assistente com Gemini e Gold v2: “Qual foi o consumo medido em Recife em junho de 2026?”. A resposta foi 5.353.512,00 kWh, período Jun/2026 e município RECIFE, com evidência detalhada. Isso comprova uma jornada de consumo mensal, não a bateria de avaliação nem todas as operações da métrica. Referências SQL independentes continuam sendo oráculos, não prova isolada da disponibilidade pela interface.
