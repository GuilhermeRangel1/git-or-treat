"""Read-only repository for the published Gold inspection triage snapshot."""
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from app.repositories.gold_context import GoldContext
from app.models.gold_v2_load import TABLES
from app.schemas.analytics import AnalyticsFilters


class GoldInspectionRepository:
    def __init__(self, context: GoldContext):
        self.context = context
        self.connection: Connection = context.connection
        self.queue = TABLES["fila_inspecao"]
        self.variation = TABLES["variacao_consumo_uc"]
        self.profile = TABLES["visao_360_uc"]

    def filter_options(self) -> dict[str, list[str]]:
        return {
            "municipio": self._options(self.queue.c.municipio),
            "bairro": self._options(self.queue.c.bairro),
            "classe": self._options(self.queue.c.classe),
            "alimentador": self._options(self.queue.c.alimentador),
        }

    def neighborhoods(self) -> list[dict[str, str]]:
        rows = self.connection.execute(
            select(self.queue.c.municipio, self.queue.c.bairro)
            .where(self.queue.c.municipio.is_not(None), self.queue.c.bairro.is_not(None))
            .distinct().order_by(self.queue.c.municipio, self.queue.c.bairro)
        )
        return [{"municipio": municipality, "bairro": neighborhood} for municipality, neighborhood in rows]

    def _options(self, column) -> list[str]:
        rows = self.connection.execute(
            select(column).distinct().where(column.is_not(None)).order_by(column)
        )
        return [row[0] for row in rows]

    def _predicates(self, filters: AnalyticsFilters) -> list:
        predicates = []
        for api_name, column_name in (
            ("municipio", "municipio"), ("bairro", "bairro"),
            ("classe", "classe"), ("alimentador", "alimentador"),
        ):
            value = getattr(filters, api_name)
            if value is not None:
                predicates.append(getattr(self.queue.c, column_name) == value)
        return predicates

    def count(self, filters: AnalyticsFilters) -> int:
        return self.connection.execute(
            select(func.count()).select_from(self.queue).where(*self._predicates(filters))
        ).scalar_one()

    def category_counts(self, filters: AnalyticsFilters) -> dict[str | None, int]:
        rows = self.connection.execute(
            select(self.queue.c.prioridade_inspecao, func.count())
            .where(*self._predicates(filters))
            .group_by(self.queue.c.prioridade_inspecao)
            .order_by(self.queue.c.prioridade_inspecao)
        )
        return {category: count for category, count in rows}

    def bairro_belongs_to_municipio(self, bairro: str, municipio: str) -> bool:
        return self.connection.execute(
            select(func.count()).select_from(self.queue).where(
                self.queue.c.bairro == bairro, self.queue.c.municipio == municipio,
            )
        ).scalar_one() > 0

    def list_page(self, filters: AnalyticsFilters, page: int, page_size: int, order_by: str, direction: str) -> list[dict]:
        q, v, p = self.queue, self.variation, self.profile
        columns = [
            q.c.id_uc, q.c.municipio, q.c.bairro, q.c.classe, q.c.alimentador,
            q.c.prioridade_inspecao, q.c.total_inspecoes_realizadas,
            q.c.total_inspecoes_irregulares, q.c.media_consumo_historico,
            q.c.possui_geracao_solar, q.c.motivo_prioridade,
            q.c.ordem_prioridade_inspecao, q.c.posicao_fila_inspecao,
            q.c.media_historica_recuperacao_kwh_por_inspecao,
            q.c.intervalo_historico_recuperacao_inferior_kwh,
            q.c.intervalo_historico_recuperacao_superior_kwh,
            q.c.referencia_media_historica_recuperacao,
            q.c.estado_media_historica_recuperacao,
            q.c.energia_estimada_recuperavel_kwh,
            q.c.intervalo_recuperacao_inferior_kwh,
            q.c.intervalo_recuperacao_superior_kwh,
            q.c.estado_estimativa_recuperacao, q.c.metodo_estimativa_recuperacao,
            v.c.id_uc.label("variation_uc_id"),
            v.c.consumo_medio_inicial, v.c.meses_com_leitura_p1,
            v.c.consumo_medio_final, v.c.meses_com_leitura_p2,
            v.c.variacao_kwh, v.c.variacao_pct,
            v.c.queda_consumo_superior_30_pct,
            p.c.status, p.c.total_chamados_callcenter,
            p.c.total_interrupcoes_sofridas,
        ]
        statement = select(*columns).select_from(
            q.outerjoin(v, q.c.id_uc == v.c.id_uc).outerjoin(p, q.c.id_uc == p.c.id_uc)
        ).where(*self._predicates(filters))
        if order_by == "queue_position":
            position = q.c.posicao_fila_inspecao.desc() if direction == "desc" else q.c.posicao_fila_inspecao.asc()
            statement = statement.order_by(position, q.c.id_uc.asc())
        elif order_by == "category":
            category = q.c.prioridade_inspecao.desc() if direction == "desc" else q.c.prioridade_inspecao.asc()
            statement = statement.order_by(
                category, q.c.id_uc.asc()
            )
        else:
            statement = statement.order_by(
                q.c.id_uc.desc() if direction == "desc" else q.c.id_uc.asc()
            )
        statement = statement.offset((page - 1) * page_size).limit(page_size)
        return [dict(row._mapping) for row in self.connection.execute(statement)]

    def detail(self, uc_id: str) -> dict | None:
        q, v, p = self.queue, self.variation, self.profile
        columns = [
            q.c.id_uc, q.c.municipio, q.c.bairro, q.c.classe, q.c.alimentador,
            q.c.prioridade_inspecao, q.c.total_inspecoes_realizadas,
            q.c.total_inspecoes_irregulares, q.c.media_consumo_historico,
            q.c.possui_geracao_solar, q.c.motivo_prioridade,
            q.c.ordem_prioridade_inspecao, q.c.posicao_fila_inspecao,
            q.c.media_historica_recuperacao_kwh_por_inspecao,
            q.c.intervalo_historico_recuperacao_inferior_kwh,
            q.c.intervalo_historico_recuperacao_superior_kwh,
            q.c.referencia_media_historica_recuperacao,
            q.c.estado_media_historica_recuperacao,
            q.c.energia_estimada_recuperavel_kwh,
            q.c.intervalo_recuperacao_inferior_kwh,
            q.c.intervalo_recuperacao_superior_kwh,
            q.c.estado_estimativa_recuperacao, q.c.metodo_estimativa_recuperacao,
            v.c.id_uc.label("variation_uc_id"),
            v.c.consumo_medio_inicial, v.c.meses_com_leitura_p1,
            v.c.consumo_medio_final, v.c.meses_com_leitura_p2,
            v.c.variacao_kwh, v.c.variacao_pct,
            v.c.queda_consumo_superior_30_pct,
            p.c.status, p.c.total_chamados_callcenter,
            p.c.total_interrupcoes_sofridas,
        ]
        statement = select(*columns).select_from(
            q.outerjoin(v, q.c.id_uc == v.c.id_uc).outerjoin(p, q.c.id_uc == p.c.id_uc)
        ).where(q.c.id_uc == uc_id)
        row = self.connection.execute(statement).mappings().first()
        return dict(row) if row else None

    def consumption_rows(self, uc_id: str) -> tuple[str | None, list]:
        monthly = TABLES["consumo_mensal_uc"]
        end = self.connection.execute(select(func.max(monthly.c.competencia))).scalar_one()
        if not end:
            return None, []
        rows = self.connection.execute(
            select(monthly).where(monthly.c.id_uc == uc_id, monthly.c.competencia <= end).order_by(monthly.c.competencia.desc()).limit(15)
        ).mappings().all()
        return end, rows

    def meter_rows(self, uc_id: str) -> list:
        meter = TABLES["medidor_uc"]
        return self.connection.execute(select(
            meter.c.data_instalacao, meter.c.data_retirada,
            meter.c.flag_instalacao_sentinela, meter.c.flag_instalacao_futura,
            meter.c.flag_retirada_sentinela, meter.c.flag_retirada_futura,
        ).where(meter.c.id_uc == uc_id)).mappings().all()
