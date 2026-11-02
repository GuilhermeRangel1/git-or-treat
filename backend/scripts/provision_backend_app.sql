-- Administrador, depois das migrações. Senha é definida fora deste arquivo.
-- Não aplica a proprietários de objetos ou papéis com privilégios herdados.
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v_energy_app') THEN
        CREATE ROLE v_energy_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v_energy_app'
        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
    OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member='v_energy_app'::regrole)
    OR EXISTS (SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass
        AND refobjid='v_energy_app'::regrole AND deptype='o') THEN
        RAISE EXCEPTION 'Papel operacional privilegiado; revisão administrativa necessária';
    END IF;
END $$;
ALTER ROLE v_energy_app CONNECTION LIMIT 32;
ALTER ROLE v_energy_app SET statement_timeout='10s';
ALTER ROLE v_energy_app SET lock_timeout='2s';
ALTER ROLE v_energy_app SET idle_in_transaction_session_timeout='10s';
REVOKE ALL ON SCHEMA public, gold, gold_v2 FROM v_energy_app;
REVOKE ALL ON ALL TABLES IN SCHEMA public, gold, gold_v2 FROM v_energy_app;
GRANT USAGE ON SCHEMA public, gold, gold_v2 TO v_energy_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    public.auth_users, public.auth_sessions, public.genai_audit_events,
    public.operational_inspection_orders, public.operational_order_history TO v_energy_app;
GRANT USAGE, SELECT ON SEQUENCE public.operational_inspection_orders_id_seq,
    public.operational_order_history_id_seq TO v_energy_app;
GRANT SELECT ON gold.publicacao_atual, gold.publicacao_linhagem,
    gold.publicacao_contexto TO v_energy_app;
GRANT SELECT ON gold_v2.diagnostico_receita, gold_v2.indicadores_dec_fec,
    gold_v2.fila_inspecao, gold_v2.visao_360_uc, gold_v2.consumo_receita_bairro,
    gold_v2.variacao_consumo_uc, gold_v2.consumo_mensal_uc, gold_v2.faturas_uc,
    gold_v2.medidor_uc, gold_v2.atendimentos_uc, gold_v2.ocorrencias_uc,
    gold_v2.gd_uc, gold_v2.tratativas_uc, gold_v2.cobertura_dominios,
    gold_v2.decomposicao_receita TO v_energy_app;
-- Sem CREATE/TEMP, escrita Gold, tabela de carga ou cadastro restrito.
DO $$
BEGIN
    IF has_database_privilege('v_energy_app', current_database(), 'CREATE,TEMP')
       OR EXISTS (SELECT 1 FROM pg_namespace n
                  WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                    AND n.nspname !~ '^pg_'
                    AND has_schema_privilege('v_energy_app', n.oid, 'CREATE')) THEN
        RAISE EXCEPTION 'Privilégios PUBLIC/herdados exigem revisão administrativa';
    END IF;
END $$;
COMMIT;
