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
    *, rows, status, grouped=False, operation=None, dimension="municipality",
    period_start="2025-01-01", period_end="2025-12-31",
):
    if operation == "comparison":
        columns = [
            {"name": "current", "role": "measure", "value_type": "decimal", "unit": "R$"},
            {"name": "previous", "role": "measure", "value_type": "decimal", "unit": "R$"},
            {"name": "difference", "role": "measure", "value_type": "decimal", "unit": "R$"},
        ]
        measure_semantics = {
            "current": "period_0_total",
            "previous": "period_1_total",
            "difference": "period_0_minus_period_1",
        }
    else:
        columns = (
            [
                {"name": dimension, "role": "dimension", "value_type": "string"},
                {"name": "revenue", "role": "measure", "value_type": "decimal", "unit": "R$"},
            ]
            if grouped
            else [{"name": "revenue", "role": "measure", "value_type": "decimal", "unit": "R$"}]
        )
        measure_semantics = {"revenue": "revenue_total"}
    names = [column["name"] for column in columns]
    normalized_rows = tuple(tuple(row) for row in rows)
    payload = {
        "evidence_contract_version": "text-to-sql-f1-evidence-v1",
        "source_id": "gold.local",
        "source_table": "gold_v2.diagnostico_receita",
        "metric_id": "billing.revenue",
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
        "interpretation": {
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
            "ranking_direction": "desc" if operation == "ranking" else None,
            "ranking_limit": 5 if operation == "ranking" else None,
        },
        "columns": columns,
        "measure_semantics": measure_semantics,
        "dimension_semantics": {dimension: dimension} if grouped else {},
        "rows": normalized_rows,
        "status": status,
    }
    payload["interpretation"] = SqlInterpretation.model_validate(payload["interpretation"])
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
    payload["evidence_digest"] = sql_evidence_digest(
        provisional.model_dump(mode="json", exclude={"evidence_digest"})
    )
    return SqlEvidence.model_validate(payload)


def test_grouped_table_is_identical_to_evidence_and_answer_uses_exact_decimal():
    evidence = _evidence(rows=[["Recife", "1234.50"]], status="available", grouped=True)

    presentation = present_sql_evidence(evidence)

    assert presentation.state == "ready"
    assert presentation.answer == "O faturamento por Município no período janeiro a dezembro de 2025 está detalhado na tabela."
    assert presentation.columns[1].unit == "R$"
    assert presentation.rows[0].cells == evidence.rows[0]
    assert presentation.evidence_digest == evidence.evidence_digest
    assert presentation.limitations == (
        "Faturamento representa valor faturado e não confirma recebimento ou pagamento.",
    )


def test_total_answer_prints_exact_money_and_period():
    presentation = present_sql_evidence(
        _evidence(rows=[["950.00"]], status="available")
    )

    assert presentation.answer == (
        "O faturamento total no período janeiro a dezembro de 2025 foi R$ 950,00."
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
def test_empty_and_null_measure_states_remain_distinct(rows, status, state, answer_fragment):
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
    evidence = _evidence(
        rows=[["Recife", "1234.50"]], status="available", grouped=True
    )
    run = SimpleNamespace(evidence=evidence, candidate=None)
    response = SqlAnalysisResponse.from_run(
        "0" * 32, run, audit_reference="1" * 32
    )

    assert response.presentation is not None
    assert response.presentation.evidence_digest == evidence.evidence_digest
    assert response.audit_reference == "1" * 32

    with pytest.raises(ValueError, match="apresentação vinculada à evidência"):
        SqlAnalysisResponse.model_validate({
            **response.model_dump(mode="json"),
            "presentation": {
                **response.presentation.model_dump(mode="json"),
                "evidence_digest": "f" * 64,
            },
        })
