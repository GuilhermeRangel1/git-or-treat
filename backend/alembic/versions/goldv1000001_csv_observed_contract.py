"""Cria contrato físico provisório dos sete CSVs Gold, separado das ordens."""
from alembic import op

revision = "goldv1000001"
down_revision = "a7d070000001"
branch_labels = None
depends_on = None


def upgrade():
    from app.models.gold_v1 import BATCH, TABLES
    for table in [BATCH, *TABLES.values()]:
        table.create(op.get_bind())


def downgrade():
    from app.models.gold_v1 import BATCH, TABLES
    for table in reversed([BATCH, *TABLES.values()]):
        table.drop(op.get_bind())
