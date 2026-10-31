"""Linhagem mínima para conferência somente leitura de prontidão."""
from alembic import op

revision = "goldv2000002"
down_revision = "goldv2000001"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""CREATE VIEW gold.publicacao_linhagem AS
        SELECT schema_version, lote, publication_id,
            origem ->> 'run_id_silver' AS run_id_silver,
            origem ->> 'lote_bronze_silver' AS lote_bronze_silver
        FROM public.gold_carga_atual
        WHERE publication_id IS NOT NULL AND origem IS NOT NULL""")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'venergy_gold_reader') THEN
            GRANT SELECT ON gold.publicacao_linhagem TO venergy_gold_reader;
        END IF;
    END $$""")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP VIEW gold.publicacao_linhagem")
