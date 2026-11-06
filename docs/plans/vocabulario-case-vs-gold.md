# Vocabulário do case e cobertura no projeto

Comparação documental entre [PRD](../PRD.md), [dicionário Gold](../dicionario_gold.md), [catálogo Gold](../gold-catalog.md) e [implementação por domínio](../contracts/genai-domain-implementation.md). Cobertura da Gold e do fluxo existente não implica cobertura no Text-to-SQL F1, restrito a faturamento.

| Termo | O que existe | Correspondência e limite |
| --- | --- | --- |
| Volume residencial (pergunta de Henrique) | O contexto do case indica volume de energia faturada em kWh; a Gold v2 atual publica consumo medido, que é outro indicador | Não responder com `consumo_total_kwh` como se fosse energia faturada. Informar a lacuna da medida faturada; oferecer consumo medido somente como alternativa explícita. Em conversa já delimitada a consumo medido, “volume residencial” pode herdar essa métrica. |
| Energia faturada | Consumo medido e consumo da base comparável | Nenhum desses dois campos comprova kWh efetivamente faturado. O PRD distingue as medidas. |
| Faturamento, receita comercial | Receita faturada em reais, com recorte por classe e município | Bate para faturamento. Crescimento percentual exige comparação de períodos equivalentes e base válida. |
| Conta de luz, pagamento, arrecadação | Valor faturado e consumo são conceitos separados no catálogo | O valor faturado não comprova pagamento. “Conta de luz” precisa de contexto. |
| Falta de luz, queda de luz, apagão | Ocorrências de rede e indicadores DEC/FEC | Interrupção é a leitura inicial. Contagem de eventos é diferente de FEC, que representa frequência equivalente. DEC representa duração equivalente. “Apagão” não comprova porte, causa ou população afetada. |
| Chamados, reclamações, satisfação | Métricas de protocolos e notas de atendimento | Total de protocolos não é total de reclamações. Satisfação usa notas válidas e não equivale a tempo de resolução. |
| Solar/GD com queda acima de 30% | Marcação cadastral GD e `queda_consumo_superior_30_pct` na Gold | A flag pronta usa jul/2022–jun/2023 e jul/2025–jun/2026. Jan–jun/2026 contra jan–jun/2025 exige recálculo com cobertura comparável. A marcação GD não data a instalação. |
| Tarifa e preço/volume | `tarifa_media_efetiva` em R$/kWh na base comparável | É preço observado, distinto de reajuste homologado. Decomposição exige receita e consumo na mesma população. |
| Último ano, meses atrás | Competências da publicação e resolução temporal do GenAI | Com junho/2026 como referência, últimos 12 meses = jul/2025–jun/2026. Exibir o recorte e sinalizar lacunas. |

Os percentuais de referência do case são premissas a reconciliar com a Gold. A revisão de negócio está em [vocabulário para revisão](vocabulário-case-revisao.md).
