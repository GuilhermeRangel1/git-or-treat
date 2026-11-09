# Gabaritos de referência — amostra inicial da Melhoria Geral

## Proveniência

- Execução de leitura em 09/11/2026, em transações PostgreSQL marcadas `READ ONLY`.
- Publicação consultada: `schema_version=gold-csv-v2`, lote `GOLD_20261103T173853Z_76c37784`, publicação `9a42137a-399e-4974-876d-0169bdc530e0`, fingerprint `d1e9d3cb4455895155c09da82865807f5f83a608f832246be91e08063d158856`.
- As consultas em [REFERENCIAS_SQL_MELHORIA_GERAL_CHATBOT.sql](REFERENCIAS_SQL_MELHORIA_GERAL_CHATBOT.sql) foram formuladas diretamente sobre as fontes Gold v2 e executadas numa transação `READ ONLY`; servem como cálculo independente da rota F1. Não são saídas do chatbot.
- O papel de leitura não tem `SELECT` em `gold_v2.cobertura_dominios`. Por isso, os valores não certificam prontidão, grants nem completude declarada. A avaliação pela rota ainda deve registrar esses estados; não se deve tratar falha de controle como zero.
- Valores decimais aqui mantêm mais casas para comparação; a precisão exibida ao usuário deve seguir a unidade e o contrato da métrica.
- A consulta de MGC-005 confirmou 3.510 UCs com GD, 3.388 elegíveis, 3.111 flags e 3.111 recálculos independentes, com zero divergência entre flag e cálculo nos elegíveis.

## Referências da bateria completa

Os gabaritos numéricos para os 219 casos que devem executar SQL estão em [GABARITOS_GOLD_MELHORIA_GERAL_CHATBOT.json](GABARITOS_GOLD_MELHORIA_GERAL_CHATBOT.json). A execução READ ONLY de [REFERENCIAS_GOLD_MGC_230.sql](REFERENCIAS_GOLD_MGC_230.sql) produziu 257 resultados caso/métrica/período e 2.001 linhas no snapshot acima: zero conjuntos vazios e um único NULL numérico, esperado em MGC-041 para denominador zero. Os 11 casos de recusa, esclarecimento ou limite não têm SQL e são avaliados pelo estado esperado.

O relatório inclui deltas por grupo e rankings derivados das consultas independentes. MGC-015 foi reconciliado com o ranking e as variações por classe do fixture; não existe decomposição publicada para a janela solicitada, então o caso exige disclosure explícito e não autoriza atribuir causalidade. MGC-184 também inclui a agregação DEC/FEC ponderada de jan–jun/2026: DEC 0,5385047281323877 h/UC e FEC 0,299645390070922 ocorrências/UC, com 564 UCs contadas uma única vez; os valores observados não certificam cobertura.

Para reproduzir o relatório, execute o SQL em conexão Gold v2 somente leitura e salve a saída de `psql -X -q -A -t` num arquivo. Então rode `python backend/scripts/build_mgc_gold_reference_report.py <arquivo-de-saida>`. Isso recalcula as referências e os deltas sem chamar Gemini nem a rota F1.

## Resultados observados

| Caso | Gabarito independente da Gold ativa | Fonte e observação |
| --- | --- | --- |
| MGC-001 | Recife, 2026-06: **R$ 4.313.585,27**; consumo medido associado **5.353.512 kWh**; **16.602** UCs com leitura | `diagnostico_receita`, filtrado por município e competência. O valor de R$ 10.864.353,97 visto anteriormente é o total territorial sem filtro de Recife. |
| MGC-002 | Recife, 2026-06: Comercial **1.130.524 kWh**; Industrial **2.437.945 kWh**; Poder Público **115.335 kWh**; Residencial **1.611.976 kWh**; Rural **57.732 kWh**. Total **5.353.512 kWh**. | `diagnostico_receita`; soma dos grupos reconcilia com MGC-001. |
| MGC-003 | **322,461872 kWh/UC com leitura** (`5.353.512 / 16.602`) | `diagnostico_receita`; razão das somas, não média das médias. |
| MGC-004 | **3.510 UCs com GD** no lote | `variacao_consumo_uc`, contagem de UCs distintas com `possui_gd='Sim'`. É retrato do lote. |
| MGC-005 | **3.111 UCs elegíveis** com queda >30%; **3.388** UCs com GD atingem pelo menos seis leituras em cada janela. | `variacao_consumo_uc` reconciliada independentemente com `consumo_mensal_uc` para jul/2022–jun/2023 e jul/2025–jun/2026. Entre os elegíveis, a flag publicada e o recálculo da queda tiveram **0 divergências**. |
| MGC-006 | ALM-ABR-001, jan–jun/2026: **DEC ponderado 0,538505 h/UC** (numerador 303,7166667 / 564 UCs) e **FEC ponderado 0,299645 ocorrências/UC** (numerador 169 / 564 UCs). As seis competências têm denominador 564 e numeradores presentes para os dois indicadores. | `indicadores_dec_fec`; filtro fixo pelo alimentador; soma dos seis numeradores dividida por um denominador único. O SQL independente foi executado em transação somente leitura; isso não certifica cobertura. Em 09/11, pela rota pública autenticada como admin, a pergunta conjunta pediu esclarecimento entre DEC/FEC; pedidos separados para jan–jun retornaram série mensal, não a razão ponderada do período. Após a correção, a rota pública autenticada como admin respondeu a razão ponderada para o período completo: DEC 0,5385047281 h/UC e FEC 0,2996453901 ocorrências/UC. Os dois valores reconciliaram com o SQL independente e a resposta manteve o aviso de cobertura observada não certificada; MGC-006 passou no comportamento agregado esperado. |
| MGC-007 | Média **4,098466**; **6.260** notas não nulas em **6.433** protocolos abertos em jun/2026. | `atendimentos_uc`, abertura em UTC; nulos ignorados e zero continua nota válida. A consulta não certifica cobertura mensal. |
| MGC-008 | **6.433 protocolos** abertos em jun/2026 UTC. | `atendimentos_uc`; contagem de protocolos distintos. A consulta não certifica cobertura mensal. |
| MGC-009 | **0,755715 R$/kWh**, exibível como **R$ 0,7557/kWh** | Razão de `receita_base_comparavel_reais / consumo_base_comparavel_kwh` em `diagnostico_receita`, Recife, 2026-06. Preço observado, não tarifa homologada. |
| MGC-010 | Quedas mais altas: Jaboatão dos Guararapes **−1.578.750 kWh** (33.103.977 → 31.525.227; **−4,7691%**); Recife **−1.561.364 kWh** (79.821.812 → 78.260.448; **−1,9561%**); Olinda **−280.631 kWh** (19.589.430 → 19.308.799; **−1,4326%**). | `diagnostico_receita`, jul/2024–jun/2025 contra jul/2025–jun/2026; ordenar pela diferença período 2 menos período 1, ascendente para maiores quedas. Há 14 municípios com dados nos dois períodos. |
| MGC-011 | Por classe, consumo (P0 → P1; variação kWh): Comercial **44.800.999 → 42.485.399; −2.315.600**; Industrial **78.598.296 → 78.293.911; −304.385**; Poder Público **3.768.846 → 3.826.040; +57.194**; Residencial **71.909.990 → 70.463.244; −1.446.746**; Rural **2.066.144 → 2.077.522; +11.378**. Receita por classe (P0 → P1; variação R$): Comercial **39.264.777,51 → 40.545.062,59; +1.280.285,08**; Industrial **63.278.892,10 → 57.842.238,79; −5.436.653,31**; Poder Público **3.348.593,86 → 3.692.623,33; +344.029,47**; Residencial **59.021.018,52 → 60.676.634,77; +1.655.616,25**; Rural **1.829.182,07 → 2.007.268,05; +178.085,98**. | Duas agregações independentes sobre `diagnostico_receita`; mesmas janelas e classes. Os universos são métricas distintas; esses resultados não provam causalidade nem autorizam um JOIN de fatos. |
| MGC-012 | Turno 1 Recife: **R$ 4.313.585,27**. Turno 2 Olinda, preservando 2026-06: **R$ 1.068.679,93**. | `diagnostico_receita`; no segundo turno deve trocar apenas o município. |
| MGC-013 | Turno 1 consumo Recife: **5.353.512 kWh**. Turno 2 receita no mesmo recorte: **R$ 4.313.585,27**. | `diagnostico_receita`; troca a métrica e unidade, preserva localidade e competência. |
| MGC-014 | **Pedir esclarecimento; não executar SQL.** | Estado esperado pelo contrato, sem gabarito numérico. Rodada isolada e rodada com contexto anterior são avaliações separadas. |
| MGC-015 | Referência jul/2024–jun/2025; recente jul/2025–jun/2026; 14 municípios com as duas janelas completas. Top quedas: Jaboatão **−1.578.750 kWh** (−4,7691%), Recife **−1.561.364 kWh** (−1,9561%), Olinda **−280.631 kWh** (−1,4326%). Variação total de receita: −R$ 1.132.818,13; −R$ 905.207,44; −R$ 88.863,75, respectivamente. | Gabarito independente por município/classe abaixo. A tabela de decomposição tem zero linhas para essas janelas e 1.106 linhas para jul/2022–jun/2023 vs. jul/2025–jun/2026. A avaliação MGC-015 aceita comparação observada com aviso claro; não aceita alegação de causalidade preço/volume. |
| MGC-041 | **Indisponível (NULL), nunca zero**: uma linha Gold para IGARASSU / PODER PUBLICO / 2023-06; `qtd_ucs_com_leitura=0`, `consumo_total_kwh=NULL`. | `diagnostico_receita`; a razão de somas não tem denominador positivo. Caso real de borda adicionado à diversidade; a prontidão e autorização continuam obrigatórias na rota. |

## Consultas de reprodução

Todos os exemplos usam exclusivamente fontes Gold v2 e podem ser executados em uma transação somente leitura. Os valores adicionais de MGC-015 foram conferidos em consultas SQL independentes que agregam cada janela separadamente; a reprodução integral e os limites da decomposição estão em `REFERENCIAS_SQL_MELHORIA_GERAL_CHATBOT.sql`. Em pseudocódigo SQL:

### MGC-015 — Variação por município e classe

| Município | Classe | Δ consumo (kWh) | Δ receita faturada (R$) |
| --- | --- | ---: | ---: |
| Jaboatão dos Guararapes | Comercial | −968.990 | −367.222,28 |
| Jaboatão dos Guararapes | Industrial | −158.568 | −930.345,59 |
| Jaboatão dos Guararapes | Poder Público | +23.024 | +62.046,83 |
| Jaboatão dos Guararapes | Residencial | −478.914 | +68.323,93 |
| Jaboatão dos Guararapes | Rural | +4.698 | +34.378,98 |
| Recife | Comercial | −1.034.244 | +510.261,75 |
| Recife | Industrial | +207.113 | −2.148.035,93 |
| Recife | Poder Público | −876 | +159.163,17 |
| Recife | Residencial | −736.062 | +507.445,43 |
| Recife | Rural | +2.705 | +65.958,14 |
| Olinda | Comercial | −30.531 | +258.801,54 |
| Olinda | Industrial | −215.882 | −620.662,35 |
| Olinda | Poder Público | +11.937 | +22.707,76 |
| Olinda | Residencial | −45.181 | +235.666,42 |
| Olinda | Rural | −974 | +14.622,88 |

```sql
-- MGC-001/002/003/009/012/013: fonte no grão municipal-classe
SELECT
  SUM(receita_total_reais),
  SUM(consumo_total_kwh),
  SUM(qtd_ucs_com_leitura),
  SUM(consumo_total_kwh) / NULLIF(SUM(qtd_ucs_com_leitura), 0),
  SUM(receita_base_comparavel_reais)
    / NULLIF(SUM(consumo_base_comparavel_kwh), 0)
FROM gold_v2.diagnostico_receita
WHERE competencia = '2026-06' AND municipio = 'RECIFE';

-- MGC-002: a mesma população, agrupada por classe_consumo
SELECT classe_consumo, SUM(consumo_total_kwh)
FROM gold_v2.diagnostico_receita
WHERE competencia = '2026-06' AND municipio = 'RECIFE'
GROUP BY classe_consumo ORDER BY classe_consumo;

-- MGC-005: validar a flag publicada contra médias mensais independentes
-- de consumo_mensal_uc, preservando tem_leitura e as duas janelas fixas.
-- A contagem só inclui GD, seis ou mais leituras em cada janela e queda < -30%.

-- MGC-006: por alimentador, exigir seis competências, denominador positivo
-- constante e numerador válido em todas; dividir soma dos numeradores pelo
-- denominador único. Não agregar nem fazer média dos campos DEC/FEC publicados.

-- MGC-010/015: agregar cada janela por município antes de comparar; delta
-- = total_p1 - total_p0; percentual = 100 * delta / NULLIF(total_p0, 0).

-- MGC-011/015: repetir a agregação por classe para consumo e receita em
-- consultas independentes. Não fazer JOIN entre fatos crus.
```

## Estado da amostra

MGC-001–MGC-015 têm especificação e referência independente; o baseline ainda não foi executado. MGC-006 foi conferido pela rota pública sob perfil admin e conciliou DEC/FEC ponderados com o SQL independente, preservando o aviso de cobertura não certificada. MGC-015 está especificado como comparação limitada, com períodos, população, ranking e deltas por classe reproduzíveis. A publicação não contém a decomposição preço-volume solicitada; por isso o teste exige declarar essa ausência e proíbe inferir causalidade. A auditoria de dados também encontrou oito grupos município/classe/mês com denominador de leitura zero; MGC-041 registra um exemplo real. Os valores dependem do snapshot acima e devem ser recalculados se a publicação mudar.
