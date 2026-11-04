"""Contexto analítico mínimo para o papel operacional Docker."""
from alembic import op

revision = "dockerpub0001"
down_revision = "20261103_merge_history"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""CREATE VIEW gold.publicacao_analitica AS
        SELECT schema_version, lote, publication_id, fingerprint, importado_em,
               jsonb_build_object('preco_volume_configuracao',
                   origem::jsonb -> 'preco_volume_configuracao') AS origem
        FROM public.gold_carga_atual
        WHERE id=1""")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='v_energy_app') THEN
            GRANT SELECT ON gold.publicacao_analitica TO v_energy_app;
        END IF;
    END $$""")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP VIEW gold.publicacao_analitica")
