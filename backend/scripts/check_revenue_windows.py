"""Reconciliação privada somente leitura; imprime apenas resultados dos controles.

Execute com REVENUE_CHECK_DATABASE_URL apontando para a publicação Gold v2 local.
Não cria contas, altera banco ou grava os dados consultados em arquivos.
"""
import math
import os

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models.gold_v2_load import TABLES
from app.repositories.gold import GoldAnalyticsRepository
from app.schemas.analytics import AnalyticsFilters, RevenueWindowDecomposition
from app.services.gold_revenue import (
    WINDOW_COMPONENTS,
    window_breakdown,
    window_decomposition,
)


def main():
    engine = create_engine(
        os.environ["REVENUE_CHECK_DATABASE_URL"], hide_parameters=True,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=5000"},
    )
    table = TABLES["decomposicao_receita"]
    try:
        with Session(engine) as session:
            repository = GoldAnalyticsRepository(session, allow_v2=True)
            assert repository.schema_version == "gold-csv-v2", "Publicação local não é Gold v2."
            for filters in (AnalyticsFilters(), AnalyticsFilters(classe="Residencial")):
                result = window_decomposition(repository, filters)
                RevenueWindowDecomposition.model_validate(result)
                assert result["status"] in {"available", "partial"}, "Decomposição configurada V3 indisponível nesta publicação local."
                conditions = [table.c.classe_consumo == filters.classe] if filters.classe else []
                for key, field in WINDOW_COMPONENTS.items():
                    expected = session.scalar(select(func.sum(table.c[field])).where(*conditions))
                    actual = result["components"][key]
                    assert (actual is None and expected is None) or math.isclose(actual, expected, abs_tol=0.01), "Componente divergente do SQL."
                for dimension in ("municipio", "bairro", "classe"):
                    items = window_breakdown(repository, filters, dimension)
                    assert items, "Agrupamento vazio na publicação local."
                    for key in WINDOW_COMPONENTS:
                        values = [item["decomposition"]["components"].get(key) for item in items]
                        known = [value for value in values if value is not None]
                        if known:
                            assert math.isclose(math.fsum(known), result["components"][key], abs_tol=0.01), "Soma de grupos divergente do agregado."
                for key, field in (("initial_amount_brl", "faturamento_p0_reais"), ("final_amount_brl", "faturamento_p1_reais")):
                    if result[key] is not None:
                        expected = session.scalar(select(func.sum(table.c[field])).where(*conditions))
                        assert math.isclose(result[key], expected, abs_tol=0.01), "Base de janela divergente do SQL."
            print("Gold v2: sete componentes, bases e três agrupamentos reconciliados no total e residencial; somente leitura.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
