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
    # Pergunta pública até SQL/síntese: expectativas literais, sem usar o planner
    # para calcular o resultado esperado. Correção e grafia preservam o recorte.
    for question, metric, expected, filters in (
        ('Qual o faturamento em lumenia em janeiro de 2001?',
         'billing.revenue', 12.0, {'geography.municipality': ['Lumenia']}),
        ('Qual a receita em Outra Cidade, não, em Lumenia em janeiro de 2001?',
         'billing.revenue', 12.0, {'geography.municipality': ['Lumenia']}),
        ('Qual a receita em Lumenia sem GD em janeiro de 2001?',
         'billing.revenue', 12.0,
         {'geography.municipality': ['Lumenia'], 'generation.distributed': ['Não']}),
        ('Qual a receita em Zero Lumenia em janeiro de 2001?',
         'billing.revenue', 0.0, {'geography.municipality': ['Zero Lumenia']}),
        ('Qual a receita residencial em Lumenia em janeiro de 2001?',
         'billing.revenue', 12.0,
         {'geography.municipality': ['Lumenia'],
          'customer.consumption_class': ['RESIDENCIAL']}),
        ('Qual a receita no bairro Bairro Ficticio em Lumenia em janeiro de 2001?',
         'billing.revenue', 7.0,
         {'geography.municipality': ['Lumenia'],
          'geography.neighborhood': ['Bairro Ficticio']}),
        ('Qual o DEC no alimentador AL-TESTE em janeiro de 2001?',
         'network.equivalent_interruption_duration', 1.5,
         {'network.feeder': ['AL-TESTE']}),
    ):
        GENAI_TRANSPORT_EVENTS.clear()
        response = client.post('/api/v1/ai/questions', headers=headers,
                               json={'question': question})
        assert response.status_code == 200, (question, response.text)
        assert response.json()['status'] == 'answered', (question, response.text)
        assert len(GENAI_TRANSPORT_EVENTS) == 2
        planned, synthesized = GENAI_TRANSPORT_EVENTS
        plan = planned['response']['plan']
        assert plan['metric_id'] == metric
        assert {f['dimension_id']: f['values'] for f in plan['filters']} == filters
        assert not plan['group_by_dimension_ids'] and plan['order'] is None
        assert 0 < plan['limit'] <= 100
        assert plan['window']['start'] == '2001-01-01'
        assert plan['window']['end'] == '2001-01-31'
        assert synthesized['request']['plan'] == plan
        assert synthesized['request']['lookup']['evidence']['records'][0]['value'] == expected

    GENAI_TRANSPORT_EVENTS.clear()
    follow = client.post('/api/v1/ai/questions', headers=headers, json={
        'question': 'E em Outra Cidade?',
        'context': [{'role': 'user', 'content':
                     'Qual a receita residencial sem GD em Lumenia em janeiro de 2001?'}],
    })
    assert follow.status_code == 200 and follow.json()['status'] == 'answered', follow.text
    follow_plan = GENAI_TRANSPORT_EVENTS[0]['response']['plan']
    assert {f['dimension_id']: f['values'] for f in follow_plan['filters']} == {
        'geography.municipality': ['Outra Cidade'],
        'customer.consumption_class': ['RESIDENCIAL'],
        'generation.distributed': ['Não'],
    }
    assert GENAI_TRANSPORT_EVENTS[1]['request']['lookup']['evidence']['records'][0]['value'] == 999.0

    # Janela relativa completa na mesma publicação: onze meses artificiais
    # adicionais mais janeiro já existente. Removidos antes das provas de lacuna.
    table = TABLES['diagnostico_receita']
    months = tuple(f'2000-{month:02d}' for month in range(2, 13))
    with owner.begin() as db:
        original = dict(db.execute(select(table).where(
            table.c.municipio == 'Lumenia', table.c.competencia == '2001-01',
        )).mappings().one())
        db.execute(table.insert(), [
            {**original, 'competencia': month, 'receita_total_reais': 1} for month in months
        ])
    try:
        GENAI_TRANSPORT_EVENTS.clear()
        annual = client.post('/api/v1/ai/questions', headers=headers, json={
            'question': 'Qual a receita em Lumenia no último ano?',
        })
        assert annual.status_code == 200 and annual.json()['status'] == 'answered', annual.text
        plan = GENAI_TRANSPORT_EVENTS[0]['response']['plan']
        assert plan['window']['start'] == '2000-02-01'
        assert plan['window']['end'] == '2001-01-31'
        records = GENAI_TRANSPORT_EVENTS[1]['request']['lookup']['evidence']['records']
        assert [r['period'] for r in records] == [*months, '2001-01']
        assert [r['value'] for r in records] == [*([1.0] * 11), 12.0]
    finally:
        with owner.begin() as db:
            db.execute(table.delete().where(
                table.c.municipio == 'Lumenia', table.c.competencia.in_(months),
            ))

    def ask(question=QUESTION, *, context=None):
        GENAI_TRANSPORT_EVENTS.clear()
        response = client.post('/api/v1/ai/questions', headers=headers,
                               json={'question': question, 'context': context or []})
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

    # Pedidos sem suporte não podem perder o qualificador e consultar um total maior.
    for question in (
        'Qual a receita paga em Lumenia em janeiro de 2001?',
        'Qual a receita da UC UC-999 em janeiro de 2001?',
        'Qual a receita em Lumenia nos últimos 12 meses?',
        'Qual a receita em Lumenia entre 15 e 20 de janeiro de 2001?',
        'Quais os três bairros com maior receita em janeiro de 2001?',
        'Qual a receita em Lumenia e Outra Cidade em janeiro de 2001?',
        'Qual a receita em Lumenia em kWh em janeiro de 2001?',
        'Qual a receita no município Desconhecido em janeiro de 2001?',
        'Qual a receita em Lumenia com GD e sem GD em janeiro de 2001?',
        'Compare a receita em Lumenia em janeiro de 2001 com dezembro de 2000.',
        'Qual a variação percentual da receita em Zero Lumenia em janeiro de 2001?',
    ):
        response, body = ask(question)
        assert response.status_code == 200
        assert body['status'] in {'needs_clarification', 'refused'}, question
        assert len(GENAI_TRANSPORT_EVENTS) <= 1  # Sem síntese nem modelo.

    # Nulo é detectado na execução e traduzido pela síntese, sem gerar número.
    response, body = ask('Qual a receita em Nulo Lumenia em janeiro de 2001?')
    assert response.status_code == 200 and body['status'] == 'needs_clarification'
    assert len(GENAI_TRANSPORT_EVENTS) == 2

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

    with owner.connect() as db:
        previous_profile = db.scalar(
            select(AuthUser.profile).where(AuthUser.username == 'reader')
        )
    with owner.begin() as db:
        db.execute(update(AuthUser).where(AuthUser.username == 'reader').values(profile=None))
    try:
        response, body = ask('E em Lumenia?', context=[{'role': 'user', 'content': QUESTION}])
        assert response.status_code == 403
        assert body['error'] == {'code': 'access_denied', 'retryable': False}
        assert not GENAI_TRANSPORT_EVENTS
    finally:
        with owner.begin() as db:
            db.execute(update(AuthUser).where(AuthUser.username == 'reader')
                       .values(profile=previous_profile))

    # Falhas e revogação não contaminam a requisição seguinte após restauração.
    recovered = client.post('/api/v1/ai/questions', headers=headers, json={'question': QUESTION})
    assert recovered.status_code == 200
    assert recovered.json()['status'] == 'answered'
    assert '12.0 R$' in recovered.json()['answer']
    assert recovered.json()['audit_reference']
    assert all(not item['is_demo'] for item in recovered.json()['evidence'])

    # A mesma síntese Gold remove aliases/estruturas derivadas antes do provedor.
    with monkeypatch.context() as patch:
        patch.setenv('GENAI_TEST_PRIVACY_PROBE', '1')
        privacy = client.post('/api/v1/ai/questions', headers=headers,
                              json={'question': QUESTION})
    assert privacy.status_code == 200 and privacy.json()['status'] == 'answered'
    retained = AuditStore(owner).read(privacy.json()['correlation_id'])
    surfaces = privacy.text + str(retained) + str(GENAI_TRANSPORT_EVENTS)
    assert 'private-nested-probe' not in surfaces
    assert 'private-alias-probe' not in surfaces
