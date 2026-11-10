"""Envelope público da análise Text-to-SQL; nunca expõe SQL nem parâmetros."""

import hashlib
from decimal import Decimal
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.ai import AICorrelationId, AIQuestionRequest
from app.schemas.genai_evidence import PublishedWindows
from app.schemas.sql_evidence import SqlEvidence
from app.schemas.sql_generation import SqlClarification, SqlUnsupported

PresentationText = Annotated[str, StringConstraints(min_length=1, max_length=4000)]
ExactDecimal = Annotated[str, StringConstraints(pattern=r"^-?(?:0|[1-9][0-9]{0,100})(?:\.[0-9]{1,100})?$")]


def _format_compound_number(value: Decimal, places: int) -> str:
    formatted = f"{value:,.{places}f}"
    return formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _exact_decimal_text(value) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def _format_month_label(period: str) -> str:
    month_names = (
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    )
    year, month = period.split("-")
    return f"{month_names[int(month) - 1]} de {year}"


class SqlCompoundRevenueEffect(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    consumption_class: str = Field(min_length=1, max_length=120)
    neighborhood: str = Field(min_length=1, max_length=120)
    variation_brl: ExactDecimal
    volume_effect_brl: ExactDecimal | None
    price_effect_brl: ExactDecimal | None
    interaction_effect_brl: ExactDecimal | None
    state: Literal["CALCULADA_BASE_COMUM", "SEM_BASE_COMUM", "DECOMPOSICAO_INDISPONIVEL"]
    consumption_change_kwh: ExactDecimal | None = None
    average_consumption_kwh: ExactDecimal | None = None


class ObservedComparisonWindows(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    p0_start: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    p0_end: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    p1_start: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    p1_end: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    method: Literal["VARIACAO_OBSERVADA"]

    @model_validator(mode="after")
    def validate_order(self):
        if self.p0_start == self.p0_end == self.p1_start == self.p1_end:
            return self
        if not self.p0_start <= self.p0_end < self.p1_start <= self.p1_end:
            raise ValueError("janelas observadas inválidas")
        return self


class SqlCompoundMunicipality(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    municipality: str = Field(min_length=1, max_length=120)
    previous_consumption_kwh: ExactDecimal
    current_consumption_kwh: ExactDecimal
    change_kwh: ExactDecimal
    change_percent: ExactDecimal
    revenue_by_class: tuple[SqlCompoundRevenueEffect, ...] = Field(min_length=1, max_length=1500)


class SqlCompoundAnalysis(BaseModel):
    """Multi-source evidence; Gold and local staging retain separate provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["text-to-sql-f1-compound-v1"]
    answer: PresentationText
    active_gold_batch: str = Field(min_length=1, max_length=200)
    staging_manifest_digest: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    staging_csv_digest: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    method: Literal["PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3", "VARIACAO_OBSERVADA"]
    windows: PublishedWindows | ObservedComparisonWindows
    municipalities: tuple[SqlCompoundMunicipality, ...] = Field(max_length=100)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=10)
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_digest(self):
        observed = self.method == "VARIACAO_OBSERVADA"
        if (
            self.windows.method != self.method
            or (self.staging_manifest_digest is None) != observed
            or (self.staging_csv_digest is None) != observed
        ):
            raise ValueError("proveniência da evidência composta diverge")
        payload = self.model_dump(mode="json", exclude={"evidence_digest"})
        actual = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        if actual != self.evidence_digest:
            raise ValueError("digest da evidência composta diverge")
        return self

    @classmethod
    def from_sources(cls, result, manifest, manifest_digest, *, municipality_limit=None):
        snapshot = (
            manifest is None
            and result.scope.windows.p0_start == result.scope.windows.p1_start
        )
        selected_municipalities = (
            result.municipalities[:municipality_limit]
            if municipality_limit is not None else result.municipalities
        )
        if snapshot and municipality_limit is None:
            selected_municipalities = tuple(
                sorted(selected_municipalities, key=lambda row: row.consumption.municipality)
            )
        municipalities = tuple(SqlCompoundMunicipality(
            municipality=row.consumption.municipality,
            previous_consumption_kwh=_exact_decimal_text(row.consumption.previous_kwh),
            current_consumption_kwh=_exact_decimal_text(row.consumption.current_kwh),
            change_kwh=_exact_decimal_text(row.change_kwh),
            change_percent=format(row.change_percent, ".6f"),
            revenue_by_class=tuple(SqlCompoundRevenueEffect(
                consumption_class=effect.consumption_class,
                neighborhood=effect.neighborhood or "Todos",
                variation_brl=format(effect.variation_brl, "f"),
                volume_effect_brl=format(effect.volume_effect_brl, "f") if effect.volume_effect_brl is not None else None,
                price_effect_brl=format(effect.price_effect_brl, "f") if effect.price_effect_brl is not None else None,
                interaction_effect_brl=format(effect.interaction_effect_brl, "f") if effect.interaction_effect_brl is not None else None,
                state=effect.state,
                consumption_change_kwh=(
                    _exact_decimal_text(effect.consumption_change_kwh)
                    if effect.consumption_change_kwh is not None else None
                ),
                average_consumption_kwh=(
                    format(effect.average_consumption_kwh, ".2f")
                    if effect.average_consumption_kwh is not None else None
                ),
            ) for effect in row.revenue_by_class),
        ) for row in selected_municipalities)
        answer = (
            "Os três municípios com maior queda de consumo foram comparados com "
            "a variação observada de faturamento por classe. A decomposição publicada "
            "mostra componentes contábeis, não prova causalidade."
            if municipality_limit == 3 else
            "A comparação preço-volume foi calculada para jul/2024–jun/2025 "
            "contra jul/2025–jun/2026. A tabela mostra municípios com queda de "
            "consumo e a decomposição da receita por classe de consumo."
        )
        limitations = [
            "A decomposição foi lida de staging local Gold v2, não da Gold ativa.",
            "Consumo e faturamento vêm de agregações independentes; as bases populacionais podem diferir.",
            "Preço observado não é tarifa regulada e não indica causalidade.",
            "A resposta lista apenas municípios com queda de consumo; efeitos de receita são detalhados por classe.",
            "Para grupos sem base comum comparável, os efeitos de volume, preço e interação permanecem sem valor.",
        ]
        if manifest is None:
            if snapshot:
                limitations = ["Consumo medido e receita faturada são indicadores distintos."]
                class_effects = [
                    (row.municipality, effect)
                    for row in municipalities
                    for effect in row.revenue_by_class
                    if effect.consumption_class != "Todas"
                ]
                if class_effects:
                    limitations = ["Consumo médio calculado pela razão entre consumo total e UCs com leitura."]
                    average_rows = [
                        item for item in class_effects
                        if item[1].average_consumption_kwh is not None
                    ]
                    if average_rows:
                        average_leader = max(
                            average_rows,
                            key=lambda item: Decimal(str(item[1].average_consumption_kwh)),
                        )
                        revenue_leader = max(class_effects, key=lambda item: Decimal(str(item[1].variation_brl)))
                        average_municipality, average_effect = average_leader
                        revenue_municipality, revenue_effect = revenue_leader
                        answer = (
                            f"Em {_format_month_label(result.scope.windows.p1_start)}, "
                            f"em {average_municipality}, "
                            f"a classe {average_effect.consumption_class} teve o maior consumo médio "
                            f"por UC com leitura ({_format_compound_number(Decimal(str(average_effect.average_consumption_kwh)), 2)} kWh/UC). "
                            f"O maior faturamento foi na classe {revenue_effect.consumption_class} "
                            f"(R$ {_format_compound_number(Decimal(str(revenue_effect.variation_brl)), 2)})."
                        )
                else:
                    period = result.scope.windows.p1_start
                    period_label = _format_month_label(period)
                    if municipalities:
                        consumption_leader = max(
                            municipalities,
                            key=lambda row: Decimal(str(row.current_consumption_kwh)),
                        )
                        revenue_totals = {
                            row.municipality: sum(
                                (Decimal(str(effect.variation_brl)) for effect in row.revenue_by_class),
                                Decimal(0),
                            )
                            for row in municipalities
                        }
                        revenue_municipality = max(revenue_totals, key=revenue_totals.get)
                        revenue_value = revenue_totals[revenue_municipality]
                        consumption_value = Decimal(str(consumption_leader.current_consumption_kwh))
                        if consumption_leader.municipality == revenue_municipality:
                            answer = (
                                f"Em {period_label}, {revenue_municipality} teve o maior consumo medido "
                                f"({_format_compound_number(consumption_value, 0)} kWh) e o maior faturamento "
                                f"(R$ {_format_compound_number(revenue_value, 2)}) entre os municípios consultados."
                            )
                        else:
                            answer = (
                                f"Em {period_label}, {consumption_leader.municipality} teve o maior consumo medido "
                                f"({_format_compound_number(consumption_value, 0)} kWh), enquanto {revenue_municipality} "
                                f"teve o maior faturamento (R$ {_format_compound_number(revenue_value, 2)})."
                            )
                    else:
                        answer = f"Não há valores disponíveis para {period_label}."
            elif result.scope.windows.p0_start == result.scope.windows.p0_end:
                if municipalities:
                    p0 = _format_month_label(result.scope.windows.p0_start)
                    p1 = _format_month_label(result.scope.windows.p1_start)
                    findings = []
                    for row in municipalities:
                        for effect in row.revenue_by_class:
                            consumption_change = Decimal(str(effect.consumption_change_kwh or "0"))
                            revenue_change = Decimal(str(effect.variation_brl))
                            findings.append(
                                f"na classe {effect.consumption_class}, o consumo caiu "
                                f"{_format_compound_number(abs(consumption_change), 0)} kWh e "
                                f"o faturamento subiu R$ {_format_compound_number(revenue_change, 2)}"
                            )
                    answer = (
                        f"Entre {p0} e {p1}, em {municipalities[0].municipality}, "
                        + "; ".join(findings)
                        + ". São variações observadas; elas não demonstram que a queda de consumo causou a alta do faturamento."
                    )
                else:
                    answer = "Nenhuma classe apresentou queda de consumo e alta de receita no recorte."
            elif municipality_limit is None and len(municipalities) == 1:
                municipality = municipalities[0]
                class_findings = []
                for effect in municipality.revenue_by_class:
                    consumption_change = Decimal(str(effect.consumption_change_kwh or "0"))
                    revenue_change = Decimal(str(effect.variation_brl))
                    consumption_direction = (
                        "caiu" if consumption_change < 0 else
                        "subiu" if consumption_change > 0 else "ficou estável"
                    )
                    revenue_direction = (
                        "caiu" if revenue_change < 0 else
                        "subiu" if revenue_change > 0 else "ficou estável"
                    )
                    class_findings.append(
                        f"{effect.consumption_class}: consumo {consumption_direction} "
                        f"{_format_compound_number(abs(consumption_change), 0)} kWh; "
                        f"receita faturada {revenue_direction} "
                        f"R$ {_format_compound_number(abs(revenue_change), 2)}"
                    )
                answer = (
                    f"Em {municipality.municipality}, entre jul/2024–jun/2025 e "
                    "jul/2025–jun/2026, as variações por classe foram: "
                    + "; ".join(class_findings)
                    + ". São mudanças observadas em paralelo; os dados não demonstram "
                    "que a variação do consumo causou a variação da receita."
                    if class_findings else
                    "Não há classes com valores completos nas duas janelas comparadas."
                )
            elif municipality_limit is None:
                answer = (
                    "A tabela mostra a variação de consumo medido e de receita faturada "
                    "por classe entre jul/2024–jun/2025 e jul/2025–jun/2026."
                )
            else:
                answer = (
                    "A tabela ordena os municípios pela maior queda de consumo entre "
                    "jul/2024–jun/2025 e jul/2025–jun/2026 e mostra a variação observada "
                    "de consumo e receita por classe."
                    if municipalities else "Nenhum município teve queda de consumo entre as duas janelas."
                )
            if result.scope.windows.p0_start != result.scope.windows.p1_start:
                limitations = [
                    "A decomposição preço-volume está indisponível para essas janelas.",
                    "As variações observadas não isolam o efeito do consumo sobre a receita.",
                ]
        if municipality_limit is not None and municipalities:
            leader = municipalities[0]
            ranked_findings = []
            for row in municipalities:
                increased = [
                    effect.consumption_class for effect in row.revenue_by_class
                    if Decimal(str(effect.variation_brl)) > 0
                ]
                decreased = [
                    effect.consumption_class for effect in row.revenue_by_class
                    if Decimal(str(effect.variation_brl)) < 0
                ]
                revenue_direction = []
                if increased:
                    revenue_direction.append(f"subiu em {', '.join(increased)}")
                if decreased:
                    revenue_direction.append(f"caiu em {', '.join(decreased)}")
                change = _format_compound_number(Decimal(str(row.change_kwh)).copy_abs(), 0)
                percent = _format_compound_number(Decimal(str(row.change_percent)).copy_abs(), 2)
                ranked_findings.append(
                    f"{row.municipality}: consumo caiu {change} kWh ({percent}%)"
                    + (f"; faturamento {' e '.join(revenue_direction)}" if revenue_direction else "")
                )
            answer = (
                "Entre os três municípios com maior queda de consumo, "
                + "; ".join(ranked_findings)
                + ". A tabela detalha o faturamento por classe e, quando disponível, os componentes da decomposição publicada; "
                "essa comparação não demonstra que a mudança no consumo causou a mudança na receita."
            )
        base = {
            "contract_version": "text-to-sql-f1-compound-v1",
            "answer": answer,
            "active_gold_batch": result.scope.batch_ref,
            "staging_manifest_digest": manifest_digest,
            "staging_csv_digest": manifest["csv_sha256"] if manifest else None,
            "method": result.scope.windows.method,
            "windows": result.scope.windows.model_dump(mode="json"),
            "municipalities": [item.model_dump(mode="json") for item in municipalities],
            "limitations": limitations,
        }
        digest = hashlib.sha256(json.dumps(
            base, ensure_ascii=False, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        return cls(**base, evidence_digest=digest)


class SqlPresentationColumn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    role: Literal["dimension", "measure"]
    semantic_id: Literal[
        "competency",
        "municipality",
        "neighborhood",
        "consumption_class",
        "inspection_priority",
        "revenue_total",
        "energy_total",
        "attendance_total",
        "attendance_accumulated_total",
        "satisfaction_accumulated_average",
        "gd_units_total",
        "gd_consumption_drop_units",
        "satisfaction_average",
        "dec_value",
        "fec_value",
        "feeders_included",
        "feeders_excluded",
        "average_consumption_per_uc",
        "average_ticket",
        "effective_tariff",
        "units_count",
        "period_0_total",
        "period_1_total",
        "period_0_minus_period_1",
        "period_1_minus_period_0",
        "period_0_growth_percent",
    ]
    unit: str | None = Field(default=None, max_length=64)


class SqlPresentationRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(pattern=r"^row_[1-9][0-9]{0,2}$")
    cells: tuple[str | None, ...] = Field(min_length=1, max_length=32)


class SqlAnalysisPresentation(BaseModel):
    """Texto e tabela projetados da mesma evidência imutável do executor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[
        "text-to-sql-f1-presentation-v1",
        "text-to-sql-f1-presentation-v2",
        "text-to-sql-f1-presentation-v3",
        "text-to-sql-f1-presentation-v4",
        "text-to-sql-f1-presentation-v5",
        "text-to-sql-f1-presentation-v6",
        "text-to-sql-f1-presentation-v7",
        "text-to-sql-f1-presentation-v8",
        "text-to-sql-f1-presentation-v9",
        "text-to-sql-f1-presentation-v10",
        "text-to-sql-f1-presentation-v11",
        "text-to-sql-f1-presentation-v12",
    ]
    state: Literal["ready", "empty", "all_measures_null"]
    operation: Literal[
        "total",
        "monthly_series",
        "grouped_total",
        "ranking",
        "comparison",
        "grain_read",
        "accumulated_total",
        "average",
        "snapshot_total",
        "accumulated_average",
        "ratio_of_sums",
        "weighted_continuity",
    ]
    answer: PresentationText
    period: str = Field(min_length=1, max_length=100)
    filters: tuple[str, ...] = Field(max_length=20)
    universe: tuple[str, ...] = Field(max_length=3)
    limitations: tuple[str, ...] = Field(max_length=10)
    columns: tuple[SqlPresentationColumn, ...] = Field(min_length=1, max_length=32)
    rows: tuple[SqlPresentationRow, ...] = Field(max_length=100)
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class SqlContinuityMetricResult(BaseModel):
    """One independently validated DEC or FEC result in a paired answer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence: SqlEvidence
    presentation: SqlAnalysisPresentation

    @model_validator(mode="after")
    def validate_metric_presentation(self):
        from app.services.genai_sql_presentation import present_sql_evidence

        if (
            self.evidence.metric_id
            not in {
                "network.equivalent_interruption_duration",
                "network.equivalent_interruption_frequency",
            }
            or self.evidence.interpretation.operation
            not in {"weighted_continuity", "grain_read"}
            or self.presentation != present_sql_evidence(self.evidence)
        ):
            raise ValueError("resultado DEC/FEC exige evidência e apresentação compatíveis")
        return self


class SqlContinuityPairAnalysis(BaseModel):
    """Two separate DEC/FEC calculations over the same publication and scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["text-to-sql-f1-continuity-pair-v1"]
    answer: PresentationText
    active_gold_batch: str = Field(min_length=1, max_length=200)
    dec: SqlContinuityMetricResult
    fec: SqlContinuityMetricResult
    limitations: tuple[str, ...] = Field(max_length=10)
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_pair(self):
        dec, fec = self.dec.evidence, self.fec.evidence
        warning = "Valores observados; cobertura do alimentador não certificada."
        expected_answer = " ".join(
            item.removesuffix(f" {warning}")
            for item in (self.dec.presentation.answer, self.fec.presentation.answer)
        )
        expected_limitations = ()
        if "observed_uncertified" in {dec.coverage_quality, fec.coverage_quality}:
            expected_answer = f"{expected_answer} {warning}"
            expected_limitations = (warning,)
        if (
            dec.metric_id != "network.equivalent_interruption_duration"
            or fec.metric_id != "network.equivalent_interruption_frequency"
            or dec.batch_ref != self.active_gold_batch
            or fec.batch_ref != self.active_gold_batch
            or dec.interpretation != fec.interpretation.model_copy(
                update={"metric_id": dec.metric_id}
            )
            or dec.coverage_quality != fec.coverage_quality
            or self.answer != expected_answer
            or self.limitations != expected_limitations
        ):
            raise ValueError("DEC e FEC devem compartilhar publicação e recorte")
        base = self.model_dump(mode="json", exclude={"evidence_digest"})
        actual = hashlib.sha256(
            json.dumps(
                base,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if actual != self.evidence_digest:
            raise ValueError("digest da evidência DEC/FEC divergente")
        return self

    @classmethod
    def from_evidence(cls, dec: SqlEvidence, fec: SqlEvidence):
        from app.services.genai_sql_presentation import present_sql_evidence

        dec_presentation = present_sql_evidence(dec)
        fec_presentation = present_sql_evidence(fec)
        warning = "Valores observados; cobertura do alimentador não certificada."
        answer = " ".join(
            item.removesuffix(f" {warning}")
            for item in (dec_presentation.answer, fec_presentation.answer)
        )
        limitations = []
        if "observed_uncertified" in {dec.coverage_quality, fec.coverage_quality}:
            answer = f"{answer} {warning}"
            limitations.append(warning)
        payload = {
            "contract_version": "text-to-sql-f1-continuity-pair-v1",
            "answer": answer,
            "active_gold_batch": dec.batch_ref,
            "dec": {"evidence": dec.model_dump(mode="json"), "presentation": dec_presentation.model_dump(mode="json")},
            "fec": {"evidence": fec.model_dump(mode="json"), "presentation": fec_presentation.model_dump(mode="json")},
            "limitations": limitations,
        }
        digest = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return cls(**payload, evidence_digest=digest)


class SqlServiceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["text-to-sql-f1-service-summary-v1"] = "text-to-sql-f1-service-summary-v1"
    active_gold_batch: str
    start_month: str
    end_month: str
    protocols: int = Field(ge=0)
    satisfaction: ExactDecimal | None
    monthly: tuple[tuple[str, ExactDecimal, ExactDecimal], ...] = ()
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @property
    def answer(self) -> str:
        satisfaction = (
            f"{self.satisfaction.replace('.', ',')} pontos"
            if self.satisfaction is not None else "indisponível"
        )
        protocols = format(self.protocols, ",").replace(",", ".")
        return (
            f"De {self.start_month} a {self.end_month}, foram registrados "
            f"{protocols} protocolos. A satisfação média foi {satisfaction}."
        )


class SqlFinancialComparisonRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    period: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    consumption_kwh: ExactDecimal | None
    revenue_brl: ExactDecimal | None
    observed_price_brl_per_kwh: ExactDecimal | None


class SqlFinancialComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["text-to-sql-f1-financial-comparison-v1"] = "text-to-sql-f1-financial-comparison-v1"
    active_gold_batch: str = Field(min_length=1, max_length=200)
    municipality: str = Field(min_length=1, max_length=120)
    start_month: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    end_month: str = Field(pattern=r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
    answer: PresentationText
    metric_ids: tuple[
        Literal["billing.revenue", "energy.consumption", "billing.effective_tariff"],
        ...,
    ] = Field(min_length=1, max_length=3)
    monthly: tuple[SqlFinancialComparisonRow, ...] = Field(min_length=1, max_length=12)
    limitations: tuple[PresentationText, ...] = Field(min_length=1, max_length=10)
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_digest(self):
        if self.start_month > self.end_month or len(set(self.metric_ids)) != len(self.metric_ids):
            raise ValueError("períodos da comparação financeira inválidos")
        expected_periods = []
        year, month = (int(value) for value in self.start_month.split("-"))
        end_year, end_month = (int(value) for value in self.end_month.split("-"))
        while (year, month) <= (end_year, end_month):
            expected_periods.append(f"{year:04d}-{month:02d}")
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        if tuple(row.period for row in self.monthly) != tuple(expected_periods):
            raise ValueError("competências da comparação financeira incompletas")
        metrics = set(self.metric_ids)
        for row in self.monthly:
            if (row.consumption_kwh is not None) != ("energy.consumption" in metrics):
                raise ValueError("consumo diverge das métricas solicitadas")
            if (row.revenue_brl is not None) != ("billing.revenue" in metrics):
                raise ValueError("faturamento diverge das métricas solicitadas")
            if "billing.effective_tariff" not in metrics and row.observed_price_brl_per_kwh is not None:
                raise ValueError("preço observado não solicitado")
        payload = self.model_dump(mode="json", exclude={"evidence_digest"})
        actual = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        if actual != self.evidence_digest:
            raise ValueError("digest da comparação financeira diverge")
        return self


class SqlPublishedDecomposition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["text-to-sql-f1-published-decomposition-v1"] = "text-to-sql-f1-published-decomposition-v1"
    active_gold_batch: str
    answer: PresentationText
    windows: PublishedWindows
    records: tuple[tuple[str, str, ExactDecimal], ...]
    groups_without_base: int = Field(ge=0)
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class SqlFeederOccurrences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["text-to-sql-f1-feeder-occurrences-v1"] = "text-to-sql-f1-feeder-occurrences-v1"
    active_gold_batch: str
    feeder: str
    month: str
    occurrences: int = Field(ge=1)
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class SqlAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: AICorrelationId
    audit_reference: Annotated[
        str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{32}$")
    ]
    status: Literal["answered", "needs_clarification", "unsupported"]
    evidence: SqlEvidence | None = None
    presentation: SqlAnalysisPresentation | None = None
    compound_analysis: (
        SqlCompoundAnalysis | SqlServiceSummary | SqlFinancialComparison |
        SqlPublishedDecomposition | SqlFeederOccurrences | None
    ) = None
    continuity_pair_analysis: SqlContinuityPairAnalysis | None = None
    clarification: SqlClarification | None = None
    unsupported_reason: SqlUnsupported | None = None
    continuation_token: (
        Annotated[str, StringConstraints(min_length=1, max_length=16000)] | None
    ) = None

    @model_validator(mode="after")
    def validate_result_shape(self):
        if self.status == "answered":
            if self.continuity_pair_analysis is not None:
                if (
                    self.compound_analysis is not None
                    or self.evidence is not None
                    or self.presentation is not None
                    or self.clarification is not None
                    or self.unsupported_reason is not None
                ):
                    raise ValueError("DEC/FEC composto não pode misturar envelopes")
                return self
            if self.compound_analysis is not None:
                if self.evidence is not None or self.presentation is not None or self.clarification is not None or self.unsupported_reason is not None:
                    raise ValueError("evidência composta não pode misturar o envelope de métrica única")
                return self
            from app.services.genai_sql_presentation import present_sql_evidence

            if (
                self.evidence is None
                or self.presentation is None
                or self.clarification is not None
                or self.unsupported_reason is not None
                or self.presentation.evidence_digest != self.evidence.evidence_digest
                or self.presentation.state
                != {
                    "available": "ready",
                    "empty": "empty",
                    "all_measures_null": "all_measures_null",
                }[self.evidence.status]
                or len(self.presentation.rows) != len(self.evidence.rows)
                or tuple(column.key for column in self.presentation.columns)
                != tuple(column.name for column in self.evidence.columns)
                or tuple(
                    (column.role, column.unit) for column in self.presentation.columns
                )
                != tuple((column.role, column.unit) for column in self.evidence.columns)
                or self.presentation.operation != self.evidence.interpretation.operation
                or self.presentation != present_sql_evidence(self.evidence)
            ):
                raise ValueError("resposta exige apresentação vinculada à evidência")
            for index, row in enumerate(self.presentation.rows, start=1):
                if (
                    row.observation_id != f"row_{index}"
                    or len(row.cells) != len(self.presentation.columns)
                    or row.cells != self.evidence.rows[index - 1]
                ):
                    raise ValueError("tabela de apresentação diverge da evidência")
        elif self.evidence is not None or self.presentation is not None or self.compound_analysis is not None or self.continuity_pair_analysis is not None:
            raise ValueError(
                "estado não respondido não pode incluir resultado quantitativo"
            )
        elif self.status == "needs_clarification":
            if self.clarification is None or self.unsupported_reason is not None:
                raise ValueError("esclarecimento exige somente a pergunta pendente")
        elif self.unsupported_reason is None or self.clarification is not None:
            raise ValueError("capacidade não suportada exige motivo tipado")
        return self

    @classmethod
    def from_run(cls, correlation_id, run, *, audit_reference):
        candidate = run.candidate
        if run.evidence is not None:
            from app.services.genai_sql_presentation import present_sql_evidence

            return cls(
                correlation_id=correlation_id,
                audit_reference=audit_reference,
                status="answered",
                evidence=run.evidence,
                presentation=present_sql_evidence(run.evidence),
            )
        return cls(
            correlation_id=correlation_id,
            audit_reference=audit_reference,
            status=candidate.status,
            clarification=candidate.clarification,
            unsupported_reason=candidate.unsupported_reason,
        )

    @classmethod
    def from_compound(cls, correlation_id, analysis, *, audit_reference):
        return cls(
            correlation_id=correlation_id,
            audit_reference=audit_reference,
            status="answered",
            compound_analysis=analysis,
        )

    @classmethod
    def from_continuity_pair(cls, correlation_id, analysis, *, audit_reference):
        return cls(
            correlation_id=correlation_id,
            audit_reference=audit_reference,
            status="answered",
            continuity_pair_analysis=analysis,
        )


class SqlAnalysisRequest(AIQuestionRequest):
    """Pergunta F1 autenticada; contexto de follow-up exige token assinado."""

    conversation_id: (
        Annotated[str, StringConstraints(pattern=r"^[a-f0-9-]{36}$")] | None
    ) = None
    continuation_token: (
        Annotated[str, StringConstraints(min_length=1, max_length=16000)] | None
    ) = None
