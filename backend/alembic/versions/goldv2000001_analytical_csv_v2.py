"""Cria o snapshot analítico das quinze tabelas Gold CSV v2."""
from alembic import op

revision = "goldv2000001"
down_revision = "goldv1000003"
branch_labels = None
depends_on = None


def upgrade():
    from app.models.gold_v2 import SCHEMA, TABLES

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
    for table in TABLES.values():
        table.create(bind, checkfirst=False)


def downgrade():
    from app.models.gold_v2 import TABLES

    bind = op.get_bind()
    for table in reversed(tuple(TABLES.values())):
        table.drop(bind, checkfirst=False)
