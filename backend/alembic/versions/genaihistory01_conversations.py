"""Histórico privado de conversas, separado da Gold e da auditoria."""

import sqlalchemy as sa
from alembic import op

revision = "genaihistory01"
down_revision = "genai12000001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "owner_id",
            sa.String(36),
            sa.ForeignKey("auth_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "request_id", name="uq_ai_conversation_creation"
        ),
    )
    op.create_index(
        "ix_ai_conversation_owner_updated",
        "ai_conversations",
        ["owner_id", "updated_at"],
    )
    op.create_index("ix_ai_conversation_expiry", "ai_conversations", ["expires_at"])
    op.create_table(
        "ai_conversation_exchanges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.String(36), nullable=False),
        sa.Column("format_version", sa.Integer(), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("scope_digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("question", sa.String(1000)),
        sa.Column("response", sa.JSON()),
        sa.Column("anchor", sa.String(1000)),
        sa.Column("batch", sa.String(200)),
        sa.UniqueConstraint(
            "conversation_id", "request_id", name="uq_ai_exchange_request"
        ),
        sa.UniqueConstraint(
            "conversation_id", "sequence", name="uq_ai_exchange_sequence"
        ),
    )


def downgrade():
    op.drop_table("ai_conversation_exchanges")
    op.drop_table("ai_conversations")
