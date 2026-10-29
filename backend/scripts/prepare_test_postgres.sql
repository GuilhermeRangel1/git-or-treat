-- Somente para o banco efêmero da CI; credenciais sintéticas de teste.
-- Execute como administrador antes dos testes, nunca no banco de desenvolvimento.
\set ON_ERROR_STOP on

DO $$
BEGIN
    IF current_database() <> 'v_energy_test' THEN
        RAISE EXCEPTION 'Execute este script somente no banco descartável v_energy_test';
    END IF;
END
$$;

CREATE ROLE venergy_migrator LOGIN PASSWORD 'venergy_migrator'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER DATABASE v_energy_test OWNER TO venergy_migrator;
ALTER SCHEMA public OWNER TO venergy_migrator;

-- Banco separado para as cargas sintéticas; ambos devem terminar vazios.
CREATE DATABASE gold_import_test OWNER venergy_migrator;
\connect gold_import_test
ALTER SCHEMA public OWNER TO venergy_migrator;
\connect v_energy_test

-- Gold analytics and orders use separate disposable databases and fixtures.
CREATE DATABASE gold_analytics_test OWNER venergy_migrator;
\connect gold_analytics_test
ALTER SCHEMA public OWNER TO venergy_migrator;
\connect v_energy_test
CREATE DATABASE gold_orders_test OWNER venergy_migrator;
\connect gold_orders_test
ALTER SCHEMA public OWNER TO venergy_migrator;
