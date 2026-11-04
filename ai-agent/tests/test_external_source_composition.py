"""A fonte futura só atravessa HTTP com escopo produzido por uma borda confiável."""

import asyncio
from types import SimpleNamespace

import pytest

from app.api.access import (
    SYNTHETIC_SOURCE_ID,
    demo_access_context,
    resolve_access_context,
)
from app.config import Settings
from app.main import create_app
from app.profiles.grid360_demo import GRID360_DEMO_PROFILE
from app.schemas.evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceProvenance,
    EvidenceReference,
    EvidenceResult,
)
from app.schemas.questions import QuestionRequest

from .conftest import FakeModelAdapter, InProcessClient

SOURCE_ID = "external.test"
TOKEN = "s" * 32
PROFILE = GRID360_DEMO_PROFILE.model_copy(update={"profile_id": "external.test.v1"})
QUESTION = "Qual foi o consumo no período de demonstração?"


class EmptyExternalSource:
    def __init__(self) -> None:
        self.calls = 0

    async def retrieve(self, plan, access_context):
        self.calls += 1
        assert plan.source_id == access_context.source_id == SOURCE_ID
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.NO_EVIDENCE,
            message="Sem evidência para o recorte solicitado.",
        )


class DemoExternalSource(EmptyExternalSource):
    async def retrieve(self, plan, access_context):
        self.calls += 1
        reference = "external_test:fixture"
        return EvidenceLookupResult(
            status=EvidenceLookupStatus.AVAILABLE,
            evidence=EvidenceResult(
                reference=EvidenceReference(
                    source=reference,
                    description="Synthetic test value.",
                    is_demo=True,
                ),
                records=[{"value": 420, "unit": plan.unit}],
                provenance=EvidenceProvenance(
                    source_id=plan.source_id,
                    reference_source=reference,
                    plan_fingerprint=plan.fingerprint(),
                    catalog_version=plan.catalog_version,
                    metric_id=plan.metric_id,
                    unit=plan.unit,
                    window=plan.window,
                    filters=plan.filters,
                    dimension_ids=plan.dimension_ids,
                ),
            ),
            limitations=[
                "Valor inventado; não representa leitura, consumo ou unidade consumidora "
                "da V-Energy."
            ],
        )


class DurableSink:
    durable = True

    def __init__(self) -> None:
        self.events = []

    def record(self, event) -> None:
        self.events.append(event)


def _settings(**overrides):
    values = {
        "environment": "local",
        "enable_demo_access": False,
        "service_api_token": TOKEN,
        **overrides,
    }
    return Settings(_env_file=None, **values)


def _verified_context(request):
    return demo_access_context(
        PROFILE, request.state.correlation_id, SOURCE_ID
    ).model_copy(update={"caller_ref": "verified.test"})


def test_external_resolver_must_match_request_correlation_and_real_caller() -> None:
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace()),
        state=SimpleNamespace(correlation_id="a" * 32),
    )
    request.app.state.access_context_resolver = _verified_context
    assert resolve_access_context(request) == _verified_context(request)

    request.app.state.access_context_resolver = lambda request: _verified_context(
        request
    ).model_copy(update={"correlation_id": "b" * 32})
    assert resolve_access_context(request) is None

    request.app.state.access_context_resolver = lambda request: demo_access_context(
        PROFILE, request.state.correlation_id, SOURCE_ID
    )
    assert resolve_access_context(request) is None


def test_external_core_returns_no_evidence_from_injected_source() -> None:
    source = EmptyExternalSource()
    app = create_app(
        settings=_settings(),
        domain_profile=PROFILE,
        source_id=SOURCE_ID,
        source_mode="external",
        evidence_source=source,
        access_context_resolver=_verified_context,
        event_sink=DurableSink(),
        require_durable_audit=True,
        model_adapter=FakeModelAdapter(),
    )
    context = demo_access_context(PROFILE, "a" * 32, SOURCE_ID).model_copy(
        update={"caller_ref": "verified.test"}
    )

    response = asyncio.run(
        app.state.question_orchestrator.answer(QuestionRequest(question=QUESTION), context)
    )

    assert response.status == "no_evidence"
    assert source.calls == 1


def test_external_source_reaches_http_only_with_verified_request_scope() -> None:
    source = EmptyExternalSource()
    app = create_app(
        settings=_settings(),
        domain_profile=PROFILE,
        source_id=SOURCE_ID,
        source_mode="external",
        evidence_source=source,
        access_context_resolver=_verified_context,
        event_sink=DurableSink(),
        require_durable_audit=True,
        model_adapter=FakeModelAdapter(),
    )

    with InProcessClient(app) as client:
        response = client.post(
            "/api/v1/questions",
            json={"question": QUESTION},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "no_evidence"
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]
    assert source.calls == 1


def test_external_source_does_not_accept_synthetic_insight() -> None:
    app = create_app(
        settings=_settings(),
        domain_profile=PROFILE,
        source_id=SOURCE_ID,
        source_mode="external",
        evidence_source=EmptyExternalSource(),
        access_context_resolver=_verified_context,
        event_sink=DurableSink(),
        require_durable_audit=True,
        model_adapter=FakeModelAdapter(),
    )
    screen = {
        "metric": "consumo demonstrativo",
        "unit": "kWh fictícios",
        "period": {"start": "2025-01-01", "end": "2025-03-31", "granularity": "month"},
        "filters": {"classe": "residencial"},
        "observations": [{"label": "consumo total", "value": 420}],
        "reference": {
            "source": "synthetic_screen:consumption",
            "description": "Resultado artificial de tela.",
            "is_demo": True,
        },
        "limitations": ["O resultado é sintético."],
    }

    with InProcessClient(app) as client:
        response = client.post(
            "/api/v1/insights",
            json={"screen": screen},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "service_unavailable", "retryable": False
    }
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]


def test_external_source_denies_scope_from_wrong_source_before_read() -> None:
    source = EmptyExternalSource()

    def wrong_scope(request):
        return _verified_context(request).model_copy(update={"source_id": "other.test"})

    app = create_app(
        settings=_settings(),
        domain_profile=PROFILE,
        source_id=SOURCE_ID,
        source_mode="external",
        evidence_source=source,
        access_context_resolver=wrong_scope,
        event_sink=DurableSink(),
        require_durable_audit=True,
        model_adapter=FakeModelAdapter(),
    )

    with InProcessClient(app) as client:
        response = client.post(
            "/api/v1/questions",
            json={"question": QUESTION},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "refused"
    assert response.json()["error"]["code"] == "access_denied"
    assert source.calls == 0


def test_external_source_never_publishes_demo_evidence() -> None:
    source = DemoExternalSource()
    app = create_app(
        settings=_settings(),
        domain_profile=PROFILE,
        source_id=SOURCE_ID,
        source_mode="external",
        evidence_source=source,
        access_context_resolver=_verified_context,
        event_sink=DurableSink(),
        require_durable_audit=True,
        model_adapter=FakeModelAdapter(),
    )

    with InProcessClient(app) as client:
        response = client.post(
            "/api/v1/questions",
            json={"question": QUESTION},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "recoverable_error"
    assert response.json()["evidence"] == []
    assert source.calls == 1


@pytest.mark.parametrize(
    "missing",
    ["domain_profile", "evidence_source", "access_context_resolver"],
)
def test_external_source_requires_explicit_dependencies(missing: str) -> None:
    arguments = {
        "domain_profile": PROFILE,
        "evidence_source": EmptyExternalSource(),
        "access_context_resolver": _verified_context,
    }
    arguments.pop(missing)

    with pytest.raises(ValueError, match="Fonte externa exige perfil próprio, fonte"):
        create_app(
            settings=_settings(), source_id=SOURCE_ID, source_mode="external", **arguments
        )


def test_external_source_rejects_demo_access_and_missing_service_token() -> None:
    arguments = {
        "domain_profile": PROFILE,
        "evidence_source": EmptyExternalSource(),
        "access_context_resolver": _verified_context,
        "source_id": SOURCE_ID,
        "source_mode": "external",
    }

    with pytest.raises(ValueError, match="acesso demonstrativo desligado"):
        create_app(settings=_settings(enable_demo_access=True), **arguments)
    with pytest.raises(ValueError, match="token interno"):
        create_app(
            settings=Settings(
                _env_file=None, environment="local", enable_demo_access=False
            ),
            **arguments,
        )


def test_external_source_requires_durable_audit() -> None:
    arguments = {
        "settings": _settings(),
        "source_mode": "external",
        "source_id": SOURCE_ID,
        "domain_profile": PROFILE,
        "evidence_source": EmptyExternalSource(),
        "access_context_resolver": _verified_context,
    }
    with pytest.raises(ValueError, match="auditoria durável"):
        create_app(**arguments)
    with pytest.raises(ValueError, match="auditoria durável"):
        create_app(**arguments, require_durable_audit=True)


def test_demo_mode_cannot_install_external_access_resolver() -> None:
    with pytest.raises(ValueError, match="exige modo external"):
        create_app(
            settings=_settings(),
            source_id=SYNTHETIC_SOURCE_ID,
            access_context_resolver=_verified_context,
        )


def test_demo_mode_cannot_name_an_external_source() -> None:
    with pytest.raises(ValueError, match="Modo demo exige fonte sintética"):
        create_app(settings=_settings(), source_id=SOURCE_ID)


def test_external_mode_cannot_reuse_demonstration_profile() -> None:
    with pytest.raises(ValueError, match="Fonte externa exige perfil próprio"):
        create_app(
            settings=_settings(),
            source_mode="external",
            source_id=SOURCE_ID,
            domain_profile=GRID360_DEMO_PROFILE,
            evidence_source=EmptyExternalSource(),
            access_context_resolver=_verified_context,
        )
