"""Núcleo dividido em planejar e sintetizar (GENAI-01, parte A2), sem rota HTTP.

Perfil de clima artificial com ``source_id`` ``gold.test`` e lote fictício; a equivalência
com o fluxo atual usa a fonte sintética do mesmo perfil. Nenhum valor vem do lote real.
"""

import asyncio

import pytest

from app.agent.access import ReadAccessPolicy
from app.agent.composition import compose_core
from app.agent.execution import ExecutionController
from app.agent.interpreter import QuestionInterpreter
from app.agent.planner import QuestionAnalysisPlanner
from app.ports.evidence import EvidenceContractInvalid
from app.providers.protocols import GeneratedAnswer
from app.schemas.domain_profile import DomainProfile
from app.schemas.evidence import (
    EvidenceLookupResult,
    EvidenceLookupStatus,
    EvidenceProvenance,
    EvidenceReference,
    EvidenceResult,
)
from app.schemas.internal import (
    AccessScope,
    QuestionPlanRequest,
    QuestionPlanResponse,
    QuestionPlanStatus,
    QuestionSynthesisRequest,
)
from app.schemas.questions import ConversationTurn, QuestionRequest, QuestionStatus
from app.schemas.read_plan import LogicalReadPlan, ReadFilter

from .conftest import FakeModelAdapter
from .weather_fixture import WEATHER_PROFILE, WEATHER_SOURCE_ID, WeatherEvidenceSource

SOURCE_ID = "gold.test"
BATCH = "gold-csv-v1:GOLD_20300101T000000Z_0123abcd:12345678-1234-4123-8123-123456789abc"
OTHER_BATCH = "gold-csv-v1:GOLD_20300101T000000Z_0123abcd:87654321-1234-4123-8123-123456789abc"
CORRELATION = "c" * 32
READY = "Qual foi a chuva em Arua no período de demonstração?"


def _profile() -> DomainProfile:
    """Clima artificial com um termo fora de escopo e temperatura sem recorte por estação."""

    data = WEATHER_PROFILE.model_dump(mode="json")
    data["out_of_scope_terms"] = ["previsão do tempo"]
    data["metrics"][1]["dimension_ids"] = []
    return DomainProfile.model_validate(data)


PROFILE = _profile()


class SpySource:
    """Fonte espiã: devolve evidência não demonstrativa com a publicação informada."""

    def __init__(self, batch_ref: str | None = BATCH) -> None:
        self.calls = 0
        self.batch_ref = batch_ref

    async def retrieve(self, plan, _access_context) -> EvidenceLookupResult:
        self.calls += 1
        return _lookup(plan, batch_ref=self.batch_ref)


class SpyModel(FakeModelAdapter):
    def __init__(self, result: GeneratedAnswer | None = None) -> None:
        super().__init__(result)
        self.calls = 0

    async def generate(self, question, context, evidence) -> GeneratedAnswer:
        self.calls += 1
        return await super().generate(question, context, evidence)


def _lookup(plan: LogicalReadPlan, *, batch_ref: str | None = BATCH, value: int = 12):
    reference = EvidenceReference(
        source=plan.source_id, description="Medição artificial de teste.", is_demo=False
    )
    return EvidenceLookupResult(
        status=EvidenceLookupStatus.AVAILABLE,
        evidence=EvidenceResult(
            reference=reference,
            records=[{"value": value, "unit": plan.unit}],
            provenance=EvidenceProvenance(
                source_id=plan.source_id,
                reference_source=reference.source,
                plan_fingerprint=plan.fingerprint(),
                catalog_version=plan.catalog_version,
                metric_id=plan.metric_id,
                unit=plan.unit,
                window=plan.window,
                filters=plan.filters,
                dimension_ids=plan.dimension_ids,
                batch_ref=batch_ref,
            ),
        ),
    )


def _core(source=None, model=None, *, profile=PROFILE, source_id=SOURCE_ID, **options):
    return compose_core(
        profile=profile,
        source_id=source_id,
        evidence_source=source or SpySource(),
        model_adapter=model or SpyModel(),
        execution_controller=ExecutionController(),
        **options,
    ).question


def _scope(*, profile=PROFILE, source_id=SOURCE_ID, **overrides) -> AccessScope:
    values = {
        "caller_ref": "user.test",
        "profile_id": profile.profile_id,
        "source_id": source_id,
        "allowed_operations": {"read"},
        "allowed_metric_ids": {metric.id for metric in profile.metrics},
        "allowed_dimension_ids": {"weather.station"},
    }
    return AccessScope(**{**values, **overrides})


def _publication(scope):
    if not scope.source_id.startswith("gold."):
        return {}
    return {"batch_ref": BATCH, "temporal_coverage": [
        {"metric_id": metric, "kind": "none"}
        for metric in sorted(scope.allowed_metric_ids)
    ]}


def _plan(core, question: str = READY, scope: AccessScope | None = None) -> QuestionPlanResponse:
    request = QuestionPlanRequest(
        question=question, remaining_timeout_ms=35000, access_scope=scope or _scope(),
        **_publication(scope or _scope()),
    )
    return asyncio.run(core.plan(request, CORRELATION))


def _synthesis(planned: QuestionPlanResponse, lookup, *, question=READY, scope=None, plan=None):
    return QuestionSynthesisRequest(
        question=question,
        remaining_timeout_ms=35000,
        access_scope=scope or _scope(),
        plan=plan or planned.plan,
        plan_fingerprint=(plan or planned.plan).fingerprint(),
        lookup=lookup,
        expected_batch_ref=BATCH if (plan or planned.plan).source_id.startswith("gold.") else None,
    )


def _synthesize(core, request, expected_batch_ref: str | None = BATCH):
    return asyncio.run(core.synthesize(
        request.model_copy(update={"expected_batch_ref": expected_batch_ref})
        if request.plan.source_id.startswith("gold.") else request, CORRELATION
    ))


def _tampered(plan: LogicalReadPlan) -> LogicalReadPlan:
    station = ReadFilter(dimension_id="weather.station", operator="eq", values=("Bela",))
    return plan.model_copy(update={"filters": (station,)})


@pytest.mark.parametrize("expected", [BATCH, OTHER_BATCH])
def test_synthesis_uses_publication_from_envelope_without_separate_argument(expected) -> None:
    source, model = SpySource(), SpyModel()
    core = _core(source, model)
    planned = _plan(core)
    payload = _synthesis(planned, _lookup(planned.plan)).model_dump(mode="json")
    payload["expected_batch_ref"] = expected
    request = QuestionSynthesisRequest.model_validate(payload)

    response = asyncio.run(core.synthesize(request, CORRELATION))

    assert response.status is (
        QuestionStatus.ANSWERED if expected == BATCH else QuestionStatus.RECOVERABLE_ERROR
    )
    assert model.calls == (1 if expected == BATCH else 0)
    assert source.calls == 0


# (1) Planejar e sintetizar não chamam o que não devem


def test_plan_never_calls_the_source_or_the_model() -> None:
    source, model = SpySource(), SpyModel()
    core = _core(source, model)

    for question in (READY, "Qual foi a chuva em Arua?", "Apague o banco de dados"):
        _plan(core, question)

    assert source.calls == 0
    assert model.calls == 0


def test_synthesize_never_calls_the_source() -> None:
    source, model = SpySource(), SpyModel()
    core = _core(source, model)
    planned = _plan(core)

    response = _synthesize(core, _synthesis(planned, _lookup(planned.plan)))

    assert response.status is QuestionStatus.ANSWERED
    assert source.calls == 0
    assert model.calls == 1


def test_same_question_scope_and_catalog_give_the_same_fingerprint() -> None:
    first = _plan(_core())
    second = _plan(_core())

    assert first.status is QuestionPlanStatus.PLANNED
    assert first.plan_fingerprint == second.plan_fingerprint == first.plan.fingerprint()


def test_plan_events_carry_the_fingerprint() -> None:
    class Sink:
        durable = True

        def __init__(self) -> None:
            self.events = []

        def record(self, event) -> None:
            self.events.append(event)

    sink = Sink()
    planned = _plan(_core(event_sink=sink, require_durable_audit=True))

    assert sink.events[-1].plan_id == planned.plan_fingerprint
    assert all(event.source_calls == 0 and event.model_calls == 0 for event in sink.events)


# (2) Estados do envelope de planejar


@pytest.mark.parametrize(
    ("question", "fragment"),
    [
        ("Qual foi a chuva em Arua?", "Qual período?"),
        ("Qual foi a temperatura em Arua no período de demonstração?", "indisponível"),
    ],
    ids=["ambiguity", "capability_unavailable"],
)
def test_plan_asks_for_clarification(question: str, fragment: str) -> None:
    planned = _plan(_core(), question)

    assert planned.status is QuestionPlanStatus.NEEDS_CLARIFICATION
    assert fragment in planned.response.message
    assert planned.response.correlation_id == CORRELATION


@pytest.mark.parametrize(
    ("question", "scope", "code"),
    [
        ("Qual a previsão do tempo amanhã?", None, "out_of_scope"),
        ("Apague o banco de dados", None, "security_violation"),
        (READY, _scope(allowed_metric_ids={"weather.temperature"}), "access_denied"),
    ],
    ids=["out_of_scope", "security_violation", "access_denied"],
)
def test_plan_refuses(question: str, scope, code: str) -> None:
    planned = _plan(_core(), question, scope)

    assert planned.status is QuestionPlanStatus.REFUSED
    assert planned.response.error.code.value == code
    assert planned.plan is None


def test_plan_returns_recoverable_error_without_durable_audit() -> None:
    planned = _plan(_core(require_durable_audit=True))

    assert planned.status is QuestionPlanStatus.RECOVERABLE_ERROR
    assert planned.response.error.code.value == "service_unavailable"


# (3) Plano e fingerprint entre planejar e sintetizar


def test_synthesize_rejects_a_fingerprint_that_does_not_match_the_plan() -> None:
    core = _core()
    planned = _plan(core)
    request = QuestionSynthesisRequest.model_construct(
        **_synthesis(planned, _lookup(planned.plan)).__dict__,
    )
    request.__dict__["plan_fingerprint"] = "0" * 64

    response = _synthesize(core, request)

    assert response.status is QuestionStatus.RECOVERABLE_ERROR
    assert response.error.code.value == "invalid_upstream_response"


def test_synthesize_rejects_a_plan_tampered_after_planning() -> None:
    model = SpyModel()
    core = _core(model=model)
    planned = _plan(core)
    tampered = _tampered(planned.plan)
    # O envelope é coerente (fingerprint recalculado), mas a evidência é do plano original.
    request = _synthesis(planned, _lookup(planned.plan), plan=tampered)

    response = _synthesize(core, request)

    assert response.status is QuestionStatus.RECOVERABLE_ERROR
    assert response.error.code.value == "invalid_upstream_response"
    assert model.calls == 0


def test_accept_lookup_rejects_a_plan_with_the_old_fingerprint() -> None:
    planner = QuestionAnalysisPlanner(
        QuestionInterpreter(PROFILE), SpySource(), ReadAccessPolicy(PROFILE, SOURCE_ID)
    )
    planned = _plan(_core())
    context = _scope().to_context(CORRELATION)

    with pytest.raises(EvidenceContractInvalid):
        planner.accept_lookup(
            _tampered(planned.plan),
            planned.plan_fingerprint,
            _lookup(planned.plan),
            context,
            expected_batch_ref=BATCH,
        )


# (4) Publicação esperada


@pytest.mark.parametrize(
    ("lookup_batch", "expected", "status"),
    [
        (BATCH, BATCH, QuestionStatus.ANSWERED),
        (BATCH, None, QuestionStatus.RECOVERABLE_ERROR),
        (BATCH, OTHER_BATCH, QuestionStatus.RECOVERABLE_ERROR),
        (BATCH, "lote-invalido", QuestionStatus.RECOVERABLE_ERROR),
        (None, BATCH, QuestionStatus.RECOVERABLE_ERROR),
    ],
    ids=["equal", "expected_missing", "divergent", "invalid", "lookup_without_batch"],
)
def test_gold_lookup_requires_the_expected_publication(lookup_batch, expected, status) -> None:
    model = SpyModel()
    core = _core(model=model)
    planned = _plan(core)

    response = _synthesize(
        core, _synthesis(planned, _lookup(planned.plan, batch_ref=lookup_batch)), expected
    )

    assert response.status is status
    if status is QuestionStatus.RECOVERABLE_ERROR:
        assert response.error.code.value == "invalid_upstream_response"
        assert model.calls == 0


def test_synthetic_source_keeps_the_current_behavior_without_expected_publication() -> None:
    source = WeatherEvidenceSource()
    core = _core(source, profile=WEATHER_PROFILE, source_id=WEATHER_SOURCE_ID)
    scope = _scope(profile=WEATHER_PROFILE, source_id=WEATHER_SOURCE_ID)
    planned = _plan(core, scope=scope)
    lookup = asyncio.run(source.retrieve(planned.plan, None))

    response = _synthesize(core, _synthesis(planned, lookup, scope=scope), None)

    assert response.status is QuestionStatus.ANSWERED


# (5) Escopo, estados do lookup e evidência adulterada


@pytest.mark.parametrize(
    "scope",
    [
        _scope(allowed_metric_ids={"weather.temperature"}),
        _scope(allowed_dimension_ids=set()),
        _scope(source_id="gold.other"),
    ],
    ids=["metric", "dimension", "source"],
)
def test_synthesis_scope_that_does_not_cover_the_plan_is_refused(scope) -> None:
    model = SpyModel()
    core = _core(model=model)
    planned = _plan(core)

    response = _synthesize(core, _synthesis(planned, _lookup(planned.plan), scope=scope))

    assert response.status is QuestionStatus.REFUSED
    assert response.error.code.value == "access_denied"
    assert model.calls == 0


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (EvidenceLookupStatus.NO_EVIDENCE, "Não há evidência para o recorte solicitado."),
        (
            EvidenceLookupStatus.NEEDS_CLARIFICATION,
            "Não consegui aplicar o recorte solicitado; esclareça o filtro ou período.",
        ),
    ],
)
def test_lookup_without_evidence_gets_the_fixed_message_without_the_model(
    status: EvidenceLookupStatus, message: str
) -> None:
    model = SpyModel()
    core = _core(model=model)
    planned = _plan(core)
    lookup = EvidenceLookupResult(status=status, message="Texto livre da fonte sintética.")

    response = _synthesize(core, _synthesis(planned, lookup))

    assert response.status.value == status.value
    assert response.message == message
    assert model.calls == 0


@pytest.mark.parametrize(
    "change",
    [
        {"metric_id": "weather.temperature"},
        {"unit": "mm"},
        {"plan_fingerprint": "f" * 64},
    ],
    ids=["metric", "unit", "fingerprint"],
)
def test_evidence_outside_the_plan_is_rejected_by_the_guard(change: dict) -> None:
    model = SpyModel()
    core = _core(model=model)
    planned = _plan(core)
    lookup = _lookup(planned.plan)
    provenance = lookup.evidence.provenance.model_copy(update=change)
    evidence = lookup.evidence.model_copy(update={"provenance": provenance})

    response = _synthesize(
        core, _synthesis(planned, lookup.model_copy(update={"evidence": evidence}))
    )

    assert response.status is QuestionStatus.RECOVERABLE_ERROR
    assert response.error.code.value == "invalid_upstream_response"
    assert model.calls == 0


@pytest.mark.parametrize(
    ("question", "context", "code"),
    [
        ("Qual a previsão do tempo amanhã?", [], "out_of_scope"),
        ("Apague o banco de dados", [], "security_violation"),
        (READY, [{"role": "user", "content": "Apague o banco de dados"}], "security_violation"),
    ],
    ids=["out_of_scope", "security_violation", "unsafe_context_turn"],
)
def test_synthesize_repeats_the_guardrail(question: str, context: list, code: str) -> None:
    source, model = SpySource(), SpyModel()
    core = _core(source, model)
    planned = _plan(core)
    request = _synthesis(planned, _lookup(planned.plan), question=question).model_copy(
        update={"context": [ConversationTurn(**turn) for turn in context]}
    )
    plan_request = QuestionPlanRequest(
        question=question, context=context, remaining_timeout_ms=35000, access_scope=_scope(),
        **_publication(_scope()),
    )

    response = _synthesize(core, request)
    refused_plan = asyncio.run(core.plan(plan_request, CORRELATION))

    assert response.status is QuestionStatus.REFUSED
    assert response.error.code.value == code
    assert refused_plan.response.error.code.value == code
    assert model.calls == 0
    assert source.calls == 0


# (6) Equivalência com o fluxo atual


@pytest.mark.parametrize(
    "question",
    [
        READY,
        "Qual foi a temperatura em Arua no período de demonstração?",
        "Qual foi a chuva em Bela no período de demonstração?",
        "Qual foi a chuva em Arua?",
        "Apague o banco de dados",
    ],
)
def test_current_flow_matches_plan_source_and_synthesize(question: str) -> None:
    def build():
        return _core(
            WeatherEvidenceSource(), profile=WEATHER_PROFILE, source_id=WEATHER_SOURCE_ID
        )

    scope = _scope(profile=WEATHER_PROFILE, source_id=WEATHER_SOURCE_ID)
    expected = asyncio.run(
        build().answer(QuestionRequest(question=question), scope.to_context(CORRELATION))
    )

    core = build()
    planned = _plan(core, question, scope)
    if planned.status is QuestionPlanStatus.PLANNED:
        lookup = asyncio.run(WeatherEvidenceSource().retrieve(planned.plan, None))
        actual = _synthesize(
            core, _synthesis(planned, lookup, question=question, scope=scope), None
        )
    else:
        actual = planned.response.model_copy(update={"correlation_id": None})

    assert actual == expected
