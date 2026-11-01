"""Trilha GenAI operacional com expiração indexada."""

import sqlalchemy as sa
from alembic import op

revision = "genai08000001"
down_revision = "merge_gold_v2_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "genai_audit_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("correlation_id", sa.String(32), nullable=False),
        sa.Column("service", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event", sa.JSON(), nullable=False),
    )
    op.create_index("ix_genai_audit_correlation", "genai_audit_events",
                    ["correlation_id", "created_at"])
    op.create_index("ix_genai_audit_expiry", "genai_audit_events", ["expires_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("REVOKE ALL ON public.genai_audit_events FROM PUBLIC")


def downgrade():
    op.drop_table("genai_audit_events")
