import subprocess
import sys
import textwrap


def test_model_metadata_loads_without_importing_database_engine():
    script = textwrap.dedent(
        """
        import sys

        from app.db.base import Base
        import app.models

        assert set(Base.metadata.tables) == {
            "gold_indicadores",
            "gold_carga_atual",
            "gold_consumo_mensal_uc",
            "gold_consumo_receita_bairro",
            "gold_diagnostico_receita",
            "gold_fila_inspecao",
            "gold_indicadores_dec_fec",
            "gold_variacao_consumo_uc",
            "gold_visao_360_uc",
            "operational_inspection_orders",
            "operational_order_history",
        }
        assert "app.core.database" not in sys.modules

        from app.core.database import Base as DatabaseBase
        assert DatabaseBase is Base
        """
    )

    subprocess.run([sys.executable, "-c", script], check=True, text=True)
