"""Preserva dados v1 e vincula publicações futuras à origem validada."""
from alembic import op
import sqlalchemy as sa

revision = "goldv1000003"
down_revision = "goldv1000002"
branch_labels = None
depends_on = None

# Snapshot da migração, independente dos modelos de runtime.
TABLES = (
    "gold_consumo_mensal_uc", "gold_consumo_receita_bairro", "gold_diagnostico_receita",
    "gold_fila_inspecao", "gold_indicadores_dec_fec", "gold_variacao_consumo_uc", "gold_visao_360_uc",
)


def upgrade():
    op.add_column("gold_carga_atual", sa.Column("publication_id", sa.String(36)))
    op.add_column("gold_carga_atual", sa.Column("origem", sa.JSON))
    op.add_column("gold_carga_tentativas", sa.Column("origem", sa.JSON))
    op.add_column("gold_carga_tentativas", sa.Column("publication_id", sa.String(36)))
    # Legado permanece legível, mas não ganha origem/publicação inventadas.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE SCHEMA IF NOT EXISTS gold")
        for name in TABLES:
            op.execute(f'ALTER TABLE public."{name}" SET SCHEMA gold')
        op.execute("""CREATE VIEW gold.publicacao_atual AS
            SELECT schema_version, lote, publication_id
            FROM public.gold_carga_atual
            WHERE publication_id IS NOT NULL AND origem IS NOT NULL""")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP VIEW gold.publicacao_atual")
        has_reader = op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'venergy_gold_reader')"))
        for name in reversed(TABLES):
            if has_reader:
                op.execute(f'REVOKE ALL ON gold."{name}" FROM venergy_gold_reader')
            op.execute(f'ALTER TABLE gold."{name}" SET SCHEMA public')
        # O schema pode conter grants/objetos administrados fora da migração.
    op.drop_column("gold_carga_tentativas", "publication_id")
    op.drop_column("gold_carga_tentativas", "origem")
    op.drop_column("gold_carga_atual", "origem")
    op.drop_column("gold_carga_atual", "publication_id")
