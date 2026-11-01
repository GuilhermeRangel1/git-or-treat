"""Operação administrativa: consulta por referência ou expurgo dos 30 dias."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine
from app.services.genai_audit import AuditStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--reference")
    action.add_argument("--purge", action="store_true")
    args = parser.parse_args()
    try:
        store = AuditStore(engine)
        result = ({"removed": store.purge()} if args.purge
                  else store.read_reference(args.reference))
        print(json.dumps(result, default=str, ensure_ascii=False))
    except (SQLAlchemyError, ValueError):
        print("Operação de auditoria indisponível.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
