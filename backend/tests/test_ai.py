def test_ai_query_cannot_report_success_without_a_gold_reader(client):
    response = client.post(
        "/api/v1/ai/query",
        json={
            "intent": "consultar faturamento mensal",
            "target_table": "gold_indicadores",
            "filters": {"municipio": "Recife"},
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "contract_version": "v1",
        "status": "error",
        "correlation_id": response.headers["x-correlation-id"],
        "message": "A consulta analítica ainda não está disponível.",
        "error": {"code": "service_unavailable", "retryable": False},
    }


def test_ai_query_rejects_invalid_request_field_types(client):
    response = client.post(
        "/api/v1/ai/query",
        json={"intent": [], "target_table": "gold_indicadores", "filters": []},
    )

    assert response.status_code == 422
    assert "detail" in response.json()
    assert "error" not in response.json()


def test_ai_query_does_not_advertise_an_unapproved_table_allowlist(client):
    response = client.post(
        "/api/v1/ai/query",
        json={"intent": "consulta", "target_table": "operational_inspection_orders"},
    )

    assert response.status_code == 503
    assert "records" not in response.json()
    assert "gold_" not in response.text
