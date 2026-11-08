"""Inicializa exclusivamente o banco privado da composição Docker Gold v2."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.gold_import_v2 import TABLES


def stage_package(source: Path, target: Path) -> Path | None:
    """Isola o contrato CSV dos marcadores Spark, sem modificar a origem."""
    expected = {"manifest.json", *TABLES, "cadastro_titular_uc"}
    if any(item.is_symlink() or item.name not in expected for item in source.iterdir()):
        raise ValueError("Inventário raiz fora do contrato Gold v2.")
    shutil.copyfile(source / "manifest.json", target / "manifest.json")
    cadastro = None
    for name in (*TABLES, "cadastro_titular_uc"):
        folder = source / name
        if name == "cadastro_titular_uc" and not folder.exists():
            continue
        destination = target / name
        destination.mkdir()
        for item in folder.iterdir():
            if item.is_symlink() or not item.is_file():
                raise ValueError("Entrada de pacote inválida.")
            if item.suffix == ".csv" or (name == "cadastro_titular_uc" and item.name == "manifest.json"):
                shutil.copyfile(item, destination / item.name)
            elif not re.fullmatch(r"_SUCCESS|_(?:committed|started)_\d+", item.name):
                raise ValueError("Arquivo fora do contrato de exportação.")
        if name == "cadastro_titular_uc":
            cadastro = destination
    # O contrato analítico não aceita o cadastro junto às quinze relações.
    if cadastro is not None:
        isolated = target.parent / (target.name + "-cadastro")
        cadastro.rename(isolated)
        cadastro = isolated
    return cadastro


def run(*arguments: str) -> None:
    subprocess.run(arguments, cwd=ROOT, check=True)


def validate_database_target() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    if url.host != "db" or url.username != "gold_loader" or url.database != "v_energy":
        raise ValueError("Inicialização restrita ao banco privado da composição Docker.")


def provision_roles() -> None:
    validate_database_target()
    url = make_url(os.environ["DATABASE_URL"])
    dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)
    roles = (
        ("v_energy_app", "DOCKER_APP_PASSWORD", "provision_backend_app.sql"),
        ("venergy_genai_reader", "DOCKER_READER_PASSWORD", "provision_genai_gold_reader.sql"),
        ("venergy_gold_cadastro_reader", "DOCKER_CADASTRO_PASSWORD", "provision_gold_cadastro_reader.sql"),
    )
    with psycopg.connect(dsn, autocommit=True) as connection:
        # Banco novo e dedicado: os papéis de consulta não herdam CREATE/TEMP.
        connection.execute("REVOKE CREATE, TEMP ON DATABASE v_energy FROM PUBLIC")
        connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        connection.execute("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC")
        for role, variable, filename in roles:
            password = os.environ[variable]
            if not re.fullmatch(r"[a-f0-9]{64}", password):
                raise ValueError("Use as credenciais geradas pelo configurador Docker.")
            script = (ROOT / "scripts" / filename).read_text(encoding="utf-8")
            script = "\n".join(line for line in script.splitlines() if not line.startswith("\\"))
            connection.execute(script)
            connection.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password),
            ))


def main() -> int:
    try:
        if os.getenv("DOCKER_BOOTSTRAP") != "true":
            raise ValueError("Inicialização Docker não habilitada.")
        validate_database_target()
        run(sys.executable, "-m", "alembic", "upgrade", "head")
        with TemporaryDirectory(prefix="gold-docker-") as temporary:
            analytical = Path(temporary) / "analytical"
            analytical.mkdir()
            cadastro = stage_package(Path("/gold-input"), analytical)
            load = [sys.executable, "scripts/load_gold.py", "--directory", str(analytical),
                    "--schema-version", "gold-csv-v2"]
            if cadastro is not None:
                load.extend(("--cadastro-directory", str(cadastro)))
            result = subprocess.run(load, cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE)
            summary = json.loads(result.stdout)
            print(f"Carga Gold v2: {summary['status']}; cadastro: {summary.get('cadastro_status', 'não fornecido')}.", flush=True)
        provision_roles()
        run(sys.executable, "scripts/bootstrap_local_auth.py", "--output", "/work/local-auth/credentials.txt",
            "--commercial-username", "comercial-demo", "--customer-service-username", "atendimento",
            "--losses-username", "perdas", "--operations-username", "operacao")
        print("Banco Gold v2, leitores restritos e contas locais preparados.", flush=True)
        return 0
    except Exception as error:  # noqa: BLE001 - CLI deve sanitizar erros SQL e segredos.
        # Não imprimir DSNs, SQL ou parâmetros que possam conter segredos.
        print(f"Inicialização Docker interrompida: {type(error).__name__}.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
