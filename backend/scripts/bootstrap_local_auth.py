"""Create artificial local accounts for each platform profile once."""

import argparse
import os
from pathlib import Path
import secrets
import sys
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.passwords import hash_password  # noqa: E402
from app.core.platform_access import PlatformProfile  # noqa: E402
from app.models.auth import AuthUser  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provisiona contas artificiais locais sem alterar contas existentes.")
    parser.add_argument("--database-url", help="Override explícito da URL de banco (use DATABASE_URL no fluxo normal).")
    parser.add_argument("--output", type=Path, default=REPOSITORY_ROOT / "work" / "local-auth" / "credentials.txt")
    for profile in PlatformProfile:
        parser.add_argument(
            f"--{profile.value.replace('_', '-')}-username",
            dest=f"{profile.value}_username",
            default=profile.value,
        )
    return parser.parse_args()


def append_private_credentials(path: Path, entries: list[tuple[str, str, str]]) -> None:
    if not entries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for role, username, password in entries:
        lines.extend((f"{role} username: {username}", f"{role} password: {password}", ""))
    with path.open("a", encoding="utf-8", newline="\n") as credentials_file:
        credentials_file.write("\n".join(lines))
        credentials_file.flush()
        os.fsync(credentials_file.fileno())
    try:
        path.chmod(0o600)
    except OSError:
        pass


def main() -> int:
    args = parse_args()
    database_url = args.database_url or settings.DATABASE_URL
    engine_options = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
    engine = create_engine(database_url, **engine_options)
    entries: list[tuple[str, str, str]] = []
    try:
        with Session(engine) as db, db.begin():
            accounts = [
                (profile.value, getattr(args, f"{profile.value}_username"), profile)
                for profile in PlatformProfile
            ]
            normalized_usernames = [name.strip().casefold() for _, name, _ in accounts]
            if len(normalized_usernames) != len(set(normalized_usernames)):
                raise ValueError("Cada perfil precisa de um username diferente.")
            for role, raw_username, profile in accounts:
                username = raw_username.strip().casefold()
                if not 1 <= len(username) <= 128:
                    raise ValueError("Username deve ter entre 1 e 128 caracteres.")
                existing = db.scalar(select(AuthUser.id).where(AuthUser.username == username))
                if existing is not None:
                    continue
                password = secrets.token_urlsafe(32)
                db.add(AuthUser(
                    id=str(uuid4()),
                    username=username,
                    password_hash=hash_password(password),
                    permissions=[],
                    profile=profile.value,
                    is_active=True,
                ))
                entries.append((role, username, password))
            # Write the only copy of new passwords before committing the new accounts.
            append_private_credentials(args.output, entries)
        if entries:
            print(f"Contas locais provisionadas; credenciais privadas em {args.output}.")
        else:
            print("As contas locais já existem; nenhuma credencial ou permissão foi alterada.")
        return 0
    except Exception as error:
        print(f"Falha ao provisionar contas locais: {type(error).__name__}.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
