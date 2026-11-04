-- Execute como administrador após `python -m alembic upgrade heads`.
-- Defina senha fora do repositório com `\password venergy_gold_cadastro_reader`.
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'venergy_gold_cadastro_reader') THEN
        CREATE ROLE venergy_gold_cadastro_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'venergy_gold_cadastro_reader'
        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) OR EXISTS (
        SELECT 1 FROM pg_auth_members WHERE member = (SELECT oid FROM pg_roles WHERE rolname = 'venergy_gold_cadastro_reader')
    ) OR EXISTS (
        SELECT 1 FROM pg_shdepend WHERE refclassid = 'pg_authid'::regclass
        AND refobjid = (SELECT oid FROM pg_roles WHERE rolname = 'venergy_gold_cadastro_reader') AND deptype = 'o'
    ) THEN
        RAISE EXCEPTION 'Papel cadastral existente possui privilégios inesperados; revise manualmente';
    END IF;
END $$;
ALTER ROLE venergy_gold_cadastro_reader SET statement_timeout = '2s';
ALTER ROLE venergy_gold_cadastro_reader SET default_transaction_read_only = on;
ALTER ROLE venergy_gold_cadastro_reader SET search_path = gold_cadastro, pg_catalog;
REVOKE ALL ON SCHEMA public FROM venergy_gold_cadastro_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM venergy_gold_cadastro_reader;
REVOKE ALL ON SCHEMA gold FROM venergy_gold_cadastro_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA gold FROM venergy_gold_cadastro_reader;
REVOKE ALL ON SCHEMA gold_v2 FROM venergy_gold_cadastro_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA gold_v2 FROM venergy_gold_cadastro_reader;
REVOKE ALL ON SCHEMA gold_cadastro FROM venergy_gold_cadastro_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA gold_cadastro FROM venergy_gold_cadastro_reader;
GRANT USAGE ON SCHEMA gold_cadastro TO venergy_gold_cadastro_reader;
GRANT SELECT ON gold_cadastro.cadastro_titular_uc TO venergy_gold_cadastro_reader;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('gold_cadastro', 'pg_catalog', 'information_schema') AND n.nspname !~ '^pg_'
        AND CASE WHEN c.relkind IN ('r', 'v', 'm', 'p', 'f') THEN
            has_table_privilege('venergy_gold_cadastro_reader', c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') ELSE false END
    ) OR EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'gold_cadastro' AND c.relname <> 'cadastro_titular_uc'
        AND CASE WHEN c.relkind IN ('r', 'v', 'm', 'p', 'f') THEN has_table_privilege('venergy_gold_cadastro_reader', c.oid, 'SELECT') ELSE false END
    ) OR EXISTS (
        SELECT 1 FROM pg_namespace n WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
        AND n.nspname !~ '^pg_' AND has_schema_privilege('venergy_gold_cadastro_reader', n.oid, 'CREATE')
    ) OR has_database_privilege('venergy_gold_cadastro_reader', current_database(), 'CREATE') THEN
        RAISE EXCEPTION 'Privilégios herdados incompatíveis com o leitor cadastral; revise manualmente';
    END IF;
END $$;
COMMIT;
