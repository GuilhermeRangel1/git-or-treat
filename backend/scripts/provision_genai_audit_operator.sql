-- Execute como administrador após aplicar as migrações do Backend.
-- Defina a senha separadamente, fora do Git, usando ALTER ROLE/\password.
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='venergy_genai_audit_operator') THEN
        CREATE ROLE venergy_genai_audit_operator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='venergy_genai_audit_operator'
        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
    OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member='venergy_genai_audit_operator'::regrole)
    OR EXISTS (SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass
        AND refobjid='venergy_genai_audit_operator'::regrole AND deptype='o') THEN
        RAISE EXCEPTION 'Papel preexistente privilegiado; revisão administrativa necessária';
    END IF;
END $$;
ALTER ROLE venergy_genai_audit_operator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE venergy_genai_audit_operator CONNECTION LIMIT 3;
ALTER ROLE venergy_genai_audit_operator SET statement_timeout='2s';
ALTER ROLE venergy_genai_audit_operator SET lock_timeout='500ms';
ALTER ROLE venergy_genai_audit_operator SET idle_in_transaction_session_timeout='5s';
ALTER ROLE venergy_genai_audit_operator SET search_path=pg_catalog,public;
DO $$
DECLARE
    obj record;
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO venergy_genai_audit_operator', current_database());
    EXECUTE format('REVOKE CREATE,TEMP ON DATABASE %I FROM venergy_genai_audit_operator', current_database());
    REVOKE ALL ON SCHEMA public, gold, gold_v2 FROM venergy_genai_audit_operator;
    REVOKE ALL ON ALL TABLES IN SCHEMA public, gold, gold_v2 FROM venergy_genai_audit_operator;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA public, gold, gold_v2 FROM venergy_genai_audit_operator;
    REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public, gold, gold_v2 FROM venergy_genai_audit_operator;
    GRANT USAGE ON SCHEMA public TO venergy_genai_audit_operator;
    GRANT SELECT, DELETE ON public.genai_audit_events TO venergy_genai_audit_operator;

    IF has_database_privilege('venergy_genai_audit_operator', current_database(), 'CREATE,TEMP') THEN
        RAISE EXCEPTION 'CREATE/TEMP efetivo deve ser revogado por administrador';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname NOT IN ('pg_catalog','information_schema')
        AND nspname !~ '^pg_' AND has_schema_privilege('venergy_genai_audit_operator', oid, 'CREATE')) THEN
        RAISE EXCEPTION 'Papel pode criar objetos em schema';
    END IF;
    FOR obj IN SELECT c.oid,c.relname,n.nspname FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_'
        AND c.relkind IN ('r','v','m','p','f')
    LOOP
        IF obj.nspname='public' AND obj.relname='genai_audit_events' THEN
            IF NOT has_table_privilege('venergy_genai_audit_operator',obj.oid,'SELECT,DELETE')
                OR has_table_privilege('venergy_genai_audit_operator',obj.oid,'INSERT,UPDATE,TRUNCATE,REFERENCES,TRIGGER') THEN
                RAISE EXCEPTION 'Privilégios inesperados na trilha de auditoria';
            END IF;
            CONTINUE;
        END IF;
        IF has_table_privilege('venergy_genai_audit_operator',obj.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
            OR has_any_column_privilege('venergy_genai_audit_operator',obj.oid,'SELECT,INSERT,UPDATE,REFERENCES') THEN
            RAISE EXCEPTION 'Acesso efetivo a tabela fora da trilha de auditoria';
        END IF;
    END LOOP;
    IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_'
        AND CASE WHEN c.relkind='S' THEN
            has_sequence_privilege('venergy_genai_audit_operator',c.oid,'USAGE,SELECT,UPDATE')
            ELSE false END)
    OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_'
        AND has_function_privilege('venergy_genai_audit_operator',p.oid,'EXECUTE')) THEN
        RAISE EXCEPTION 'Acesso efetivo a sequência/função de aplicação não permitido';
    END IF;
END $$;
COMMIT;
