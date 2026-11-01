"""Add nullable platform profiles for explicit local account assignment."""

from alembic import op
import sqlalchemy as sa


revision = "20261101_profiles"
down_revision = "genai08000001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("auth_users") as batch:
        batch.add_column(sa.Column("profile", sa.String(length=32), nullable=True))
        batch.create_check_constraint(
            "ck_auth_users_platform_profile",
            "profile IS NULL OR profile IN ('commercial', 'customer_service', 'losses', 'operations', 'admin')",
        )


def downgrade():
    # Rollback must not reactivate tokens or restore the legacy broad JSON grants.
    op.execute(sa.text("DELETE FROM auth_sessions"))
    op.execute(sa.text("UPDATE auth_users SET permissions = '[]'"))
    with op.batch_alter_table("auth_users") as batch:
        batch.drop_constraint("ck_auth_users_platform_profile", type_="check")
        batch.drop_column("profile")
