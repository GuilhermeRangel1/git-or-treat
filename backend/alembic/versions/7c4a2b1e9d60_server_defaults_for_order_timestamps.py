"""Provide insert timestamps for SQL clients as well as the ORM.

Revision ID: 7c4a2b1e9d60
Revises: 2d848fa6f44a
"""

from alembic import op
import sqlalchemy as sa


revision = "7c4a2b1e9d60"
down_revision = "2d848fa6f44a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("operational_inspection_orders") as batch:
        for name in ("created_at", "updated_at"):
            batch.alter_column(
                name,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=sa.func.now(),
            )


def downgrade() -> None:
    with op.batch_alter_table("operational_inspection_orders") as batch:
        for name in ("created_at", "updated_at"):
            batch.alter_column(
                name,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=None,
            )
