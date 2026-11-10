-- Gabaritos independentes da amostra inicial e das bordas Gold auditadas (MGC-001..015, MGC-041).
-- Executar em Gold v2, em sessão somente leitura, no snapshot registrado no MD.
BEGIN TRANSACTION READ ONLY;

-- MGC-001: faturamento de Recife em jun/2026.
SELECT SUM(receita_total_reais) AS receita_reais
FROM gold_v2.diagnostico_receita
WHERE competencia = '2026-06' AND municipio = 'RECIFE';

-- MGC-002: consumo por classe; a soma dos grupos deve reconciliar com MGC-001.
SELECT classe_consumo, SUM(consumo_total_kwh) AS consumo_kwh
FROM gold_v2.diagnostico_receita
WHERE competencia = '2026-06' AND municipio = 'RECIFE'
GROUP BY classe_consumo
ORDER BY classe_consumo;

-- MGC-003: razão de somas, sem média de médias.
SELECT SUM(consumo_total_kwh) / NULLIF(SUM(qtd_ucs_com_leitura), 0) AS kwh_por_uc_com_leitura
FROM gold_v2.diagnostico_receita
WHERE competencia = '2026-06' AND municipio = 'RECIFE';

-- MGC-004: retrato cadastral de UCs com GD no lote.
SELECT COUNT(DISTINCT id_uc) AS ucs_com_gd
FROM gold_v2.variacao_consumo_uc
WHERE possui_gd = 'Sim';

-- MGC-005: gabarito de flag publicado e conferência independente pelas leituras.
WITH leituras AS (
    SELECT id_uc,
           COUNT(*) FILTER (WHERE competencia BETWEEN '2022-07' AND '2023-06' AND tem_leitura) AS meses_p0,
           AVG(consumo_kwh::numeric) FILTER (WHERE competencia BETWEEN '2022-07' AND '2023-06' AND tem_leitura) AS media_p0,
           COUNT(*) FILTER (WHERE competencia BETWEEN '2025-07' AND '2026-06' AND tem_leitura) AS meses_p1,
           AVG(consumo_kwh::numeric) FILTER (WHERE competencia BETWEEN '2025-07' AND '2026-06' AND tem_leitura) AS media_p1
    FROM gold_v2.consumo_mensal_uc
    GROUP BY id_uc
), validacao AS (
    SELECT v.id_uc, v.queda_consumo_superior_30_pct,
           l.meses_p0, l.media_p0, l.meses_p1, l.media_p1,
           (l.meses_p0 >= 6 AND l.meses_p1 >= 6 AND l.media_p0 > 0
            AND (l.media_p1 - l.media_p0) / l.media_p0 * 100 < -30) AS queda_recalculada
    FROM gold_v2.variacao_consumo_uc v
    JOIN leituras l USING (id_uc)
    WHERE v.possui_gd = 'Sim'
)
SELECT COUNT(*) AS ucs_gd,
       COUNT(*) FILTER (WHERE meses_p0 >= 6 AND meses_p1 >= 6) AS elegiveis,
       COUNT(*) FILTER (WHERE meses_p0 >= 6 AND meses_p1 >= 6 AND queda_consumo_superior_30_pct IS TRUE) AS flag_gold,
       COUNT(*) FILTER (WHERE meses_p0 >= 6 AND meses_p1 >= 6 AND queda_recalculada IS TRUE) AS queda_recalculada,
       COUNT(*) FILTER (WHERE meses_p0 >= 6 AND meses_p1 >= 6 AND media_p0 > 0
                         AND queda_consumo_superior_30_pct IS DISTINCT FROM queda_recalculada) AS divergencias
FROM validacao;

-- MGC-006: resultado individual por alimentador; NULL significa inelegível.
WITH por_alimentador AS (
    SELECT id_alimentador,
           COUNT(DISTINCT competencia) AS competencias,
           MIN(total_ucs_alimentador) AS denominador_min,
           MAX(total_ucs_alimentador) AS denominador_max,
           COUNT(*) FILTER (WHERE duracao_total_interrupcoes_horas IS NOT NULL) AS meses_dec_validos,
           COUNT(*) FILTER (WHERE frequencia_total_interrupcoes IS NOT NULL) AS meses_fec_validos,
           SUM(duracao_total_interrupcoes_horas) AS numerador_dec,
           SUM(frequencia_total_interrupcoes) AS numerador_fec
    FROM gold_v2.indicadores_dec_fec
    WHERE competencia BETWEEN '2026-01' AND '2026-06'
      AND id_alimentador = 'ALM-ABR-001'
    GROUP BY id_alimentador
)
SELECT id_alimentador,
       CASE WHEN competencias = 6 AND denominador_min > 0
                  AND denominador_min = denominador_max AND meses_dec_validos = 6
            THEN numerador_dec / denominador_min END AS dec_ponderado,
       CASE WHEN competencias = 6 AND denominador_min > 0
                  AND denominador_min = denominador_max AND meses_fec_validos = 6
            THEN numerador_fec::numeric / denominador_min END AS fec_ponderado
FROM por_alimentador
ORDER BY id_alimentador;

-- MGC-007/008: junho UTC, média das notas válidas e contagem de protocolos.
SELECT COUNT(DISTINCT protocolo) AS protocolos,
       AVG(nota_satisfacao::numeric) AS media_satisfacao,
       COUNT(nota_satisfacao) AS notas_validas
FROM gold_v2.atendimentos_uc
WHERE data_abertura >= TIMESTAMPTZ '2026-06-01 00:00:00+00'
  AND data_abertura <  TIMESTAMPTZ '2026-07-01 00:00:00+00';

-- MGC-009: preço observado em população comparável, não tarifa regulada.
SELECT SUM(receita_base_comparavel_reais)
       / NULLIF(SUM(consumo_base_comparavel_kwh), 0) AS preco_observado_reais_kwh
FROM gold_v2.diagnostico_receita
WHERE competencia = '2026-06' AND municipio = 'RECIFE';

-- MGC-010: todos os municípios, janelas comuns e desempate determinístico.
WITH p0 AS (
    SELECT municipio, SUM(consumo_total_kwh) AS consumo_p0
    FROM gold_v2.diagnostico_receita
    WHERE competencia BETWEEN '2024-07' AND '2025-06'
    GROUP BY municipio
), p1 AS (
    SELECT municipio, SUM(consumo_total_kwh) AS consumo_p1
    FROM gold_v2.diagnostico_receita
    WHERE competencia BETWEEN '2025-07' AND '2026-06'
    GROUP BY municipio
)
SELECT p0.municipio, p0.consumo_p0, p1.consumo_p1,
       p1.consumo_p1 - p0.consumo_p0 AS variacao_kwh,
       100 * (p1.consumo_p1 - p0.consumo_p0) / NULLIF(p0.consumo_p0, 0) AS variacao_pct
FROM p0 JOIN p1 USING (municipio)
ORDER BY variacao_kwh ASC, p0.municipio ASC;

-- MGC-011: duas agregações por classe em fonte comum; sem JOIN de fatos crus.
WITH p0 AS (
    SELECT classe_consumo, SUM(consumo_total_kwh) AS consumo_kwh,
           SUM(receita_total_reais) AS receita_reais
    FROM gold_v2.diagnostico_receita
    WHERE competencia BETWEEN '2024-07' AND '2025-06'
    GROUP BY classe_consumo
), p1 AS (
    SELECT classe_consumo, SUM(consumo_total_kwh) AS consumo_kwh,
           SUM(receita_total_reais) AS receita_reais
    FROM gold_v2.diagnostico_receita
    WHERE competencia BETWEEN '2025-07' AND '2026-06'
    GROUP BY classe_consumo
)
SELECT p0.classe_consumo,
       p0.consumo_kwh AS consumo_p0, p1.consumo_kwh AS consumo_p1,
       p1.consumo_kwh - p0.consumo_kwh AS variacao_consumo_kwh,
       p0.receita_reais AS receita_p0, p1.receita_reais AS receita_p1,
       p1.receita_reais - p0.receita_reais AS variacao_receita_reais
FROM p0 JOIN p1 USING (classe_consumo)
ORDER BY p0.classe_consumo;

-- MGC-012/013: mesmo recorte temporal, município explícito.
SELECT municipio, SUM(receita_total_reais) AS receita_reais,
       SUM(consumo_total_kwh) AS consumo_kwh
FROM gold_v2.diagnostico_receita
WHERE competencia = '2026-06' AND municipio IN ('RECIFE', 'OLINDA')
GROUP BY municipio ORDER BY municipio;

-- MGC-014: nenhum SQL. Resultado esperado é needs_clarification.

-- MGC-015: comparação observada nas janelas completas disponíveis.
-- Agregar por município/classe em cada janela antes da comparação; só manter
-- município/classe com 12 competências em ambas as janelas. Sem JOIN de fatos.
WITH p0 AS (
    SELECT municipio, classe_consumo,
           SUM(consumo_total_kwh) AS consumo_kwh,
           SUM(receita_total_reais) AS receita_reais,
           COUNT(DISTINCT competencia) AS competencias
    FROM gold_v2.diagnostico_receita
    WHERE competencia BETWEEN '2024-07' AND '2025-06'
    GROUP BY municipio, classe_consumo
), p1 AS (
    SELECT municipio, classe_consumo,
           SUM(consumo_total_kwh) AS consumo_kwh,
           SUM(receita_total_reais) AS receita_reais,
           COUNT(DISTINCT competencia) AS competencias
    FROM gold_v2.diagnostico_receita
    WHERE competencia BETWEEN '2025-07' AND '2026-06'
    GROUP BY municipio, classe_consumo
), comparacao AS (
    SELECT p0.municipio, p0.classe_consumo,
           p0.consumo_kwh AS consumo_p0, p1.consumo_kwh AS consumo_p1,
           p1.consumo_kwh - p0.consumo_kwh AS delta_consumo_kwh,
           p0.receita_reais AS receita_p0, p1.receita_reais AS receita_p1,
           p1.receita_reais - p0.receita_reais AS delta_receita_reais
    FROM p0 JOIN p1 USING (municipio, classe_consumo)
    WHERE p0.competencias = 12 AND p1.competencias = 12
), ranking AS (
    SELECT municipio, SUM(delta_consumo_kwh) AS delta_municipal_kwh,
           ROW_NUMBER() OVER (
               ORDER BY SUM(delta_consumo_kwh), municipio
           ) AS posicao
    FROM comparacao
    GROUP BY municipio
)
SELECT r.posicao, c.*
FROM comparacao c JOIN ranking r USING (municipio)
WHERE r.posicao <= 3
ORDER BY r.posicao, c.classe_consumo;

-- MGC-015: empate exato entre deltas municipais nas duas janelas completas.
-- Esperado: zero valores empatados entre os 14 municípios elegíveis.
WITH deltas AS (
    SELECT municipio,
           SUM(consumo_total_kwh) FILTER (
               WHERE competencia BETWEEN '2024-07' AND '2025-06'
           ) AS consumo_p0,
           SUM(consumo_total_kwh) FILTER (
               WHERE competencia BETWEEN '2025-07' AND '2026-06'
           ) AS consumo_p1,
           COUNT(DISTINCT competencia) FILTER (
               WHERE competencia BETWEEN '2024-07' AND '2025-06'
           ) AS meses_p0,
           COUNT(DISTINCT competencia) FILTER (
               WHERE competencia BETWEEN '2025-07' AND '2026-06'
           ) AS meses_p1
    FROM gold_v2.diagnostico_receita
    GROUP BY municipio
), elegiveis AS (
    SELECT municipio, consumo_p1 - consumo_p0 AS delta_kwh
    FROM deltas WHERE meses_p0 = 12 AND meses_p1 = 12
)
SELECT COUNT(*) AS valores_de_delta_empatados
FROM (
    SELECT delta_kwh FROM elegiveis GROUP BY delta_kwh HAVING COUNT(*) > 1
) empates;

-- MGC-015: a decomposição disponível usa outra janela. Esperado: 0 para as
-- janelas pedidas; não alegar decomposição nem atribuição causal.
SELECT COUNT(*) AS linhas_janela_solicitada
FROM gold_v2.decomposicao_receita
WHERE inicio_p0 = '2024-07' AND fim_p0 = '2025-06'
  AND inicio_p1 = '2025-07' AND fim_p1 = '2026-06';

-- MGC-041: borda real de razão de somas com denominador nulo/zero.
SELECT COUNT(*) AS linhas_gold,
       SUM(consumo_total_kwh) AS consumo_kwh,
       SUM(qtd_ucs_com_leitura) AS ucs_com_leitura,
       SUM(consumo_total_kwh)
           / NULLIF(SUM(qtd_ucs_com_leitura), 0) AS kwh_por_uc_com_leitura
FROM gold_v2.diagnostico_receita
WHERE competencia = '2023-06'
  AND municipio = 'IGARASSU'
  AND classe_consumo = 'PODER PUBLICO';

ROLLBACK;
