-- Execute como administrador no banco escolhido, após as migrações.
-- A senha é definida fora do Git. Não corrige privilégios PUBLIC automaticamente.
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='venergy_genai_reader') THEN
        CREATE ROLE venergy_genai_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='venergy_genai_reader'
        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
    OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member='venergy_genai_reader'::regrole)
    OR EXISTS (SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass
        AND refobjid='venergy_genai_reader'::regrole AND deptype='o') THEN
        RAISE EXCEPTION 'Papel preexistente privilegiado; revisão administrativa necessária';
    END IF;
END $$;
ALTER ROLE venergy_genai_reader CONNECTION LIMIT 8;
ALTER ROLE venergy_genai_reader SET statement_timeout='5s';
ALTER ROLE venergy_genai_reader SET lock_timeout='2s';
ALTER ROLE venergy_genai_reader SET idle_in_transaction_session_timeout='5s';
ALTER ROLE venergy_genai_reader SET default_transaction_read_only=on;
ALTER ROLE venergy_genai_reader SET work_mem='4MB';
ALTER ROLE venergy_genai_reader SET temp_file_limit='16MB';
ALTER ROLE venergy_genai_reader SET search_path=pg_catalog;
REVOKE ALL ON SCHEMA public, gold, gold_v2 FROM venergy_genai_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public, gold, gold_v2 FROM venergy_genai_reader;
GRANT USAGE ON SCHEMA gold, gold_v2 TO venergy_genai_reader;
GRANT SELECT ON gold.publicacao_atual, gold.publicacao_linhagem, gold.publicacao_contexto TO venergy_genai_reader;
GRANT SELECT ("competencia", "municipio", "classe_consumo", "subgrupo_tarifario", "bandeira_tarifaria", "possui_gd", "receita_total_reais", "consumo_total_kwh", "receita_base_comparavel_reais", "consumo_base_comparavel_kwh", "qtd_ucs_distintas_faturadas_no_mes", "qtd_ucs_com_leitura") ON gold_v2.diagnostico_receita TO venergy_genai_reader;
GRANT SELECT ("competencia", "municipio", "bairro", "classe_consumo", "receita_total_reais", "consumo_total_kwh", "receita_base_comparavel_reais", "consumo_base_comparavel_kwh", "qtd_ucs_distintas_faturadas_no_mes", "qtd_ucs_com_leitura") ON gold_v2.consumo_receita_bairro TO venergy_genai_reader;
GRANT SELECT ("competencia", "municipio", "id_alimentador", "total_ucs_alimentador", "ucs_interrompidas", "frequencia_total_interrupcoes", "duracao_total_interrupcoes_horas", "DEC", "FEC") ON gold_v2.indicadores_dec_fec TO venergy_genai_reader;
GRANT SELECT ("id_uc", "competencia", "consumo_kwh", "receita_reais", "tem_fatura", "tem_leitura", "qtd_faturas", "qtd_leituras_observadas") ON gold_v2.consumo_mensal_uc TO venergy_genai_reader;
GRANT SELECT ("dominio", "competencia", "recorte", "estado_cobertura", "qtd_registros", "qtd_sem_competencia", "zero_registros_confirmado", "data_corte_evidencia", "referencia_evidencia", "natureza_certificacao", "reconciliacao_extracao_json", "run_id_silver", "lote_bronze_silver") ON gold_v2.cobertura_dominios TO venergy_genai_reader;
-- Atendimento: somente colunas necessárias à agregação; sem conteúdo de chamados ou cadastro.
GRANT SELECT ("id_uc", "protocolo", "data_abertura", "nota_satisfacao", "_nota_invalida", "_nota_negativa", "_abertura_futura") ON gold_v2.atendimentos_uc TO venergy_genai_reader;
GRANT SELECT ("id_uc", "municipio", "classe", "alimentador", "possui_gd", "media_consumo_historico", "total_chamados_callcenter", "media_satisfacao_atendimento") ON gold_v2.visao_360_uc TO venergy_genai_reader;
-- C05/C06/C07: only the identifiers and categorical labels needed for counts.
GRANT SELECT ("id_uc", "prioridade_inspecao") ON gold_v2.fila_inspecao TO venergy_genai_reader;
-- Alcance local autorizado em 01/11/2026: somente projeções analíticas, sem cadastro ou texto.
GRANT SELECT ("id_uc", "municipio", "possui_gd", "consumo_medio_inicial", "consumo_medio_final", "meses_com_leitura_p1", "meses_com_leitura_p2", "variacao_pct", "queda_consumo_superior_30_pct") ON gold_v2.variacao_consumo_uc TO venergy_genai_reader;
GRANT SELECT ("id_ocorrencia", "id_uc", "alimentador", "data_abertura", "duracao_min", "flag_duracao_incompativel", "flag_abertura_futura", "flag_encerramento_futuro") ON gold_v2.ocorrencias_uc TO venergy_genai_reader;
GRANT SELECT ("municipio", "bairro", "classe_consumo", "qtd_ucs_base_comum", "qtd_ucs_entrantes", "qtd_ucs_saintes", "qtd_ucs_observadas", "faturamento_p0_reais", "faturamento_p1_reais", "efeito_volume_reais", "efeito_preco_observado_reais", "efeito_interacao_reais", "variacao_entradas_reais", "variacao_saidas_reais", "variacao_sem_leitura_fora_base_reais", "variacao_outros_fora_base_reais", "estado_decomposicao", "variacao_faturamento_total_reais", "residuo_reconciliacao_reais", "inicio_p0", "fim_p0", "inicio_p1", "fim_p1", "metodo", "run_id_silver", "lote_bronze_silver", "data_processamento_gold") ON gold_v2.decomposicao_receita TO venergy_genai_reader;
DO $$
DECLARE
    obj record;
    bad_column text;
BEGIN
    IF has_database_privilege('venergy_genai_reader', current_database(), 'CREATE,TEMP') THEN
        RAISE EXCEPTION 'CREATE/TEMP efetivo deve ser retirado por administrador; confira PUBLIC';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname NOT IN ('pg_catalog','information_schema')
        AND nspname !~ '^pg_' AND has_schema_privilege('venergy_genai_reader', oid, 'CREATE')) THEN
        RAISE EXCEPTION 'Papel pode criar objetos em schema';
    END IF;
    FOR obj IN SELECT c.oid,c.relname,n.nspname FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_'
        AND c.relkind IN ('r','v','m','p','f')
    LOOP
        IF has_table_privilege('venergy_genai_reader',obj.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
            OR has_any_column_privilege('venergy_genai_reader',obj.oid,'INSERT,UPDATE,REFERENCES') THEN
            RAISE EXCEPTION 'Permissão efetiva de escrita encontrada';
        END IF;
        IF obj.nspname='gold' AND obj.relname IN ('publicacao_atual','publicacao_linhagem','publicacao_contexto') THEN
            CONTINUE;
        END IF;
        WITH allowed(table_name,column_name) AS (VALUES
                ('diagnostico_receita', 'competencia'),
                ('diagnostico_receita', 'municipio'),
                ('diagnostico_receita', 'classe_consumo'),
                ('diagnostico_receita', 'subgrupo_tarifario'),
                ('diagnostico_receita', 'bandeira_tarifaria'),
                ('diagnostico_receita', 'possui_gd'),
                ('diagnostico_receita', 'receita_total_reais'),
                ('diagnostico_receita', 'consumo_total_kwh'),
                ('diagnostico_receita', 'receita_base_comparavel_reais'),
                ('diagnostico_receita', 'consumo_base_comparavel_kwh'),
                ('diagnostico_receita', 'qtd_ucs_distintas_faturadas_no_mes'),
                ('diagnostico_receita', 'qtd_ucs_com_leitura'),
                ('consumo_receita_bairro', 'competencia'),
                ('consumo_receita_bairro', 'municipio'),
                ('consumo_receita_bairro', 'bairro'),
                ('consumo_receita_bairro', 'classe_consumo'),
                ('consumo_receita_bairro', 'receita_total_reais'),
                ('consumo_receita_bairro', 'consumo_total_kwh'),
                ('consumo_receita_bairro', 'receita_base_comparavel_reais'),
                ('consumo_receita_bairro', 'consumo_base_comparavel_kwh'),
                ('consumo_receita_bairro', 'qtd_ucs_distintas_faturadas_no_mes'),
                ('consumo_receita_bairro', 'qtd_ucs_com_leitura'),
                ('indicadores_dec_fec', 'competencia'),
                ('indicadores_dec_fec', 'municipio'),
                ('indicadores_dec_fec', 'id_alimentador'),
                ('indicadores_dec_fec', 'DEC'),
                ('indicadores_dec_fec', 'FEC'),
                ('consumo_mensal_uc', 'competencia'),
                ('consumo_mensal_uc', 'id_uc'),
                ('consumo_mensal_uc', 'consumo_kwh'),
                ('consumo_mensal_uc', 'receita_reais'),
                ('consumo_mensal_uc', 'tem_fatura'),
                ('consumo_mensal_uc', 'tem_leitura'),
                ('consumo_mensal_uc', 'qtd_faturas'),
                ('consumo_mensal_uc', 'qtd_leituras_observadas'),
                ('atendimentos_uc', 'protocolo'),
                ('atendimentos_uc', 'data_abertura'),
                ('atendimentos_uc', 'nota_satisfacao'),
                ('atendimentos_uc', 'id_uc'),
                ('atendimentos_uc', '_nota_invalida'),
                ('atendimentos_uc', '_nota_negativa'),
                ('atendimentos_uc', '_abertura_futura'),
                ('visao_360_uc', 'id_uc'),
                ('visao_360_uc', 'municipio'),
                ('visao_360_uc', 'classe'),
                ('visao_360_uc', 'alimentador'),
                ('visao_360_uc', 'possui_gd'),
                ('visao_360_uc', 'media_consumo_historico'),
                ('visao_360_uc', 'total_chamados_callcenter'),
                ('visao_360_uc', 'media_satisfacao_atendimento'),
                ('fila_inspecao', 'id_uc'),
                ('fila_inspecao', 'prioridade_inspecao'),
                ('variacao_consumo_uc', 'municipio'),
                ('variacao_consumo_uc', 'id_uc'),
                ('variacao_consumo_uc', 'possui_gd'),
                ('variacao_consumo_uc', 'consumo_medio_inicial'),
                ('variacao_consumo_uc', 'consumo_medio_final'),
                ('variacao_consumo_uc', 'meses_com_leitura_p1'),
                ('variacao_consumo_uc', 'meses_com_leitura_p2'),
                ('variacao_consumo_uc', 'variacao_pct'),
                ('variacao_consumo_uc', 'queda_consumo_superior_30_pct'),
                ('ocorrencias_uc', 'id_ocorrencia'),
                ('ocorrencias_uc', 'alimentador'),
                ('ocorrencias_uc', 'data_abertura'),
                ('ocorrencias_uc', 'id_uc'),
                ('ocorrencias_uc', 'duracao_min'),
                ('ocorrencias_uc', 'flag_duracao_incompativel'),
                ('ocorrencias_uc', 'flag_abertura_futura'),
                ('ocorrencias_uc', 'flag_encerramento_futuro'),
                ('indicadores_dec_fec', 'total_ucs_alimentador'),
                ('indicadores_dec_fec', 'ucs_interrompidas'),
                ('indicadores_dec_fec', 'frequencia_total_interrupcoes'),
                ('indicadores_dec_fec', 'duracao_total_interrupcoes_horas'),
                ('cobertura_dominios', 'dominio'),
                ('cobertura_dominios', 'competencia'),
                ('cobertura_dominios', 'recorte'),
                ('cobertura_dominios', 'estado_cobertura'),
                ('cobertura_dominios', 'qtd_registros'),
                ('cobertura_dominios', 'qtd_sem_competencia'),
                ('cobertura_dominios', 'zero_registros_confirmado'),
                ('cobertura_dominios', 'data_corte_evidencia'),
                ('cobertura_dominios', 'referencia_evidencia'),
                ('cobertura_dominios', 'natureza_certificacao'),
                ('cobertura_dominios', 'reconciliacao_extracao_json'),
                ('cobertura_dominios', 'run_id_silver'),
                ('cobertura_dominios', 'lote_bronze_silver'),
                ('decomposicao_receita', 'municipio'),
                ('decomposicao_receita', 'bairro'),
                ('decomposicao_receita', 'classe_consumo'),
                ('decomposicao_receita', 'qtd_ucs_base_comum'),
                ('decomposicao_receita', 'qtd_ucs_entrantes'),
                ('decomposicao_receita', 'qtd_ucs_saintes'),
                ('decomposicao_receita', 'qtd_ucs_observadas'),
                ('decomposicao_receita', 'faturamento_p0_reais'),
                ('decomposicao_receita', 'faturamento_p1_reais'),
                ('decomposicao_receita', 'efeito_volume_reais'),
                ('decomposicao_receita', 'efeito_preco_observado_reais'),
                ('decomposicao_receita', 'efeito_interacao_reais'),
                ('decomposicao_receita', 'variacao_entradas_reais'),
                ('decomposicao_receita', 'variacao_saidas_reais'),
                ('decomposicao_receita', 'variacao_sem_leitura_fora_base_reais'),
                ('decomposicao_receita', 'variacao_outros_fora_base_reais'),
                ('decomposicao_receita', 'estado_decomposicao'),
                ('decomposicao_receita', 'variacao_faturamento_total_reais'),
                ('decomposicao_receita', 'residuo_reconciliacao_reais'),
                ('decomposicao_receita', 'inicio_p0'),
                ('decomposicao_receita', 'fim_p0'),
                ('decomposicao_receita', 'inicio_p1'),
                ('decomposicao_receita', 'fim_p1'),
                ('decomposicao_receita', 'metodo'),
                ('decomposicao_receita', 'run_id_silver'),
                ('decomposicao_receita', 'lote_bronze_silver'),
                ('decomposicao_receita', 'data_processamento_gold')
            )
            SELECT a.attname INTO bad_column FROM pg_attribute a WHERE a.attrelid=obj.oid
                AND a.attnum>0 AND NOT a.attisdropped
                AND has_column_privilege('venergy_genai_reader',obj.oid,a.attnum,'SELECT')
                AND NOT EXISTS (SELECT 1 FROM allowed p WHERE obj.nspname='gold_v2'
                    AND p.table_name=obj.relname AND p.column_name=a.attname)
            LIMIT 1;
        IF bad_column IS NOT NULL THEN
            RAISE EXCEPTION 'Leitura efetiva fora da matriz concedida em %.%', obj.relname, bad_column;
        END IF;
    END LOOP;
    IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_'
        AND CASE WHEN c.relkind='S' THEN
            has_sequence_privilege('venergy_genai_reader',c.oid,'USAGE,SELECT,UPDATE') ELSE false END)
    OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_'
        AND has_function_privilege('venergy_genai_reader',p.oid,'EXECUTE')) THEN
        RAISE EXCEPTION 'Acesso efetivo a sequência/função de aplicação não permitido';
    END IF;
END $$;
COMMIT;
