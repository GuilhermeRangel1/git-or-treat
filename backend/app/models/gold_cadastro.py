"""Restricted holder names, separate from analytical and GenAI tables."""

from sqlalchemy import CheckConstraint, Column, DateTime, Index, MetaData, String, Table

from app.db.base import Base

SCHEMA = "gold_cadastro"
METADATA = MetaData()
_CADASTRO_TITULAR_UC = Table(
    "cadastro_titular_uc",
    METADATA,
    Column("run_id", String(100), primary_key=True),
    Column("analytic_export_id", String(128), primary_key=True),
    Column("cadastro_export_id", String(128), nullable=False),
    Column("id_uc", String(100), primary_key=True),
    Column("nome_exibicao_titular", String(512)),
    Column("situacao_identificacao", String(32), nullable=False),
    Column("data_processamento_gold", DateTime(timezone=True), nullable=False),
    *[
        CheckConstraint(
            "situacao_identificacao IN ('DISPONIVEL', 'AUSENTE_NA_ORIGEM', 'CONFLITO_NA_ORIGEM')",
            name="ck_gold_cadastro_situacao",
        ),
        CheckConstraint(
            "situacao_identificacao = 'DISPONIVEL' OR nome_exibicao_titular IS NULL",
            name="ck_gold_cadastro_nome_status",
        ),
    ],
    schema=SCHEMA,
    comment="Dados pessoais mínimos para a jornada de Atendimento; proibido no catálogo GenAI.",
)
Index("ix_gold_cadastro_uc", _CADASTRO_TITULAR_UC.c.id_uc)

CADASTRO_TITULAR_UC = _CADASTRO_TITULAR_UC.to_metadata(Base.metadata)
