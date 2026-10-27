"""Consultas Gold parametrizadas; nenhuma reconstrução de fatos de demonstração."""
from datetime import timezone

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.models.gold_v1 import BATCH, TABLES

LIMITATIONS = [
    "Gold CSV provisória: definições e cobertura aguardam o dicionário da engenharia de dados.",
    "Receita e consumo publicados incluem apenas UC/competência com fatura e leitura correspondentes; não representam a totalidade da Silver.",
    "Cadastro e classificação da UC são atuais; não comprovam vigência histórica.",
    "Atualização indica a importação local, não a data de processamento da Gold.",
]
MISSING = "__grid360_missing__"


class GoldAnalyticsRepository:
    source_kind = "gold_csv"
    source_is_demo = False

    def __init__(self, session: Session):
        self.db = session
        # Compartilha o lock da carga para não misturar tabelas/lotes na requisição.
        if session.bind.dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock_shared(73460127)"))
        elif not session.in_transaction():
            # SQLite legacy não inicia snapshot em SELECT automaticamente.
            session.execute(text("BEGIN"))
        batch = session.execute(select(BATCH)).mappings().first()
        if batch is None:
            from app.repositories.analytics import AnalyticsSourceUnavailable
            raise AnalyticsSourceUnavailable()
        self.source_version = f"{batch['lote']}:{batch['fingerprint']}"
        stamp = batch["importado_em"]
        self.source_updated_at = stamp.replace(tzinfo=timezone.utc).isoformat() if stamp.tzinfo is None else stamp.isoformat()
        self.source_limitations = list(LIMITATIONS)
        self._options = None

    @property
    def units(self):
        # Impede consumidores legados de varrer o banco ou cair em fixtures.
        from app.repositories.analytics import AnalyticsSourceUnavailable
        raise AnalyticsSourceUnavailable()

    feeders = units

    def rows(self, statement):
        return [dict(row) for row in self.db.execute(statement).mappings()]

    def scalar(self, statement):
        return self.db.scalar(statement)

    def options(self):
        if self._options is not None:
            return self._options
        uc = TABLES["visao_360_uc"]
        monthly = TABLES["consumo_mensal_uc"]
        result = {field: list(self.db.scalars(select(uc.c[field]).where(uc.c[field].is_not(None)).distinct().order_by(uc.c[field]))) for field in ("municipio", "bairro", "classe", "alimentador")}
        result["bairros"] = self.rows(select(uc.c.municipio, uc.c.bairro).distinct().order_by(uc.c.municipio, uc.c.bairro))
        result["competencias"] = list(self.db.scalars(select(monthly.c.competencia).distinct().order_by(monthly.c.competencia)))
        self._options = result
        return result

    def unit(self, uc_id):
        from app.services.analytics import AnalyticsAPIError
        from app.services.uc_analytics import validate_uc_id
        uc_id = validate_uc_id(uc_id)
        uc = TABLES["visao_360_uc"]
        row = self.db.execute(select(uc).where(uc.c.id_uc == uc_id)).mappings().first()
        if row is None:
            raise AnalyticsAPIError(404, "not_found", "Unidade consumidora não encontrada.")
        return dict(row)

    def conditions(self, table, filters):
        from app.services.analytics import AnalyticsAPIError
        predicates = []
        for field, value in filters.model_dump(exclude_none=True).items():
            if not value.strip() or len(value) > 100:
                raise AnalyticsAPIError(422, "invalid_query", "Filtro inválido.")
            column = func.coalesce(table.c[field], MISSING)
            if not self.scalar(select(func.count()).select_from(table).where(column == value)):
                raise AnalyticsAPIError(422, "invalid_query", "Filtro desconhecido.")
            predicates.append(column == value)
        if filters.municipio and filters.bairro and not self.scalar(select(func.count()).select_from(table).where(
            func.coalesce(table.c.municipio, MISSING) == filters.municipio,
            func.coalesce(table.c.bairro, MISSING) == filters.bairro,
        )):
            raise AnalyticsAPIError(422, "invalid_query", "Combinação geográfica contraditória.")
        return predicates

    def page(self, statement, page, page_size, *ordering):
        if page < 1 or page > 1_000_000_000 or not 1 <= page_size <= 100:
            from app.services.analytics import AnalyticsAPIError
            raise AnalyticsAPIError(422, "invalid_query", "Paginação fora do intervalo permitido.")
        total = self.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
        items = self.rows(statement.order_by(*ordering).offset((page - 1) * page_size).limit(page_size))
        return items, {"page": page, "page_size": page_size, "total": total, "total_pages": (total + page_size - 1) // page_size}

    def revenue_groups(self, start, end, filters, group_by):
        monthly, uc = TABLES["consumo_mensal_uc"], TABLES["visao_360_uc"]
        self.conditions(uc, filters)
        if filters.alimentador is None:
            territory = TABLES["consumo_receita_bairro"]
            columns = {"municipio": territory.c.municipio, "bairro": territory.c.bairro,
                       "classe": territory.c.classe_consumo}
            fields = ["municipio", "bairro"] if group_by == "bairro" else [group_by]
            dimensions = [columns[field].label(field) for field in fields]
            conditions = [func.coalesce(columns[field], MISSING) == value
                          for field, value in filters.model_dump(exclude_none=True).items()]
            return self.rows(select(
                territory.c.competencia, *dimensions,
                func.sum(territory.c.receita_total_reais).label("amount"),
                func.sum(territory.c.consumo_total_kwh).label("energy"),
                func.sum(territory.c.qtd_ucs_distintas_faturadas_no_mes).label("uc_count"),
            ).where(territory.c.competencia.between(start, end), *conditions)
              .group_by(territory.c.competencia, *dimensions)
              .order_by(territory.c.competencia, *dimensions))
        dimensions = [uc.c.municipio, uc.c.bairro] if group_by == "bairro" else [uc.c[group_by]]
        return self.rows(select(
            monthly.c.competencia, *dimensions,
            func.sum(monthly.c.receita_reais).label("amount"),
            func.sum(monthly.c.consumo_kwh).label("energy"),
            func.count(func.distinct(monthly.c.id_uc)).label("uc_count"),
        ).select_from(monthly.outerjoin(uc, monthly.c.id_uc == uc.c.id_uc)).where(
            monthly.c.competencia.between(start, end), *self.conditions(uc, filters),
        ).group_by(monthly.c.competencia, *dimensions).order_by(monthly.c.competencia, *dimensions))

    def queue(self, filters, page, page_size, order_by, direction):
        from app.services.analytics import AnalyticsAPIError
        table = TABLES["fila_inspecao"]
        ranking = case(
            (table.c.prioridade_inspecao.startswith("ALTA"), 3),
            (table.c.prioridade_inspecao.startswith("MEDIA"), 2),
            (table.c.prioridade_inspecao.startswith("REVISAR"), 1), else_=0,
        )
        if order_by not in {"priority", "uc_id", "potential_recoverable_energy_kwh"} or direction not in {"asc", "desc"}:
            raise AnalyticsAPIError(422, "invalid_query", "Ordenação inválida.")
        # Estimativas ausentes não recebem ordenação numérica fictícia.
        if order_by == "potential_recoverable_energy_kwh":
            return self.page(select(table).where(*self.conditions(table, filters)), page, page_size, table.c.id_uc.asc())
        sort = ranking if order_by == "priority" else table.c.id_uc
        return self.page(select(table).where(*self.conditions(table, filters)), page, page_size,
                         sort.desc() if direction == "desc" else sort.asc(), table.c.id_uc.asc())
