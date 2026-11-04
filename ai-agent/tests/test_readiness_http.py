"""Prontidão interna pela fábrica realmente usada pelo serviço."""

import pytest

from app.config import Settings
from app.main import create_app

from .conftest import InProcessClient
from .test_gold_readiness import _v2_facts

TOKEN = "test-readiness-service-token-0000000000"
PATH = "/api/v1/internal/gold-readiness"


def test_readiness_endpoint_uses_existing_evaluator_and_service_auth():
    app = create_app(settings=Settings(service_api_token=TOKEN))
    with InProcessClient(app) as client:
        assert client.post(PATH, json=_v2_facts()).status_code == 401
        response = client.post(
            PATH,
            json=_v2_facts(),
            headers={"Authorization": "Bearer " + TOKEN, "X-Correlation-ID": "a" * 32},
        )
    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "a" * 32
    assert response.json()["capabilities"]["atendimento.mensal"]["status"] == "available"


def test_readiness_is_disabled_without_configured_service_token_even_locally():
    with InProcessClient(create_app()) as client:
        assert client.post(PATH, json=_v2_facts()).status_code == 503


def test_readiness_http_blocks_monthly_without_closed_coverage():
    facts = _v2_facts()
    facts["coverage"]["atendimento.mensal"]["closed_periods"] = []
    with InProcessClient(create_app(settings=Settings(service_api_token=TOKEN))) as client:
        response = client.post(PATH, json=facts, headers={"Authorization": "Bearer " + TOKEN})
    assert response.status_code == 200
    assert response.json()["capabilities"]["atendimento.uc_acumulado"]["status"] == "available"
    assert response.json()["capabilities"]["atendimento.mensal"]["status"] == "unavailable"


def test_readiness_http_rejects_extra_business_records():
    facts = _v2_facts()
    facts["records"] = [{"note": "PRIVATE_MARKER_NOT_TO_RETURN"}]
    with InProcessClient(create_app(settings=Settings(service_api_token=TOKEN))) as client:
        response = client.post(PATH, json=facts, headers={"Authorization": "Bearer " + TOKEN})
    assert response.status_code == 422
    assert "PRIVATE_MARKER_NOT_TO_RETURN" not in response.text


@pytest.mark.parametrize(
    "capability,controls",
    [
        ("faturamento.receita", ("C01", "C02", "C04")),
        ("faturamento.receita_bairro", ("C12", "C13")),
        ("consumo.mensal_uc", ("C03", "C10")),
        ("interrupcoes.dec_fec", ("C11",)),
    ],
)
@pytest.mark.parametrize("case", ["available", "failed", "unapproved", "unclosed", "old_control"])
def test_readiness_http_domain_controls_and_coverage(capability, controls, case):
    facts = _v2_facts()
    reference = facts["batch_ref"]
    for control in controls:
        facts["control_results"][control] = {
            "batch_ref": reference,
            "status": "passed",
            "approved": True,
        }
    facts["coverage"][capability] = {
        "batch_ref": reference,
        "requested_periods": ["2001-01"],
        "observed_periods": ["2001-01"],
        "closed_periods": ["2001-01"],
        "has_undated_records": False,
    }
    if case == "failed":
        facts["control_results"][controls[0]]["status"] = "failed"
    if case == "unapproved":
        facts["control_results"][controls[0]]["approved"] = False
    if case == "unclosed":
        facts["coverage"][capability]["closed_periods"] = []
    if case == "old_control":
        from .test_gold_readiness import REF_B

        facts["control_results"][controls[0]]["batch_ref"] = REF_B
    with InProcessClient(create_app(settings=Settings(service_api_token=TOKEN))) as client:
        response = client.post(PATH, json=facts, headers={"Authorization": "Bearer " + TOKEN})
    assert response.status_code == 200
    report = response.json()["capabilities"]
    assert report[capability]["status"] == ("available" if case == "available" else "unavailable")
    assert report["atendimento.uc_acumulado"]["status"] == "available"
