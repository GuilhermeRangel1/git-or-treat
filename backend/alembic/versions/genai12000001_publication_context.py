"""Metadados mínimos do Panorama sem acesso à tabela operacional de carga."""
from alembic import op

revision = "genai12000001"
down_revision = "genai08000001"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""CREATE VIEW gold.publicacao_contexto AS
        SELECT schema_version, lote, publication_id, fingerprint, importado_em
        FROM public.gold_carga_atual
        WHERE id = 1 AND publication_id IS NOT NULL AND origem IS NOT NULL""")
    # Preserva as identidades autorizadas a ler a publicação, inclusive papéis
    # operacionais configurados com outro nome. Não concede tabela operacional.
    from sqlalchemy import text
    bind = op.get_bind()
    roles = bind.execute(text("SELECT DISTINCT grantee FROM information_schema.table_privileges "
        "WHERE table_schema='gold' AND table_name='publicacao_atual' AND privilege_type='SELECT' "
        "AND grantee <> 'PUBLIC'" )).scalars()
    quote = bind.dialect.identifier_preparer.quote
    for role in roles:
        op.execute(f"GRANT SELECT ON gold.publicacao_contexto TO {quote(role)}")



def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP VIEW gold.publicacao_contexto")
