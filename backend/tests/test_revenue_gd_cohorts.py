from datetime import date

from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.gold_v2_load import TABLES
from app.repositories.gold import GoldAnalyticsRepository
from app.schemas.analytics import AnalyticsFilters


def test_real_repository_pairs_same_uc_and_month_without_leaking_other_city():
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           execution_options={"schema_translate_map": {"gold_v2": None}})
    for name in ("visao_360_uc", "consumo_mensal_uc", "gd_uc"):
        TABLES[name].create(engine)
    windows = ["2023-01", "2023-06", "2024-01", "2024-06"]
    uc, monthly, gd = (TABLES[name] for name in ("visao_360_uc", "consumo_mensal_uc", "gd_uc"))
    with engine.begin() as connection:
        connection.execute(insert(uc), [{"id_uc": str(i), "municipio": "A" if i < 10 else "B",
            "bairro": "Centro", "classe": "RESIDENCIAL", "possui_gd": "Sim" if i < 5 else "Não"} for i in range(11)])
        connection.execute(insert(gd), [{"id_uc": str(i), "data_conexao": date(2023, 9, 1),
            "flag_conexao_futura": False, "flag_conexao_sentinela": False} for i in range(5)])
        connection.execute(insert(monthly), [{"id_uc": str(i), "competencia": f"{year}-{month:02d}",
            "tem_fatura": True, "receita_base_comparavel_reais": 100,
            "consumo_base_comparavel_kwh": 100 if year == 2023 else 30 if i < 5 else 110}
            for i in range(11) for year in (2023, 2024) for month in range(1, 7)])
    with Session(engine) as session:
        repo = object.__new__(GoldAnalyticsRepository)
        repo.db, repo.tables = session, TABLES
        rows = repo.revenue_gd_cohort_rows(AnalyticsFilters(municipio="A"), windows)
        by_group = {row["cohort"]: row for row in rows}
        assert set(by_group) == {"connected_between", "no_record"}
        assert by_group["connected_between"]["uc_count"] == 5
        assert by_group["connected_between"]["q0"] == 3000
        assert by_group["connected_between"]["q1"] == 900
        assert by_group["connected_between"]["volume_effect"] == -2100
        assert by_group["no_record"]["uc_count"] == 5
        assert by_group["no_record"]["volume_effect"] == 300
        assert repo.revenue_billed_population(AnalyticsFilters(municipio="A"), windows) == {"initial":10,"final":10}
    engine.dispose()
