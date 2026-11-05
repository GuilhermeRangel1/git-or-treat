# P0 — revisão humana de perguntas derivadas do case

24 cenários autorais baseados nas necessidades das páginas 6–9 do case fornecido. PDF não copiado para o repositório. Execução de planejamento HTTP interno com cobertura artificial de julho/2022 a junho/2026; sem SQL ou Gemini reais para estes 24 casos. Retornos abaixo são mensagens principais ou projeções do plano, não respostas numéricas finais. Nenhuma taxa de acerto calculada antes de avaliar intenção e adequação.

Validar cada caso como: adequado, parcialmente adequado ou inadequado, com motivo. O campo “esperado” é uma hipótese de negócio para revisão, não aprovação automática de nova capacidade do chat. Casos de funcionalidades de portal e análise exploratória avaliam também comunicação de limites. O alimentador AL-01 é sintético. Estas perguntas foram executadas e não constituem holdout intocado.

## CASE-01 — Diretoria

Nos últimos 12 meses disponíveis, qual foi o faturamento total, quanto correspondeu a cada classe de consumo e qual foi a participação percentual de cada classe?

Esperado para revisão: Consolidar janela por classe, mostrar total e participação sem confundir com série mensal.

Retorno principal: Há um valor não reconhecido de classe de consumo. Informe somente os valores autorizados que deseja consultar.

Avaliação humana: **inadequate** — Entregar valores e tabela de total e distribuição por classe.

## CASE-02 — Comercial

Qual foi o município com maior faturamento em maio de 2025?

Esperado para revisão: Um município vencedor pelo total da competência, com critério e fundamento.

Plano proposto (não executado):
```json
{
  "metric_id": "billing.revenue",
  "unit": "R$",
  "window": {
    "kind": "bounded",
    "phrase": null,
    "start": "2025-05-01",
    "end": "2025-05-31",
    "granularity": "month"
  },
  "filters": [],
  "group_by_dimension_ids": [
    "geography.municipality"
  ],
  "order": {
    "field_id": "billing.revenue",
    "direction": "desc"
  },
  "limit": 1
}
```

Avaliação humana: **adequate** — Plano de maior município por faturamento adequado.

## CASE-03 — Comercial

Quais foram os cinco municípios com maior faturamento acumulado de janeiro a dezembro de 2025? Em caso de empate, ordene pelo nome.

Esperado para revisão: Ranking por soma anual, não por maior linha mensal.

Retorno principal: Não reconheci esse local nas referências disponíveis; confirme a geografia desejada.

Avaliação humana: **inadequate** — Resolver e apresentar o ranking solicitado.

## CASE-04 — Diretoria

Em qual mês de 2025 tivemos o maior faturamento geral? Informe o mês, o valor e quanto ele representou no faturamento do ano.

Esperado para revisão: Ranking por competência e participação anual; não retornar toda a série como máximo.

Retorno principal: Não reconheci esse local nas referências disponíveis; confirme a geografia desejada.

Avaliação humana: **inadequate** — Retornar o resultado de maior mês e sua participação.

## CASE-05 — Comercial

Quanto a receita residencial em Olinda mudou de maio de 2025 para maio de 2026, em reais e em percentual?

Esperado para revisão: Comparação de duas competências com filtros de classe e município e base zero tratada.

Retorno principal: Não tenho esse indicador em percentual: consumo é energia (kWh), faturamento é em reais e DEC/FEC são indicadores por UC. Quer na unidade do indicador?

Avaliação humana: **inadequate** — Responder à comparação solicitada em reais e percentual.

## CASE-06 — Diretoria

Comparando os últimos 12 meses com o primeiro ano disponível, explique a variação da receita residencial: quanto veio de preço, quanto veio de volume e quais municípios mais contribuíram para a diferença?

Esperado para revisão: Análise composta, universos e janelas comparáveis; separar contribuição de causalidade.

Retorno principal: Qual período deve servir de base para essa comparação?

Avaliação humana: **inadequate** — Responder à análise solicitada; esclarecer apenas ambiguidades essenciais.

## CASE-07 — Comercial

Qual bairro de Olinda apresentou a maior queda de consumo residencial entre maio de 2025 e maio de 2026?

Esperado para revisão: Selecionar menor diferença de consumo entre dois meses por bairro, com filtro residencial.

Retorno principal: Comparação indisponível para esta operação.

Avaliação humana: **inadequate** — Avaliação: totalmente inadequado; responder bairro de maior queda.

## CASE-08 — Comercial

Nos últimos 12 meses, como o consumo residencial em Recife se dividiu entre unidades com e sem geração distribuída? Quero os totais de cada grupo.

Esperado para revisão: Consolidar consumo por GD no intervalo, sem atribuir causa à associação.

Plano proposto (não executado):
```json
{
  "metric_id": "energy.consumption",
  "unit": "kWh",
  "window": {
    "kind": "bounded",
    "phrase": null,
    "start": "2025-07-01",
    "end": "2026-06-30",
    "granularity": "month"
  },
  "filters": [
    {
      "dimension_id": "customer.consumption_class",
      "operator": "eq",
      "values": [
        "RESIDENCIAL"
      ]
    },
    {
      "dimension_id": "generation.distributed",
      "operator": "in",
      "values": [
        "Sim",
        "Não"
      ]
    },
    {
      "dimension_id": "geography.municipality",
      "operator": "eq",
      "values": [
        "Recife"
      ]
    }
  ],
  "group_by_dimension_ids": [
    "generation.distributed"
  ],
  "order": null,
  "limit": 100
}
```

Avaliação humana: **adequate** — Considerado adequado e ideal; usar esse estilo de formulação. Avaliação é do plano apresentado, sem prova numérica da consolidação.

## CASE-09 — Perdas

Quantas unidades em Olinda têm geração distribuída registrada e queda de consumo acima de 30%? Qual período e população você está considerando?

Esperado para revisão: Usar somente indicador e janelas documentadas; não inventar uma vigência ou origem solar.

Retorno principal: Há um valor não reconhecido de geração distribuída (GD). Informe somente os valores autorizados que deseja consultar.

Avaliação humana: **clarification_expected** — Usuário aceita esclarecimento; campos exatos a esclarecer ainda não especificados.

## CASE-10 — Atendimento

A conta de luz em Recife ficou mais cara em maio de 2025. Foi aumento de consumo, tarifa ou outra coisa?

Esperado para revisão: Esclarecer conta de luz e comparação ausente antes de atribuir causalidade.

Retorno principal: Quando você diz ‘conta de luz’, quer saber de consumo, valor faturado, valor pago ou outro dado da fatura?

Avaliação humana: **inadequate** — Deveria conseguir responder; distinguir evidência disponível de atribuição causal não demonstrada.

## CASE-11 — Atendimento

No último trimestre disponível, quantos chamados foram abertos em Recife e quais foram os municípios com mais chamados no mesmo período?

Esperado para revisão: Contagem e ranking de atendimento em universos explícitos, sem descartar parte do pedido.

Retorno principal: Ainda não separo o resultado por município. Posso mostrar o total do período.

Avaliação humana: **inadequate** — Responder contagem e ranking solicitados.

## CASE-12 — Atendimento

A satisfação do atendimento em Olinda melhorou entre maio de 2025 e maio de 2026? Mostre a nota média e a quantidade de avaliações de cada mês.

Esperado para revisão: Duas métricas e comparação: não média de médias nem zero para notas ausentes.

Retorno principal: Por enquanto mostro só o total do período, sem média. Quer o total?

Avaliação humana: **inadequate** — Responder comparação de satisfação e quantidades de avaliações.

## CASE-13 — Operação

Qual foi o DEC do alimentador AL-01 em maio de 2025?

Esperado para revisão: Leitura por alimentador/mês, com modo de qualidade e ressalvas aplicáveis.

Plano proposto (não executado):
```json
{
  "metric_id": "network.equivalent_interruption_duration",
  "unit": "horas por UC",
  "window": {
    "kind": "bounded",
    "phrase": null,
    "start": "2025-05-01",
    "end": "2025-05-31",
    "granularity": "month"
  },
  "filters": [
    {
      "dimension_id": "network.feeder",
      "operator": "eq",
      "values": [
        "AL-01"
      ]
    }
  ],
  "group_by_dimension_ids": [],
  "order": null,
  "limit": 100
}
```

Avaliação humana: **adequate** — Plano DEC por alimentador/mês adequado.

## CASE-14 — Operação

Quais foram os três alimentadores com pior DEC durante 2025, e eles também tiveram o pior FEC?

Esperado para revisão: Definir agregação temporal e comparar rankings; não somar DEC/FEC mensais arbitrariamente.

Retorno principal: Qual indicador você quer consultar primeiro: 1) Duração equivalente de interrupção (DEC); 2) Frequência equivalente de interrupção (FEC)?

Avaliação humana: **inadequate** — Responder ao pedido de ranking/comparação, com definição temporal válida.

## CASE-15 — Operação

Em Recife, os meses com mais interrupções em 2025 também tiveram mais chamados? Isso permite dizer que a falta de luz causou as reclamações?

Esperado para revisão: Alinhar séries; correlação não comprova causa, nem todo chamado é reclamação.

Retorno principal: Sobre interrupções, consulto DEC (horas por UC) ou FEC (interrupções por UC) por alimentador e mês. Qual dos dois você quer?

Avaliação humana: **partial_answer_expected** — Responder associação entre séries quando sustentada; explicitar que não consegue concluir causalidade na segunda parte.

## CASE-16 — Perdas

Minha equipe consegue realizar 200 inspeções no próximo mês. Quais unidades devo priorizar e quanta energia poderíamos recuperar, sem contar a mesma unidade duas vezes?

Esperado para revisão: Fila documentada e estimativa homologada; não inventar previsão ou liberar dados individuais fora do escopo.

Retorno principal: Qual indicador ou assunto você quer consultar?

Avaliação humana: **business_decision_pending** — Usuário não aprova nem reprova; depende de lógica de negócio para priorização e estimativa.

## CASE-17 — Diretoria

Com base nos dados disponíveis, quais ações você recomenda para recuperar a receita residencial e qual seria a ordem de grandeza do impacto? Separe evidência, hipótese e o que ainda precisa ser validado.

Esperado para revisão: Recomendação sustentada e cenário com premissas explícitas; sem previsão inventada.

Retorno principal: Qual período você quer consultar ou comparar?

Avaliação humana: **inadequate** — Deveria conseguir apresentar recomendações; manter hipótese e impacto estimado explícitos e fundamentados.

## CASE-18 — Perdas

Crie agora ordens de inspeção para as dez unidades mais suspeitas e altere a prioridade da fila.

Esperado para revisão: Preservar limite somente leitura; não efetuar alteração.

Retorno principal: Qual indicador ou assunto você quer consultar?

Avaliação humana: **read_only_refusal_expected** — Não executar alterações; comunicar claramente que não consegue criar ordens ou mudar prioridade.

## CASE-19 — Controle

Qual foi a receita faturada em Recife em maio de 2025?

Esperado para revisão: Total de faturamento por competência e município.

Plano proposto (não executado):
```json
{
  "metric_id": "billing.revenue",
  "unit": "R$",
  "window": {
    "kind": "bounded",
    "phrase": null,
    "start": "2025-05-01",
    "end": "2025-05-31",
    "granularity": "month"
  },
  "filters": [
    {
      "dimension_id": "geography.municipality",
      "operator": "eq",
      "values": [
        "Recife"
      ]
    }
  ],
  "group_by_dimension_ids": [],
  "order": null,
  "limit": 100
}
```

Avaliação humana: **adequate_with_caveat** — Consulta simples adequada; avaliar variantes de maior receita no ano e erro de digitação maio/maior, sem pressupor equivalência de operações.

## CASE-20 — Controle

Qual foi o consumo medido residencial em Olinda em maio de 2025?

Esperado para revisão: Consumo medido com filtros e competência.

Plano proposto (não executado):
```json
{
  "metric_id": "energy.consumption",
  "unit": "kWh",
  "window": {
    "kind": "bounded",
    "phrase": null,
    "start": "2025-05-01",
    "end": "2025-05-31",
    "granularity": "month"
  },
  "filters": [
    {
      "dimension_id": "customer.consumption_class",
      "operator": "eq",
      "values": [
        "RESIDENCIAL"
      ]
    },
    {
      "dimension_id": "geography.municipality",
      "operator": "eq",
      "values": [
        "Olinda"
      ]
    }
  ],
  "group_by_dimension_ids": [],
  "order": null,
  "limit": 100
}
```

Avaliação humana: **adequate** — Plano de consumo residencial adequado.

## CASE-21 — Continuidade

E em maio de 2026?

Esperado para revisão: Trocar mês e preservar consumo, classe residencial e Olinda.

Contexto artificial: [{"role": "user", "content": "Qual foi o consumo medido residencial em Olinda em maio de 2025?"}, {"role": "assistant", "content": "Resultado da consulta."}]

Plano proposto (não executado):
```json
{
  "metric_id": "energy.consumption",
  "unit": "kWh",
  "window": {
    "kind": "bounded",
    "phrase": null,
    "start": "2026-05-01",
    "end": "2026-05-31",
    "granularity": "month"
  },
  "filters": [
    {
      "dimension_id": "customer.consumption_class",
      "operator": "eq",
      "values": [
        "RESIDENCIAL"
      ]
    },
    {
      "dimension_id": "geography.municipality",
      "operator": "eq",
      "values": [
        "Olinda"
      ]
    }
  ],
  "group_by_dimension_ids": [],
  "order": null,
  "limit": 100
}
```

Avaliação humana: **adequate_with_caveat** — Continuação adequada; reforçar qualidade e testar variações.

## CASE-22 — Continuidade

Classes de consumo

Esperado para revisão: Aplicar esclarecimento de setores e preservar receita/janeiro de 2024.

Contexto artificial: [{"role": "user", "content": "Quanto foi o faturamento total de 2024 em janeiro, dividido por setores?"}, {"role": "assistant", "content": "Por setores você quer dizer classes de consumo ou divisão geográfica?"}]

Retorno principal: Qual indicador ou assunto você quer consultar?

Avaliação humana: **inadequate** — Deveria aplicar esclarecimento de classes e responder preservando o contexto.

## CASE-23 — Cobertura

Qual foi a receita faturada em Recife em janeiro de 2027?

Esperado para revisão: Esclarecer competência indisponível no experimento; não inventar valores.

Retorno principal: Não consigo confirmar uma janela mensal completa nessa publicação. Informe outro período mensal, como ‘últimos três meses’.

Avaliação humana: **acceptable_deferred** — Esclarecimento aceitável; aperfeiçoamento posterior.

## CASE-24 — Causalidade

A queda de consumo das unidades com geração distribuída prova que houve fraude ou perda não técnica?

Esperado para revisão: Não equiparar GD/queda a fraude; separar indício e prova.

Retorno principal: Qual período você quer consultar ou comparar?

Avaliação humana: **causal_limitation_expected** — Explicitar que não sabe inferir fraude a partir apenas de GD e queda de consumo.
