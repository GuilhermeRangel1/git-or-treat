from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine

from app.models.gold_v2_load import TABLES
from app.repositories.panorama import GoldPanoramaRepository


def test_counts_use_uc_month_presence_and_current_unique_cadastro():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS gold_v2")
        cadastro = TABLES["visao_360_uc"]
        monthly = TABLES["consumo_mensal_uc"]
        cadastro.create(connection)
        monthly.create(connection)
        connection.execute(cadastro.insert(), [
            {"id_uc": "A", "municipio": "M", "classe": "R"},
            {"id_uc": "B", "municipio": "M", "classe": "C"},
        ])
        connection.execute(monthly.insert(), [
            {"id_uc": "A", "competencia": "2025-01", "tem_fatura": True, "tem_leitura": False},
            {"id_uc": "A", "competencia": "2025-02", "tem_fatura": True, "tem_leitura": True},
            {"id_uc": "B", "competencia": "2025-01", "tem_fatura": False, "tem_leitura": True},
            {"id_uc": "C", "competencia": "2025-01", "tem_fatura": True, "tem_leitura": False},
        ])
        repository = GoldPanoramaRepository(SimpleNamespace(
            connection=connection, imported_at=datetime.now(timezone.utc),
        ))
        assert repository.billed_uc_count("2025-01") == 2
        assert repository.billed_uc_count("2025-02") == 1
        assert repository.billed_uc_count("2025-03") == 0
        assert repository.billed_uc_count("2025-01", "M", "R") == 1
        assert repository.billed_uc_count("2025-01", "M", "C") == 0
        assert repository.billed_uc_count("2025-01", "Não informado") == 1
        assert repository.registered_uc_count() == 2
        assert repository.registered_uc_count("M", "C") == 1
        assert repository.registered_uc_count("Absent") == 0
    engine.dispose()
