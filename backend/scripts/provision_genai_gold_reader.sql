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
GRANT SELECT ("competencia", "municipio", "id_alimentador", "DEC", "FEC") ON gold_v2.indicadores_dec_fec TO venergy_genai_reader;
GRANT SELECT ("competencia") ON gold_v2.consumo_mensal_uc TO venergy_genai_reader;
DO $$
DECLARE
    obj record;
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
        IF EXISTS (
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
                ('consumo_mensal_uc', 'competencia')
            )
            SELECT 1 FROM pg_attribute a WHERE a.attrelid=obj.oid
                AND a.attnum>0 AND NOT a.attisdropped
                AND has_column_privilege('venergy_genai_reader',obj.oid,a.attnum,'SELECT')
                AND NOT EXISTS (SELECT 1 FROM allowed p WHERE obj.nspname='gold_v2'
                    AND p.table_name=obj.relname AND p.column_name=a.attname)
        ) THEN
            RAISE EXCEPTION 'Leitura efetiva fora da matriz concedida';
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
