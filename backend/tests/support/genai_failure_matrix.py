"""Mesma fatia HTTP/PostgreSQL com falhas determinísticas nas fronteiras de I/O."""

from sqlalchemy import event, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.models.auth import AuthUser
from app.models.gold_v2_load import TABLES
from app.services.genai_audit import AuditStore
from tests.support.genai_transport import GENAI_TRANSPORT_EVENTS

QUESTION = "Qual a receita em Lumenia em janeiro de 2001?"


def assert_first_question_failures(client, owner, monkeypatch, headers):
    """Não altera lote real: chamada exclusiva do fixture PostgreSQL descartável."""
    def ask(question=QUESTION):
        GENAI_TRANSPORT_EVENTS.clear()
        response = client.post('/api/v1/ai/questions', headers=headers,
                               json={'question': question})
        body = response.json()
        assert response.headers['x-correlation-id'] == body['correlation_id']
        assert not body.get('answer')
        assert not body.get('evidence')
        assert 'private' not in response.text
        assert body.get('message')
        return response, body

    # Município e mês existem separadamente, mas o cruzamento autorizado está vazio.
    table = TABLES['diagnostico_receita']
    with owner.begin() as db:
        row = dict(db.execute(select(table).where(
            table.c.municipio == 'Outra Cidade', table.c.competencia == '2001-01',
        )).mappings().one())
        row['competencia'] = '2001-02'
        db.execute(table.insert(), row)
        assert db.execute(select(table.c.municipio).where(
            table.c.municipio == 'Lumenia', table.c.competencia == '2001-02',
        )).first() is None
    try:
        response, body = ask('Qual a receita em Lumenia em fevereiro de 2001?')
        assert response.status_code == 200 and body['status'] == 'needs_clarification'
        assert body['error'] is None
        assert 'cobertura' in body['message']
        assert len(GENAI_TRANSPORT_EVENTS) == 1  # Sem síntese/modelo.
    finally:
        with owner.begin() as db:
            db.execute(table.delete().where(*(
                table.c[column.name] == row[column.name] for column in table.primary_key
            )))

    response, body = ask('Qual a receita em Lumenia?')
    assert response.status_code == 200 and body['status'] == 'needs_clarification'
    assert body['error'] is None

    # Falha DBAPI apenas no SQL quantitativo do leitor, após planejamento/prontidão.
    triggered = []

    def disconnect(conn, cursor, statement, parameters, context, executemany):
        if (conn.engine.url.username == 'venergy_genai_reader'
                and 'sum(' in statement.lower() and ' AS value' in statement):
            triggered.append(True)
            raise OperationalError('private query', None, RuntimeError('private source detail'))

    event.listen(Engine, 'before_cursor_execute', disconnect)
    try:
        response, body = ask()
        assert triggered and response.status_code == 503
        assert body['error'] == {'code': 'service_unavailable', 'retryable': True}
        assert len(GENAI_TRANSPORT_EVENTS) == 1
    finally:
        event.remove(Engine, 'before_cursor_execute', disconnect)

    with monkeypatch.context() as patch:
        patch.setenv('GENAI_TEST_MODEL_FAILURE', 'unavailable')
        response, body = ask()
        assert response.status_code == 200 and body['status'] == 'recoverable_error'
        assert body['error'] == {'code': 'service_unavailable', 'retryable': True}
        assert len(GENAI_TRANSPORT_EVENTS) == 2

    original_record = AuditStore.record
    failed = []

    def fail_confirmation(self, audit_event, *, service='backend'):
        if service == 'backend' and audit_event.stage == 'response':
            failed.append(True)
            raise SQLAlchemyError('private audit confirmation detail')
        return original_record(self, audit_event, service=service)

    with monkeypatch.context() as patch:
        patch.setattr(AuditStore, 'record', fail_confirmation)
        response, body = ask()
        assert failed and response.status_code == 503
        assert body['error'] == {'code': 'service_unavailable', 'retryable': False}
        assert len(GENAI_TRANSPORT_EVENTS) == 2  # Síntese pronta não publica sem auditoria.
        retained = AuditStore(owner).read(body['correlation_id'])
        assert any(item['service'] == 'backend' and item['event']['stage'] == 'source'
                   for item in retained)
        assert not any(item['service'] == 'backend' and item['event']['stage'] == 'response'
                       for item in retained)
        assert not body.get('audit_reference')

    with owner.begin() as db:
        db.execute(update(AuthUser).where(AuthUser.username == 'reader').values(permissions=[]))
    try:
        response, body = ask()
        assert response.status_code == 403
        assert body['error'] == {'code': 'access_denied', 'retryable': False}
        assert not GENAI_TRANSPORT_EVENTS
    finally:
        with owner.begin() as db:
            db.execute(update(AuthUser).where(AuthUser.username == 'reader')
                       .values(permissions=['orders:read']))

    # Falhas e revogação não contaminam a requisição seguinte após restauração.
    recovered = client.post('/api/v1/ai/questions', headers=headers, json={'question': QUESTION})
    assert recovered.status_code == 200
    assert recovered.json()['status'] == 'answered'
    assert '12.0 R$' in recovered.json()['answer']
    assert recovered.json()['audit_reference']
    assert all(not item['is_demo'] for item in recovered.json()['evidence'])
