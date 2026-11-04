"""Composição explícita das leituras demonstrativas sobre SQLite artificial."""

import logging
from hashlib import sha256
from pathlib import Path

from app.agent.access import ReadAccessPolicy
from app.agent.read_plan import ReadPlanValidator
from app.profiles.grid360_sql_demo import (
    GRID360_SQL_DEMO_PROFILE,
    SQL_DEMO_TRUNCATION_LIMITATION,
)
from app.schemas.domain_profile import CatalogGranularity, FilterOperator
from app.sql.audit import AUDIT_LOGGER_NAME, LoggingAuditSink
from app.sql.dictionary import load_dictionary
from app.sql.evidence import SqlArtificialEvidenceSource
from app.sql.executors import SqliteReadOnlyExecutor
from app.sql.plan import SqlMetricBinding, SqlPlanCatalog, SqlPlanReader
from app.sql.service import ReadOnlySqlService

SQL_DEMO_SOURCE_ID = "synthetic.sql"
_AUDIT_HANDLER_NAME = "grid360.sql.demo.stderr"


def _demo_audit_sink() -> LoggingAuditSink:
    logger = logging.getLogger(AUDIT_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if not any(handler.name == _AUDIT_HANDLER_NAME for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.name = _AUDIT_HANDLER_NAME
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return LoggingAuditSink(logger)


def build_sql_demo_source(database_path: Path) -> SqlArtificialEvidenceSource:
    profile = GRID360_SQL_DEMO_PROFILE
    dictionary = load_dictionary(Path(__file__).with_name("dictionary.toml"))
    executor = SqliteReadOnlyExecutor(
        database_path,
        max_rows=dictionary.limits.max_rows,
        timeout_ms=dictionary.limits.timeout_ms,
        dictionary=dictionary,
    )
    source_version = sha256(database_path.read_bytes()).hexdigest()
    service = ReadOnlySqlService(dictionary, executor, _demo_audit_sink())
    catalog = SqlPlanCatalog(
        profile_id=profile.profile_id,
        source_id=SQL_DEMO_SOURCE_ID,
        version=profile.contract_version,
        dictionary_version=dictionary.version,
        table="gold_indicadores",
        period_column="competencia",
        period_granularity=CatalogGranularity.MONTH,
        metrics={
            "billing.revenue": SqlMetricBinding(
                domain_id="revenue",
                unit="unidades fictícias",
                column="receita_total",
                aggregation="sum",
                dimension_ids=frozenset({"geography.municipality"}),
                filter_operators=frozenset({FilterOperator.EQ, FilterOperator.IN}),
            ),
            "energy.consumption": SqlMetricBinding(
                domain_id="consumption",
                unit="kWh fictícios",
                column="energia_consumida_kwh",
                aggregation="sum",
                dimension_ids=frozenset({"geography.municipality"}),
                filter_operators=frozenset({FilterOperator.EQ, FilterOperator.IN}),
            ),
            "network.interruptions": SqlMetricBinding(
                domain_id="network",
                unit="ocorrências fictícias",
                column="interrupcoes",
                aggregation="sum",
                dimension_ids=frozenset({"geography.municipality"}),
                filter_operators=frozenset({FilterOperator.EQ, FilterOperator.IN}),
            ),
            "service.attendance": SqlMetricBinding(
                domain_id="service",
                unit="atendimentos fictícios",
                column="chamados",
                aggregation="sum",
                dimension_ids=frozenset({"geography.municipality"}),
                filter_operators=frozenset({FilterOperator.EQ, FilterOperator.IN}),
            ),
        },
        dimensions={"geography.municipality": "municipio"},
        source_version=source_version,
    )
    policy = ReadAccessPolicy(profile, SQL_DEMO_SOURCE_ID)
    reader = SqlPlanReader(
        catalog,
        dictionary,
        service,
        ReadPlanValidator(profile, SQL_DEMO_SOURCE_ID, policy),
    )
    return SqlArtificialEvidenceSource(
        reader,
        demo_limitation=profile.metrics[0].limitation_texts[0],
        truncation_limitation=SQL_DEMO_TRUNCATION_LIMITATION,
        demo_limitations={metric.id: metric.limitation_texts[0] for metric in profile.metrics},
        source_version=source_version,
        database_path=database_path,
    )
