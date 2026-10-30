import subprocess
import sys
import textwrap
from pathlib import Path


def test_model_metadata_loads_without_importing_database_engine():
    script = textwrap.dedent(
        """
        import sys

        from app.db.base import Base
        import app.models

        assert set(Base.metadata.tables) == {
            "gold_indicadores",
            "gold_carga_atual",
            "gold_carga_tentativas",
            "gold.gold_consumo_mensal_uc",
            "gold.gold_consumo_receita_bairro",
            "gold.gold_diagnostico_receita",
            "gold.gold_fila_inspecao",
            "gold.gold_indicadores_dec_fec",
            "gold.gold_variacao_consumo_uc",
            "gold.gold_visao_360_uc",
            "operational_inspection_orders",
            "operational_order_history",
            "auth_users",
            "auth_sessions",
        }
        assert "app.core.database" not in sys.modules

        from app.core.database import Base as DatabaseBase
        assert DatabaseBase is Base
        """
    )

    backend_root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, "-c", script], check=True, text=True, cwd=backend_root)
