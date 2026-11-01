"""Prontidão Gold por capacidade com fatos inventados: nenhum dado de lote real."""

import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

import app.readiness.evaluate as evaluate_module
from app.readiness import (
    CAPABILITY_REQUIREMENTS,
    CapabilityRequirement,
    CapabilityStatus,
    CaseDomain,
    GoldTable,
    LotState,
    PublicationFacts,
    ReadinessReport,
    ReasonCode,
    TableFacts,
    evaluate_readiness,
)
from app.readiness.requirements import DOCUMENTED_CONTROLS, TABLES_WITH_COMPETENCIA
from app.schemas.evidence import GoldBatchRef

DICTIONARY = Path(__file__).resolve().parents[2] / "docs" / "dicionario_gold.md"

REF_A = "gold-csv-v1:GOLD_20000101T000000Z_0000000a:00000000-0000-4000-8000-00000000000a"
REF_B = "gold-csv-v1:GOLD_20000102T000000Z_0000000b:00000000-0000-4000-8000-00000000000b"
PERIODS = ("2001-01", "2001-02", "2001-03")

AVAILABLE_WHEN_READY = {
    "faturamento.receita",
    "faturamento.receita_bairro",
    "consumo.mensal_uc",
    "interrupcoes.dec_fec",
}
DEFINITION_PENDING = {
    "faturamento.preco_volume",
    "consumo.variacao_uc",
    "interrupcoes.uc_acumulado",
    "atendimento.uc_acumulado",
    "apoio.fila_inspecao",
}
NOT_IN_GOLD = {"faturamento.faturas_em_aberto", "apoio.medidor_uc", "apoio.energia_recuperavel"}


def _table(*, ref: str | None = REF_A, periods: tuple[str, ...] = PERIODS) -> dict:
    return {"present": True, "has_rows": True, "batch_ref": ref, "periods": periods}


def _facts(**overrides) -> dict:
    tables = {
        table.value: _table(periods=PERIODS if table in TABLES_WITH_COMPETENCIA else ())
        for table in GoldTable
    }
    data = {
        "batch_ref": REF_A,
        "expected_batch_ref": REF_A,
        "tables": tables,
        "approved_controls": sorted(DOCUMENTED_CONTROLS),
        "backend_reachable": True,
    }
    data.update(overrides)
    return data


def _evaluate(data: dict) -> ReadinessReport:
    return evaluate_readiness(PublicationFacts.model_validate(data))


def _reasons(report: ReadinessReport, capability_id: str) -> tuple[ReasonCode, ...]:
    return report.capabilities[capability_id].reasons


def _available(report: ReadinessReport) -> set[str]:
    return {
        capability_id
        for capability_id, readiness in report.capabilities.items()
        if readiness.status is CapabilityStatus.AVAILABLE
    }


def test_ready_lot_releases_only_capabilities_with_approved_definition_and_controls() -> None:
    report = _evaluate(_facts())

    assert report.lot_state is LotState.READY
    assert report.batch_ref == REF_A
    assert report.readiness_version == "gold-readiness-v1"
    assert _available(report) == AVAILABLE_WHEN_READY
    for capability_id in DEFINITION_PENDING:
        assert _reasons(report, capability_id) == (ReasonCode.DEFINITION_PENDING,)
    for capability_id in NOT_IN_GOLD:
        assert _reasons(report, capability_id) == (ReasonCode.SOURCE_NOT_IN_GOLD,)
    assert set(report.capabilities) == {req.id for req in CAPABILITY_REQUIREMENTS}


@pytest.mark.parametrize("reference", [REF_A, REF_B])
def test_publication_reference_round_trips_through_readiness(reference: str) -> None:
    validated = TypeAdapter(GoldBatchRef).validate_python(reference)
    data = _facts(batch_ref=validated, expected_batch_ref=validated)
    for table in data["tables"].values():
        table["batch_ref"] = validated

    report = _evaluate(data)

    assert report.lot_state is LotState.READY
    assert report.batch_ref == validated
    assert ReadinessReport.model_validate_json(report.model_dump_json()) == report


@pytest.mark.parametrize("field", ["batch_ref", "expected_batch_ref", "table", "report"])
@pytest.mark.parametrize(
    "reference",
    [
        "SINTETICO_DEV",
        "LOTE_DEV",
        REF_A.replace("-4000-", "-1000-"),
        f" {REF_A}",
        f"{REF_A} ",
        123,
    ],
)
def test_invalid_reference_is_rejected_at_every_readiness_boundary(field, reference) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(GoldBatchRef).validate_python(reference)

    data = _facts()
    if field == "report":
        report = _evaluate(data).model_dump(mode="json")
        report["batch_ref"] = reference
        with pytest.raises(ValidationError):
            ReadinessReport.model_validate(report)
        return
    if field == "table":
        data["tables"]["visao_360_uc"]["batch_ref"] = reference
    else:
        data[field] = reference
    with pytest.raises(ValidationError):
        PublicationFacts.model_validate(data)


def test_unreachable_backend_takes_precedence_and_never_reads_as_empty() -> None:
    data = _facts(backend_reachable=False, expected_batch_ref=REF_B, tables={})

    report = _evaluate(data)

    assert report.lot_state is LotState.UNAVAILABLE
    for capability_id, readiness in report.capabilities.items():
        assert readiness.status is CapabilityStatus.UNAVAILABLE
        assert ReasonCode.BACKEND_UNAVAILABLE in readiness.reasons
        assert ReasonCode.TABLE_EMPTY not in readiness.reasons
        assert (ReasonCode.SOURCE_NOT_IN_GOLD in readiness.reasons) == (
            capability_id in NOT_IN_GOLD
        )


def test_stale_publication_takes_precedence_over_mixed_tables() -> None:
    data = _facts(expected_batch_ref=REF_B)
    data["tables"]["fila_inspecao"]["batch_ref"] = REF_B

    report = _evaluate(data)

    assert report.lot_state is LotState.STALE
    assert all(
        ReasonCode.PUBLICATION_STALE in readiness.reasons
        for readiness in report.capabilities.values()
    )
    assert _available(report) == set()


def _assert_unidentified(report: ReadinessReport) -> None:
    assert report.lot_state is LotState.INVALID
    for capability_id, readiness in report.capabilities.items():
        assert readiness.status is CapabilityStatus.UNAVAILABLE
        assert ReasonCode.PUBLICATION_UNIDENTIFIED in readiness.reasons
        assert ReasonCode.PUBLICATION_MIXED not in readiness.reasons
        assert (ReasonCode.SOURCE_NOT_IN_GOLD in readiness.reasons) == (
            capability_id in NOT_IN_GOLD
        )


@pytest.mark.parametrize("expected", [REF_A, None])
def test_lot_without_current_batch_ref_is_invalid(expected: str | None) -> None:
    _assert_unidentified(_evaluate(_facts(batch_ref=None, expected_batch_ref=expected)))


def test_present_table_without_batch_ref_is_invalid_not_mixed() -> None:
    data = _facts()
    data["tables"]["visao_360_uc"]["batch_ref"] = None

    _assert_unidentified(_evaluate(data))


def test_legacy_publication_without_any_batch_ref_is_invalid_never_ready() -> None:
    tables = {
        table.value: _table(ref=None, periods=PERIODS if table in TABLES_WITH_COMPETENCIA else ())
        for table in GoldTable
    }

    _assert_unidentified(
        _evaluate(_facts(batch_ref=None, expected_batch_ref=None, tables=tables))
    )


def test_absent_table_without_batch_ref_does_not_make_the_lot_invalid() -> None:
    data = _facts()
    data["tables"]["visao_360_uc"] = {"present": False, "has_rows": False}

    assert _evaluate(data).lot_state is LotState.PARTIAL


def test_tables_with_different_batch_refs_are_mixed() -> None:
    data = _facts()
    data["tables"]["visao_360_uc"]["batch_ref"] = REF_B

    report = _evaluate(data)

    assert report.lot_state is LotState.MIXED
    assert all(
        ReasonCode.PUBLICATION_MIXED in readiness.reasons
        and ReasonCode.PUBLICATION_UNIDENTIFIED not in readiness.reasons
        for readiness in report.capabilities.values()
    )


def test_full_lot_state_precedence() -> None:
    """Remove uma condição por vez: cada estado só aparece sem os anteriores."""
    data = _facts(backend_reachable=False, expected_batch_ref=REF_B)
    data["tables"]["visao_360_uc"]["batch_ref"] = None
    data["tables"]["fila_inspecao"]["batch_ref"] = REF_B
    data["tables"]["consumo_mensal_uc"] = {"present": False, "has_rows": False}
    observed = [_evaluate(data).lot_state]

    data["backend_reachable"] = True
    observed.append(_evaluate(data).lot_state)
    data["tables"]["visao_360_uc"]["batch_ref"] = REF_A
    observed.append(_evaluate(data).lot_state)
    data["expected_batch_ref"] = REF_A
    observed.append(_evaluate(data).lot_state)
    data["tables"]["fila_inspecao"]["batch_ref"] = REF_A
    observed.append(_evaluate(data).lot_state)
    data["tables"]["consumo_mensal_uc"] = _table()
    observed.append(_evaluate(data).lot_state)
    empty = _facts(
        tables={
            table.value: {"present": True, "has_rows": False, "batch_ref": REF_A}
            for table in GoldTable
        }
    )

    assert observed == [
        LotState.UNAVAILABLE,
        LotState.INVALID,
        LotState.STALE,
        LotState.MIXED,
        LotState.PARTIAL,
        LotState.READY,
    ]
    assert _evaluate(empty).lot_state is LotState.EMPTY
    empty["tables"]["visao_360_uc"]["batch_ref"] = REF_B
    assert _evaluate(empty).lot_state is LotState.MIXED
    empty["tables"]["visao_360_uc"]["batch_ref"] = None
    assert _evaluate(empty).lot_state is LotState.INVALID


def test_lot_without_rows_is_empty_and_every_table_is_empty_not_zero() -> None:
    tables = {
        table.value: {"present": True, "has_rows": False, "batch_ref": REF_A}
        for table in GoldTable
    }

    report = _evaluate(_facts(tables=tables))

    assert report.lot_state is LotState.EMPTY
    for capability_id, readiness in report.capabilities.items():
        assert readiness.status is CapabilityStatus.UNAVAILABLE
        if capability_id not in NOT_IN_GOLD:
            assert ReasonCode.TABLE_EMPTY in readiness.reasons


def test_missing_table_blocks_only_dependent_capabilities() -> None:
    ready = _evaluate(_facts())
    data = _facts()
    del data["tables"]["consumo_mensal_uc"]

    report = _evaluate(data)

    assert report.lot_state is LotState.PARTIAL
    assert _reasons(report, "consumo.mensal_uc") == (ReasonCode.TABLE_MISSING,)
    del report.capabilities["consumo.mensal_uc"], ready.capabilities["consumo.mensal_uc"]
    assert report.capabilities == ready.capabilities


def test_empty_table_differs_from_missing_table() -> None:
    data = _facts()
    data["tables"]["indicadores_dec_fec"] = {"present": True, "has_rows": False, "batch_ref": REF_A}
    data["tables"]["visao_360_uc"] = {"present": False, "has_rows": False}

    report = _evaluate(data)

    assert report.lot_state is LotState.PARTIAL
    assert _reasons(report, "interrupcoes.dec_fec") == (ReasonCode.TABLE_EMPTY,)
    assert _reasons(report, "atendimento.uc_acumulado") == (
        ReasonCode.TABLE_MISSING,
        ReasonCode.DEFINITION_PENDING,
    )
    assert _reasons(report, "faturamento.receita") == ()


def test_non_consecutive_periods_are_insufficient() -> None:
    data = _facts()
    data["tables"]["diagnostico_receita"]["periods"] = ("2001-01", "2001-03")

    report = _evaluate(data)

    assert report.lot_state is LotState.READY
    assert _reasons(report, "faturamento.receita") == (ReasonCode.PERIOD_INSUFFICIENT,)
    assert ReasonCode.PERIOD_INSUFFICIENT in _reasons(report, "faturamento.preco_volume")
    assert _reasons(report, "faturamento.receita_bairro") == ()


def test_periods_crossing_a_year_are_consecutive_regardless_of_order() -> None:
    data = _facts()
    data["tables"]["consumo_mensal_uc"]["periods"] = ("2002-01", "2001-12", "2001-11")

    assert _reasons(_evaluate(data), "consumo.mensal_uc") == ()


def test_table_with_rows_but_no_competencia_has_period_missing() -> None:
    data = _facts()
    data["tables"]["indicadores_dec_fec"]["periods"] = ()

    assert _reasons(_evaluate(data), "interrupcoes.dec_fec") == (ReasonCode.PERIOD_MISSING,)


def test_minimum_consecutive_months_is_enforced_when_declared(monkeypatch) -> None:
    requirement = CapabilityRequirement(
        id="consumo.janela_minima",
        domain=CaseDomain.CONSUMO,
        tables=(GoldTable.CONSUMO_MENSAL_UC,),
        temporal_column="competencia",
        min_consecutive_months=4,
        definition_approved=True,
    )
    monkeypatch.setattr(evaluate_module, "CAPABILITY_REQUIREMENTS", (requirement,))

    short = _evaluate(_facts())
    data = _facts()
    data["tables"]["consumo_mensal_uc"]["periods"] = (*PERIODS, "2001-04")
    enough = _evaluate(data)

    assert _reasons(short, "consumo.janela_minima") == (ReasonCode.PERIOD_INSUFFICIENT,)
    assert _reasons(enough, "consumo.janela_minima") == ()


def test_pending_control_blocks_only_capabilities_that_require_it() -> None:
    controls = sorted(DOCUMENTED_CONTROLS - {"C11"})

    report = _evaluate(_facts(approved_controls=controls))

    assert _reasons(report, "interrupcoes.dec_fec") == (ReasonCode.CONTROL_PENDING,)
    assert _available(report) == AVAILABLE_WHEN_READY - {"interrupcoes.dec_fec"}


def test_without_approved_controls_no_gold_capability_with_controls_is_released() -> None:
    report = _evaluate(_facts(approved_controls=[]))

    for requirement in CAPABILITY_REQUIREMENTS:
        if requirement.required_controls:
            assert ReasonCode.CONTROL_PENDING in _reasons(report, requirement.id)


def test_definition_pending_capabilities_are_declared() -> None:
    pending = {
        req.id
        for req in CAPABILITY_REQUIREMENTS
        if not req.definition_approved and not req.source_not_in_gold
    }

    assert pending == DEFINITION_PENDING


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"backend_reachable": False},
        {"batch_ref": None},
        {"expected_batch_ref": REF_B},
        {"tables": {}},
        {"approved_controls": []},
    ],
)
def test_capabilities_outside_gold_are_always_unavailable(overrides: dict) -> None:
    report = _evaluate(_facts(**overrides))

    for capability_id in NOT_IN_GOLD:
        readiness = report.capabilities[capability_id]
        assert readiness.status is CapabilityStatus.UNAVAILABLE
        assert ReasonCode.SOURCE_NOT_IN_GOLD in readiness.reasons


def test_capabilities_outside_gold_declare_no_table_period_or_control() -> None:
    outside = [req for req in CAPABILITY_REQUIREMENTS if req.source_not_in_gold]

    assert {req.id for req in outside} == NOT_IN_GOLD
    assert all(not req.tables and req.temporal_column is None for req in outside)
    assert all(not req.required_controls for req in outside)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.update(row_count=1),
        lambda data: data.update(readiness_version="gold-readiness-v2"),
        lambda data: data["tables"].update(tabela_inventada=_table()),
        lambda data: data["tables"]["consumo_mensal_uc"].update(row_count=1),
        lambda data: data.update(approved_controls=["controle"]),
        lambda data: data.update(batch_ref="lote-qualquer"),
    ],
)
def test_unknown_field_version_table_or_reference_is_rejected(mutate) -> None:
    data = _facts()
    mutate(data)

    with pytest.raises(ValidationError):
        PublicationFacts.model_validate(data)


@pytest.mark.parametrize(
    "periods",
    [
        ("2001-13",),
        ("2001-00",),
        ("2001-1",),
        ("200101",),
        ("2001-01-01",),
        ("01/2001",),
        ("2001-01", "2001-01"),
    ],
)
def test_invalid_or_duplicated_competencia_is_rejected_not_corrected(periods) -> None:
    data = _facts()
    data["tables"]["consumo_mensal_uc"]["periods"] = periods

    with pytest.raises(ValidationError):
        PublicationFacts.model_validate(data)


@pytest.mark.parametrize(
    "table",
    [
        {"present": False, "has_rows": True},
        {"present": False, "has_rows": False, "batch_ref": REF_A},
        {"present": True, "has_rows": False, "batch_ref": REF_A, "periods": PERIODS},
    ],
)
def test_contradictory_table_facts_are_rejected(table: dict) -> None:
    data = _facts()
    data["tables"]["consumo_mensal_uc"] = table

    with pytest.raises(ValidationError):
        PublicationFacts.model_validate(data)


def _scalars(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _scalars(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _scalars(item)
    else:
        yield value


@pytest.mark.parametrize(
    "overrides",
    [{}, {"backend_reachable": False}, {"expected_batch_ref": REF_B}, {"approved_controls": []}],
)
def test_report_carries_only_codes_and_states_never_numbers_or_periods(overrides: dict) -> None:
    dumped = _evaluate(_facts(**overrides)).model_dump(mode="json")
    version = dumped.pop("readiness_version")
    batch_ref = dumped.pop("batch_ref")

    assert version == "gold-readiness-v1"
    assert batch_ref == REF_A
    for scalar in _scalars(dumped):
        assert isinstance(scalar, str)
        assert not re.search(r"[0-9]", scalar)


def test_same_facts_produce_the_same_report() -> None:
    data = _facts()
    reordered = _facts(tables=dict(reversed(list(data["tables"].items()))))
    reordered["tables"]["diagnostico_receita"]["periods"] = tuple(reversed(PERIODS))
    reordered["approved_controls"] = list(reversed(data["approved_controls"]))

    first = _evaluate(data)

    assert _evaluate(data) == first
    assert _evaluate(reordered).model_dump_json() == first.model_dump_json()


def test_every_capability_points_to_official_gold_tables() -> None:
    text = DICTIONARY.read_text(encoding="utf-8").split("## 1.", 1)[0]
    official = set(re.findall(r"^\| `([a-z0-9_]+)` \|", text, flags=re.MULTILINE))

    official.discard("controle_gold")
    assert len(official) == 15
    assert {table.value for table in GoldTable} == official
    for requirement in CAPABILITY_REQUIREMENTS:
        assert {table.value for table in requirement.tables} <= official


def test_requirements_are_unique_and_reference_documented_controls() -> None:
    ids = [req.id for req in CAPABILITY_REQUIREMENTS]

    assert len(ids) == len(set(ids))
    assert {req.domain for req in CAPABILITY_REQUIREMENTS} == set(CaseDomain)
    for requirement in CAPABILITY_REQUIREMENTS:
        assert set(requirement.required_controls) <= DOCUMENTED_CONTROLS


@pytest.mark.parametrize(
    "declaration",
    [
        {"source_not_in_gold": True, "tables": ["consumo_mensal_uc"]},
        {"tables": []},
        {"tables": ["visao_360_uc"], "temporal_column": "competencia"},
        {"tables": ["visao_360_uc"], "min_consecutive_months": 3},
        {"tables": ["consumo_mensal_uc"], "required_controls": ["C99"]},
        {"tables": ["consumo_mensal_uc"], "coluna_extra": "x"},
    ],
)
def test_invalid_requirement_declaration_is_rejected(declaration: dict) -> None:
    with pytest.raises(ValidationError):
        CapabilityRequirement.model_validate(
            {"id": "consumo.teste", "domain": "consumo", "definition_approved": True, **declaration}
        )


def test_models_are_immutable() -> None:
    facts = PublicationFacts.model_validate(_facts())
    table = TableFacts(present=True, has_rows=False)

    with pytest.raises(ValidationError):
        facts.backend_reachable = False
    with pytest.raises(ValidationError):
        table.has_rows = True


V2_REF = REF_A.replace("gold-csv-v1:", "gold-csv-v2:")


def _v2_facts():
    data = _facts()
    data.update(readiness_version="gold-readiness-v2", batch_ref=V2_REF,
                expected_batch_ref=V2_REF, approved_controls=[],
                control_results={"C14": {"status": "passed", "approved": True,
                                         "batch_ref": V2_REF},
                                 "C15": {"status": "passed", "approved": True,
                                         "batch_ref": V2_REF}})
    for table in data["tables"].values():
        table["batch_ref"] = V2_REF
    data["tables"]["atendimentos_uc"] = _table(ref=V2_REF, periods=())
    data["tables"]["cobertura_dominios"] = _table(ref=V2_REF, periods=PERIODS)
    data["coverage"] = {"atendimento.mensal": {
        "batch_ref": V2_REF, "requested_periods": ["2001-01"],
        "observed_periods": ["2001-01"], "closed_periods": ["2001-01"],
        "has_undated_records": False,
    }}
    return data


def test_v2_attendance_uses_current_controls_and_preserves_version():
    report = _evaluate(_v2_facts())
    assert report.readiness_version == "gold-readiness-v2"
    assert report.capabilities["atendimento.uc_acumulado"].status is CapabilityStatus.AVAILABLE
    assert report.capabilities["atendimento.mensal"].status is CapabilityStatus.AVAILABLE
    assert ReasonCode.SOURCE_NOT_IN_GOLD not in _reasons(report, "apoio.medidor_uc")
    assert ReasonCode.SOURCE_NOT_IN_GOLD not in _reasons(report, "faturamento.faturas_em_aberto")


@pytest.mark.parametrize("status", ["failed", "pending", "unavailable"])
def test_v2_failed_monthly_control_blocks_only_monthly_attendance(status):
    data = _v2_facts()
    data["control_results"]["C15"]["status"] = status
    report = _evaluate(data)
    assert report.capabilities["atendimento.mensal"].status is CapabilityStatus.UNAVAILABLE
    assert report.capabilities["atendimento.uc_acumulado"].status is CapabilityStatus.AVAILABLE


def test_v2_partial_coverage_is_not_released_by_passing_controls():
    data = _v2_facts()
    data["coverage"]["atendimento.mensal"]["closed_periods"] = []
    report = _evaluate(data)
    assert report.capabilities["atendimento.mensal"].status is CapabilityStatus.UNAVAILABLE
    assert report.capabilities["atendimento.uc_acumulado"].status is CapabilityStatus.AVAILABLE


@pytest.mark.parametrize("case", ["missing", "unapproved", "old_publication"])
def test_v2_control_evidence_must_be_approved_for_current_publication(case):
    data = _v2_facts()
    if case == "missing":
        del data["control_results"]["C14"]
    elif case == "unapproved":
        data["control_results"]["C14"]["approved"] = False
    else:
        data["control_results"]["C14"]["batch_ref"] = REF_B
    report = _evaluate(data)
    assert report.capabilities["atendimento.uc_acumulado"].status is CapabilityStatus.UNAVAILABLE
    assert report.capabilities["atendimento.mensal"].status is CapabilityStatus.UNAVAILABLE


@pytest.mark.parametrize("case", ["missing", "old_publication", "undated", "missing_observation"])
def test_v2_coverage_evidence_is_bound_to_publication_and_requested_period(case):
    data = _v2_facts()
    if case == "missing":
        data["coverage"] = {}
    elif case == "old_publication":
        data["coverage"]["atendimento.mensal"]["batch_ref"] = REF_B
    elif case == "undated":
        data["coverage"]["atendimento.mensal"]["has_undated_records"] = True
    else:
        data["coverage"]["atendimento.mensal"]["observed_periods"] = []
    report = _evaluate(data)
    assert report.capabilities["atendimento.mensal"].status is CapabilityStatus.UNAVAILABLE
    assert report.capabilities["atendimento.uc_acumulado"].status is CapabilityStatus.AVAILABLE


def test_v2_confirmed_zero_is_distinct_from_empty_unobserved_table():
    data = _v2_facts()
    data["tables"]["atendimentos_uc"] = {"present": True, "has_rows": False,
                                         "batch_ref": V2_REF}
    coverage = data["coverage"]["atendimento.mensal"]
    coverage.update(observed_periods=[], zero_confirmed_periods=["2001-01"])
    report = _evaluate(data)
    assert report.capabilities["atendimento.mensal"].status is CapabilityStatus.AVAILABLE
    assert report.capabilities["atendimento.uc_acumulado"].status is CapabilityStatus.UNAVAILABLE
    coverage["zero_confirmed_periods"] = []
    assert _evaluate(data).capabilities["atendimento.mensal"].status is CapabilityStatus.UNAVAILABLE


def test_v2_confirmed_zero_does_not_replace_missing_coverage_table():
    data = _v2_facts()
    data["coverage"]["atendimento.mensal"].update(
        observed_periods=[], zero_confirmed_periods=["2001-01"])
    data["tables"]["cobertura_dominios"] = {"present": True, "has_rows": False,
                                           "batch_ref": V2_REF}
    report = _evaluate(data)
    assert ReasonCode.TABLE_EMPTY in _reasons(report, "atendimento.mensal")


def test_v2_new_sources_are_not_falsely_absent_or_automatically_approved():
    report = _evaluate(_v2_facts())
    for capability in ("faturamento.faturas_em_aberto", "apoio.medidor_uc",
                       "apoio.energia_recuperavel"):
        assert ReasonCode.SOURCE_NOT_IN_GOLD not in _reasons(report, capability)
        assert ReasonCode.DEFINITION_PENDING in _reasons(report, capability)
        assert report.capabilities[capability].status is CapabilityStatus.UNAVAILABLE
    for capability in (
        "faturamento.preco_volume", "interrupcoes.uc_acumulado", "consumo.variacao_uc",
    ):
        assert ReasonCode.DEFINITION_PENDING not in _reasons(report, capability)
        assert ReasonCode.CONTROL_PENDING in _reasons(report, capability)
        assert report.capabilities[capability].status is CapabilityStatus.UNAVAILABLE


@pytest.mark.parametrize("case", ["legacy_controls", "legacy_version", "contradictory_zero",
                                  "duplicate_month", "bad_year", "string_boolean"])
def test_v2_incompatible_or_contradictory_facts_are_rejected(case):
    data = _v2_facts()
    if case == "legacy_controls":
        data["approved_controls"] = ["C14", "C15"]
    elif case == "legacy_version":
        data["readiness_version"] = "gold-readiness-v1"
    elif case == "contradictory_zero":
        data["coverage"]["atendimento.mensal"]["zero_confirmed_periods"] = ["2001-01"]
    elif case == "duplicate_month":
        data["coverage"]["atendimento.mensal"]["requested_periods"] = ["2001-01", "2001-01"]
    elif case == "bad_year":
        data["coverage"]["atendimento.mensal"]["requested_periods"] = ["0000-01"]
    else:
        data["control_results"]["C14"]["approved"] = "false"
    with pytest.raises(ValidationError):
        PublicationFacts.model_validate(data)


@pytest.mark.parametrize("case", ["mixed", "stale", "unidentified", "unavailable"])
def test_v2_invalid_publication_cannot_release_any_capability(case):
    data = _v2_facts()
    if case == "mixed":
        data["tables"]["atendimentos_uc"]["batch_ref"] = REF_B
    elif case == "stale":
        data["expected_batch_ref"] = REF_B
    elif case == "unidentified":
        data["batch_ref"] = None
    else:
        data["backend_reachable"] = False
    assert _available(_evaluate(data)) == set()


def test_v2_old_failed_controls_do_not_leak_counts_or_periods_in_report():
    data = _v2_facts()
    data["control_results"]["C15"]["status"] = "failed"
    report = _evaluate(data).model_dump(mode="json")
    assert report.pop("readiness_version") == "gold-readiness-v2"
    assert report.pop("batch_ref") == V2_REF
    assert all(isinstance(value, str) and not re.search(r"[0-9]", value)
               for value in _scalars(report))



def test_v2_undated_record_observation_cannot_be_omitted():
    data = _v2_facts()
    del data["coverage"]["atendimento.mensal"]["has_undated_records"]
    with pytest.raises(ValidationError):
        PublicationFacts.model_validate(data)


def test_v2_monthly_attendance_requires_month_present_in_coverage_table():
    data = _v2_facts()
    coverage = data["coverage"]["atendimento.mensal"]
    for field in ("requested_periods", "observed_periods", "closed_periods"):
        coverage[field] = ["2002-01"]
    report = _evaluate(data)
    assert report.capabilities["atendimento.mensal"].status is CapabilityStatus.UNAVAILABLE
    assert ReasonCode.PERIOD_MISSING in _reasons(report, "atendimento.mensal")


def test_v2_incomplete_inventory_is_partial_without_blocking_independent_attendance():
    data = _v2_facts()
    del data["tables"]["gd_uc"], data["tables"]["tratativas_uc"]
    report = _evaluate(data)
    assert report.lot_state is LotState.PARTIAL
    assert report.capabilities["atendimento.mensal"].status is CapabilityStatus.AVAILABLE
