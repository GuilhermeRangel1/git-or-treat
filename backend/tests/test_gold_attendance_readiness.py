"""Banco controlado real: fatos de prontidão não vêm do navegador."""
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.models.gold_v2_load import BATCH, TABLES
from app.services.gold_attendance_readiness import observe_attendance_readiness


@pytest.fixture
def published():
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False},
                           execution_options={"schema_translate_map": {"gold": None, "gold_v2": None}})
    BATCH.create(engine)
    for table in TABLES.values():
        table.create(engine)
    with engine.begin() as c:
        c.execute(BATCH.insert().values(id=1, lote="GOLD_20000101T000000Z_aaaaaaaa",
            schema_version="gold-csv-v2", publication_id=str(uuid4()), origem={
                "run_id_silver": "silver_test", "lote_bronze_silver": "bronze_test"},
            manifesto={}, fingerprint="f"*64, importado_em=datetime.now(UTC)))
        c.execute(TABLES["visao_360_uc"].insert(), {
            "id_uc": "UC_PRIVATE", "total_chamados_callcenter": 1,
            "media_satisfacao_atendimento": 0})
        c.execute(TABLES["atendimentos_uc"].insert(), {
            "protocolo": "PROTO_PRIVATE", "id_uc": "UC_PRIVATE", "nota_satisfacao": 0,
            "data_abertura": datetime(2001,1,1,tzinfo=UTC),
            "_nota_invalida": False,"_nota_negativa":False,"_abertura_futura":False})
        c.execute(TABLES["cobertura_dominios"].insert(), {
            "dominio":"atendimentos","competencia":"2001-01","recorte":"DOMINIO",
            "qtd_registros":1,"qtd_sem_competencia":0,"zero_registros_confirmado":False,
            "estado_cobertura":"NAO_CERTIFICADA", "run_id_silver":"silver_test",
            "lote_bronze_silver":"bronze_test"})
    yield engine
    engine.dispose()


def test_backend_observes_same_publication_without_certifying_partial_data(published):
    facts = observe_attendance_readiness(published, requested_periods=("2001-01",),
                                        approved_controls=frozenset({"C14","C15"}))
    assert facts["control_results"]["C14"]["status"] == "passed"
    assert facts["control_results"]["C15"]["status"] == "passed"
    assert facts["coverage"]["atendimento.mensal"]["closed_periods"] == []
    assert all(item["batch_ref"] == facts["batch_ref"]
               for item in facts["control_results"].values())
    assert "UC_PRIVATE" not in str(facts) and "PROTO_PRIVATE" not in str(facts)


def test_backend_detects_mean_mismatch(published):
    with published.begin() as c:
        c.execute(TABLES["visao_360_uc"].update().values(media_satisfacao_atendimento=4))
    facts = observe_attendance_readiness(published, requested_periods=("2001-01",),
                                        approved_controls=frozenset({"C14","C15"}))
    assert facts["control_results"]["C14"]["status"] == "failed"


@pytest.mark.parametrize("case", ["unchanged", "different_response", "publication_changed"])
def test_backend_transport_preserves_publication_and_rechecks_before_return(published, case):
    import asyncio

    import httpx

    from app.repositories.gold_publication import GoldPublicationChanged
    from app.services.genai_client import GenAIResponseInvalid
    from app.services.gold_readiness import evaluate_attendance_readiness

    def transport(request):
        import json
        facts = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer controlled-token"
        assert request.url.path == "/api/v1/internal/gold-readiness"
        assert facts["control_results"]["C14"]["status"] == "passed"
        assert facts["coverage"]["atendimento.mensal"]["closed_periods"] == []
        capabilities = {key: {"status":"unavailable", "reasons":["control_pending"]} for key in (
            "faturamento.receita", "faturamento.receita_bairro", "faturamento.preco_volume",
            "faturamento.faturas_em_aberto", "consumo.mensal_uc", "consumo.variacao_uc",
            "interrupcoes.dec_fec", "interrupcoes.uc_acumulado", "atendimento.uc_acumulado",
            "atendimento.mensal", "apoio.fila_inspecao", "apoio.medidor_uc", "apoio.energia_recuperavel")}
        ref = facts["batch_ref"]
        if case == "different_response":
            ref = ref.rsplit(":",1)[0] + ":" + str(uuid4())
        if case == "publication_changed":
            with published.begin() as c:
                c.execute(BATCH.update().values(publication_id=str(uuid4())))
        return httpx.Response(200, json={"readiness_version":"gold-readiness-v2",
            "batch_ref":ref,"lot_state":"partial","capabilities":capabilities},
            headers={"X-Correlation-ID":"a"*32})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            return await evaluate_attendance_readiness(published, http_client=client,
                base_url="http://genai",service_token="controlled-token",requested_periods=("2001-01",),
                approved_controls=frozenset({"C14","C15"}),correlation_id="a"*32)
    if case == "unchanged":
        assert asyncio.run(run()).lot_state == "partial"
    else:
        error = GenAIResponseInvalid if case == "different_response" else GoldPublicationChanged
        with pytest.raises(error):
            asyncio.run(run())



def test_backend_only_approves_controls_explicitly_accepted_by_operator(published):
    facts = observe_attendance_readiness(published, requested_periods=("2001-01",),
                                        approved_controls=frozenset())
    assert facts["control_results"]["C14"] == {
        "status":"passed", "approved":False, "batch_ref":facts["batch_ref"]}


@pytest.mark.parametrize("case", ["lineage", "counts", "future_flag", "invalid_note_flag"])
def test_backend_rejects_contradictions_in_persisted_source(published, case):
    with published.begin() as c:
        if case == "lineage":
            c.execute(TABLES["cobertura_dominios"].update().values(run_id_silver="other_run"))
        elif case == "counts":
            c.execute(TABLES["cobertura_dominios"].update().values(qtd_registros=0))
        elif case == "future_flag":
            c.execute(TABLES["atendimentos_uc"].update().values(_abertura_futura=True))
        else:
            c.execute(TABLES["atendimentos_uc"].update().values(_nota_invalida=True))
    facts = observe_attendance_readiness(published, requested_periods=("2001-01",),
                                        approved_controls=frozenset({"C14","C15"}))
    assert facts["control_results"]["C15"]["status"] == "failed"


def test_backend_accepts_closed_month_only_with_same_origin_and_evidence(published):
    with published.begin() as c:
        c.execute(TABLES["cobertura_dominios"].update().values(estado_cobertura="FECHADO",
            referencia_evidencia="controlled.reference",natureza_certificacao="EXTRACAO",
            data_corte_evidencia=datetime(2001,2,1,tzinfo=UTC)))
    facts = observe_attendance_readiness(published, requested_periods=("2001-01",),
                                        approved_controls=frozenset({"C14","C15"}))
    assert facts["control_results"]["C15"]["status"] == "passed"
    assert facts["coverage"]["atendimento.mensal"]["closed_periods"] == ["2001-01"]


def test_backend_closed_month_without_evidence_does_not_pass_control(published):
    with published.begin() as c:
        c.execute(TABLES["cobertura_dominios"].update().values(estado_cobertura="FECHADO"))
    facts = observe_attendance_readiness(published, requested_periods=("2001-01",),
                                        approved_controls=frozenset({"C14","C15"}))
    assert facts["control_results"]["C15"]["status"] == "failed"
    assert facts["coverage"]["atendimento.mensal"]["closed_periods"] == []



def test_sqlite_observer_restores_query_only_state(published):
    from sqlalchemy import text
    with published.connect() as c:
        before = c.scalar(text("PRAGMA query_only"))
    observe_attendance_readiness(published, requested_periods=("2001-01",),
                                approved_controls=frozenset())
    with published.connect() as c:
        assert c.scalar(text("PRAGMA query_only")) == before


@pytest.mark.parametrize("periods", [("2001-01", "2001-01"), (), ("2001-1",), ("0000-01",)])
def test_invalid_requested_periods_are_rejected_before_query(published, periods):
    with pytest.raises(ValueError):
        observe_attendance_readiness(published, requested_periods=periods,
                                    approved_controls=frozenset())
