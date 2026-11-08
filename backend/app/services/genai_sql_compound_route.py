"""Read the checked local price-volume staging file and independent Gold totals."""

import csv
import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.models.gold_v2 import TABLES
from app.schemas.genai_evidence import PublishedWindows
from app.services.genai_publication import GoldPublicationContext
from app.services.genai_sql_compound import (
    CompoundEvidenceUnavailable,
    ConsumptionTotals,
    EvidenceScope,
    RevenueEffect,
    compose_consumption_revenue,
)

EXPECTED_WINDOWS = {
    "inicio_p0": "2024-07",
    "fim_p0": "2025-06",
    "inicio_p1": "2025-07",
    "fim_p1": "2026-06",
}
EXPECTED_METHOD = "PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3"
REQUIRED_COLUMNS = {
    "municipio", "bairro", "classe_consumo", "variacao_faturamento_total_reais",
    "efeito_volume_reais", "efeito_preco_observado_reais", "efeito_interacao_reais",
    "estado_decomposicao", "inicio_p0", "fim_p0", "inicio_p1", "fim_p1", "metodo",
}
MAX_MANIFEST_BYTES = 64 * 1024
MAX_CSV_BYTES = 8 * 1024 * 1024


class CompoundStagingUnavailable(ValueError):
    """The staging artifact is absent, stale, malformed, or out of scope."""


def is_price_volume_question(question: str) -> bool:
    normalized = re.sub(r"\s+", " ", question.casefold())
    asks_composition = any(
        phrase in normalized
        for phrase in ("preço-volume", "preco-volume", "efeito preço e volume", "efeito preco e volume", "decomposição preço", "decomposicao preco")
    )
    asks_metrics = any(token in normalized for token in ("consumo", "kwh")) and any(
        token in normalized for token in ("receita", "faturamento", "faturamento")
    )
    return asks_composition and asks_metrics


def _decimal(value: str, field: str) -> Decimal:
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError):
        raise CompoundStagingUnavailable(f"Campo {field} inválido no staging.") from None
    if not number.is_finite():
        raise CompoundStagingUnavailable(f"Campo {field} não finito no staging.")
    return number


def _optional_decimal(value: str, field: str) -> Decimal | None:
    if value == r"\N":
        return None
    return _decimal(value, field)


def load_price_volume_staging(directory: str | Path, *, expected_lot: str):
    """Validate the immutable manifest and CSV before exposing any rows."""
    root = Path(directory).resolve()
    manifest_path = (root / "manifest-staging.json").resolve()
    csv_path = (root / "decomposicao_receita.csv").resolve()
    if root not in manifest_path.parents or root not in csv_path.parents:
        raise CompoundStagingUnavailable("Caminho de staging inválido.")
    try:
        if manifest_path.stat().st_size > MAX_MANIFEST_BYTES or csv_path.stat().st_size > MAX_CSV_BYTES:
            raise CompoundStagingUnavailable("Artefato de staging excede o limite permitido.")
        manifest_bytes = manifest_path.read_bytes()
        csv_bytes = csv_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, ValueError, json.JSONDecodeError):
        raise CompoundStagingUnavailable("Manifesto ou CSV de staging indisponível.") from None
    if (
        manifest.get("schema_version") != "gold-v2-price-volume-staging-v1"
        or manifest.get("status") != "STAGING_ONLY_NOT_ACTIVE"
        or manifest.get("source_publication", {}).get("lote") != expected_lot
        or manifest.get("requested_price_volume_windows") != EXPECTED_WINDOWS
        or manifest.get("method") != EXPECTED_METHOD
        or manifest.get("csv_file") != csv_path.name
        or hashlib.sha256(csv_bytes).hexdigest() != manifest.get("csv_sha256")
    ):
        raise CompoundStagingUnavailable("Staging não corresponde à publicação Gold ativa.")
    try:
        text = csv_bytes.decode("utf-8-sig")
        reader = csv.DictReader(text.splitlines(), delimiter=";")
        if reader.fieldnames is None or not REQUIRED_COLUMNS <= set(reader.fieldnames):
            raise CompoundStagingUnavailable("Estrutura do CSV de staging inválida.")
        effects: list[RevenueEffect] = []
        for row in reader:
            if any(row.get(name) != value for name, value in EXPECTED_WINDOWS.items()):
                raise CompoundStagingUnavailable("Janela divergente no CSV de staging.")
            if row.get("metodo") != EXPECTED_METHOD:
                raise CompoundStagingUnavailable("Método divergente no CSV de staging.")
            if row.get("estado_decomposicao") not in {"CALCULADA_BASE_COMUM", "SEM_BASE_COMUM"}:
                raise CompoundStagingUnavailable("Estado de decomposição desconhecido.")
            state = row["estado_decomposicao"]
            volume, price, interaction = (
                _optional_decimal(row["efeito_volume_reais"], "efeito_volume_reais"),
                _optional_decimal(row["efeito_preco_observado_reais"], "efeito_preco_observado_reais"),
                _optional_decimal(row["efeito_interacao_reais"], "efeito_interacao_reais"),
            )
            if (state == "CALCULADA_BASE_COMUM") != all(
                value is not None for value in (volume, price, interaction)
            ):
                raise CompoundStagingUnavailable("Efeitos divergem do estado de decomposição.")
            effects.append(RevenueEffect(
                municipality=(row.get("municipio") or "").strip(),
                consumption_class=(row.get("classe_consumo") or "").strip(),
                variation_brl=_decimal(row["variacao_faturamento_total_reais"], "variacao_faturamento_total_reais"),
                volume_effect_brl=volume,
                price_effect_brl=price,
                interaction_effect_brl=interaction,
                state=state,
                neighborhood=(row.get("bairro") or "").strip(),
            ))
    except (UnicodeDecodeError, KeyError, csv.Error):
        raise CompoundStagingUnavailable("CSV de staging inválido.") from None
    if not effects or len(effects) != manifest.get("group_rows"):
        raise CompoundStagingUnavailable("Quantidade de grupos diverge do manifesto.")
    return manifest, tuple(effects), hashlib.sha256(manifest_bytes).hexdigest()


def query_compound_from_sources(
    engine: Engine,
    staging_dir: str | Path,
    *,
    batch_ref: str,
    publication: GoldPublicationContext | None = None,
):
    """Aggregate monthly consumption separately, then compose published effects.

    No raw fact join is performed. The output explicitly keeps staging separate
    from the active Gold publication and carries both source identities.
    """
    expected_lot = batch_ref.split(":")[1] if batch_ref.startswith("gold-csv-v2:") else ""
    manifest, revenue, manifest_digest = load_price_volume_staging(
        staging_dir, expected_lot=expected_lot
    )
    expected_municipalities = frozenset(item.municipality for item in revenue)
    expected_groups = frozenset((item.municipality, item.neighborhood, item.consumption_class) for item in revenue)
    table = TABLES["diagnostico_receita"]
    periods = tuple(
        f"{year:04d}-{month:02d}"
        for start, end in (("2024-07", "2025-06"), ("2025-07", "2026-06"))
        for year in range(int(start[:4]), int(end[:4]) + 1)
        for month in range(1, 13)
        if f"{year:04d}-{month:02d}" >= start and f"{year:04d}-{month:02d}" <= end
    )
    statement = (
        select(
            table.c.municipio,
            table.c.competencia,
            func.sum(table.c.consumo_total_kwh).label("consumo_kwh"),
            func.count(table.c.competencia.distinct()).label("competencias"),
        )
        .where(table.c.competencia.in_(periods))
        .group_by(table.c.municipio, table.c.competencia)
        .order_by(table.c.municipio, table.c.competencia)
    )
    try:
        if publication is None:
            with engine.connect() as connection:
                rows = connection.execute(statement).mappings().all()
        else:
            with publication.execution_snapshot(
                engine,
                validate_f1_catalog=True,
                dimension_ids=frozenset({"geography.municipality", "customer.consumption_class"}),
                metric_ids=frozenset({"billing.revenue", "energy.consumption"}),
                source_capability_ids={
                    "billing.revenue": "faturamento.receita",
                    "energy.consumption": "faturamento.receita",
                },
            ) as connection:
                if connection.dialect.name == "postgresql":
                    connection.execute(text("SET LOCAL statement_timeout = '5000ms'")).close()
                rows = connection.execute(statement).mappings().all()
    except SQLAlchemyError as exc:
        # Don't surface driver details or SQL in the public API.
        raise CompoundEvidenceUnavailable("Consumo Gold indisponível para a comparação.") from exc
    monthly: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for row in rows:
        if row["municipio"] is None or row["consumo_kwh"] is None:
            raise CompoundEvidenceUnavailable("Consumo Gold contém valores ausentes.")
        monthly[str(row["municipio"])][str(row["competencia"])] = Decimal(str(row["consumo_kwh"]))
    if frozenset(monthly) != expected_municipalities or any(
        set(values) != set(periods) for values in monthly.values()
    ):
        raise CompoundEvidenceUnavailable("Cobertura mensal de consumo diverge do staging.")
    previous = set(periods[:12])
    current = set(periods[12:])
    consumption = tuple(
        ConsumptionTotals(
            municipality,
            sum((value for month, value in months.items() if month in previous), Decimal(0)),
            sum((value for month, value in months.items() if month in current), Decimal(0)),
        )
        for municipality, months in monthly.items()
    )
    windows = PublishedWindows(
        p0_start=EXPECTED_WINDOWS["inicio_p0"], p0_end=EXPECTED_WINDOWS["fim_p0"],
        p1_start=EXPECTED_WINDOWS["inicio_p1"], p1_end=EXPECTED_WINDOWS["fim_p1"],
        method=EXPECTED_METHOD,
    )
    scope_digest = hashlib.sha256(
        json.dumps({"batch": batch_ref, "manifest": manifest_digest, "csv": manifest["csv_sha256"]}, sort_keys=True).encode()
    ).hexdigest()
    scope = EvidenceScope(batch_ref, scope_digest, windows)
    result = compose_consumption_revenue(
        scope, scope, consumption, revenue,
        expected_municipalities=expected_municipalities,
        expected_revenue_groups=expected_groups,
    )
    return result, manifest, manifest_digest
