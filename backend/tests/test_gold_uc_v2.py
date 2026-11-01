from datetime import date, datetime, timezone

from app.core.database import get_analytics_db
from app.main import app
from app.models.gold_load import BATCH
from app.models.gold_v2_load import TABLES
from app.services.gold_uc import meter_at_reference
from tests.test_gold_http import gold_client  # noqa: F401


def test_meter_reference_requires_one_unambiguous_candidate():
    reference = datetime(2025, 3, 1, tzinfo=timezone.utc)
    def meter(identifier, installed, removed=None, **flags):
        return {"id_medidor": identifier, "data_instalacao": installed, "data_retirada": removed,
                "ingestao_data": reference, "flag_instalacao_sentinela": False, "flag_instalacao_futura": False,
                "flag_retirada_sentinela": False, "flag_retirada_futura": False, **flags}
    old = meter("M-OLD", date(2024, 1, 1), date(2025, 1, 1))
    current = meter("M-CURRENT", date(2025, 1, 1))
    result = meter_at_reference([old, current])
    assert result["item"]["meter_id"] == "M-CURRENT" and result["status"] == "partial"
    assert "2025-03-01" in result["limitations"][0]
    assert meter_at_reference([current, meter("M-OTHER", date(2024, 1, 1))])["item"] is None
    assert meter_at_reference([current, meter("M-UNKNOWN", None)])["item"] is None
    assert meter_at_reference([meter("M-FLAG", date(2024, 1, 1), flag_retirada_sentinela=True)])["item"] is None
    assert meter_at_reference([meter("M-SAME-DAY", date(2024, 1, 1), date(2025, 3, 1))])["item"] is None
    assert meter_at_reference([old])["status"] == "unavailable"


def publish_fixture():
    dependency = app.dependency_overrides[get_analytics_db]()
    db = next(dependency)
    try:
        for name in ("visao_360_uc", "consumo_mensal_uc", "faturas_uc", "medidor_uc", "atendimentos_uc", "ocorrencias_uc", "gd_uc", "tratativas_uc"):
            TABLES[name].create(db.get_bind())
        db.execute(TABLES["visao_360_uc"].insert(), [
            {"id_uc": "FAKE-A", "municipio": "Cidade", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-1", "status": "ATIVA", "possui_gd": "Sim"},
            {"id_uc": "FAKE-B", "municipio": "Cidade", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-1", "status": "ATIVA", "possui_gd": "Não"},
        ])
        db.execute(TABLES["consumo_mensal_uc"].insert(), [
            {"id_uc": "FAKE-A", "competencia": "2025-01", "consumo_kwh": 0., "receita_reais": 20., "qtd_leituras_observadas": 1, "qtd_leituras_validas": 1},
            {"id_uc": "FAKE-A", "competencia": "2025-02", "consumo_kwh": 30., "receita_reais": 50., "qtd_leituras_observadas": 2, "qtd_leituras_validas": 1},
            {"id_uc": "FAKE-B", "competencia": "2025-01", "consumo_kwh": 999., "receita_reais": 999., "qtd_leituras_observadas": 1, "qtd_leituras_validas": 1},
        ])
        for invoice in [
            {"id_fatura": "F-1", "id_uc": "FAKE-A", "mes_referencia": "2025-01", "valor_total": 20., "data_vencimento": date(2025, 2, 10), "status": "EM ABERTO", "valor_fatura_declarada_em_aberto_reais": 20., "data_pagamento": date(2025, 2, 11), "flag_data_pagamento_inconclusiva": False, "flag_pagamento_antes_emissao": False, "flag_pagamento_sentinela": False, "flag_pagamento_futuro": False},
            {"id_fatura": "F-2", "id_uc": "FAKE-B", "mes_referencia": "2025-01", "valor_total": 999., "data_vencimento": date(2025, 2, 10), "status": None, "valor_fatura_declarada_em_aberto_reais": None},
            {"id_fatura": "F-3", "id_uc": "FAKE-A", "mes_referencia": "2025-02", "valor_total": 25., "status": "PAGA", "data_pagamento": date(2025, 3, 1), "flag_paga": True, "flag_tem_pagamento": True, "flag_data_pagamento_inconclusiva": False, "flag_pagamento_antes_emissao": False, "flag_pagamento_sentinela": False, "flag_pagamento_futuro": False},
        ]:
            db.execute(TABLES["faturas_uc"].insert().values(**invoice))
        db.execute(TABLES["medidor_uc"].insert().values(id_medidor="M-1", id_uc="FAKE-A", data_instalacao=None))
        db.execute(TABLES["medidor_uc"].insert().values(id_medidor="M-2", id_uc="FAKE-B", data_instalacao=date(2024, 1, 1), ingestao_data=datetime(2025, 3, 1, tzinfo=timezone.utc)))
        db.execute(TABLES["gd_uc"].insert().values(id_uc="FAKE-A", potencia_kwp=3.5, modalidade="AUTOCONSUMO"))
        db.execute(TABLES["atendimentos_uc"].insert().values(protocolo="C-1", id_uc="FAKE-A", data_abertura=datetime(2025, 1, 3, tzinfo=timezone.utc), assunto="Atendimento"))
        db.execute(TABLES["tratativas_uc"].insert().values(protocolo="C-1", id_uc="FAKE-A", posicao_historico=1, acao_categoria="CONTEUDO_RESTRITO", canal="TELEFONE"))
        db.execute(TABLES["ocorrencias_uc"].insert().values(id_ocorrencia="E-1", id_uc="FAKE-A", data_abertura=datetime(2025, 2, 3, tzinfo=timezone.utc), duracao_min=None))
        db.execute(BATCH.update().values(schema_version="gold-csv-v2", publication_id="test-publication"))
        db.commit()
    finally:
        dependency.close()


def test_uc_v2_search_overview_and_histories_keep_uc_scope_and_absence(gold_client):
    client, _ = gold_client
    publish_fixture()
    assert client.get("/api/v1/ucs?q=FAKE&page_size=1").json()["pagination"]["total"] == 2
    overview = client.get("/api/v1/ucs/FAKE-A/overview?start=2025-01&end=2025-02")
    assert overview.status_code == 200, overview.text
    data = overview.json()["data"]
    assert data["comparison"]["initial"]["measured_energy_kwh"]["value"] == 0
    assert data["comparison"]["final"]["measured_energy_kwh"]["status"] == "partial"
    assert data["comparison"]["billed_amount"]["percent_change"] is None
    assert data["current_meter"]["item"] is None
    other_overview = client.get("/api/v1/ucs/FAKE-B/overview?start=2025-01&end=2025-02").json()["data"]
    assert other_overview["current_meter"]["item"]["meter_id"] == "M-2"
    assert other_overview["current_meter"]["status"] == "partial"
    assert other_overview["gold_generation_record"] is False
    assert data["open_invoices"]["count"] == 1
    assert data["open_invoices"]["status"] == "partial"
    assert data["profile"]["customer_name"] is None
    assert data["gold_generation"]["capacity_kwp"] == 3.5
    assert data["gold_generation_record"] is True
    series = client.get("/api/v1/ucs/FAKE-A/history/consumption?start=2025-01&end=2025-03").json()
    assert [item["competencia"] for item in series["data"]["items"]] == ["2025-02", "2025-01"]
    assert series["data"]["items"][0]["measured_energy_kwh"] is None
    assert series["data"]["items"][1]["measured_energy_kwh"] == 0
    ordered = client.get("/api/v1/ucs/FAKE-A/history/consumption?start=2025-01&end=2025-03&order_by=measured_energy_kwh&page_size=1").json()
    assert ordered["data"]["items"][0]["competencia"] == "2025-01"
    assert ordered["pagination"]["total"] == 2
    empty_page = client.get("/api/v1/ucs/FAKE-A/history/consumption?start=2025-01&end=2025-03&page=3&page_size=1").json()
    assert empty_page["data"]["items"] == [] and empty_page["metadata"]["status"] == "partial"
    for section in ("invoices", "meters", "calls", "interruptions"):
        response = client.get(f"/api/v1/ucs/FAKE-A/history/{section}?start=2025-01&end=2025-02")
        assert response.status_code == 200, response.text
        assert response.json()["pagination"]["total"] == (2 if section == "invoices" else 1)
        assert response.json()["metadata"]["status"] == "partial"
    invoices = client.get("/api/v1/ucs/FAKE-A/history/invoices?start=2025-01&end=2025-02").json()["data"]["items"]
    invoice = next(item for item in invoices if item["invoice_id"] == "F-1")
    assert invoice["invoice_id"] == "F-1" and invoice["paid_amount"] is None and invoice["payment_status"] == "unknown"
    assert invoice["declared_status"] == "EM ABERTO" and invoice["declared_open_amount"] == 20
    assert invoice["declared_payment_date"] is None and invoice["payment_date"] is None
    assert next(item for item in invoices if item["invoice_id"] == "F-3")["declared_payment_date"] == "2025-03-01"
    assert client.get("/api/v1/ucs/FAKE-A/overview?start=2025-02&end=2025-02").json()["data"]["open_invoices"]["count"] == 0
    assert client.get("/api/v1/ucs/FAKE-A/overview?start=2024-01&end=2024-01").json()["data"]["open_invoices"]["count"] is None
    other = client.get("/api/v1/ucs/FAKE-B/history/invoices?start=2025-01&end=2025-02").json()["data"]["items"][0]
    assert other["declared_status"] is None and other["declared_open_amount"] is None
    event = client.get("/api/v1/ucs/FAKE-A/history/interruptions?start=2025-01&end=2025-02").json()["data"]["items"][0]
    assert event["duration_hours"] is None
    treatment = client.get("/api/v1/ucs/FAKE-A/history/treatments?start=2025-01&end=2025-02").json()
    assert treatment["data"]["items"] == [{"call_id": "C-1", "position": 1, "treatment_date": None, "action_category": "CONTEUDO_RESTRITO", "channel": "TELEFONE"}]
    assert client.get("/api/v1/ucs/FAKE-B/history/treatments?start=2025-01&end=2025-02").json()["data"]["items"] == []
    assert client.get("/api/v1/ucs/FAKE-A/history/invoices?order_by=payment_date").status_code == 422
    assert client.get("/api/v1/ucs/FAKE-A/history/distributed_generation").json()["metadata"]["status"] == "unavailable"
