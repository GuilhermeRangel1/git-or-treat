"""Envelope público da análise Text-to-SQL; nunca expõe SQL nem parâmetros."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.ai import AICorrelationId, AIQuestionRequest
from app.schemas.genai_evidence import PublishedWindows
from app.schemas.sql_evidence import SqlEvidence
from app.schemas.sql_generation import SqlClarification, SqlUnsupported

PresentationText = Annotated[str, StringConstraints(min_length=1, max_length=4000)]
ExactDecimal = Annotated[str, StringConstraints(pattern=r"^-?(?:0|[1-9][0-9]{0,100})(?:\.[0-9]{1,100})?$")]


class SqlCompoundRevenueEffect(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    consumption_class: str = Field(min_length=1, max_length=120)
    neighborhood: str = Field(min_length=1, max_length=120)
    variation_brl: ExactDecimal
    volume_effect_brl: ExactDecimal | None
    price_effect_brl: ExactDecimal | None
    interaction_effect_brl: ExactDecimal | None
    state: Literal["CALCULADA_BASE_COMUM", "SEM_BASE_COMUM"]


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
    staging_manifest_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    staging_csv_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    method: Literal["PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3"]
    windows: PublishedWindows
    municipalities: tuple[SqlCompoundMunicipality, ...] = Field(max_length=100)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=10)
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_digest(self):
        payload = self.model_dump(mode="json", exclude={"evidence_digest"})
        actual = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        if actual != self.evidence_digest:
            raise ValueError("digest da evidência composta diverge")
        return self

    @classmethod
    def from_sources(cls, result, manifest, manifest_digest):
        municipalities = tuple(SqlCompoundMunicipality(
            municipality=row.consumption.municipality,
            previous_consumption_kwh=format(row.consumption.previous_kwh, "f"),
            current_consumption_kwh=format(row.consumption.current_kwh, "f"),
            change_kwh=format(row.change_kwh, "f"),
            change_percent=format(row.change_percent, ".6f"),
            revenue_by_class=tuple(SqlCompoundRevenueEffect(
                consumption_class=effect.consumption_class,
                neighborhood=effect.neighborhood,
                variation_brl=format(effect.variation_brl, "f"),
                volume_effect_brl=format(effect.volume_effect_brl, "f") if effect.volume_effect_brl is not None else None,
                price_effect_brl=format(effect.price_effect_brl, "f") if effect.price_effect_brl is not None else None,
                interaction_effect_brl=format(effect.interaction_effect_brl, "f") if effect.interaction_effect_brl is not None else None,
                state=effect.state,
            ) for effect in row.revenue_by_class),
        ) for row in result.municipalities)
        answer = (
            "A comparação preço-volume foi calculada para jul/2024–jun/2025 "
            "contra jul/2025–jun/2026. A tabela mostra municípios com queda de "
            "consumo e a decomposição da receita por classe de consumo."
        )
        base = {
            "contract_version": "text-to-sql-f1-compound-v1",
            "answer": answer,
            "active_gold_batch": result.scope.batch_ref,
            "staging_manifest_digest": manifest_digest,
            "staging_csv_digest": manifest["csv_sha256"],
            "method": manifest["method"],
            "windows": result.scope.windows.model_dump(mode="json"),
            "municipalities": [item.model_dump(mode="json") for item in municipalities],
            "limitations": [
                "A decomposição foi lida de staging local Gold v2, não da Gold ativa.",
                "Consumo e faturamento vêm de agregações independentes; as bases populacionais podem diferir.",
                "Preço observado não é tarifa regulada e não indica causalidade.",
                "A resposta lista apenas municípios com queda de consumo; efeitos de receita são detalhados por classe.",
                "Para grupos sem base comum comparável, os efeitos de volume, preço e interação permanecem sem valor.",
            ],
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


class SqlAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: AICorrelationId
    audit_reference: Annotated[
        str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{32}$")
    ]
    status: Literal["answered", "needs_clarification", "unsupported"]
    evidence: SqlEvidence | None = None
    presentation: SqlAnalysisPresentation | None = None
    compound_analysis: SqlCompoundAnalysis | None = None
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
