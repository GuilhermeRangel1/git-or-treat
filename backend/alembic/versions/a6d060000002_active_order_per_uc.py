"""Align DEV-06 and DEV-07: one active order per UC, including manual orders."""
from alembic import op
import sqlalchemy as sa

revision = "a6d060000002"
down_revision = "a6d060000001"
branch_labels = None
depends_on = None

ACTIVE = sa.text("status IN ('PENDING', 'IN_PROGRESS')")
TABLE = "operational_inspection_orders"


def upgrade():
    duplicate = op.get_bind().execute(sa.text(
        "SELECT 1 FROM operational_inspection_orders "
        "WHERE status IN ('PENDING', 'IN_PROGRESS') GROUP BY uc_id HAVING count(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError(
            "Há UCs com ordens ativas duplicadas. Reconcilie as ordens antes da migração; "
            "nenhum registro foi cancelado ou removido automaticamente."
        )
    op.create_index("uq_orders_active_uc", TABLE, ["uc_id"], unique=True,
                    postgresql_where=ACTIVE, sqlite_where=ACTIVE)
    op.drop_index("uq_orders_active_suspicion", table_name=TABLE)


def downgrade():
    op.create_index("uq_orders_active_suspicion", TABLE, ["suspicion_reference"], unique=True,
                    postgresql_where=ACTIVE, sqlite_where=ACTIVE)
    op.drop_index("uq_orders_active_uc", table_name=TABLE)
