# GENAI-10A — Registro sanitizado por cenário

## Escopo da evidência

Este registro organiza a execução já realizada em 01/11/2026; não representa uma nova rodada nem aprovação de Dados. A matriz versionada contém perguntas parametrizadas, contexto, fonte, filtros, tolerâncias e controles independentes. Os valores numéricos, parâmetros do lote, respostas e identificadores privados permanecem no relatório local ignorado.

Execução: `20261101T191911_607411Z`. Matriz da branch `feat/genai-10a-runner` (9064c5a), executada com o núcleo e catálogo da branch `feat/genai-cobertura-dominios` (f1fe88a). Os commits identificam os arquivos posteriormente versionados; a execução ocorreu antes dos commits. SQL, sessão, autorização e auditoria reais; modelo controlado. Não comprova linguagem do Gemini nem jornada visual.

## Resultado por caso

| Caso | Domínio | Métrica | Estado esperado | Estado público observado | HTTP | Resultado |
| --- | --- | --- | --- | --- | --- | --- |
| FAT-01 | faturamento | billing.revenue | sucesso | answered | 200 | PASS |
| FAT-02 | faturamento | billing.revenue | sucesso | answered | 200 | PASS |
| FAT-03 | faturamento | billing.revenue | sucesso | answered | 200 | PASS |
| FAT-04 | faturamento | billing.revenue | sucesso | answered | 200 | PASS |
| FAT-05 | faturamento | billing.average_ticket | sucesso | answered | 200 | PASS |
| FAT-06 | faturamento | billing.effective_tariff | sucesso | answered | 200 | PASS |
| FAT-07 | faturamento | — | ambiguidade | needs_clarification | 200 | PASS |
| FAT-08 | faturamento | — | filtro_sem_suporte | needs_clarification | 200 | BLOQUEADO |
| FAT-09 | faturamento | billing.revenue | sucesso | answered | 200 | PASS |
| FAT-10 | faturamento | billing.revenue | sucesso | answered | 200 | PASS |
| FAT-11 | faturamento | billing.price_volume | sucesso | answered | 200 | PASS |
| FAT-12 | faturamento | billing.revenue | zero | — | — | SEM_AMOSTRA_NO_LOTE |
| FAT-13 | faturamento | billing.revenue | nulo | — | — | SEM_AMOSTRA_NO_LOTE |
| FAT-14 | faturamento | billing.revenue | ausencia | needs_clarification | 200 | PASS |
| FAT-15 | faturamento | billing.effective_tariff | base_zero | — | — | SEM_AMOSTRA_NO_LOTE |
| FAT-16 | faturamento | billing.revenue | parcial | answered | 200 | PASS |
| FAT-17 | faturamento | billing.revenue | parcial | needs_clarification | 200 | PASS |
| CON-01 | consumo | energy.consumption | sucesso | answered | 200 | PASS |
| CON-02 | consumo | energy.consumption | sucesso | answered | 200 | PASS |
| CON-03 | consumo | — | ambiguidade | needs_clarification | 200 | PASS |
| CON-04 | consumo | energy.consumption | sucesso | answered | 200 | PASS |
| CON-05 | consumo | energy.average_consumption_per_uc | sucesso | answered | 200 | PASS |
| CON-06 | consumo | energy.consumption | sucesso | answered | 200 | PASS |
| CON-07 | consumo | energy.consumption | sucesso | answered | 200 | PASS |
| CON-08 | consumo | energy.gd_consumption_drop | sucesso | answered | 200 | PASS |
| CON-09 | consumo | — | ambiguidade | needs_clarification | 200 | PASS |
| CON-10 | consumo | energy.consumption | nulo | — | — | SEM_AMOSTRA_NO_LOTE |
| CON-11 | consumo | energy.consumption | parcial | needs_clarification | 200 | PASS |
| INT-01 | interrupcoes | network.equivalent_interruption_duration | bloqueado | error:service_unavailable | 503 | BLOQUEADO |
| INT-02 | interrupcoes | network.equivalent_interruption_frequency | bloqueado | error:service_unavailable | 503 | BLOQUEADO |
| INT-03 | interrupcoes | network.interruption_events | bloqueado | error:service_unavailable | 503 | BLOQUEADO |
| INT-04 | interrupcoes | — | ambiguidade | needs_clarification | 200 | PASS |
| INT-05 | interrupcoes | network.equivalent_interruption_duration | filtro_sem_suporte | needs_clarification | 200 | PASS |
| INT-06 | interrupcoes | network.equivalent_interruption_duration | bloqueado | — | — | SEM_AMOSTRA_NO_LOTE |
| INT-07 | interrupcoes | network.equivalent_interruption_frequency | bloqueado | — | — | SEM_AMOSTRA_NO_LOTE |
| ATE-01 | atendimento | service.attendance | bloqueado | error:service_unavailable | 503 | BLOQUEADO |
| ATE-02 | atendimento | service.attendance | zero | — | — | SEM_AMOSTRA_NO_LOTE |
| ATE-03 | atendimento | service.accumulated_attendance | sucesso | answered | 200 | PASS |
| ATE-04 | atendimento | service.accumulated_satisfaction | sucesso | answered | 200 | PASS |
| ATE-05 | atendimento | service.accumulated_attendance | sucesso | answered | 200 | PASS |
| ATE-06 | atendimento | — | recusa | refused | 200 | PASS |
| ATE-07 | atendimento | — | filtro_sem_suporte | needs_clarification | 200 | PASS |
| AMB-01 | ambiguidade_limites | — | ambiguidade | needs_clarification | 200 | PASS |
| AMB-02 | ambiguidade_limites | — | ambiguidade | needs_clarification | 200 | PASS |
| AMB-03 | ambiguidade_limites | — | ambiguidade | needs_clarification | 200 | PASS |
| AMB-04 | ambiguidade_limites | billing.revenue | sucesso | answered | 200 | PASS |
| AMB-05 | ambiguidade_limites | billing.revenue | sucesso | answered | 200 | PASS |
| AMB-06 | ambiguidade_limites | — | ambiguidade | needs_clarification | 200 | PASS |
| AMB-07 | ambiguidade_limites | — | filtro_sem_suporte | needs_clarification | 200 | PASS |
| AMB-08 | ambiguidade_limites | — | ambiguidade | needs_clarification | 200 | PASS |
| SEG-01 | protecao_falhas | — | recusa | refused | 200 | PASS |
| SEG-02 | protecao_falhas | — | recusa | refused | 200 | PASS |
| SEG-03 | protecao_falhas | — | recusa | refused | 200 | PASS |
| SEG-04 | protecao_falhas | — | recusa | refused | 200 | PASS |
| SEG-05 | protecao_falhas | — | acesso_negado | error:access_denied | 403 | PASS |
| SEG-06 | protecao_falhas | — | indisponibilidade | — | — | NAO_EXECUTADO |
| SEG-07 | protecao_falhas | — | sucesso | — | — | NAO_EXECUTADO |

## Revisão que ainda falta

- Conferir os controles numéricos no relatório privado com Dados, por domínio e recorte; os 22 aceites técnicos locais não substituem essa revisão.
- Revisar estratos de sucesso, ausência, zero, nulo, base zero, ambiguidade, recusa e indisponibilidade. Casos sem amostra real continuam pendentes, ainda que tenham regressão sintética.
- FAT-08: comprovar a medida de recebimento. INT-01/02/03 e ATE-01: certificar a cobertura mensal da origem.
- Revalidar a jornada do portal com o mesmo lote e versão. SEG-06/07 permanecem provas técnicas separadas, sem converter NAO_EXECUTADO em PASS Gold.

A completude deste inventário não conclui os cartões 10A/10B. O critério de evidência integral continua aberto enquanto existirem fonte obrigatória ausente, controle não revisado ou jornada pendente.


### Revalidação HTTP pública — 01/11/2026

Rodada `20261101T195433_504518Z`: 57 casos avaliados com cliente HTTP externo ao processo do Backend isolado, login e cookies reais, endpoint público `/api/v1/ai/questions`, leitura Gold restrita e auditoria reais. Modelo controlado, sem novas chamadas Gemini. O transporte entre Backend e núcleo usa o adaptador de integração de teste existente; não comprova tráfego HTTP entre esses dois serviços nem qualidade de linguagem do provedor.

Resultado por ID idêntico ao anterior: 43 PASS, cinco BLOQUEADO, sete SEM_AMOSTRA_NO_LOTE e dois NAO_EXECUTADO (SEG-06/07, provas técnicas separadas). Sem divergências ou erros de execução. As duas contas temporárias e suas sessões foram removidas; Backend isolado encerrado.

Comando na worktree 10B: `docker exec --env-file work/genai10/.env.genai10b-backend -w /repo/backend genai10b-tests python /repo/work/genai10/http-acceptance.py`. Script e valores privados permanecem ignorados. A primeira tentativa foi rejeitada no login por Host interno não permitido; o cliente passou a enviar o Host local autorizado, sem mudar a proteção do servidor.

A fronteira HTTP pública foi comprovada; renderização/interação no navegador, revisão de Dados e lacunas de fonte continuam pendentes. Critérios e estados preservados.
