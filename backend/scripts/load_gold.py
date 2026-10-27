"""Carga explícita dos CSVs Gold em banco previamente migrado."""
import argparse
import csv
import json
import sys
from pathlib import Path
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
from app.core.database import engine
from app.services.gold_import import GoldImportError, import_gold


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=settings.GOLD_DATA_DIR / "v1")
    parser.add_argument("--batch", default="v1")
    args = parser.parse_args()
    try:
        result = import_gold(engine, args.directory, args.batch)
    except (GoldImportError, SQLAlchemyError, OSError, UnicodeError, csv.Error) as error:
        message = str(error) if isinstance(error, GoldImportError) else "Falha de leitura ou persistência. Confira o banco migrado e os arquivos."
        print(message, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
