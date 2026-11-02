"""Database-side queries for aggregated Gold DEC/FEC indicators."""
from datetime import datetime, timezone
from sqlalchemy import func, select

from app.models.gold_v2_load import TABLES
from app.repositories.gold_context import GoldContext


class GoldOperationsRepository:
    def __init__(self, context: GoldContext):
        self.context = context
        self.connection = context.connection
        self.table = TABLES["indicadores_dec_fec"]

    def options(self) -> tuple[list[str], dict[str, str | None]]:
        table = self.table
        rows = self.connection.execute(select(
            table.c.competencia, table.c.id_alimentador,
            func.min(table.c.municipio).label("municipality"),
        ).group_by(table.c.competencia, table.c.id_alimentador)).all()
        return (
            sorted({row.competencia for row in rows}),
            {row.id_alimentador: row.municipality for row in rows},
        )

    def occurrences(self, feeder_id: str, start: str, end: str, page: int, page_size: int):
        table = TABLES["ocorrencias_uc"]
        first = datetime(int(start[:4]), int(start[5:]), 1, tzinfo=timezone.utc)
        year, month = int(end[:4]), int(end[5:])
        last = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc) if (year, month) != (9999, 12) else None
        conditions = [table.c.alimentador == feeder_id, table.c.data_abertura >= first]
        if last is not None:
            conditions.append(table.c.data_abertura < last)
        total = self.connection.scalar(select(func.count()).select_from(table).where(*conditions))
        query = select(table.c.id_ocorrencia, table.c.id_uc, table.c.data_abertura, table.c.causa, table.c.duracao_min).where(*conditions).order_by(table.c.data_abertura.desc(), table.c.id_ocorrencia.asc(), table.c.id_uc.asc()).limit(page_size).offset((page - 1) * page_size)
        rows = self.connection.execute(query).mappings().all()
        return [{"event_id": row["id_ocorrencia"], "uc_id": row["id_uc"], "opened_at": row["data_abertura"].isoformat(), "cause": row["causa"], "duration_hours": row["duracao_min"] / 60 if row["duracao_min"] is not None else None} for row in rows], total

    def aggregate(self, start: str, end: str, municipio: str | None = None, alimentador: str | None = None):
        table = self.table
        conditions = [table.c.competencia >= start, table.c.competencia <= end]
        if municipio is not None:
            conditions.append(table.c.municipio == municipio)
        if alimentador is not None:
            conditions.append(table.c.id_alimentador == alimentador)
        query = select(
            table.c.id_alimentador.label("feeder_id"),
            table.c.competencia,
            func.min(table.c.municipio).label("municipality"),
            func.min(table.c.total_ucs_alimentador).label("min_denominator"),
            func.max(table.c.total_ucs_alimentador).label("max_denominator"),
            func.sum(table.c.duracao_total_interrupcoes_horas).label("duration_sum"),
            func.sum(table.c.frequencia_total_interrupcoes).label("interruption_count"),
            func.count().label("observed_rows"),
            func.count(table.c.duracao_total_interrupcoes_horas).label("duration_values"),
            func.count(table.c.frequencia_total_interrupcoes).label("count_values"),
            func.count(table.c.total_ucs_alimentador).label("denominator_values"),
        ).where(*conditions).group_by(table.c.id_alimentador, table.c.competencia).order_by(table.c.id_alimentador, table.c.competencia)
        return [dict(row) for row in self.connection.execute(query).mappings()]
