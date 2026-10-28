"""Metadados atuais da carga, separados do snapshot físico histórico v1."""
from sqlalchemy import CheckConstraint, Column, DateTime, Index, JSON, String, Table, Text

from app.db.base import Base
from app.models import gold_v1

SCHEMA_VERSION = "gold-csv-v1"
TABLES = {name: table.to_metadata(Base.metadata) for name, table in gold_v1.TABLES.items()}
BATCH = gold_v1.BATCH.to_metadata(Base.metadata)
BATCH.append_column(Column("schema_version", String(32), nullable=False, server_default="gold-csv-v1"))

ATTEMPTS = Table(
    "gold_carga_tentativas", Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("lote", String(100)),
    Column("schema_version", String(32)),
    Column("fingerprint", String(64)),
    Column("status", String(16), nullable=False),
    Column("iniciado_em", DateTime(timezone=True), nullable=False),
    Column("finalizado_em", DateTime(timezone=True)),
    Column("manifesto", JSON, nullable=False),
    Column("erro_codigo", String(40)),
    Column("erro_mensagem", Text),
    CheckConstraint("status IN ('running', 'loaded', 'unchanged', 'failed')", name="ck_gold_tentativa_status"),
    CheckConstraint(
        "(status = 'running' AND finalizado_em IS NULL) OR "
        "(status <> 'running' AND finalizado_em IS NOT NULL)",
        name="ck_gold_tentativa_finalizacao",
    ),
)
Index("ix_gold_tentativas_lote_inicio", ATTEMPTS.c.lote, ATTEMPTS.c.iniciado_em)
