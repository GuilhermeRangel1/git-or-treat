"""Create isolated storage for the restricted UC holder projection."""

from alembic import op
import sqlalchemy as sa


revision = "20261102_cadastro"
down_revision = ("20261101_profiles", "genai12000001")
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE SCHEMA gold_cadastro")
    op.create_table(
        "cadastro_titular_uc",
        sa.Column("run_id", sa.String(100), primary_key=True),
        sa.Column("analytic_export_id", sa.String(128), primary_key=True),
        sa.Column("cadastro_export_id", sa.String(128), nullable=False),
        sa.Column("id_uc", sa.String(100), primary_key=True),
        sa.Column("nome_exibicao_titular", sa.String(512), nullable=True),
        sa.Column("situacao_identificacao", sa.String(32), nullable=False),
        sa.Column("data_processamento_gold", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "situacao_identificacao IN ('DISPONIVEL', 'AUSENTE_NA_ORIGEM', 'CONFLITO_NA_ORIGEM')",
            name="ck_gold_cadastro_situacao",
        ),
        sa.CheckConstraint(
            "situacao_identificacao = 'DISPONIVEL' OR nome_exibicao_titular IS NULL",
            name="ck_gold_cadastro_nome_status",
        ),
        schema="gold_cadastro",
        comment="Dados pessoais mínimos para Atendimento; não conceder ao leitor analítico/GenAI.",
    )
    op.create_index(
        "ix_gold_cadastro_uc",
        "cadastro_titular_uc",
        ["id_uc"],
        schema="gold_cadastro",
    )
    op.execute("REVOKE ALL ON SCHEMA gold_cadastro FROM PUBLIC")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA gold_cadastro FROM PUBLIC")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("ix_gold_cadastro_uc", table_name="cadastro_titular_uc", schema="gold_cadastro")
        op.drop_table("cadastro_titular_uc", schema="gold_cadastro")
        op.execute("DROP SCHEMA gold_cadastro")
