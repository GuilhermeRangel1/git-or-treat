"""Create the isolated local SELECT role and store its DSN only in backend/.env."""

from pathlib import Path
import secrets
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402

ROLE = "venergy_gold_cadastro_reader"


def main() -> int:
    admin_url = make_url(settings.DATABASE_URL)
    password = secrets.token_urlsafe(32)
    engine = create_engine(admin_url, hide_parameters=True)
    try:
        with engine.begin() as connection:
            role = connection.execute(text(
                "SELECT oid, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = :role"
            ), {"role": ROLE}).mappings().one_or_none()
            if role is not None:
                if any(role[key] for key in ("rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls")):
                    raise RuntimeError("Papel cadastral existente possui atributos privilegiados.")
                if connection.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_auth_members WHERE member=:oid)"), {"oid": role["oid"]}):
                    raise RuntimeError("Papel cadastral existente herda privilégios de outro papel.")
                if connection.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass AND refobjid=:oid AND deptype='o')"), {"oid": role["oid"]}):
                    raise RuntimeError("Papel cadastral existente é proprietário de objetos.")
                connection.exec_driver_sql(f"ALTER ROLE {ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '{password}'")
            else:
                connection.exec_driver_sql(f"CREATE ROLE {ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '{password}'")
            connection.exec_driver_sql(f"ALTER ROLE {ROLE} SET statement_timeout = '2s'")
            connection.exec_driver_sql(f"ALTER ROLE {ROLE} SET default_transaction_read_only = on")
            connection.exec_driver_sql(f"ALTER ROLE {ROLE} SET search_path = gold_cadastro, pg_catalog")
            for schema in ("public", "gold", "gold_v2", "gold_cadastro"):
                connection.exec_driver_sql(f"REVOKE ALL ON SCHEMA {schema} FROM {ROLE}")
                connection.exec_driver_sql(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {ROLE}")
            connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA gold_cadastro TO {ROLE}")
            connection.exec_driver_sql(f"GRANT SELECT ON gold_cadastro.cadastro_titular_uc TO {ROLE}")
            unexpected = connection.scalar(text(
                "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname NOT IN ('gold_cadastro','pg_catalog','information_schema') AND n.nspname !~ '^pg_' "
                "AND CASE WHEN c.relkind IN ('r','v','m','p','f') THEN "
                "has_table_privilege(:role,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') ELSE false END) "
                "OR EXISTS (SELECT 1 FROM pg_namespace n WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
                "AND n.nspname !~ '^pg_' AND has_schema_privilege(:role,n.oid,'CREATE')) "
                "OR has_database_privilege(:role,current_database(),'CREATE')"
            ), {"role": ROLE})
            if unexpected:
                raise RuntimeError("Privilégios herdados incompatíveis; papel não provisionado.")
        if not admin_url.host or not admin_url.database:
            raise RuntimeError("DATABASE_URL precisa indicar host e banco local.")
        reader_url = URL.create(
            "postgresql+psycopg",
            username=ROLE,
            password=password,
            host=admin_url.host,
            port=admin_url.port,
            database=admin_url.database,
        )
        env_path = BACKEND_DIR / ".env"
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        replacement = f"GOLD_CADASTRO_DATABASE_URL={reader_url.render_as_string(hide_password=False)}"
        updated = [line for line in lines if not line.startswith("GOLD_CADASTRO_DATABASE_URL=")]
        updated.append(replacement)
        env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
        try:
            env_path.chmod(0o600)
        except OSError:
            pass
        print("Leitor cadastral de privilégio mínimo provisionado; DSN gravado no backend/.env.")
        return 0
    except Exception as error:
        print(f"Falha ao provisionar leitor cadastral: {type(error).__name__}.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
