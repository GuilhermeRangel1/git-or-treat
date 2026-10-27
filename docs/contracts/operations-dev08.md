# Operação — contratos backend DEV-08 1.1.0 e summary 1.2.0

Requisitos WEB-06 e WEB-07; depende de DEV-01. Integração Gold/DE-05 futura. O portal consome estes contratos na página `/operacao`, com filtros, consolidado, ranking e detalhe do alimentador; veja o [guia do frontend](../services/frontend.md#operação--dev-08). A rota DEV-01 `/operations/continuity` preserva o contrato 1.0.0.

## Consultas

Prefixo `/api/v1/operations`. Ativar explicitamente `ANALYTICS_SOURCE=synthetic`. Sem fonte disponível, retorna 503, sem fallback. Swagger em `/docs` descreve os schemas e envelopes de erro.

- `GET /series`: série mensal em `data.items`, ordenada por competência e ID do alimentador. Inclui meses sem eventos: zero apenas quando a cobertura é conhecida; fora da cobertura, valores nulos.
- `GET /ranking?metric=dec`: ranking decrescente do DEC no total da janela. `metric=fec` usa FEC. Empates são desfeitos pelo ID. `data.items` contém apenas resultados `available`; `data.excluded` preserva alimentadores parciais/indisponíveis e suas limitações, sem atribuir posição.
- `GET /feeders/{feeder_id}`: `data.summary`, `data.series`, `data.occurrences` e `pagination` na raiz. `page` começa em 1, `page_size` entre 1 e 100 (padrão 20); a paginação afeta somente as ocorrências. Ordenação por competência, evento e UC. Alimentador inexistente retorna 404 `not_found`.
- `GET /continuity`: lista já existente de alimentadores e indicadores, que pode alimentar as opções do filtro. Nenhum município pode ser inferido exclusivamente de um alimentador que atravessa vários municípios.
- `GET /summary`: consolidado demonstrativo de DEC/FEC sobre os alimentadores elegíveis em toda a janela. A resposta tem `contract_version=1.2.0`; as demais rotas mantêm os contratos existentes (1.0.0 em `/continuity`, 1.1.0 nas consultas DEV-08).

Todas as novas consultas aceitam `periodo=YYYY-MM` ou `competencia_inicio`/`competencia_fim`, com extremos inclusivos. Não combinar o alias com intervalo. Padrão janeiro–fevereiro/2025, preservado da DEV-01. Janela máxima de 120 competências; parâmetros inválidos retornam 422 `invalid_query`. Série e ranking aceitam `alimentador` exato, validado na fonte. No detalhe, o ID do path é o filtro efetivo.

Exemplos:

```text
GET /api/v1/operations/series?alimentador=AL-01&competencia_inicio=2025-01&competencia_fim=2025-02
GET /api/v1/operations/ranking?periodo=2025-02&metric=dec
GET /api/v1/operations/feeders/AL-01?page=1&page_size=20
```

## Definicao demonstrativa

DEC = soma das horas dos registros UC-interrupção / denominador de UCs do alimentador. Unidade: h/UC. FEC = quantidade de registros UC-interrupção / mesmo denominador. Unidade: interrupções/UC. Cada registro representa uma UC afetada; interrupções repetidas da mesma UC contam separadamente. Não é uma contagem de UCs distintas nem de eventos de rede agrupados.

A população demonstrativa usa UCs ativas do snapshot; o denominador é configurado por alimentador, constante durante a janela. Isso é uma hipótese herdada da DEV-01, sem homologação para dados reais. O período acumulado é calculado dos registros originais, nunca pela soma de meses arredondados. Mantém três casas e o arredondamento da DEV-01.

Cada resposta DEV-08 existente inclui `data.definition` com referência, fórmulas, unidades, grão, população e arredondamento. Cada ponto contém `period` solicitado, `observed_period` ou null, numerador `duration_hours_sum`, contagem de registros, denominador, população atendida/coberta, cobertura, status e limitações. `metadata` registra filtros efetivos, fonte, versão, atualização e janela. Essas consultas mantêm `contract_version=1.1.0`.

### Consolidado `/summary` — contrato 1.2.0

`data.summary` contém `period`, `observed_period`, `dec_hours_per_uc`, `fec_interruptions_per_uc`, `duration_hours_sum`, `interruption_count`, `denominator_uc_count`, `served_uc_count`, `included_uc_count`, `included_feeder_ids`, `excluded_feeder_ids`, `status`, `limitations` e `text_alternative`. A população atendida é a contagem cadastral ativa no recorte; `included_uc_count` é a soma dos denominadores positivos efetivamente incluídos.

A elegibilidade exige estado `available` durante toda a janela solicitada e denominador inteiro positivo. DEC é a soma das durações originais dos registros UC-interrupção dividida pela soma dos denominadores incluídos; FEC é a contagem original desses registros dividida pela mesma base. Só o resultado consolidado é arredondado a três casas. Não se agregam indicadores arredondados por alimentador. `data.definition` continua sendo `ContinuityDefinition`, com as fórmulas agregadas e a regra de inclusão explícita.

Se houver alimentadores excluídos, a resposta tem estado `partial` e identifica a base incluída e cada exclusão em `limitations`. Com fonte sem alimentadores, o estado é `empty`. Com alimentadores, mas sem elegíveis, o estado é `unavailable` e numeradores/indicadores/denominador consolidados são `null`; IDs e população cadastral permanecem explícitos. Zero DEC/FEC só é retornado quando há base elegível e cobertura temporal completa conhecida. O endpoint aceita os filtros de período já documentados e `alimentador` opcional, com o limite de 120 competências.

Denominador nulo ou zero produz DEC/FEC nulos, estado indisponível e exclusão do ranking. As ocorrências observadas continuam consultáveis. Janela parcial divulga sua interseção com a cobertura e não compete no ranking. Cobertura desconhecida ou janela externa não permite inferir zero pela ausência de eventos. `duration_hours_sum=0` e contagem zero nessas janelas são apenas a soma/lista observada vazia; não representam ausência comprovada de interrupções. Sempre interpretar com status e `observed_period`.

Cada ponto oferece `text_alternative` em português com indicador, unidade, janela, denominador, estado e identificação demonstrativa. As mesmas linhas podem alimentar uma tabela acessível no frontend. Renderização, navegação e acessibilidade da tela dependem da implementação de frontend.

## Controles independentes

Fixture canônica DEV-01: AL-01 tem denominador 2, evento de 2h em janeiro e de 1h em fevereiro. Janeiro: DEC 1, FEC 0,5; fevereiro: DEC 0,5, FEC 0,5; janela: DEC 1,5, FEC 1. AL-02 tem denominador 2 e um evento de 3h em fevereiro: janeiro zero conhecido; fevereiro/janela DEC 1,5, FEC 0,5. AL-03 não tem denominador e fica excluído. Em fevereiro o ranking DEC é AL-02 antes de AL-01; o ranking FEC empata e usa ID.

No summary de janeiro–fevereiro/2025, AL-01 e AL-02 somam 6 horas, 3 registros e denominador 4: DEC 1,5 h/UC e FEC 0,75 interrupções/UC. AL-03 permanece excluído por denominador ausente, então o status consolidado é `partial`.

Os testes HTTP em `backend/tests/test_operations_dev08.py` conferem esses resultados manuais contra série, ranking e detalhe, sem usar o cálculo do serviço como oráculo. Cobrem também paginação, validação, ocorrências repetidas da mesma UC, cobertura desconhecida/parcial, denominador zero/nulo, fonte indisponível e OpenAPI.

## Referências e limites

Foi consultada a estrutura do frame Figma `16:735`, arquivo `oTjmpIBgbA7OOYb9ZmMG9K`: DEC/FEC, base atendida, cobertura, território e abertura do alimentador. Os números e identificadores ilustrativos do desenho não substituem a fixture canônica.

A fonte é injetada por `AnalyticsRepository`; nenhum modelo, migração ou escrita de banco foi alterado. A futura DE-05 precisa homologar grão, deduplicação, duração, população e denominador temporal no dicionário Gold, implementar consultas filtradas/agregadas na fonte e reconciliar Gold → API → portal. Não se reivindica conformidade regulatória nem conclusão integral de WEB-06/WEB-07.

FastAPI local 0.143.3, Pydantic 2.14.1. Documentação oficial consultada via Context7 em 26/10/2026: [modelos de resposta](https://fastapi.tiangolo.com/tutorial/response-model/) e [limites de paginação](https://fastapi.tiangolo.com/tutorial/sql-databases/). Mantidos `response_model`, `Depends`, `Query` e os envelopes existentes.


## Proteções da revisão de 26/10/2026

Todas as rotas de Operação rejeitam parâmetros desconhecidos ou repetidos com 422 `invalid_query`, antes de resolver a fonte. No detalhe, informar `alimentador` na query não substitui o ID do path: esse parâmetro é recusado. Isso evita filtros silenciosamente ignorados e interpretações divergentes de parâmetros duplicados. As respostas de Operação, inclusive erros, incluem `Cache-Control: no-store`.

O denominador precisa ser inteiro positivo; nulo, zero ou negativo não permite calcular DEC/FEC. Inteiros zero e negativos permanecem explícitos na resposta, com estado indisponível. Valores de origem que não sejam inteiros — incluindo booleanos, floats e strings, mesmo strings numéricas — são normalizados para `null` antes da validação do schema e também não permitem calcular DEC/FEC. Essa normalização não interrompe a resposta dos demais alimentadores nem oculta ocorrências observadas. O status da cobertura compara as contagens originais, sem usar a razão arredondada: 2000 UCs cobertas / denominador 2001 continua parcial, mesmo quando a razão exibida é 1,000, e fica fora do ranking.

Os controles existentes de host, limites de corpo e headers continuam compartilhados. Estas proteções não implementam identidade ou autorização de leitura por usuário/território para a área analítica. Antes de conectar dados reais ou disponibilizar o portal externamente, essa autorização precisa ser implementada e homologada. A revisão foi estática e por testes HTTP; não incluiu pentest, scan de dependências ou infraestrutura.

## Organização interna

A composição, seleção e paginação do detalhe ficam no serviço `build_feeder_detail`, com retorno `OperationDetailResponse`. A rota apenas valida entrada, injeta a fonte e delega. As rotas têm retornos tipados. A classe HTTP `StrictAnalyticsRoute` usa a detecção de parâmetros repetidos compartilhada com Receita; não muda a política de parâmetros desconhecidos de Receita nem os envelopes existentes.
