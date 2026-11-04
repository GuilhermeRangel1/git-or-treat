from datetime import date

import pytest

from app.schemas.ai import AIQuestionResponse
from app.schemas.genai_audit import BackendAuditEvent
from app.schemas.genai_plan import LogicalReadPlan
from app.schemas.gold_readiness import CapabilityReadiness, GoldReadinessReport
from app.services.genai_coordination import (
    OBSERVED_CONTINUITY_WARNING,
    _apply_observed_continuity_warning,
    _observed_continuity_quality,
)

BATCH = (
    "gold-csv-v2:GOLD_20260601T000000Z_12345678:"
    "12345678-1234-4234-8234-123456789012"
)


def _plan(metric="network.equivalent_interruption_duration"):
    return LogicalReadPlan.model_validate({
        "catalog_version": "v1", "operation": "read",
        "profile_id": "v-energy-grid-360-gold", "source_id": "gold.local",
        "domain_id": "continuity", "metric_id": metric, "unit": "horas por UC",
        "window": {"kind": "bounded", "start": date(2026, 6, 1),
                   "end": date(2026, 6, 30), "granularity": "month"},
        "dimension_ids": ["network.feeder"],
        "filters": [{"dimension_id": "network.feeder", "operator": "eq", "values": ["AL-01"]}],
        "limit": 10,
    })


def _report(reason="coverage_incomplete"):
    return GoldReadinessReport(
        readiness_version="gold-readiness-v2", batch_ref=BATCH, lot_state="partial",
        capabilities={"interrupcoes.dec_fec": CapabilityReadiness(
            status="unavailable", reasons=(reason,),
        )},
    )


def test_only_dec_fec_with_exclusively_uncertified_coverage_enters_observed_mode():
    quality = _observed_continuity_quality(_report(), _plan(), BATCH)

    assert quality is not None
    assert quality.quality_mode == "observed_uncertified"
    assert quality.available_capability_ids == ()
    assert quality.observed_capability_ids == ("interrupcoes.dec_fec",)
    assert quality.observed_periods == ("2026-06",)


def test_nonadjacent_comparison_requires_only_the_two_requested_months():
    from app.services.genai_executor import (
        GoldExecutionDenied,
        _validate_observed_continuity_rows,
    )

    data = _plan().model_dump(mode="python")
    data["window"]["start"] = date(2026, 1, 1)
    data["comparison_periods"] = ("2026-01", "2026-06")
    plan = LogicalReadPlan.model_validate(data)
    quality = _observed_continuity_quality(_report(), plan, BATCH)
    assert quality.observed_periods == ("2026-01", "2026-06")
    rows = [{"period": month, "feeder": "AL-01", "value": value}
            for month, value in [("2026-01", 0.25), ("2026-06", 0.5)]]
    _validate_observed_continuity_rows(rows, plan, quality)
    with pytest.raises(GoldExecutionDenied):
        _validate_observed_continuity_rows(rows[:1], plan, quality)


@pytest.mark.parametrize("reason", ["control_failed", "table_empty", "coverage_missing"])
def test_other_readiness_failures_remain_blocked(reason):
    assert _observed_continuity_quality(_report(reason), _plan(), BATCH) is None


def test_other_metrics_and_multi_feeder_queries_remain_blocked():
    assert _observed_continuity_quality(
        _report(), _plan("billing.revenue"), BATCH,
    ) is None
    data = _plan().model_dump(mode="python")
    data["filters"] = [{
        "dimension_id": "network.feeder", "operator": "in", "values": ["AL-01", "AL-02"],
    }]
    multi_feeder = LogicalReadPlan.model_validate(data)
    assert _observed_continuity_quality(_report(), multi_feeder, BATCH) is None


def test_public_answer_always_receives_deterministic_observed_warning():
    from app.schemas.genai_evidence import GoldEvidenceQuality

    quality = GoldEvidenceQuality(
        readiness_version="gold-readiness-v2", batch_ref=BATCH, lot_state="partial",
        quality_mode="observed_uncertified", available_capability_ids=(),
        observed_capability_ids=("interrupcoes.dec_fec",), observed_periods=("2026-06",),
    )
    response = AIQuestionResponse(
        status="answered", answer="O DEC observado foi 0,12 horas por UC.",
        evidence=[{"source": "gold.local", "description": "Evidência Gold v2", "is_demo": False}],
    )

    published = _apply_observed_continuity_warning(response, quality)

    assert OBSERVED_CONTINUITY_WARNING in published.answer
    assert OBSERVED_CONTINUITY_WARNING in published.limitations


def test_audit_records_observed_mode_scope_and_limitation_without_values():
    event = BackendAuditEvent(
        correlation_id="a" * 32,
        stage="response",
        code="completed",
        outcome="success",
        duration_ms=12,
        batch_ref=BATCH,
        quality_mode="observed_uncertified",
        observed_capability_ids=("interrupcoes.dec_fec",),
        observed_periods=("2026-06",),
        quality_limitation=OBSERVED_CONTINUITY_WARNING,
    )

    payload = event.model_dump(mode="json")

    assert payload["quality_mode"] == "observed_uncertified"
    assert payload["observed_periods"] == ["2026-06"]
    assert payload["quality_limitation"] == OBSERVED_CONTINUITY_WARNING
    assert "value" not in payload


@pytest.mark.parametrize(("state", "allowed"), [
    ("NAO_CERTIFICADA", True),
    ("PARCIAL", False),
    ("AUSENTE", False),
])
def test_observed_mode_requires_explicit_uncertified_coverage_and_matching_lineage(
    state, allowed,
):
    from app.services.genai_continuity_coverage import coverage_rows_valid

    origin = {"run_id_silver": "run-test", "lote_bronze_silver": "lot-test"}
    row = {
        "competencia": "2026-06",
        "estado_cobertura": state,
        "natureza_certificacao": (
            "NAO_CERTIFICADA" if state == "NAO_CERTIFICADA" else "EXTRACAO"
        ),
        "motivo": (
            "SEM_EVIDENCIA_DE_COBERTURA"
            if state == "NAO_CERTIFICADA" else f"{state}_DECLARADO"
        ),
        "data_corte_evidencia": None,
        "referencia_evidencia": None,
        "reconciliacao_extracao_json": None,
        "qtd_sem_competencia": 0,
        "qtd_registros": 3,
        "zero_registros_confirmado": False,
        **origin,
    }

    assert coverage_rows_valid([row], ("2026-06",), origin) is allowed
    assert not coverage_rows_valid(
        [row], ("2026-06",), {**origin, "run_id_silver": "different-run"}
    )
    assert not coverage_rows_valid([], ("2026-06",), origin)


def test_observed_coverage_reads_only_the_requested_feeder_and_month(monkeypatch):
    from sqlalchemy import create_engine

    from app.models.gold_v2 import TABLES
    from app.services import genai_continuity_coverage as coverage

    origin = {"run_id_silver": "run-test", "lote_bronze_silver": "lot-test"}
    monkeypatch.setattr(coverage, "publication_lineage", lambda connection, batch: origin)
    engine = create_engine(
        "sqlite://",
        execution_options={"schema_translate_map": {"gold_v2": None}},
    )
    table = TABLES["cobertura_dominios"]
    quality = _observed_continuity_quality(_report(), _plan(), BATCH)
    rows = [
        {"dominio": "ocorrencias", "competencia": "2026-06",
         "recorte": "ALIMENTADOR:AL-01", "estado_cobertura": "NAO_CERTIFICADA",
         "natureza_certificacao": "NAO_CERTIFICADA",
         "motivo": "SEM_EVIDENCIA_DE_COBERTURA", "qtd_registros": 3,
         "qtd_sem_competencia": 0, "zero_registros_confirmado": False, **origin},
        {"dominio": "ocorrencias", "competencia": "2026-06",
         "recorte": "ALIMENTADOR:OTHER", "estado_cobertura": "PARCIAL",
         "natureza_certificacao": "EXTRACAO", "motivo": "PARCIAL_DECLARADO",
         "qtd_registros": 3, "qtd_sem_competencia": 0,
         "zero_registros_confirmado": False, **origin},
    ]
    with engine.begin() as connection:
        table.create(connection)
        connection.execute(table.insert(), rows)
        assert coverage.observed_coverage_valid(connection, _plan(), quality)
        connection.execute(table.update().where(
            table.c.recorte == "ALIMENTADOR:AL-01"
        ).values(estado_cobertura="PARCIAL"))
        assert not coverage.observed_coverage_valid(connection, _plan(), quality)
    engine.dispose()


@pytest.mark.parametrize("eligible", [True, False])
def test_observed_coverage_runs_on_readiness_connection(monkeypatch, eligible):
    import asyncio
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from app.services import genai_coordination as coordination
    from app.services.genai_deadline import GenAIRequestDeadline

    readiness_engine, readiness_connection = object(), Mock()

    @contextmanager
    def snapshot(engine):
        assert engine is readiness_engine
        yield readiness_connection

    planned = SimpleNamespace(
        response=SimpleNamespace(plan=_plan(), correlation_id="a" * 32),
        publication=SimpleNamespace(batch_ref=BATCH, execution_snapshot=snapshot),
        deadline=GenAIRequestDeadline.start(10),
    )
    report = _report()
    client = SimpleNamespace(evaluate_readiness=AsyncMock(return_value=report))
    read_coverage = Mock(return_value=eligible)
    monkeypatch.setattr(coordination, "observed_coverage_valid", read_coverage)
    gate = coordination.build_readiness_gate(readiness_engine, client, {"C11"})
    if eligible:
        assert asyncio.run(gate(planned)) == report
    else:
        with pytest.raises(coordination.GoldCoverageUnavailable):
            asyncio.run(gate(planned))
    assert read_coverage.call_args.args[0] is readiness_connection
    assert read_coverage.call_args.args[2].batch_ref == BATCH
    readiness_connection.exec_driver_sql.assert_called_once()
