"""Read the minimum restricted UC identity through its dedicated DB role."""

from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings


@lru_cache(maxsize=1)
def _reader_engine() -> Engine | None:
    if settings.GOLD_CADASTRO_DATABASE_URL is None:
        return None
    return create_engine(
        settings.GOLD_CADASTRO_DATABASE_URL.get_secret_value(),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
        pool_timeout=3,
        pool_recycle=1800,
        connect_args={"options": "-c statement_timeout=2000 -c default_transaction_read_only=on"},
        hide_parameters=True,
    )


def resolve_customer_identification(
    *, run_id: str, analytic_export_id: str | None, cadastro_export_id: str | None, uc_id: str
) -> dict[str, str | None]:
    unavailable = {"customer_name": None, "customer_identification_status": "unavailable"}
    reader = _reader_engine()
    if reader is None or not analytic_export_id or not cadastro_export_id:
        return unavailable
    try:
        with reader.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT nome_exibicao_titular, situacao_identificacao "
                    "FROM gold_cadastro.cadastro_titular_uc "
                    "WHERE run_id = :run_id AND analytic_export_id = :analytic_export_id "
                    "AND cadastro_export_id = :cadastro_export_id AND id_uc = :uc_id"
                ),
                {
                    "run_id": run_id,
                    "analytic_export_id": analytic_export_id,
                    "cadastro_export_id": cadastro_export_id,
                    "uc_id": uc_id,
                },
            ).mappings().one_or_none()
    except SQLAlchemyError:
        return unavailable
    if row is None:
        return unavailable
    state = {
        "DISPONIVEL": "available",
        "AUSENTE_NA_ORIGEM": "absent",
        "CONFLITO_NA_ORIGEM": "conflict",
    }.get(row["situacao_identificacao"])
    if state is None:
        return unavailable
    return {
        "customer_name": row["nome_exibicao_titular"] if state == "available" else None,
        "customer_identification_status": state,
    }
