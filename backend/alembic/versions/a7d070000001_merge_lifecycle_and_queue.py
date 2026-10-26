"""Converge existing DEV-07 lifecycle and DEV-06 queue without losing orders.

Revision ID: a7d070000001
Revises: c4b1a239d8e7, a6d060000002
"""
from alembic import op
import sqlalchemy as sa

revision = "a7d070000001"
down_revision = ("c4b1a239d8e7", "a6d060000002")
branch_labels = None
depends_on = None


def upgrade():
    indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("operational_inspection_orders")}
    with op.batch_alter_table("operational_inspection_orders") as batch:
        batch.alter_column("idempotency_key", existing_type=sa.String(100), type_=sa.String(128), existing_nullable=True)
        if "ix_operational_inspection_orders_idempotency_key" in indexes:
            batch.drop_index("ix_operational_inspection_orders_idempotency_key")
    with op.batch_alter_table("operational_order_history") as batch:
        batch.add_column(sa.Column("actor", sa.String(255), nullable=True))
        batch.add_column(sa.Column("order_version", sa.Integer(), nullable=True))
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), existing_nullable=False, server_default=sa.func.now())


def downgrade():
    with op.batch_alter_table("operational_order_history") as batch:
        batch.drop_column("order_version")
        batch.drop_column("actor")
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), existing_nullable=False, server_default=None)
