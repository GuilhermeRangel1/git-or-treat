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
            "operational_inspection_orders",
        }
        assert "app.core.database" not in sys.modules

        from app.core.database import Base as DatabaseBase
        assert DatabaseBase is Base
        """
    )

    subprocess.run([sys.executable, "-c", script], check=True, text=True)
