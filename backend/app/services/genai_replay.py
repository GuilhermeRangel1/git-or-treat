"""Artefato privado sem valores de filtros; reprodução exige nova autorização."""

import json
from hashlib import sha256

from sqlalchemy.dialects import postgresql

from app.schemas.genai_audit import AuditExecutionArtifact
from app.schemas.genai_plan import LogicalReadPlan
from app.services.genai_executor import (
    MAX_EVIDENCE_BYTES,
    MAX_EVIDENCE_ROWS,
    SQL_STATEMENT_TIMEOUT,
    GoldExecutionDenied,
    _query,
    execute_gold_plan,
)
from app.services.genai_planning import _admit_plan
from app.services.gold_catalog import load_gold_catalog


def execution_digest(lookup):
    payload = lookup.model_dump(mode="json")
    # O cache é derivado de identidade e não integra o cálculo reproduzido.
    if payload.get("evidence"):
        payload["evidence"].pop("cache_scope", None)
        if payload["evidence"].get("provenance"):
            payload["evidence"]["provenance"].pop("quality", None)
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def execution_artifact(planned, *, lookup=None):
    plan = planned.response.plan
    source = _admit_plan(plan, planned.access_scope)
    metric = next(m for m in load_gold_catalog().metrics if m.metric_id == plan.metric_id)
    redacted = plan.model_dump(mode="json")
    for index, item in enumerate(redacted["filters"]):
        item["values"] = [f"parameter:{index}:{slot}" for slot in range(len(item["values"]))]
    statement = _query(plan, source, metric)
    return AuditExecutionArtifact(
        catalog_digest=sha256(json.dumps(load_gold_catalog().model_dump(mode="json"),
            sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest(),
        redacted_plan=LogicalReadPlan.model_validate(redacted),
        query_template=str(statement.compile(dialect=postgresql.dialect())),
        max_rows=min(plan.limit, MAX_EVIDENCE_ROWS), max_bytes=MAX_EVIDENCE_BYTES,
        statement_timeout_ms=int(SQL_STATEMENT_TIMEOUT.removesuffix("ms")),
        result_digest=execution_digest(lookup) if lookup is not None else None,
    )


def verify_audited_execution(store, reference, engine, planned, *, resolve_scope):
    """Recebe planejamento confiável, não SQL; retorna somente confirmação do cálculo."""
    if planned.access_scope is None or resolve_scope() != planned.access_scope:
        raise GoldExecutionDenied
    events = store.read_reference(reference)
    if not events:
        raise GoldExecutionDenied
    event = next((row["event"] for row in reversed(events)
                  if row["service"] == "backend" and (row["event"].get("artifact") or {}).get(
                      "result_digest")), None)
    if event is None or (
        event["caller_ref"] != planned.access_scope.caller_ref
        or event["plan_id"] != planned.response.plan_fingerprint
        or event["batch_ref"] != planned.publication.batch_ref
    ):
        raise GoldExecutionDenied
    retained = AuditExecutionArtifact.model_validate(event["artifact"])
    current = execution_artifact(planned)
    if retained.model_copy(update={"result_digest": None}) != current:
        raise GoldExecutionDenied
    # Reutiliza controles do executor: snapshot, escopo, lote, timeout e limites.
    lookup = execute_gold_plan(engine, planned, resolve_scope=resolve_scope)
    # O selo de prontidão é contexto da execução original, não parte do cálculo.
    return execution_digest(lookup) == retained.result_digest
