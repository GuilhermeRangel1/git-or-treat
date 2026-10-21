"""add order lifecycle concurrency and history

Revision ID: c4b1a239d8e7
Revises: 2d848fa6f44a
Create Date: 2026-10-20 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4b1a239d8e7'
down_revision: Union[str, Sequence[str], None] = '2d848fa6f44a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add versioning, cancellation reason, idempotency and history."""
    with op.batch_alter_table('operational_inspection_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cancellation_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('version', sa.Integer(), server_default='1', nullable=False))
        batch_op.add_column(sa.Column('idempotency_key', sa.String(length=100), nullable=True))
        batch_op.create_index('ix_operational_inspection_orders_idempotency_key', ['idempotency_key'], unique=True)

    op.create_table(
        'operational_order_history',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
        sa.Column('previous_status', sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', name='orderstatus', native_enum=False, length=20), nullable=True),
        sa.Column('new_status', sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', name='orderstatus', native_enum=False, length=20), nullable=False),
        sa.Column('action', sa.Enum('CREATED', 'STATUS_UPDATED', 'RESULT_REGISTERED', 'CANCELLED', name='orderaction', native_enum=False, length=30), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['operational_inspection_orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_operational_order_history_order_id'), 'operational_order_history', ['order_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema: drop history table and order lifecycle columns."""
    op.drop_index(op.f('ix_operational_order_history_order_id'), table_name='operational_order_history')
    op.drop_table('operational_order_history')
    with op.batch_alter_table('operational_inspection_orders', schema=None) as batch_op:
        batch_op.drop_index('ix_operational_inspection_orders_idempotency_key')
        batch_op.drop_column('idempotency_key')
        batch_op.drop_column('version')
        batch_op.drop_column('cancellation_reason')
