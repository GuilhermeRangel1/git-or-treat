"""Explicitly assign a platform profile to one local account."""

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.platform_access import PlatformProfile  # noqa: E402
from app.models.auth import AuthUser  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Atribui explicitamente um perfil a uma conta local existente."
    )
    parser.add_argument("--username", required=True)
    assignment = parser.add_mutually_exclusive_group(required=True)
    assignment.add_argument("--profile", choices=[profile.value for profile in PlatformProfile])
    assignment.add_argument("--clear-profile", action="store_true", help="Remove explicit profile and revoke session permissions.")
    parser.add_argument("--database-url", help="Override explícito da URL de banco local.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database_url = args.database_url or settings.DATABASE_URL
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        username = args.username.strip().casefold()
        with Session(engine) as db:
            user = db.scalar(select(AuthUser).where(AuthUser.username == username))
            if user is None:
                print("Conta não encontrada.", file=sys.stderr)
                return 1
            previous_profile = user.profile
            user.profile = None if args.clear_profile else args.profile
            db.commit()
            print(
                "Perfil atualizado: "
                f"user_id={user.id} profile={previous_profile or 'null'}->{user.profile or 'null'}"
            )
        return 0
    except Exception as error:
        print(f"Falha ao atribuir perfil: {type(error).__name__}.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
