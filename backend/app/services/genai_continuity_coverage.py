"""Admissão de continuidade observada na mesma publicação da consulta."""

from sqlalchemy import select

from app.models.gold_v2 import TABLES
from app.repositories.gold_publication import publication_lineage
from app.services.genai_client import GenAIServiceUnavailable


class GoldCoverageUnavailable(GenAIServiceUnavailable):
    """O recorte não satisfaz a regra de cobertura para resposta observada."""

    def __init__(self):
        super().__init__(retryable=False)


def observed_coverage_valid(connection, plan, quality) -> bool:
    feeder = next(item.values[0] for item in plan.filters
                  if item.dimension_id == "network.feeder")
    table = TABLES["cobertura_dominios"]
    rows = connection.execute(select(table).where(
        table.c.dominio == "ocorrencias",
        table.c.recorte == "ALIMENTADOR:" + feeder,
        table.c.competencia.in_(quality.observed_periods),
    )).mappings().all()
    origin = publication_lineage(connection, quality.batch_ref)
    return coverage_rows_valid(rows, quality.observed_periods, origin)


def coverage_rows_valid(rows, periods, origin) -> bool:
    """Ausência de certificação não admite parcialidade ou linhagem divergente."""
    if len(rows) != len(periods) or {row["competencia"] for row in rows} != set(periods):
        return False
    return all(
        row["estado_cobertura"] == "NAO_CERTIFICADA"
        and row["natureza_certificacao"] == "NAO_CERTIFICADA"
        and row["motivo"] == "SEM_EVIDENCIA_DE_COBERTURA"
        and row["data_corte_evidencia"] is None
        and row["referencia_evidencia"] is None
        and row["reconciliacao_extracao_json"] is None
        and row["qtd_sem_competencia"] == 0
        and row["qtd_registros"] is not None
        and row["qtd_registros"] > 0
        and row["zero_registros_confirmado"] is False
        and all(row[key] == origin[key] for key in ("run_id_silver", "lote_bronze_silver"))
        for row in rows
    )
