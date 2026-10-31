"""Consultas Gold parametrizadas; nenhuma reconstrução de fatos de demonstração."""
from datetime import timezone

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.models.gold_load import BATCH, TABLES
from app.models.gold_v2_load import TABLES as TABLES_V2

LIMITATIONS = [
    "Gold CSV: interpretação orientada pelo dicionário; reconciliação e cobertura dependem de cada publicação da origem.",
    "Receita e consumo publicados incluem apenas UC/competência com fatura e leitura correspondentes; não representam a totalidade da Silver.",
    "Cadastro e classificação da UC são atuais; não comprovam vigência histórica.",
    "Atualização indica a importação local, não a data de processamento da Gold.",
]
MISSING = "__grid360_missing__"


class GoldAnalyticsRepository:
    source_kind = "gold_csv"
    source_is_demo = False

    def __init__(self, session: Session, *, allow_v2: bool = False):
        self.db = session
        # Compartilha o lock da carga para não misturar tabelas/lotes na requisição.
        if session.bind.dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock_shared(73460127)"))
        elif not session.in_transaction():
            # SQLite legacy não inicia snapshot em SELECT automaticamente.
            session.execute(text("BEGIN"))
        batch = session.execute(select(BATCH)).mappings().first()
        if batch is None or (batch["schema_version"] != "gold-csv-v1" and not (allow_v2 and batch["schema_version"] == "gold-csv-v2" and batch["publication_id"])):
            from app.repositories.analytics import AnalyticsSourceUnavailable
            raise AnalyticsSourceUnavailable()
        self.schema_version = batch["schema_version"]
        self.origin = batch["origem"] or {}
        self.tables = TABLES_V2 if self.schema_version == "gold-csv-v2" else TABLES
        self.source_version = f"{batch['lote']}:{batch['fingerprint']}" if self.schema_version == "gold-csv-v1" else f"{self.schema_version}:{batch['lote']}:{batch['publication_id']}"
        stamp = batch["importado_em"]
        self.source_updated_at = stamp.replace(tzinfo=timezone.utc).isoformat() if stamp.tzinfo is None else stamp.isoformat()
        self.source_limitations = list(LIMITATIONS) if self.schema_version == "gold-csv-v1" else [
            "Faturamento e consumo medido têm universos independentes; cobertura observada não comprova fechamento contábil.",
            "Cadastro e classificação da UC são atuais; não comprovam vigência histórica.",
            "Atualização indica a importação local, não a data de processamento da Gold.",
        ]
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
        uc = self.tables["visao_360_uc"]
        monthly = self.tables["consumo_mensal_uc"]
        result = {field: list(self.db.scalars(select(uc.c[field]).where(uc.c[field].is_not(None)).distinct().order_by(uc.c[field]))) for field in ("municipio", "bairro", "classe", "alimentador")}
        result["bairros"] = self.rows(select(uc.c.municipio, uc.c.bairro).distinct().order_by(uc.c.municipio, uc.c.bairro))
        result["competencias"] = list(self.db.scalars(select(monthly.c.competencia).distinct().order_by(monthly.c.competencia)))
        self._options = result
        return result

    def unit(self, uc_id):
        from app.services.analytics import AnalyticsAPIError
        from app.services.uc_analytics import validate_uc_id
        uc_id = validate_uc_id(uc_id)
        uc = self.tables["visao_360_uc"]
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
        monthly, uc = self.tables["consumo_mensal_uc"], self.tables["visao_360_uc"]
        self.conditions(uc, filters)
        if filters.alimentador is None:
            territory = self.tables["consumo_receita_bairro"]
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
                *([func.sum(territory.c.receita_base_comparavel_reais).label("comparable_amount"),
                   func.sum(territory.c.consumo_base_comparavel_kwh).label("comparable_energy")] if self.schema_version == "gold-csv-v2" else []),
            ).where(territory.c.competencia.between(start, end), *conditions)
              .group_by(territory.c.competencia, *dimensions)
              .order_by(territory.c.competencia, *dimensions))
        dimensions = [uc.c.municipio, uc.c.bairro] if group_by == "bairro" else [uc.c[group_by]]
        billed_uc = (case((monthly.c.tem_fatura.is_(True), monthly.c.id_uc))
                     if self.schema_version == "gold-csv-v2" else monthly.c.id_uc)
        return self.rows(select(
            monthly.c.competencia, *dimensions,
            func.sum(monthly.c.receita_reais).label("amount"),
            func.sum(monthly.c.consumo_kwh).label("energy"),
            func.count(func.distinct(billed_uc)).label("uc_count"),
            *([func.sum(monthly.c.receita_base_comparavel_reais).label("comparable_amount"),
               func.sum(monthly.c.consumo_base_comparavel_kwh).label("comparable_energy")] if self.schema_version == "gold-csv-v2" else []),
        ).select_from(monthly.outerjoin(uc, monthly.c.id_uc == uc.c.id_uc)).where(
            monthly.c.competencia.between(start, end), *self.conditions(uc, filters),
        ).group_by(monthly.c.competencia, *dimensions).order_by(monthly.c.competencia, *dimensions))

    def revenue_decomposition_rows(self, filters):
        table = TABLES_V2["decomposicao_receita"]
        columns = {"municipio": table.c.municipio, "bairro": table.c.bairro, "classe": table.c.classe_consumo}
        conditions = [func.coalesce(columns[field], MISSING) == value
                      for field, value in filters.model_dump(exclude_none=True).items() if field in columns]
        return self.rows(select(table).where(*conditions))

    def queue_options(self):
        table = self.tables["fila_inspecao"]
        return {field: list(self.db.scalars(select(table.c[field]).where(table.c[field].is_not(None)).distinct().order_by(table.c[field])))
                for field in ("municipio", "bairro", "classe", "alimentador")}

    def queue_neighborhoods(self):
        table = self.tables["fila_inspecao"]
        return self.rows(select(table.c.municipio, table.c.bairro).where(
            table.c.municipio.is_not(None), table.c.bairro.is_not(None),
        ).distinct().order_by(table.c.municipio, table.c.bairro))

    def queue(self, filters, page, page_size, order_by, direction):
        from app.services.analytics import AnalyticsAPIError
        table = self.tables["fila_inspecao"]
        ranking = case(
            (table.c.prioridade_inspecao.startswith("ALTA"), 3),
            (table.c.prioridade_inspecao.startswith("MEDIA"), 2),
            (table.c.prioridade_inspecao.startswith("REVISAR"), 1), else_=0,
        )
        if order_by not in {"priority", "uc_id", "potential_recoverable_energy_kwh"} or direction not in {"asc", "desc"}:
            raise AnalyticsAPIError(422, "invalid_query", "Ordenação inválida.")
        # Estimativas ausentes não recebem ordenação numérica fictícia.
        if order_by == "potential_recoverable_energy_kwh":
            raise AnalyticsAPIError(422, "estimate_sort_unavailable", "Ordenação por energia estimada indisponível para esta publicação Gold.")
        if order_by == "priority" and self.schema_version == "gold-csv-v2":
            position = table.c.posicao_fila_inspecao
            return self.page(select(table).where(*self.conditions(table, filters)), page, page_size,
                             position.asc() if direction == "desc" else position.desc(), table.c.id_uc.asc())
        sort = ranking if order_by == "priority" else table.c.id_uc
        return self.page(select(table).where(*self.conditions(table, filters)), page, page_size,
                         sort.desc() if direction == "desc" else sort.asc(), table.c.id_uc.asc())
