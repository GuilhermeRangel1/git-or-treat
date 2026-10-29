# ADR-0015 — Consolidado demonstrativo de continuidade

**Estado:** aprovado pela pessoa usuária em 26/10/2026 para DEV-08; definição Gold/DE-05 permanece pendente.

Os cards da visão geral de Operação no layer 06 do protótipo precisam de DEC/FEC consolidados. A API existente entrega indicadores por alimentador; médias simples ou somas desses indicadores não representam o conjunto. A pessoa usuária escolheu ampliar o backend e aprovou o [desenho](../plans/2026-10-26-dev08-operacao-design.md).

O consolidado demonstrativo inclui somente alimentadores com base válida e cobertura completa na janela solicitada (`available`). DEC é a soma das durações originais dividida pela soma dos denominadores incluídos; FEC é a quantidade original de registros UC-interrupção dividida pela mesma base. Arredondar apenas o resultado final, em três casas, com a regra demonstrativa já existente. Não calcular a média dos indicadores nem agregar resultados previamente arredondados.

Quando há exclusões, o consolidado recebe estado `partial`, com IDs incluídos/excluídos, população cadastral do recorte, população incluída, denominador, numeradores, janela observada, origem e limitações explícitos. Os valores representam a base incluída, não todos os alimentadores. Sem elegíveis, os indicadores, numeradores incluídos e denominador ficam nulos; a ausência de alimentadores produz estado `empty`. Zero requer base e cobertura conhecidas. As ocorrências dos alimentadores excluídos continuam consultáveis no detalhe.

Na amostra sintética janeiro–fevereiro/2025, AL-01 e AL-02 contribuem 6 horas, 3 registros e base de 4 UCs: DEC 1,5 h/UC e FEC 0,75 interrupções/UC. AL-03, sem denominador, fica explicitamente excluído. Essa escolha fornece uma leitura útil da base conhecida; a alternativa de ocultar todo indicador sempre que um alimentador estivesse indisponível foi apresentada e não escolhida.

`GET /api/v1/operations/summary` publica essa definição no contrato 1.2.0; os contratos anteriores permanecem disponíveis. O frontend apresenta os valores fornecidos e identifica a base parcial. A integração Gold futura deve homologar população, grão, vigência, duração, deduplicação e a regra de consolidação antes de substituir a fonte. Não se reivindica apuração ou conformidade regulatória oficial.
