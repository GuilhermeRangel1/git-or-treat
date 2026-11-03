"""Compara conservação dos CSVs reais e banco em snapshot somente leitura."""
import argparse
import csv
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    directory, output = args.directory.resolve(), args.output.resolve()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'backend'))
    os.chdir(root / 'backend')
    from sqlalchemy import Float, Integer, Numeric, create_engine, func, select, text
    from app.core.config import settings
    from app.models.gold_v2 import TABLES
    from app.schemas.gold_publication_v2 import read_export_manifest_v2
    from app.services.gold_import_v2 import discover_files, fingerprint

    manifest = read_export_manifest_v2(directory)
    files = discover_files(directory)
    signature, _ = fingerprint(files)
    checks = []

    def check(name, passed):
        checks.append({'check': name, 'passed': bool(passed)})

    engine = create_engine(settings.DATABASE_URL, hide_parameters=True)
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        publication = dict(db.execute(text('SELECT lote,schema_version,fingerprint FROM gold_carga_atual WHERE id=1')).mappings().one())
        check('manifest_batch_matches_database', publication['lote'] == manifest.run_id)
        check('csv_fingerprint_matches_database', signature == publication['fingerprint'])
        if not all(x['passed'] for x in checks):
            raise RuntimeError('Source publication mismatch')
        for name, table in TABLES.items():
            columns = [c for c in table.c if isinstance(c.type, (Integer, Numeric, Float))]
            totals = {c.name: Decimal(0) for c in columns}
            counts = {c.name: 0 for c in columns}
            rows = 0
            for file in files[name]:
                with file.open(encoding='utf-8', newline='') as stream:
                    reader = csv.DictReader(stream, delimiter=';')
                    check(name + ':header', set(reader.fieldnames or []) == set(table.c.keys()))
                    for row in reader:
                        rows += 1
                        for column in columns:
                            value = row[column.name]
                            if value != r'\N':
                                totals[column.name] += Decimal(value)
                                counts[column.name] += 1
            check(name + ':manifest_count', rows == manifest.controles_tabelas[name].registros)
            query = select(func.count()).select_from(table)
            check(name + ':database_count', rows == db.scalar(query))
            for column in columns:
                count, total = db.execute(select(func.count(column), func.sum(column))).one()
                check(name + ':' + column.name + ':nonnull_count', counts[column.name] == count)
                if count:
                    expected = totals[column.name]
                    tolerance = max(Decimal('0.00001'), abs(expected) * Decimal('1e-9')) if isinstance(column.type, Float) else Decimal(0)
                    check(name + ':' + column.name + ':sum', abs(Decimal(str(total)) - expected) <= tolerance)
                else:
                    check(name + ':' + column.name + ':null_preserved', total is None)
            print(json.dumps({'table': name, 'completed': True}), flush=True)
        estimate_available = db.scalar(text('SELECT EXISTS (SELECT 1 FROM gold_v2.fila_inspecao WHERE energia_estimada_recuperavel_kwh IS NOT NULL)'))
    check('source_unchanged_during_validation', fingerprint(discover_files(directory))[0] == signature)
    output.write_text(json.dumps({'date': datetime.now(timezone.utc).isoformat(), 'publication': publication, 'checks': checks, 'limitations': {'individual_inspection_estimate_available': bool(estimate_available), 'delta_origin_rerun': False}, 'method': 'CSV count, nonnull count and numeric sum vs read-only database snapshot; float tolerance max(0.00001,abs(sum)*1e-9); exact integer/decimal; aggregate conservation does not prove row equality or business certification'}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'checks': len(checks), 'failed': sum(not x['passed'] for x in checks), 'individual_estimate_available': bool(estimate_available)}))
    return int(any(not x['passed'] for x in checks))


if __name__ == '__main__':
    raise SystemExit(main())
