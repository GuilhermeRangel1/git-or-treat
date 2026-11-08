"""A projeção pública preserva valores e estados da evidência F1."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from app.schemas.sql_analysis import SqlAnalysisResponse
from app.schemas.sql_evidence import SqlEvidence, sql_evidence_digest
from app.schemas.sql_generation import SqlInterpretation, SqlResultColumn
from app.services.genai_sql_presentation import present_sql_evidence


def _evidence(
    *,
    rows,
    status,
    grouped=False,
    operation=None,
    dimension="municipality",
    period_start="2025-01-01",
    period_end="2025-12-31",
    growth=False,
    ranking_direction=None,
):
    if operation == "comparison":
        columns = [
            {
                "name": "current",
                "role": "measure",
                "value_type": "decimal",
                "unit": "R$",
            },
            {
                "name": "previous",
                "role": "measure",
                "value_type": "decimal",
                "unit": "R$",
            },
            {
                "name": "difference",
                "role": "measure",
                "value_type": "decimal",
                "unit": "R$",
            },
        ]
        measure_semantics = {
            "current": "period_0_total",
            "previous": "period_1_total",
            "difference": "period_0_minus_period_1",
        }
        if growth:
            columns.append(
                {
                    "name": "growth",
                    "role": "measure",
                    "value_type": "decimal",
                    "unit": "%",
                }
            )
            measure_semantics["growth"] = "period_0_growth_percent"
        if grouped:
            columns.insert(
                0,
                {
                    "name": dimension,
                    "role": "dimension",
                    "value_type": "string",
                },
            )
    else:
        columns = (
            [
                {"name": dimension, "role": "dimension", "value_type": "string"},
                {
                    "name": "revenue",
                    "role": "measure",
                    "value_type": "decimal",
                    "unit": "R$",
                },
            ]
            if grouped
            else [
                {
                    "name": "revenue",
                    "role": "measure",
                    "value_type": "decimal",
                    "unit": "R$",
                }
            ]
        )
        measure_semantics = {"revenue": "revenue_total"}
    names = [column["name"] for column in columns]
    normalized_rows = tuple(tuple(row) for row in rows)
    payload = {
        "evidence_contract_version": (
            "text-to-sql-f1-evidence-v2" if growth else "text-to-sql-f1-evidence-v1"
        ),
        "source_id": "gold.local",
        "source_table": "gold_v2.diagnostico_receita",
        "metric_id": "billing.revenue",
        "coverage_quality": "certified",
        "batch_ref": (
            "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:"
            "12345678-1234-4123-8123-123456789abc"
        ),
        "context_version": "a" * 64,
        "admission_digest": "b" * 64,
        "execution_digest": "c" * 64,
        "result_digest": "0" * 64,
        "mapping_version": "gold-catalog-v2",
        "dictionary_version": "gold-dictionary-v2",
        "interpretation": SqlInterpretation.model_validate({
            "metric_id": "billing.revenue",
            "operation": operation or ("grouped_total" if grouped else "total"),
            "aggregation": "sum",
            "periods": (
                [
                    {"start": "2025-01-01", "end": "2025-12-31"},
                    {"start": "2024-01-01", "end": "2024-12-31"},
                ]
                if operation == "comparison"
                else [{"start": period_start, "end": period_end}]
            ),
            "filters": [],
            "group_by": [dimension] if grouped else [],
            "ranking_direction": ranking_direction
            or ("desc" if operation == "ranking" else None),
            "ranking_limit": (
                5 if operation == "ranking" else 10 if ranking_direction else None
            ),
        }),
        "columns": columns,
        "measure_semantics": measure_semantics,
        "dimension_semantics": {dimension: dimension} if grouped else {},
        "rows": normalized_rows,
        "status": status,
    }
    payload["interpretation"] = SqlInterpretation.model_validate(
        payload["interpretation"]
    )
    payload["columns"] = tuple(
        SqlResultColumn.model_validate(column) for column in payload["columns"]
    )
    provisional = SqlEvidence.model_construct(**payload, evidence_digest="0" * 64)
    result = {
        "columns": names,
        "measure_semantics": [
            [name, measure_semantics[name]]
            for name in names
            if name in measure_semantics
        ],
        "rows": provisional.rows,
        "status": provisional.status,
    }
    payload["result_digest"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    provisional = SqlEvidence.model_construct(**payload, evidence_digest="0" * 64)
    digest_payload = provisional.model_dump(mode="json", exclude={"evidence_digest"})
    digest_payload.pop("coverage_quality", None)
    payload["evidence_digest"] = sql_evidence_digest(digest_payload)
    return SqlEvidence.model_validate(payload)


def test_grouped_table_is_identical_to_evidence_and_answer_uses_exact_decimal():
    evidence = _evidence(rows=[["Recife", "1234.50"]], status="available", grouped=True)

    presentation = present_sql_evidence(evidence)

    assert presentation.state == "ready"
    assert (
        presentation.answer
        == "O faturamento por Município no período janeiro a dezembro de 2025 está detalhado na tabela."
    )
    assert presentation.columns[1].unit == "R$"
    assert presentation.rows[0].cells == evidence.rows[0]
    assert presentation.evidence_digest == evidence.evidence_digest
    assert presentation.limitations == (
        "Faturamento representa valor faturado e não confirma recebimento ou pagamento.",
    )


def test_weighted_continuity_presents_weighted_value_and_included_excluded_feeders():
    columns = (
        SqlResultColumn(name="dec_value", role="measure", value_type="decimal", unit="horas por UC"),
        SqlResultColumn(name="feeders_included", role="measure", value_type="integer", unit="alimentadores"),
        SqlResultColumn(name="feeders_excluded", role="measure", value_type="integer", unit="alimentadores"),
    )
    row = ("1.25", "3", "2")
    result_payload = {
        "columns": [column.name for column in columns],
        "measure_semantics": [["dec_value", "dec_value"], ["feeders_included", "feeders_included"], ["feeders_excluded", "feeders_excluded"]],
        "rows": (row,),
        "status": "available",
    }
    payload = {
        "evidence_contract_version": "text-to-sql-f1-evidence-v12",
        "source_id": "gold.local",
        "source_table": "gold_v2.indicadores_dec_fec",
        "metric_id": "network.equivalent_interruption_duration",
        "coverage_quality": "observed_uncertified",
        "batch_ref": "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "context_version": "a" * 64,
        "admission_digest": "b" * 64,
        "execution_digest": "c" * 64,
        "result_digest": hashlib.sha256(json.dumps(result_payload, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
        "mapping_version": "gold-catalog-v2",
        "dictionary_version": "gold-dictionary-v2",
        "interpretation": SqlInterpretation.model_validate({
            "metric_id": "network.equivalent_interruption_duration",
            "operation": "weighted_continuity",
            "aggregation": "weighted_ratio",
            "periods": [{"start": "2025-01-01", "end": "2025-03-31"}],
            "filters": [], "group_by": [], "ranking_direction": None, "ranking_limit": None,
        }),
        "columns": columns,
        "measure_semantics": {"dec_value": "dec_value", "feeders_included": "feeders_included", "feeders_excluded": "feeders_excluded"},
        "dimension_semantics": {},
        "rows": (row,),
        "status": "available",
    }
    provisional = SqlEvidence.model_construct(**payload, evidence_digest="0" * 64)
    payload["evidence_digest"] = sql_evidence_digest(
        provisional.model_dump(mode="json", exclude={"evidence_digest"})
    )
    evidence = SqlEvidence.model_validate(payload)

    presentation = present_sql_evidence(evidence)

    assert presentation.contract_version == "text-to-sql-f1-presentation-v11"
    assert presentation.operation == "weighted_continuity"
    assert "DEC ponderado" in presentation.answer
    assert "3 alimentadores elegíveis" in presentation.answer
    assert "2 alimentadores observados" in presentation.answer
    assert presentation.rows[0].cells == evidence.rows[0]
    assert presentation.columns[1].unit == "alimentadores"
    assert presentation.limitations == ("Valores observados; cobertura do alimentador não certificada.",)


def test_neighborhood_dimension_is_presented_as_bairro():
    evidence = _evidence(
        rows=[["Boa Vista", "12.50"]],
        status="available",
        grouped=True,
        dimension="neighborhood",
    )
    presentation = present_sql_evidence(evidence)

    assert presentation.columns[0].label == "Bairro"
    assert "por Bairro" in presentation.answer


def test_comparison_presents_backend_derived_growth_and_zero_baseline():
    evidence = _evidence(
        rows=[["150.03", "80.00", "70.03", "87.54"]],
        status="available",
        operation="comparison",
        growth=True,
    )

    presentation = present_sql_evidence(evidence)

    assert presentation.contract_version == "text-to-sql-f1-presentation-v2"
    assert presentation.columns[-1].semantic_id == "period_0_growth_percent"
    assert presentation.columns[-1].unit == "%"
    assert presentation.rows[0].cells[-1] == "87.54"
    assert (
        "variação percentual sobre o período de referência foi 87,54%"
        in presentation.answer
    )

    zero_base = _evidence(
        rows=[["80.00", "0.00", "80.00", None]],
        status="available",
        operation="comparison",
        growth=True,
    )
    assert "base zero" in present_sql_evidence(zero_base).answer


def test_total_answer_prints_exact_money_and_period():
    presentation = present_sql_evidence(
        _evidence(rows=[["950.00"]], status="available")
    )

    assert presentation.answer == (
        "O faturamento total no período janeiro a dezembro de 2025 foi R$ 950,00."
    )


def test_attendance_evidence_presents_monthly_protocol_count():
    interpretation = SqlInterpretation.model_validate(
        {
            "metric_id": "service.attendance",
            "operation": "total",
            "aggregation": "count_non_null",
            "periods": [{"start": "2026-06-01", "end": "2026-06-30"}],
            "filters": [],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        }
    )
    columns = (
        SqlResultColumn(
            name="attendance",
            role="measure",
            value_type="integer",
            unit="protocolos",
        ),
    )
    payload = {
        "evidence_contract_version": "text-to-sql-f1-evidence-v4",
        "source_id": "gold.local",
        "source_table": "gold_v2.atendimentos_uc",
        "metric_id": "service.attendance",
        "coverage_quality": "certified",
        "batch_ref": "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "context_version": "a" * 64,
        "admission_digest": "b" * 64,
        "execution_digest": "c" * 64,
        "result_digest": "0" * 64,
        "mapping_version": "gold-catalog-v2",
        "dictionary_version": "gold-dictionary-v2",
        "interpretation": interpretation,
        "columns": columns,
        "measure_semantics": {"attendance": "attendance_total"},
        "dimension_semantics": {},
        "rows": (("6433",),),
        "status": "available",
    }
    provisional = SqlEvidence.model_construct(**payload, evidence_digest="0" * 64)
    result_digest_payload = {
        "columns": ["attendance"],
        "measure_semantics": [["attendance", "attendance_total"]],
        "rows": (("6433",),),
        "status": "available",
    }
    payload["result_digest"] = hashlib.sha256(
        json.dumps(
            result_digest_payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    provisional = SqlEvidence.model_construct(**payload, evidence_digest="0" * 64)
    digest_payload = provisional.model_dump(mode="json", exclude={"evidence_digest"})
    digest_payload.pop("coverage_quality", None)
    evidence_digest = sql_evidence_digest(digest_payload)
    evidence = SqlEvidence.model_validate(
        {**payload, "evidence_digest": evidence_digest}
    )
    presentation = present_sql_evidence(evidence)
    assert presentation.contract_version == "text-to-sql-f1-presentation-v3"
    assert presentation.answer == (
        "Foram abertos 6.433 protocolos no período junho de 2026."
    )
    assert presentation.columns[0].unit == "protocolos"
    assert presentation.limitations == ()


def test_satisfaction_evidence_presents_monthly_average_and_null_rule():
    interpretation = SqlInterpretation.model_validate(
        {
            "metric_id": "service.satisfaction",
            "operation": "average",
            "aggregation": "average_non_null",
            "periods": [{"start": "2026-06-01", "end": "2026-06-30"}],
            "filters": [],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        }
    )
    columns = (
        SqlResultColumn(
            name="satisfaction",
            role="measure",
            value_type="decimal",
            unit="pontos",
        ),
    )
    payload = {
        "evidence_contract_version": "text-to-sql-f1-evidence-v7",
        "source_id": "gold.local",
        "source_table": "gold_v2.atendimentos_uc",
        "metric_id": "service.satisfaction",
        "coverage_quality": "certified",
        "batch_ref": "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "context_version": "a" * 64,
        "admission_digest": "b" * 64,
        "execution_digest": "c" * 64,
        "result_digest": "0" * 64,
        "mapping_version": "gold-catalog-v2",
        "dictionary_version": "gold-dictionary-v2",
        "interpretation": interpretation,
        "columns": columns,
        "measure_semantics": {"satisfaction": "satisfaction_average"},
        "dimension_semantics": {},
        "rows": (("4.25",),),
        "status": "available",
    }
    result_payload = {
        "columns": ["satisfaction"],
        "measure_semantics": [["satisfaction", "satisfaction_average"]],
        "rows": (("4.25",),),
        "status": "available",
    }
    payload["result_digest"] = hashlib.sha256(
        json.dumps(
            result_payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    provisional = SqlEvidence.model_construct(**payload, evidence_digest="0" * 64)
    digest_payload = provisional.model_dump(mode="json", exclude={"evidence_digest"})
    payload["evidence_digest"] = sql_evidence_digest(digest_payload)
    presentation = present_sql_evidence(SqlEvidence.model_validate(payload))
    assert presentation.contract_version == "text-to-sql-f1-presentation-v6"
    assert presentation.operation == "average"
    assert presentation.answer == (
        "A nota média de satisfação no período junho de 2026 foi 4,25 pontos."
    )
    assert presentation.columns[0].semantic_id == "satisfaction_average"
    assert presentation.limitations == (
        "Média das notas informadas; valores ausentes são excluídos e zero é válido.",
    )


def test_gd_units_evidence_is_presented_as_a_snapshot_of_the_published_lot():
    interpretation = SqlInterpretation.model_validate(
        {
            "metric_id": "energy.gd_units",
            "operation": "snapshot_total",
            "aggregation": "count_non_null",
            "periods": [],
            "filters": [
                {
                    "dimension_id": "generation.distributed",
                    "operator": "eq",
                    "values": ["Sim"],
                }
            ],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        }
    )
    columns = (
        SqlResultColumn(
            name="gd_units",
            role="measure",
            value_type="integer",
            unit="UCs",
        ),
    )
    payload = {
        "evidence_contract_version": "text-to-sql-f1-evidence-v8",
        "source_id": "gold.local",
        "source_table": "gold_v2.variacao_consumo_uc",
        "metric_id": "energy.gd_units",
        "coverage_quality": "certified",
        "batch_ref": "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "context_version": "a" * 64,
        "admission_digest": "b" * 64,
        "execution_digest": "c" * 64,
        "result_digest": "0" * 64,
        "mapping_version": "gold-catalog-v2",
        "dictionary_version": "gold-dictionary-v2",
        "interpretation": interpretation,
        "columns": columns,
        "measure_semantics": {"gd_units": "gd_units_total"},
        "dimension_semantics": {},
        "rows": (("42",),),
        "status": "available",
    }
    result_payload = {
        "columns": ["gd_units"],
        "measure_semantics": [["gd_units", "gd_units_total"]],
        "rows": (("42",),),
        "status": "available",
    }
    payload["result_digest"] = hashlib.sha256(
        json.dumps(
            result_payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    provisional = SqlEvidence.model_construct(**payload, evidence_digest="0" * 64)
    payload["evidence_digest"] = sql_evidence_digest(
        provisional.model_dump(mode="json", exclude={"evidence_digest"})
    )

    presentation = present_sql_evidence(SqlEvidence.model_validate(payload))

    assert presentation.contract_version == "text-to-sql-f1-presentation-v7"
    assert presentation.period == "Cadastro de GD no lote"
    assert presentation.answer == (
        "Foram identificadas 42 UCs com GD cadastrada no lote publicado."
    )
    assert presentation.limitations == (
        "Retrato do cadastro no lote publicado; não informa quando a GD entrou em operação nem confirma geração ou injeção.",
    )


def test_gd_consumption_drop_presentation_states_fixed_windows_and_limitations():
    interpretation = SqlInterpretation.model_validate(
        {
            "metric_id": "energy.gd_consumption_drop",
            "operation": "snapshot_total",
            "aggregation": "count_gd_drop",
            "periods": [],
            "filters": [
                {
                    "dimension_id": "generation.distributed",
                    "operator": "eq",
                    "values": ["Sim"],
                }
            ],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        }
    )
    columns = (
        SqlResultColumn(
            name="gd_drop_units",
            role="measure",
            value_type="integer",
            unit="UCs",
        ),
    )
    payload = {
        "evidence_contract_version": "text-to-sql-f1-evidence-v10",
        "source_id": "gold.local",
        "source_table": "gold_v2.variacao_consumo_uc",
        "metric_id": "energy.gd_consumption_drop",
        "coverage_quality": "certified",
        "batch_ref": "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "context_version": "a" * 64,
        "admission_digest": "b" * 64,
        "execution_digest": "c" * 64,
        "result_digest": "0" * 64,
        "mapping_version": "gold-catalog-v2",
        "dictionary_version": "gold-dictionary-v2",
        "interpretation": interpretation,
        "columns": columns,
        "measure_semantics": {"gd_drop_units": "gd_consumption_drop_units"},
        "dimension_semantics": {},
        "rows": (("5",),),
        "status": "available",
    }
    result_payload = {
        "columns": ["gd_drop_units"],
        "measure_semantics": [["gd_drop_units", "gd_consumption_drop_units"]],
        "rows": (("5",),),
        "status": "available",
    }
    payload["result_digest"] = hashlib.sha256(
        json.dumps(
            result_payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    provisional = SqlEvidence.model_construct(**payload, evidence_digest="0" * 64)
    payload["evidence_digest"] = sql_evidence_digest(
        provisional.model_dump(mode="json", exclude={"evidence_digest"})
    )

    presentation = present_sql_evidence(SqlEvidence.model_validate(payload))

    assert presentation.contract_version == "text-to-sql-f1-presentation-v9"
    assert presentation.period == "jul/2022–jun/2023 vs. jul/2025–jun/2026"
    assert presentation.answer == (
        "Foram identificadas 5 UCs nas janelas fixas "
        "jul/2022–jun/2023 vs. jul/2025–jun/2026 "
        "(Geração distribuída (cadastro): Sim)."
    )
    assert presentation.columns[0].semantic_id == "gd_consumption_drop_units"
    assert presentation.limitations == (
        "Queda bruta nas janelas fixas; exige ao menos seis meses com leitura em cada janela e não demonstra causa nem origem solar.",
    )


def test_accumulated_satisfaction_presents_historical_average_without_a_date_range():
    interpretation = SqlInterpretation.model_validate(
        {
            "metric_id": "service.accumulated_satisfaction",
            "operation": "accumulated_average",
            "aggregation": "average_non_null",
            "periods": [],
            "filters": [],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        }
    )
    columns = (
        SqlResultColumn(
            name="satisfaction",
            role="measure",
            value_type="decimal",
            unit="pontos",
        ),
    )
    payload = {
        "evidence_contract_version": "text-to-sql-f1-evidence-v9",
        "source_id": "gold.local",
        "source_table": "gold_v2.atendimentos_uc",
        "metric_id": "service.accumulated_satisfaction",
        "coverage_quality": "certified",
        "batch_ref": "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "context_version": "a" * 64,
        "admission_digest": "b" * 64,
        "execution_digest": "c" * 64,
        "result_digest": "0" * 64,
        "mapping_version": "gold-catalog-v2",
        "dictionary_version": "gold-dictionary-v2",
        "interpretation": interpretation,
        "columns": columns,
        "measure_semantics": {"satisfaction": "satisfaction_accumulated_average"},
        "dimension_semantics": {},
        "rows": (("4.25",),),
        "status": "available",
    }
    result_payload = {
        "columns": ["satisfaction"],
        "measure_semantics": [["satisfaction", "satisfaction_accumulated_average"]],
        "rows": (("4.25",),),
        "status": "available",
    }
    payload["result_digest"] = hashlib.sha256(
        json.dumps(
            result_payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    provisional = SqlEvidence.model_construct(**payload, evidence_digest="0" * 64)
    payload["evidence_digest"] = sql_evidence_digest(
        provisional.model_dump(mode="json", exclude={"evidence_digest"})
    )

    presentation = present_sql_evidence(SqlEvidence.model_validate(payload))

    assert presentation.contract_version == "text-to-sql-f1-presentation-v8"
    assert presentation.operation == "accumulated_average"
    assert presentation.period == "Histórico acumulado"
    assert presentation.answer == (
        "A média das notas individuais válidas no histórico publicado foi 4,25 pontos. "
        "O intervalo e a completude histórica não são conhecidos."
    )
    assert presentation.limitations == (
        "Média das notas válidas do histórico publicado; o intervalo e a completude histórica não são conhecidos.",
    )


@pytest.mark.parametrize(
    ("metric_id", "meaning", "unit", "expected"),
    [
        (
            "network.equivalent_interruption_duration",
            "dec_value",
            "horas por UC",
            (
                "DEC no período junho de 2026 (Alimentador: ALIM-01): 1,25 horas por UC. "
                "Valores observados; cobertura do alimentador não certificada."
            ),
        ),
        (
            "network.equivalent_interruption_frequency",
            "fec_value",
            "interrupções por UC",
            (
                "FEC no período junho de 2026 (Alimentador: ALIM-01): 0,75 interrupções por UC. "
                "Valores observados; cobertura do alimentador não certificada."
            ),
        ),
    ],
)
def test_continuity_presents_one_grain_value_and_uncertified_coverage_warning(
    metric_id,
    meaning,
    unit,
    expected,
):
    interpretation = SqlInterpretation.model_validate(
        {
            "metric_id": metric_id,
            "operation": "grain_read",
            "aggregation": "key_grain_read",
            "periods": [{"start": "2026-06-01", "end": "2026-06-30"}],
            "filters": [
                {
                    "dimension_id": "network.feeder",
                    "operator": "eq",
                    "values": ["ALIM-01"],
                }
            ],
            "group_by": [],
            "ranking_direction": None,
            "ranking_limit": None,
        }
    )
    columns = (
        SqlResultColumn(name="value", role="measure", value_type="decimal", unit=unit),
    )
    payload = {
        "evidence_contract_version": "text-to-sql-f1-evidence-v5",
        "source_id": "gold.local",
        "source_table": "gold_v2.indicadores_dec_fec",
        "metric_id": metric_id,
        "coverage_quality": "observed_uncertified",
        "batch_ref": "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        "context_version": "a" * 64,
        "admission_digest": "b" * 64,
        "execution_digest": "c" * 64,
        "result_digest": "0" * 64,
        "mapping_version": "gold-catalog-v2",
        "dictionary_version": "gold-dictionary-v2",
        "interpretation": interpretation,
        "columns": columns,
        "measure_semantics": {"value": meaning},
        "dimension_semantics": {},
        "rows": (("1.25" if meaning == "dec_value" else "0.75",),),
        "status": "available",
    }
    result = {
        "columns": ["value"],
        "measure_semantics": [["value", meaning]],
        "rows": payload["rows"],
        "status": "available",
    }
    payload["result_digest"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    provisional = SqlEvidence.model_construct(**payload, evidence_digest="0" * 64)
    evidence_digest = sql_evidence_digest(
        provisional.model_dump(mode="json", exclude={"evidence_digest"})
    )
    evidence = SqlEvidence.model_validate(
        {**payload, "evidence_digest": evidence_digest}
    )
    presentation = present_sql_evidence(evidence)
    assert presentation.contract_version == "text-to-sql-f1-presentation-v4"
    assert presentation.answer == expected
    assert presentation.limitations == (
        "Valores observados; cobertura do alimentador não certificada.",
    )


def test_single_month_answer_uses_natural_portuguese_period():
    presentation = present_sql_evidence(
        _evidence(
            rows=[["950.00"]],
            status="available",
            period_start="2025-06-01",
            period_end="2025-06-30",
        )
    )
    assert presentation.answer == (
        "O faturamento total no período junho de 2025 foi R$ 950,00."
    )


def test_comparison_answer_uses_both_periods_and_exact_difference():
    presentation = present_sql_evidence(
        _evidence(
            rows=[["950.00", "800.00", "150.00"]],
            status="available",
            operation="comparison",
        )
    )
    assert presentation.answer == (
        "O faturamento foi R$ 950,00 de janeiro a dezembro de 2025 e R$ 800,00 de "
        "janeiro a dezembro de 2024. A diferença (primeiro período − segundo período) "
        "foi R$ 150,00."
    )


def test_grouped_comparison_presents_universe_and_both_periods():
    evidence = _evidence(
        rows=[["Recife", "150.03", "80.00", "70.03", "87.54"]],
        status="available",
        operation="comparison",
        grouped=True,
        growth=True,
    )

    presentation = present_sql_evidence(evidence)

    assert "Município" in presentation.answer
    assert "2025-01 a 2025-12 vs. 2024-01 a 2024-12" in presentation.answer
    assert presentation.universe == (
        "Municípios: todos os valores disponíveis no recorte",
    )
    assert presentation.rows[0].cells == evidence.rows[0]


def test_ranked_comparison_explains_direction_and_scope():
    evidence = _evidence(
        rows=[["Recife", "150.03", "180.00", "-29.97", "-16.65"]],
        status="available",
        operation="comparison",
        grouped=True,
        growth=True,
        ranking_direction="asc",
    )

    presentation = present_sql_evidence(evidence)

    assert "menores diferenças" in presentation.answer
    assert "primeiro período − segundo período" in presentation.answer


@pytest.mark.parametrize(
    ("rows", "status", "expected"),
    [
        ([], "empty", "Não há linhas"),
        (
            [["Recife", None, None, None, None]],
            "all_measures_null",
            "não trouxe valores",
        ),
    ],
)
def test_grouped_comparison_empty_states_name_both_windows(rows, status, expected):
    presentation = present_sql_evidence(
        _evidence(
            rows=rows,
            status=status,
            operation="comparison",
            grouped=True,
            growth=True,
        )
    )

    assert expected in presentation.answer
    assert "nos períodos 2025-01 a 2025-12 vs. 2024-01 a 2024-12" in presentation.answer


def test_monthly_series_is_presented_as_rows_not_derived_from_prose():
    evidence = _evidence(
        rows=[["2025-01-01", "10.00"], ["2025-02-01", "12.00"]],
        status="available",
        grouped=True,
        operation="monthly_series",
        dimension="competency",
    )

    presentation = present_sql_evidence(evidence)

    assert "está na tabela" in presentation.answer
    assert [row.cells for row in presentation.rows] == [
        ("2025-01-01", "10.00"),
        ("2025-02-01", "12.00"),
    ]


@pytest.mark.parametrize(
    ("rows", "status", "state", "answer_fragment"),
    [
        ([], "empty", "empty", "Não há linhas"),
        ([[None]], "all_measures_null", "all_measures_null", "não trouxe valores"),
    ],
)
def test_empty_and_null_measure_states_remain_distinct(
    rows, status, state, answer_fragment
):
    presentation = present_sql_evidence(_evidence(rows=rows, status=status))

    assert presentation.state == state
    assert answer_fragment in presentation.answer


def test_ranking_summary_identifies_the_leading_group_and_exact_amount():
    evidence = _evidence(
        rows=[["Recife", "1234.50"], ["Olinda", "975.25"]],
        status="available",
        grouped=True,
        operation="ranking",
    )

    presentation = present_sql_evidence(evidence)

    assert presentation.answer.startswith(
        "O maior faturamento do recorte foi de Recife: R$ 1.234,50"
    )
    assert presentation.universe == (
        "Municípios: todos os valores disponíveis no recorte",
    )


def test_public_response_requires_presentation_and_audit_reference_bound_to_evidence():
    evidence = _evidence(rows=[["Recife", "1234.50"]], status="available", grouped=True)
    run = SimpleNamespace(evidence=evidence, candidate=None)
    response = SqlAnalysisResponse.from_run("0" * 32, run, audit_reference="1" * 32)

    assert response.presentation is not None
    assert response.presentation.evidence_digest == evidence.evidence_digest
    assert response.audit_reference == "1" * 32

    with pytest.raises(ValueError, match="apresentação vinculada à evidência"):
        SqlAnalysisResponse.model_validate(
            {
                **response.model_dump(mode="json"),
                "presentation": {
                    **response.presentation.model_dump(mode="json"),
                    "evidence_digest": "f" * 64,
                },
            }
        )
