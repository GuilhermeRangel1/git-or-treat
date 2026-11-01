-- Execute como administrador, após alembic upgrade head, no banco local escolhido.
-- Papel dedicado: a senha é provisionada fora do repositório via \password.
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'venergy_gold_reader') THEN
        CREATE ROLE venergy_gold_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'venergy_gold_reader'
        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) OR EXISTS (
        SELECT 1 FROM pg_auth_members WHERE member = (SELECT oid FROM pg_roles WHERE rolname = 'venergy_gold_reader')
    ) OR EXISTS (
        SELECT 1 FROM pg_shdepend
        WHERE refclassid = 'pg_authid'::regclass
        AND refobjid = (SELECT oid FROM pg_roles WHERE rolname = 'venergy_gold_reader')
        AND deptype = 'o'
    ) THEN
        RAISE EXCEPTION 'Papel existente possui privilégios inesperados; revise manualmente';
    END IF;
END $$;
ALTER ROLE venergy_gold_reader SET statement_timeout = '5s';
ALTER ROLE venergy_gold_reader SET default_transaction_read_only = on;
ALTER ROLE venergy_gold_reader SET search_path = gold_v2, gold, pg_catalog;
-- Retirar criação implícita em schema público; migrações usam o proprietário.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM venergy_gold_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM venergy_gold_reader;
REVOKE ALL ON SCHEMA gold FROM venergy_gold_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA gold FROM venergy_gold_reader;
REVOKE ALL ON SCHEMA gold_v2 FROM venergy_gold_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA gold_v2 FROM venergy_gold_reader;
GRANT USAGE ON SCHEMA gold TO venergy_gold_reader;
GRANT USAGE ON SCHEMA gold_v2 TO venergy_gold_reader;
GRANT SELECT ON gold.gold_consumo_mensal_uc, gold.gold_consumo_receita_bairro,
    gold.gold_diagnostico_receita, gold.gold_fila_inspecao, gold.gold_indicadores_dec_fec,
    gold.gold_variacao_consumo_uc, gold.gold_visao_360_uc, gold.publicacao_atual, gold.publicacao_linhagem, gold.publicacao_contexto
TO venergy_gold_reader;
GRANT SELECT ON gold_v2.diagnostico_receita, gold_v2.indicadores_dec_fec,
    gold_v2.fila_inspecao, gold_v2.visao_360_uc, gold_v2.consumo_mensal_uc,
    gold_v2.consumo_receita_bairro, gold_v2.variacao_consumo_uc, gold_v2.faturas_uc,
    gold_v2.medidor_uc, gold_v2.atendimentos_uc, gold_v2.ocorrencias_uc, gold_v2.gd_uc,
    gold_v2.tratativas_uc, gold_v2.cobertura_dominios, gold_v2.decomposicao_receita
TO venergy_gold_reader;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('gold', 'gold_v2', 'pg_catalog', 'information_schema')
        AND n.nspname !~ '^pg_'
        AND CASE WHEN c.relkind IN ('r', 'v', 'm', 'p', 'f') THEN
            has_table_privilege('venergy_gold_reader', c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') ELSE false END
    ) OR EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('gold', 'gold_v2') AND CASE WHEN c.relkind IN ('r', 'v', 'm', 'p', 'f') THEN
            has_table_privilege('venergy_gold_reader', c.oid, 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
            OR ((n.nspname = 'gold' AND c.relname NOT IN (
                'gold_consumo_mensal_uc', 'gold_consumo_receita_bairro', 'gold_diagnostico_receita',
                'gold_fila_inspecao', 'gold_indicadores_dec_fec', 'gold_variacao_consumo_uc',
                'gold_visao_360_uc', 'publicacao_atual', 'publicacao_linhagem', 'publicacao_contexto'
            )) OR (n.nspname = 'gold_v2' AND c.relname NOT IN (
                'diagnostico_receita', 'indicadores_dec_fec', 'fila_inspecao', 'visao_360_uc',
                'consumo_mensal_uc', 'consumo_receita_bairro', 'variacao_consumo_uc', 'faturas_uc',
                'medidor_uc', 'atendimentos_uc', 'ocorrencias_uc', 'gd_uc', 'tratativas_uc',
                'cobertura_dominios', 'decomposicao_receita'
            ))) AND has_table_privilege('venergy_gold_reader', c.oid, 'SELECT') ELSE false END
    ) OR EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname !~ '^pg_'
        AND CASE WHEN c.relkind = 'S' THEN
            has_sequence_privilege('venergy_gold_reader', c.oid, 'USAGE,SELECT,UPDATE') ELSE false END
    ) OR EXISTS (
        SELECT 1 FROM pg_namespace n WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
        AND n.nspname !~ '^pg_' AND has_schema_privilege('venergy_gold_reader', n.oid, 'CREATE')
    ) OR has_database_privilege('venergy_gold_reader', current_database(), 'CREATE') THEN
        RAISE EXCEPTION 'Privilégios herdados de PUBLIC incompatíveis; revise manualmente';
    END IF;
END $$;
COMMIT;
