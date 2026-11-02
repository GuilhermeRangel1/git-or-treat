from pydantic import SecretStr

ROOT = '/api/v1/inspections'


def test_import_access_validation_audit_and_replay(client, monkeypatch):
    token = 'field-files-' + 'w' * 32
    monkeypatch.setattr('app.core.config.settings.ORDERS_WRITE_TOKEN', SecretStr(token))
    assert client.post(ROOT + '/field-results/import', json={'csv': 'x'}).status_code == 401
    client.headers['Authorization'] = 'Bearer ' + token
    order = client.post(ROOT + '/orders', json={'uc_id': 'FIELD-1', 'reason': 'Visita'}).json()
    oid = order['id']
    client.patch(f'{ROOT}/orders/{oid}', json={'version': 1, 'status': 'EM_ANDAMENTO'})
    content = f'ordem_id;versao;resultado\r\n{oid};2;Sem irregularidade\r\n999;1;Teste'
    result = client.post(ROOT + '/field-results/import', json={'csv': content})
    assert result.status_code == 200
    assert result.json()['imported'] == 1
    assert result.json()['errors'][0]['line'] == 3
    assert client.get(f'{ROOT}/orders/{oid}').json()['result'] == 'Sem irregularidade'
    history = client.get(f'{ROOT}/orders/{oid}/history').json()
    assert history[-1]['actor'] == 'orders-writer'
    assert client.post(ROOT + '/field-results/import', json={'csv': content}).json()['imported'] == 0
    assert len(client.get(f'{ROOT}/orders/{oid}/history').json()) == len(history)
    assert client.post(ROOT + '/field-results/import', json={'csv': 'resultado;versao;ordem_id'}).json()['errors']


def test_export_requires_access(client):
    assert client.get(ROOT + '/field-queue/export').status_code == 401


def test_excel_template_roundtrip_and_rejected_files(client, monkeypatch):
    import base64
    import io
    from openpyxl import load_workbook
    token = 'field-xlsx-' + 'w' * 32
    monkeypatch.setattr('app.core.config.settings.ORDERS_WRITE_TOKEN', SecretStr(token))
    assert client.get(ROOT + '/field-results/template').status_code == 401
    client.headers['Authorization'] = 'Bearer ' + token
    order = client.post(ROOT + '/orders', json={'uc_id': 'EXCEL-1', 'reason': 'Visita'}).json()
    oid = order['id']
    client.patch(f'{ROOT}/orders/{oid}', json={'version': 1, 'status': 'EM_ANDAMENTO'})
    template = client.get(ROOT + '/field-results/template').json()
    assert template['count'] == 1
    workbook = load_workbook(io.BytesIO(base64.b64decode(template['xlsx'])))
    sheet = workbook['Resultados']
    assert sheet['A2'].value == str(oid)
    assert sheet['C2'].value == 'EXCEL-1'
    sheet['D2'] = 'Sem irregularidade observada'
    def encoded():
        output = io.BytesIO()
        workbook.save(output)
        return base64.b64encode(output.getvalue()).decode()
    payload = {'xlsx': encoded()}
    result = client.post(ROOT + '/field-results/import', json=payload).json()
    assert result == {'imported': 1, 'errors': []}
    assert client.get(f'{ROOT}/orders/{oid}').json()['status'] == 'CONCLUIDA'
    before = client.get(f'{ROOT}/orders/{oid}/history').json()
    assert client.post(ROOT + '/field-results/import', json=payload).json()['imported'] == 0
    assert client.get(f'{ROOT}/orders/{oid}/history').json() == before
    sheet['D2'] = '=1+1'
    assert client.post(ROOT + '/field-results/import', json={'xlsx': encoded()}).json()['errors']
    assert client.post(ROOT + '/field-results/import', json={'xlsx': 'invalid'}).json()['errors']
    assert client.post(ROOT + '/field-results/import', json={'csv': 'x', 'xlsx': 'x'}).status_code == 422
    workbook.close()


def test_export_includes_entire_scope_and_real_options(client, monkeypatch):
    import csv
    import io
    from app.main import app
    from app.repositories.analytics import SyntheticAnalyticsRepository, get_analytics_repository_provider
    token = 'field-export-' + 'w' * 32
    monkeypatch.setattr('app.core.config.settings.ORDERS_WRITE_TOKEN', SecretStr(token))
    monkeypatch.setattr('app.core.config.settings.ANALYTICS_SOURCE', 'synthetic')
    client.headers['Authorization'] = 'Bearer ' + token
    app.dependency_overrides[get_analytics_repository_provider] = lambda: SyntheticAnalyticsRepository
    try:
        page = client.get(ROOT + '/queue?page_size=1').json()
        exported = client.get(ROOT + '/field-queue/export').json()
        assert exported['count'] == page['pagination']['total']
        assert exported['count'] > len(page['data']['items'])
        rows = list(csv.DictReader(io.StringIO(exported['csv']), delimiter=';'))
        assert len(rows) == exported['count']
        options = client.get(ROOT + '/field-queue/export?options_only=true').json()['options']
        assert options['municipio'] == page['data']['filter_options']['municipio']
        municipality = options['municipio'][0]
        filtered = client.get(ROOT + '/field-queue/export', params={'municipio': municipality}).json()
        filtered_rows = list(csv.DictReader(io.StringIO(filtered['csv']), delimiter=';'))
        assert all(row['municipality'] == municipality for row in filtered_rows)
        assert client.get(ROOT + '/field-queue/export?categoria=inexistente').status_code == 422
    finally:
        app.dependency_overrides.pop(get_analytics_repository_provider, None)
