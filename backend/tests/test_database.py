import os
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
            "gold_carga_tentativas",
            "gold.gold_consumo_mensal_uc",
            "gold.gold_consumo_receita_bairro",
            "gold.gold_diagnostico_receita",
            "gold.gold_fila_inspecao",
            "gold.gold_indicadores_dec_fec",
            "gold.gold_variacao_consumo_uc",
            "gold.gold_visao_360_uc",
            "gold_v2.atendimentos_uc",
            "gold_v2.cobertura_dominios",
            "gold_v2.consumo_mensal_uc",
            "gold_v2.consumo_receita_bairro",
            "gold_v2.decomposicao_receita",
            "gold_v2.diagnostico_receita",
            "gold_v2.faturas_uc",
            "gold_v2.fila_inspecao",
            "gold_v2.gd_uc",
            "gold_v2.indicadores_dec_fec",
            "gold_v2.medidor_uc",
            "gold_v2.ocorrencias_uc",
            "gold_v2.tratativas_uc",
            "gold_v2.variacao_consumo_uc",
            "gold_v2.visao_360_uc",
            "operational_inspection_orders",
            "operational_order_history",
        }
        assert "app.core.database" not in sys.modules

        from app.core.database import Base as DatabaseBase
        assert DatabaseBase is Base
        """
    )

    subprocess.run([sys.executable, "-c", script], check=True, text=True)


def test_sqlite_engine_creates_all_registered_gold_schemas():
    script = textwrap.dedent(
        """
        from app.db.base import Base
        import app.models
        from app.core.database import engine

        Base.metadata.create_all(bind=engine)
        """
    )
    environment = {**os.environ, "DATABASE_URL": "sqlite:///:memory:"}

    subprocess.run([sys.executable, "-c", script], check=True, text=True, env=environment)
