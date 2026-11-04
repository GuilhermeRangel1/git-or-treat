"""Verificação HTTP privada da DEV-15, sem chamadas GenAI ou mutações de ordens.

Execute com o Python do Backend. Credenciais ficam em arquivo privado existente;
o relatório contém somente estados, metadados de publicação e comparações booleanas.
"""
import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', default='http://127.0.0.1:5173')
    parser.add_argument('--api-base', help='API local isolada; omisso usa o proxy do portal.')
    parser.add_argument('--credentials', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reconcile', action='store_true', help='Confere o DB configurado em backend/.env em transação READ ONLY.')
    args = parser.parse_args()
    origin = args.origin.rstrip('/')
    api_base = (args.api_base or origin).rstrip('/')
    if any(urllib.parse.urlsplit(url).hostname not in {'localhost', '127.0.0.1'} for url in (origin, api_base)):
        parser.error('Use somente o portal local autorizado.')
    private = args.credentials.read_text(encoding='utf-8')
    checks = []
    publications = set()
    admin_panorama = None
    paths = ['/panorama?comparacao=nenhuma', '/revenue', '/ucs?page_size=1', '/inspections/queue?page_size=1', '/inspections/orders/search', '/operations/summary']
    allowed = {'commercial': {0, 1}, 'customer_service': {2}, 'losses': {3, 4}, 'operations': {5}, 'admin': set(range(6))}

    def record(name, passed, **details):
        checks.append({'check': name, 'passed': bool(passed), **details})

    for profile, permitted in allowed.items():
        usernames = re.findall(rf'^{profile} username: (.+)', private, re.M)
        passwords = re.findall(rf'^{profile} password: (.+)', private, re.M)
        if not usernames or not passwords:
            record(profile + ':credentials_available', False)
            continue
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        def call(path, data=None):
            request = urllib.request.Request(api_base + '/api/v1' + path,
                data=json.dumps(data).encode() if data is not None else None,
                headers={'Origin': origin, 'Content-Type': 'application/json'})
            try:
                response = opener.open(request, timeout=30)
            except urllib.error.HTTPError as error:
                response = error
            raw = response.read()
            return response.code, json.loads(raw) if raw else {}

        try:
            code, _ = call('/auth/login', {'username': usernames[-1].strip(), 'password': passwords[-1].strip()})
            record(profile + ':login', code == 200, http=code)
            if code != 200:
                continue
            code, session = call('/auth/session')
            record(profile + ':session_profile', code == 200 and (session.get('user') or {}).get('profile') == profile)
            for index, path in enumerate(paths):
                code, body = call(path)
                expected = 200 if index in permitted else 403
                record(profile + ':' + path.split('?')[0], code == expected, http=code, expected=expected)
                metadata = body.get('metadata', {})
                if metadata.get('source', {}).get('kind') == 'gold':
                    publications.add((metadata['source']['version'], metadata.get('fingerprint'), metadata.get('schema_version')))
                if profile == 'admin' and index == 0 and code == 200:
                    admin_panorama = body
                if profile == 'admin' and index == 2 and code == 200 and body['data']['items']:
                    identifier = body['data']['items'][0]['uc_id']
                    uc_path = '/ucs/' + urllib.parse.quote(identifier, safe='')
                    code, _ = call(uc_path + '/overview')
                    record('admin:uc_overview', code == 200, http=code)
            if profile == 'admin' and admin_panorama:
                filters = admin_panorama['data']['opcoesFiltros']
                municipalities = filters.get('municipios', [])
                classes = filters.get('classes', [])
                if municipalities and classes and isinstance(municipalities[0], str) and isinstance(classes[0], str):
                    query = urllib.parse.urlencode({'municipio': municipalities[0], 'classe': classes[0], 'comparacao': 'nenhuma'})
                    code, body = call('/panorama?' + query)
                    record('admin:combined_filters', code == 200 and body.get('data', {}).get('filtros', {}).get('municipio') == municipalities[0], http=code)
                for label, path, expected in [
                    ('invalid_period', '/panorama?competencia=invalida', 422),
                    ('stale_publication', '/panorama?expected_lote=DEV15_ANTIGO&expected_fingerprint=' + '0' * 64, 409),
                    ('empty_uc_search', '/ucs?q=999999999999', 200),
                    ('unknown_uc', '/ucs/999999999999/overview', 404),
                    ('recovery', '/panorama?comparacao=nenhuma', 200),
                ]:
                    code, body = call(path)
                    passed = code == expected
                    if label == 'empty_uc_search':
                        passed = passed and body.get('data', {}).get('items') == []
                    record('admin:' + label, passed, http=code, expected=expected)
        finally:
            code, _ = call('/auth/logout', {})
            record(profile + ':logout', code == 204, http=code)

    record('single_gold_v2_publication', len(publications) == 1 and next(iter(publications))[2] == 'gold-csv-v2')
    if args.reconcile and admin_panorama:
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / 'backend'))
        previous = Path.cwd()
        os.chdir(root / 'backend')
        try:
            from app.core.config import settings
            from sqlalchemy import create_engine, text
            engine = create_engine(settings.DATABASE_URL, hide_parameters=True, connect_args={'connect_timeout': 4})
            try:
                with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
                    connection.execute(text('SET TRANSACTION READ ONLY'))
                    batch = connection.execute(text('SELECT lote, fingerprint FROM gold_carga_atual WHERE id = 1')).mappings().one()
                    same = (batch['lote'], batch['fingerprint']) == (admin_panorama['metadata']['source']['version'], admin_panorama['metadata']['fingerprint'])
                    record('sql:same_publication', same)
                    if same:
                        row = connection.execute(text('SELECT sum(receita_base_comparavel_reais) AS revenue, sum(consumo_base_comparavel_kwh) AS energy FROM gold_v2.diagnostico_receita WHERE competencia = :month'), {'month': admin_panorama['data']['filtros']['periodo']}).mappings().one()
                        metrics = admin_panorama['data']['metricas']
                        record('sql:revenue_at_cent', row['revenue'] is not None and abs(Decimal(str(metrics['receitaFaturada']['valorAtual'])) - row['revenue']) <= Decimal('0.01'))
                        record('sql:energy_at_0_01_kwh', row['energy'] is not None and abs(metrics['energiaConsumida']['valorAtual'] - row['energy']) <= 0.01)
                    connection.rollback()
            finally:
                engine.dispose()
        except Exception as error:
            record('sql:available', False, error=type(error).__name__)
        finally:
            os.chdir(previous)
    result = {'origin': origin, 'api_base': api_base, 'publications': [dict(zip(['lote', 'fingerprint', 'schema_version'], p)) for p in sorted(publications)], 'checks': checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    failed = [check['check'] for check in checks if not check['passed']]
    print(json.dumps({'checks': len(checks), 'failed': failed}))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
