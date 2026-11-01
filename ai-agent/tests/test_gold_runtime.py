"""O entrypoint implantável mantém Gold, auditoria e identidade explícitos."""

import pytest

from app.config import Settings
from app.gold_runtime import create_gold_app

from .conftest import InProcessClient


def test_gold_runtime_requires_durable_audit_configuration():
    with pytest.raises(ValueError, match="auditoria"):
        create_gold_app(Settings(_env_file=None))


def test_gold_runtime_does_not_authorize_public_question_with_service_token(monkeypatch):
    from app.audit import BackendEventSink

    monkeypatch.setattr(BackendEventSink, "record", lambda self, event: None)
    token = "test-gold-runtime-service-token-000000000"
    app = create_gold_app(Settings(
        _env_file=None, service_api_token=token,
        audit_url="http://backend/api/v1/internal/genai-audit-events",
        audit_write_token="test-gold-runtime-audit-token-00000000000",
    ))
    with InProcessClient(app) as client:
        response = client.post(
            "/api/v1/questions", json={"question": "Qual foi a receita?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "refused"
    assert response.json()["evidence"] == []

@pytest.mark.parametrize(
    'case', ['answered', 'no_evidence', 'model_unavailable', 'audit_unavailable'],
)
def test_official_gold_runtime_preserves_first_question_outcomes(monkeypatch, case):
    from app import main
    from app.audit import BackendEventSink
    from app.ports.events import AuditUnavailable
    from app.providers.protocols import ModelProviderUnavailable
    from app.schemas.internal import QuestionSynthesisRequest
    from app.schemas.read_plan import LogicalReadPlan

    from .conftest import FakeModelAdapter
    from .test_core_plan_synthesis import _lookup
    from .test_gold_question_filters import _setup

    calls = []

    class Model(FakeModelAdapter):
        async def generate(self, question, context, evidence):
            calls.append('model')
            if case == 'model_unavailable':
                raise ModelProviderUnavailable('private provider detail')
            return await super().generate(question, context, evidence)

    def record(self, event):
        if case == 'audit_unavailable':
            raise AuditUnavailable('private audit detail')

    monkeypatch.setattr(main, 'build_model_adapter', lambda settings: Model())
    monkeypatch.setattr(BackendEventSink, 'record', record)
    token = 'test-gold-runtime-service-token-000000000'
    application = create_gold_app(Settings(
        _env_file=None, service_api_token=token,
        audit_url='http://backend/api/v1/internal/genai-audit-events',
        audit_write_token='test-gold-runtime-audit-token-00000000000',
    ))
    _, request = _setup('Receita residencial em Olinda em março de 2025?')
    headers = {'Authorization': f'Bearer {token}', 'X-Correlation-ID': 'a' * 32}
    with InProcessClient(application) as client:
        planned = client.post('/api/v1/internal/question-plans',
                              json=request.model_dump(mode='json'), headers=headers)
        assert planned.status_code == 200
        if case == 'audit_unavailable':
            body = planned.json()
            assert body['status'] == 'recoverable_error'
            assert body['plan'] is None
            body = body['response']
        else:
            assert planned.json()['status'] == 'planned'
            plan = LogicalReadPlan.model_validate(planned.json()['plan'])
            lookup = _lookup(plan, batch_ref=request.batch_ref)
            lookup.evidence.records[0].update(
                period='2025-03', municipality='Olinda', consumption_class='RESIDENCIAL',
            )
            if case == 'no_evidence':
                from app.schemas.evidence import EvidenceLookupResult, EvidenceLookupStatus
                lookup = EvidenceLookupResult(status=EvidenceLookupStatus.NO_EVIDENCE,
                                              message='Nenhum registro no recorte autorizado.')
            payload = QuestionSynthesisRequest(
                question=request.question, access_scope=request.access_scope,
                remaining_timeout_ms=35000, plan=plan,
                plan_fingerprint=planned.json()['plan_fingerprint'], lookup=lookup,
                expected_batch_ref=request.batch_ref,
            )
            response = client.post('/api/v1/internal/question-syntheses',
                                   json=payload.model_dump(mode='json'), headers=headers)
            assert response.status_code == 200
            body = response.json()
            assert body['status'] == ('recoverable_error' if case == 'model_unavailable' else case)
        assert 'private' not in str(body)
        if case != 'answered':
            assert body.get('answer') is None
            assert body['evidence'] == []
        else:
            assert '12 R$' in body['answer']
            assert all(not item['is_demo'] for item in body['evidence'])
        if case in {'no_evidence', 'audit_unavailable'}:
            assert calls == []
