"""Observa controles no snapshot Gold v2; retorna somente fatos técnicos.

Sem escrita, cadastro pessoal ou chamadas ao modelo. A aprovação de cada controle
é explícita e independente de seu resultado; cobertura não é certificada por inferência.
"""
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from math import isfinite
from time import monotonic

from sqlalchemy import Table, select
from sqlalchemy.engine import Engine

from app.models.gold_v2_load import TABLES
from app.repositories.gold_publication import (
    GoldPublicationChanged,
    GoldPublicationInvalid,
    current_publication,
    publication_lineage,
)
from app.services.genai_client import GenAITimeout
from app.services.genai_publication import GoldPublicationContext
from app.services.gold_domain_controls import (
    ANALYTICAL_CONTROLS,
    observe_domain_controls,
)


@contextmanager
def _snapshot(engine, context):
    if engine.dialect.name == "postgresql":
        with context.execution_snapshot(engine) as connection:
            connection.exec_driver_sql("SET LOCAL statement_timeout = '5000ms'")
            yield connection
    elif engine.dialect.name == "sqlite":
        # Somente compatibilidade de teste/local; não comprova permissões PostgreSQL.
        with engine.connect() as connection:
            previous = connection.exec_driver_sql("PRAGMA query_only").scalar_one()
            connection.commit()
            connection.exec_driver_sql("PRAGMA query_only=ON")
            connection.commit()
            try:
                connection.exec_driver_sql("BEGIN")
                current_publication(connection, context.batch_ref)
                yield connection
            finally:
                connection.rollback()
                connection.exec_driver_sql(f"PRAGMA query_only={int(previous)}")
                connection.commit()
        context.assert_current(engine)
    else:
        raise GoldPublicationInvalid("Dialeto não suportado para prontidão.")


def _remaining_sql(connection, expires):
    milliseconds = int(min(5, expires - monotonic()) * 1000)
    if milliseconds < 1:
        raise GenAITimeout
    if connection.dialect.name == "postgresql":
        from sqlalchemy import text
        connection.execute(text("SELECT set_config('statement_timeout', :timeout, true)"),
                           {"timeout": str(milliseconds)})


def _rows(connection, table, expires):
    _remaining_sql(connection, expires)
    result = connection.execution_options(yield_per=1000).execute(select(table) if isinstance(table, Table) else table)
    try:
        for row in result.mappings():
            if monotonic() >= expires:
                raise GenAITimeout
            yield row
    finally:
        result.close()


def _month(value):
    if value is None:
        return None
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.strftime("%Y-%m")


def _valid_number(value):
    return value is not None and isfinite(value)


def _observe_publication(
    engine: Engine, *, requested_periods: tuple[str, ...], approved_controls: frozenset[str],
    expected_batch_ref: str | None = None, include_domains: bool = False,
) -> dict:
    """Fatos para evaluate_readiness, fixados na mesma publicação do banco.

    requested_periods é um recorte global da publicação para uso interno autorizado.
    Recortes por UC/geografia exigem observação própria; estes fatos não os autorizam.
    """
    if (not requested_periods or len(requested_periods) > 1200
            or len(set(requested_periods)) != len(requested_periods)):
        raise ValueError("Recorte mensal inválido.")
    for period in requested_periods:
        if datetime.strptime(period, "%Y-%m").strftime("%Y-%m") != period:
            raise ValueError("Competência inválida.")
    if not approved_controls <= ({"C14", "C15"} | (ANALYTICAL_CONTROLS if include_domains else set())):
        raise ValueError("Controle fora desta observação.")
    expires = monotonic() + 35
    context = GoldPublicationContext.capture(engine)
    if expected_batch_ref is not None and expected_batch_ref != context.batch_ref:
        raise GoldPublicationChanged("A publicação Gold mudou.")
    if context.reference.schema_version != "gold-csv-v2":
        raise GoldPublicationInvalid("Prontidão de atendimento exige publicação v2.")
    with _snapshot(engine, context) as connection:
        _remaining_sql(connection, expires)
        origin = publication_lineage(connection, context.batch_ref)
        tables = {}
        for name, table in TABLES.items():
            _remaining_sql(connection, expires)
            has_rows = connection.execute(select(table).limit(1)).first() is not None
            periods = []
            column = table.c.get("competencia")
            if column is not None:
                _remaining_sql(connection, expires)
                periods = sorted(value for value in connection.execute(
                    select(column).where(column.is_not(None)).distinct().limit(1201)
                ).scalars())
                if len(periods) > 1200:
                    raise ValueError("Cobertura excede o limite do contrato.")
            tables[name] = {"present": True, "has_rows": has_rows,
                            "batch_ref": context.batch_ref, "periods": periods}
        summary = {}
        detail = defaultdict(lambda: [0, Decimal(0), 0])
        monthly = Counter()
        undated = 0
        c14_ok = c15_ok = True
        for row in _rows(connection, TABLES["visao_360_uc"], expires):
            uc, count, mean = row["id_uc"], row["total_chamados_callcenter"], row["media_satisfacao_atendimento"]
            if (not uc or uc.upper().startswith("TESTE") or uc in summary
                    or not _valid_number(count) or count < 0 or int(count) != count
                    or (mean is not None and (not _valid_number(mean) or mean < 0))):
                c14_ok = False
                continue
            summary[uc] = (count, mean)
        for row in _rows(connection, TABLES["atendimentos_uc"], expires):
            uc, note = row["id_uc"], row["nota_satisfacao"]
            if (not uc or uc.upper().startswith("TESTE") or not row["protocolo"]
                    or (note is not None and (not _valid_number(note) or note < 0))):
                c14_ok = False
                continue
            for flag in ("_nota_invalida", "_nota_negativa"):
                if row[flag] is None or (row[flag] and note is not None):
                    c14_ok = False
            bucket = detail[uc]
            bucket[0] += 1
            if note is not None:
                bucket[1] += Decimal(str(note))
                bucket[2] += 1
            opened = row["data_abertura"]
            if row["_abertura_futura"] is None or (row["_abertura_futura"] and opened is not None):
                c15_ok = False
            month = _month(opened)
            if month is None:
                undated += 1
            else:
                monthly[month] += 1
        for uc, (count, mean) in summary.items():
            actual_count, total, rated = detail.get(uc, (0, Decimal(0), 0))
            actual_mean = total / rated if rated else None
            if count != actual_count:
                c14_ok = False
            if mean is None or actual_mean is None:
                c14_ok &= mean is None and actual_mean is None
            elif abs(Decimal(str(mean)) - actual_mean) > Decimal("0.005"):
                c14_ok = False
        c14_ok &= not (detail.keys() - summary.keys())
        covered, closed, zeros = set(), set(), set()
        for row in _rows(connection, TABLES["cobertura_dominios"], expires):
            if row["dominio"] != "atendimentos" or row["recorte"] != "DOMINIO":
                continue
            month, state, count = row["competencia"], row["estado_cobertura"], row["qtd_registros"]
            if (month in covered or not month or state not in {
                    "FECHADO", "PARCIAL", "AUSENTE", "NAO_CERTIFICADA"}
                    or not _valid_number(count) or count < 0
                    or count != monthly[month] or row["qtd_sem_competencia"] != undated
                    or (state == "AUSENTE" and count != 0)
                    or (state == "FECHADO" and undated != 0)
                    or row["zero_registros_confirmado"] is None
                    or row["zero_registros_confirmado"] != (state == "FECHADO" and count == 0)
                    or row["run_id_silver"] != origin.get("run_id_silver")
                    or row["lote_bronze_silver"] != origin.get("lote_bronze_silver")):
                c15_ok = False
                continue
            covered.add(month)
            if state == "FECHADO":
                cut = row["data_corte_evidencia"]
                if (not row["referencia_evidencia"] or cut is None or _month(cut) <= month
                        or row["natureza_certificacao"] not in {"EXTRACAO", "FECHAMENTO_CONTABIL"}):
                    c15_ok = False
                    continue
                closed.add(month)
                if count == 0:
                    zeros.add(month)
        c15_ok &= c14_ok and bool(covered) and not (monthly.keys() - covered)
        facts = {
            "readiness_version": "gold-readiness-v2", "batch_ref": context.batch_ref,
            "expected_batch_ref": context.batch_ref, "backend_reachable": True,
            "tables": tables, "approved_controls": [],
            "control_results": {key: {"batch_ref": context.batch_ref,
                "status": "passed" if passed else "failed", "approved": key in approved_controls}
                for key, passed in (("C14", bool(c14_ok)), ("C15", bool(c15_ok)))},
            "coverage": {"atendimento.mensal": {"batch_ref": context.batch_ref,
                "requested_periods": list(requested_periods),
                "observed_periods": sorted(monthly), "closed_periods": sorted(closed),
                "zero_confirmed_periods": sorted(zeros), "has_undated_records": undated > 0}},
        }
        if include_domains:
            results, coverage = observe_domain_controls(
                connection, read_rows=lambda table: _rows(connection,table,expires),
                requested_periods=requested_periods, origin=origin, batch_ref=context.batch_ref)
            facts["control_results"].update({key:{"batch_ref":context.batch_ref,
                "status":"passed" if value else "failed", "approved":key in approved_controls}
                for key,value in results.items()})
            facts["coverage"].update(coverage)
    context.assert_current(engine)
    if monotonic() >= expires:
        raise GenAITimeout
    return facts


def observe_attendance_readiness(engine: Engine, *, requested_periods: tuple[str, ...],
                                  approved_controls: frozenset[str],
                                  expected_batch_ref: str | None = None) -> dict:
    """Compatibilidade da observação pública original de atendimento."""
    return _observe_publication(engine, requested_periods=requested_periods,
        approved_controls=approved_controls, expected_batch_ref=expected_batch_ref)


def observe_domain_readiness(engine: Engine, *, requested_periods: tuple[str, ...],
                             approved_controls: frozenset[str],
                             expected_batch_ref: str | None = None) -> dict:
    """Controles dos domínios e atendimento no mesmo snapshot e prazo."""
    return _observe_publication(engine, requested_periods=requested_periods,
        approved_controls=approved_controls, expected_batch_ref=expected_batch_ref, include_domains=True)
