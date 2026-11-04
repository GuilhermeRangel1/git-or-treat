"""Readiness operacional Gold v2; saída contém somente estados de componentes."""

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import Numeric, create_engine, inspect, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
from app.core.genai_gold_access import GOLD_DIMENSIONS, GOLD_METRICS
from app.repositories.gold_publication import current_publication
from app.schemas.genai_audit import BackendAuditEvent
from app.services.genai_audit import AuditStore
from app.services.gold_catalog import gold_physical_catalog, load_gold_catalog
from app.models.gold_v2 import TABLES


async def check_runtime() -> dict[str, str]:
    checks = dict.fromkeys(
        (
            "configuration",
            "database",
            "reader",
            "publication",
            "catalog",
            "audit",
            "genai",
            "generation",
        ),
        "unavailable",
    )
    reader = operational = None
    try:
        if (
            settings.ANALYTICS_SOURCE != "gold"
            or settings.GENAI_GOLD_DATABASE_URL is None
            or settings.AI_AGENT_BASE_URL is None
            or settings.AI_AGENT_SERVICE_API_TOKEN is None
        ):
            return checks
        url = make_url(settings.GENAI_GOLD_DATABASE_URL.get_secret_value())
        app_url = make_url(settings.DATABASE_URL)
        if (
            url.drivername != "postgresql+psycopg"
            or url.username != "venergy_genai_reader"
            or app_url.username == url.username
            or not url.password
            or url.query
            or (url.host, url.port, url.database)
            != (app_url.host, app_url.port, app_url.database)
        ):
            return checks
        checks["configuration"] = "ready"
        reader = create_engine(
            url,
            hide_parameters=True,
            pool_size=1,
            max_overflow=0,
            pool_timeout=2,
            connect_args={"connect_timeout": 5},
        )
        with reader.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '5s'"))
            connection.execute(text("SELECT 1"))
            checks["database"] = "ready"
            safe = connection.execute(
                text("""
                SELECT NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls)
                  AND NOT has_database_privilege(current_user, current_database(), 'TEMP')
                  AND NOT has_schema_privilege(current_user, 'gold_v2', 'CREATE')
                  AND NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE member=r.oid)
                  AND NOT EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='gold_v2' AND c.relkind IN ('r','p')
                    AND (has_table_privilege(c.oid, 'INSERT,UPDATE,DELETE,TRUNCATE')
                         OR has_any_column_privilege(c.oid, 'INSERT,UPDATE'))
                  )
                  AND NOT has_any_column_privilege('public.auth_users', 'SELECT')
                  AND NOT has_table_privilege('public.genai_audit_events', 'SELECT')
                FROM pg_roles r WHERE rolname=current_user
            """)
            ).scalar_one()
            if not safe:
                return checks
            checks["reader"] = "ready"
            publication = current_publication(connection)
            if publication.schema_version != "gold-csv-v2":
                return checks
            checks["publication"] = "ready"
            catalog = load_gold_catalog()
            inspector = inspect(connection)
            observed = {}
            for metric in catalog.metrics:
                for source in metric.sources:
                    # Fontes exclusivas de UC continuam no catálogo, mas fora
                    # do escopo quantitativo autorizado deste consumidor.
                    if source.dimension_columns and not (
                        source.dimension_columns.keys() & GOLD_DIMENSIONS
                    ):
                        continue
                    table = TABLES[source.table]
                    if source.table not in observed:
                        observed[source.table] = {
                            c["name"]: c["type"]
                            for c in inspector.get_columns(
                                source.table, schema="gold_v2"
                            )
                        }
                    names = set(source.dimension_columns.values()) | set(source.grain)
                    names.update(
                        c
                        for c in (
                            source.temporal_column,
                            source.measure_column,
                            source.numerator_column,
                            source.denominator_column,
                        )
                        if c
                    )
                    readable = {
                        name
                        for dimension, name in source.dimension_columns.items()
                        if dimension in GOLD_DIMENSIONS
                    }
                    readable.update(
                        name
                        for name in (
                            source.temporal_column,
                            source.measure_column,
                            source.numerator_column,
                            source.denominator_column,
                        )
                        if name
                    )
                    if metric.metric_id in GOLD_METRICS:
                        for name in readable:
                            if not connection.execute(
                                text(
                                    "SELECT has_column_privilege(current_user, :table, :column, 'SELECT')"
                                ),
                                {"table": "gold_v2." + source.table, "column": name},
                            ).scalar_one():
                                return checks
                    for name in names:
                        expected = table.c[name].type
                        actual = observed[source.table].get(name)
                        if not isinstance(actual, type(expected)):
                            return checks
                        if isinstance(expected, Numeric) and (
                            actual.precision,
                            actual.scale,
                        ) != (expected.precision, expected.scale):
                            return checks
            checks["catalog"] = "ready"
        operational = create_engine(
            settings.DATABASE_URL,
            hide_parameters=True,
            connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000"},
        )
        store = AuditStore(operational)
        event = BackendAuditEvent(
            correlation_id=uuid4().hex,
            stage="request",
            code="ready",
            outcome="success",
            duration_ms=0,
        )
        reference = await asyncio.to_thread(store.record, event, service="backend")
        if await asyncio.to_thread(store.read_reference, reference):
            checks["audit"] = "ready"
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get(
                str(settings.AI_AGENT_BASE_URL).rstrip("/")
                + "/api/v1/internal/runtime-status",
                headers={
                    "Authorization": "Bearer "
                    + settings.AI_AGENT_SERVICE_API_TOKEN.get_secret_value()
                },
            )
            response.raise_for_status()
            body = response.json()
        if (
            body.get("source") == "gold.local"
            and body.get("schema_version") == "gold-csv-v2"
            and body.get("audit_configured") is True
            and body.get("catalog") == gold_physical_catalog().model_dump(mode="json")
        ):
            checks["genai"] = "ready"
            checks["generation"] = (
                "configured"
                if body.get("generation_configured") is True
                else "unavailable"
            )
    except Exception:
        # CLI não imprime exceções, DSNs nem respostas internas.
        pass
    finally:
        if reader is not None:
            reader.dispose()
        if operational is not None:
            operational.dispose()
    return checks


def main() -> int:
    checks = asyncio.run(check_runtime())
    print(json.dumps({"components": checks, "provider_smoke_required": True}))
    return (
        0 if all(value in {"ready", "configured"} for value in checks.values()) else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
