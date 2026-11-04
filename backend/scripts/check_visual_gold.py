"""Reconcilia a distribuição do Panorama com SQL independente e somente leitura.

Execute com a configuração local Gold: python -m scripts.check_visual_gold.
Não escreve dados, não chama modelos e não imprime valores ou referências do lote.
"""

import json
from decimal import Decimal

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.repositories.gold_context import load_gold_context
from app.repositories.panorama import GoldPanoramaRepository
from app.services.panorama import (
    gold_panorama_revenue_metric,
    read_gold_panorama_financials,
)
from app.services.panorama_distribution import gold_distribution


def reconcile() -> list[dict]:
    engine = create_engine(settings.DATABASE_URL, hide_parameters=True, echo=False)
    try:
        with (
            engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as conn,
            conn.begin(),
        ):
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql("SET LOCAL statement_timeout = '5000ms'")
            repository = GoldPanoramaRepository(load_gold_context(conn))
            period = conn.execute(
                text("SELECT MAX(competencia) FROM gold_v2.diagnostico_receita")
            ).scalar_one()
            municipality, consumption_class = conn.execute(
                text(
                    "SELECT municipio, classe_consumo FROM gold_v2.diagnostico_receita "
                    "WHERE competencia=:period AND municipio IS NOT NULL "
                    "AND classe_consumo IS NOT NULL "
                    "GROUP BY municipio, classe_consumo "
                    "ORDER BY municipio, classe_consumo LIMIT 1"
                ),
                {"period": period},
            ).one()
            cases = [
                ("municipios", "todos", "todas"),
                ("municipios_com_classe", "todos", consumption_class),
                ("classes_do_municipio", municipality, "todas"),
                ("recorte_especifico", municipality, consumption_class),
            ]
            results = []
            for case, city, classification in cases:
                snapshot = read_gold_panorama_financials(
                    repository, period, "nenhuma", city, classification
                )
                metric = gold_panorama_revenue_metric(
                    snapshot.actual, snapshot.prior, snapshot.reference
                )
                distribution = gold_distribution(repository, snapshot, metric)
                if city != "todos" and classification != "todas":
                    assert distribution is None, (
                        "Recorte específico ampliou os filtros."
                    )
                    results.append({"caso": case, "sem_distribuicao_artificial": True})
                    continue
                # Somente os dois identificadores fixos abaixo podem entrar no SQL.
                column = "municipio" if city == "todos" else "classe_consumo"
                rows = (
                    conn.execute(
                        text(
                            f"SELECT {column} AS segment, "
                            "SUM(receita_base_comparavel_reais) AS value "
                            "FROM gold_v2.diagnostico_receita "
                            "WHERE competencia=:period "
                            "AND (:city='todos' OR municipio=:city) "
                            "AND (:classification='todas' OR classe_consumo=:classification) "
                            f"GROUP BY {column}"
                        ),
                        {
                            "period": period,
                            "city": city,
                            "classification": classification,
                        },
                    )
                    .mappings()
                    .all()
                )
                expected = {r["segment"]: r["value"] for r in rows}
                if len(expected) < 2:
                    assert distribution is None
                    results.append(
                        {
                            "caso": case,
                            "grupos": len(expected),
                            "sem_serie_artificial": True,
                        }
                    )
                    continue
                assert distribution is not None, "Distribuição válida não publicada."
                observed = {p.segmento: p.valor for p in distribution.pontos}
                assert observed.keys() == expected.keys(), "Categorias divergentes."
                for key, value in expected.items():
                    assert observed[key] == (None if value is None else float(value)), (
                        "Valor divergente."
                    )
                total = sum((v for v in expected.values() if v is not None), Decimal(0))
                assert distribution.total == float(total), "Total divergente."
                if distribution.completo:
                    assert (
                        abs(sum(p.valor for p in distribution.visual) - float(total))
                        < 0.01
                    )
                    assert all(
                        abs(p.percentual - float(Decimal(str(p.valor)) / total * 100))
                        <= 0.011
                        for p in distribution.visual
                    )
                else:
                    assert all(p.percentual is None for p in distribution.pontos)
                results.append(
                    {
                        "caso": case,
                        "grupos": len(expected),
                        "reconciliado": True,
                        "participacao_valida": distribution.completo,
                    }
                )
            return results
    finally:
        engine.dispose()


if __name__ == "__main__":
    print(
        json.dumps(
            {"fonte": "Gold v2 local", "somente_leitura": True, "casos": reconcile()},
            ensure_ascii=True,
        )
    )
