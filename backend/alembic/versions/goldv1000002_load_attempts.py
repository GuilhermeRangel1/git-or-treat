"""Versiona o lote publicado e conserva tentativas fora do rollback da carga."""
from alembic import op
import sqlalchemy as sa

revision = "goldv1000002"
down_revision = "goldv1000001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("gold_carga_atual", sa.Column(
        "schema_version", sa.String(32), nullable=False, server_default="gold-csv-v1",
    ))
    op.create_table(
        "gold_carga_tentativas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lote", sa.String(100)),
        sa.Column("schema_version", sa.String(32)),
        sa.Column("fingerprint", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalizado_em", sa.DateTime(timezone=True)),
        sa.Column("manifesto", sa.JSON, nullable=False),
        sa.Column("erro_codigo", sa.String(40)),
        sa.Column("erro_mensagem", sa.Text),
        sa.CheckConstraint("status IN ('running', 'loaded', 'unchanged', 'failed')", name="ck_gold_tentativa_status"),
        sa.CheckConstraint(
            "(status = 'running' AND finalizado_em IS NULL) OR "
            "(status <> 'running' AND finalizado_em IS NOT NULL)",
            name="ck_gold_tentativa_finalizacao",
        ),
    )
    op.create_index("ix_gold_tentativas_lote_inicio", "gold_carga_tentativas", ["lote", "iniciado_em"])


def downgrade():
    op.drop_index("ix_gold_tentativas_lote_inicio", table_name="gold_carga_tentativas")
    op.drop_table("gold_carga_tentativas")
    op.drop_column("gold_carga_atual", "schema_version")
