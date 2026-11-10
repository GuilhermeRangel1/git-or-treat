# Revisão semântica da bateria MGC

**Revisão:** 09/11/2026<br>
**Contrato conferido:** F1 v12 desta branch<br>
**Catálogo e dados de referência:** Gold v2, lote `GOLD_20261103T173853Z_76c37784`<br>
**Situação:** revisão semântica, auditoria dirigida de diversidade e referências SQL independentes concluídas. O fixture e a divisão por família estão congelados para a linha de base; isso não significa que o chatbot já passou na avaliação Gemini.

Esta revisão confere, para cada registro, se o enunciado corresponde à intenção, métrica, operação, unidade, período, filtros, grupos e estado esperado descritos no fixture. Também confere se pedidos negativos exigem ausência de SQL. Não substitui execução da rota, readiness por usuário, nem reconciliação dos valores independentes.

## Revisão por famílias

| Casos | Resultado da revisão |
| --- | --- |
| MGC-001–015 | Casos âncora revisados anteriormente, com referência independente executada. MGC-006 passou pela rota pública com perfil admin: a razão ponderada DEC/FEC de jan–jun/2026 reconciliou com SQL e preservou o aviso de cobertura não certificada. MGC-015 espera comparação limitada nas janelas 2024-07..2025-06 e 2025-07..2026-06, com disclosure de que a decomposição preço-volume não está publicada para elas. |
| MGC-016–062 | Totais e razões de somas revisados contra os filtros Gold v2 declarados: município, bairro, classe, subgrupo, bandeira e GD. A fórmula de consumo médio permanece razão das somas. Cinco casos de bairro foram corrigidos para `consumo_receita_bairro`, única fonte do catálogo que expõe bairro; a verificação estrutural agora impede usar fonte sem a dimensão pedida. |
| MGC-063–080 | Leituras DEC/FEC por um alimentador e uma competência. A formulação, o filtro e a operação `grain_read` são compatíveis; prontidão e autorização devem ser avaliadas em cada chamada. |
| MGC-081–098 | Métricas mensais de atendimento e satisfação com uma competência por consulta, seguindo o contrato mensal. Cobertura mensal não é inferida pela existência de linhas e deve ser validada por readiness. |
| MGC-099–118 | Reformulações coloquiais de atendimento/satisfação acumulados. A resposta deve preservar o caráter de histórico publicado com período desconhecido; não afirmar que é histórico completo ou associá-lo a um ano. |
| MGC-119–128 | Consultas às decomposições preço-volume publicadas no lote. Só são válidas para a janela exata identificada na publicação e após controles/população/linhagem; não substituem a janela obrigatória de MGC-015. |
| MGC-129–138 | Contagens mensais de ocorrências por alimentador, sujeitas a controles e cobertura. Negação de readiness deve impedir SQL. |
| MGC-139–147 | Retrato cadastral de UCs com GD por município. Não atribuir período, geração ou vigência além do que a Gold informa. |
| MGC-148–156 | Contagem municipal de UCs elegíveis com queda estritamente superior a 30%, usando a flag publicada e as janelas fixas. Não atribuir causalidade à GD. |
| MGC-157–174 | Rankings, comparações e séries revisados contra as operações do contrato. MGC-162 foi corrigido para recusa sem SQL: ranking por variação percentual não é admitido. MGC-174 mantém agrupamento de GD por município, expressamente permitido no contrato. |
| MGC-175–184 | Perguntas coloquiais. As operações foram corrigidas para refletir a intenção analítica, em vez do marcador genérico `interpret_natural_language`. MGC-183 usa ranking por queda absoluta e compartilha família com MGC-010; MGC-184 compartilha família com MGC-006. |
| MGC-185–192 | Transições de contexto revisadas quanto a manter, trocar ou remover filtros, período e métrica. Cada transição deve ser pontuada como plano novo do turno, sem reutilizar a evidência anterior como resposta. |
| MGC-193–201 | Perguntas compostas revisadas como etapas métricas independentes, com referências próprias e sem JOIN cru. O resultado só passa se todas as etapas pedidas forem respondidas e sustentadas; indisponibilidade de uma etapa não pode ser escondida por uma resposta parcial. |
| MGC-202–210 | Escopo, ausência de período, falta de cobertura, prompt injection, JOIN livre e dados pessoais revisados como estados negativos/limite. Todos os casos negativos agora declaram `sql_must_be_absent: true`. |
| MGC-211–220 | Dez perguntas individuais de UCs por classe cadastral, variando classes e formulações presentes na Gold v2. |
| MGC-221–230 | Dez perguntas individuais da fila de inspeção por prioridade, incluindo a categoria válida com zero ocorrências. |

## Correções aplicadas

- **MGC-162:** a pergunta de ranking por queda percentual estava classificada como respondível. F1 v12 não admite essa operação; o resultado esperado agora é `unsupported_no_SQL`.
- **MGC-175–184:** trocadas operações genéricas pela operação que o usuário realmente pede (total, média, razão de somas, ranking, retrato GD ou DEC/FEC ponderado).
- **MGC-183:** definida como ranking pela queda absoluta em kWh, consistente com MGC-010, com as mesmas janelas e desempate determinístico.
- **Casos negativos:** explicitada a exigência de não executar SQL em recusas, esclarecimentos, ausência de cobertura, acesso negado, fora de domínio e estruturas não autorizadas.
- **Famílias e holdout:** atribuído um `family_id` estável por tarefa semântica e uma divisão congelada de 186 diagnósticos / 44 holdout. Nenhuma família equivalente foi dividida entre os conjuntos. A lista e a política estão no JSON.

## Limites que continuam abertos

1. A Gold não tem decomposição preço-volume para jul/2024–jun/2025 contra jul/2025–jun/2026. O lote tem 1.106 linhas para jul/2022–jun/2023 contra jul/2025–jun/2026. MGC-015 é avaliável como comparação observada com aviso explícito; atribuição causal e decomposição continuam indisponíveis.
2. MGC-006 passou pela rota pública com perfil admin: DEC/FEC ponderados para jan–jun/2026 reconciliados com SQL e aviso de cobertura não certificada preservado.
3. As referências independentes abrangem os 219 casos com SQL esperado. O lote foi consultado em transação `READ ONLY`: 257 resultados de caso/métrica/período produziram 2.001 linhas, sem conjunto vazio; o único valor numérico nulo é MGC-041, no caso esperado de denominador zero. Os 11 casos restantes são estados sem SQL esperado. Os resultados completos estão em `GABARITOS_GOLD_MELHORIA_GERAL_CHATBOT.json`; o script de relatório é reproduzível a partir da saída do SQL.
4. O scan cobriu os grãos mensais município e município/classe em consumo/receita e as janelas anuais de MGC-015. Foram encontrados oito grupos com denominador de leitura zero, nenhum empate exato e nenhuma base zero nas janelas do MGC-015. Esses resultados não se estendem a métricas ou grãos não auditados.
5. A bateria contém famílias de consultas comparáveis; isso mede cobertura sistemática, não generalização ampla. Foram identificadas 198 famílias em 230 casos, sem família dividida entre diagnóstico e holdout; as 32 ocorrências adicionais são reformulações/transições intencionais, não 32 novas intenções independentes.

## Decisão de avaliação

A revisão semântica, a auditoria dirigida de diversidade e a auditoria de gabaritos estão concluídas para o snapshot indicado. MGC-015 é uma comparação observada com divulgação explícita de que a decomposição preço-volume pedida não existe para essas janelas; não permite atribuição causal. A divisão congelada contém 186 casos diagnósticos e 44 casos reservados, sem famílias semânticas divididas entre os splits. O holdout permanece fora de ajustes. A linha de base Gemini pela rota ainda precisa registrar modelo, prompt, controles, latência, custo e resultado por caso.
