"""Preserve queue evidence and enforce concurrent creation idempotency.

Revision ID: a6d060000001
Revises: 7c4a2b1e9d60
"""
from alembic import op
import sqlalchemy as sa

revision = "a6d060000001"
down_revision = "7c4a2b1e9d60"
branch_labels = None
depends_on = None


def upgrade():
    for name, kind in (
        ("suspicion_reference", sa.String(64)),
        ("suspicion_snapshot", sa.JSON()),
        ("idempotency_key", sa.String(128)),
        ("request_fingerprint", sa.String(64)),
    ):
        op.add_column("operational_inspection_orders", sa.Column(name, kind, nullable=True))
    op.create_index("uq_orders_idempotency", "operational_inspection_orders", ["idempotency_key"], unique=True)
    op.create_index(
        "uq_orders_active_suspicion", "operational_inspection_orders", ["suspicion_reference"],
        unique=True, postgresql_where=sa.text("status IN ('PENDING', 'IN_PROGRESS')"),
        sqlite_where=sa.text("status IN ('PENDING', 'IN_PROGRESS')"),
    )


def downgrade():
    op.drop_index("uq_orders_active_suspicion", table_name="operational_inspection_orders")
    op.drop_index("uq_orders_idempotency", table_name="operational_inspection_orders")
    with op.batch_alter_table("operational_inspection_orders") as batch:
        for name in ("request_fingerprint", "idempotency_key", "suspicion_snapshot", "suspicion_reference"):
            batch.drop_column(name)
