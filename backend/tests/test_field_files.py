from pydantic import SecretStr

ROOT = '/api/v1/inspections'


def test_export_requires_access(client):
    assert client.get(ROOT + '/field-queue/export').status_code == 401


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
