def test_ai_query_keeps_existing_placeholder_response(client):
    response = client.post(
        "/api/v1/ai/query",
        json={
            "intent": "consultar faturamento mensal",
            "target_table": "gold_indicadores",
            "filters": {"municipio": "Recife"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "intent": "consultar faturamento mensal",
        "table": "gold_indicadores",
        "records": [],
        "evidence": "Consulta analítica somente leitura",
    }


def test_ai_query_rejects_invalid_request_field_types(client):
    response = client.post(
        "/api/v1/ai/query",
        json={"intent": [], "target_table": "gold_indicadores", "filters": []},
    )

    assert response.status_code == 422
    assert "detail" in response.json()
    assert "error" not in response.json()


def test_ai_query_keeps_existing_table_allowlist_error(client):
    response = client.post(
        "/api/v1/ai/query",
        json={"intent": "consulta", "target_table": "operational_inspection_orders"},
    )

    assert response.status_code == 403
    assert response.json()["detail"].startswith("Tabela não permitida para o agente.")
