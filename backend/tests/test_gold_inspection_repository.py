from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import MetaData, create_engine, insert

from app.models.gold_v2_load import TABLES
from app.repositories.gold_inspections import GoldInspectionRepository
from app.schemas.analytics import AnalyticsFilters
from app.services.inspection_analytics import build_gold_queue_response, build_gold_suspicion_response


def test_gold_inspection_queue_preserves_grain_pagination_and_v2_fields():
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"gold_v2": None})
    metadata = MetaData()
    queue = TABLES["fila_inspecao"].to_metadata(metadata)
    variation = TABLES["variacao_consumo_uc"].to_metadata(metadata)
    profile = TABLES["visao_360_uc"].to_metadata(metadata)
    monthly = TABLES["consumo_mensal_uc"].to_metadata(metadata)
    TABLES["medidor_uc"].to_metadata(metadata)
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(insert(queue), [
            {"id_uc": "UC-1", "municipio": "Cidade A", "bairro": "Bairro A",
             "prioridade_inspecao": "REVISAR", "motivo_prioridade": "SEM HISTORICO DE CONSUMO",
             "ordem_prioridade_inspecao": None, "posicao_fila_inspecao": 2,
             "media_historica_recuperacao_kwh_por_inspecao": None,
             "intervalo_historico_recuperacao_inferior_kwh": None,
             "intervalo_historico_recuperacao_superior_kwh": None,
             "referencia_media_historica_recuperacao": None,
             "estado_media_historica_recuperacao": "SEM_REFERENCIA_VALIDADA",
             "estado_estimativa_recuperacao": "SEM_REFERENCIA_VALIDADA"},
            {"id_uc": "UC-2", "municipio": "Cidade A", "bairro": "Bairro B",
             "prioridade_inspecao": "BAIXA", "motivo_prioridade": "DEMAIS CASOS",
             "ordem_prioridade_inspecao": 4, "posicao_fila_inspecao": 1,
             "media_historica_recuperacao_kwh_por_inspecao": 13.5,
             "intervalo_historico_recuperacao_inferior_kwh": 0,
             "intervalo_historico_recuperacao_superior_kwh": 27,
             "referencia_media_historica_recuperacao": "global",
             "estado_media_historica_recuperacao": "DISPONIVEL_REFERENCIA_HISTORICA",
             "energia_estimada_recuperavel_kwh": None,
             "estado_estimativa_recuperacao": "ESTIMATIVA_UC_INDISPONIVEL"},
            {"id_uc": "UC-0", "municipio": "Cidade B", "bairro": "Bairro C",
             "prioridade_inspecao": "MEDIA", "motivo_prioridade": "NUNCA INSPECIONADO",
             "ordem_prioridade_inspecao": 3, "posicao_fila_inspecao": 1,
             "media_historica_recuperacao_kwh_por_inspecao": None,
             "intervalo_historico_recuperacao_inferior_kwh": None,
             "intervalo_historico_recuperacao_superior_kwh": None,
             "referencia_media_historica_recuperacao": None,
             "estado_media_historica_recuperacao": "SEM_REFERENCIA_VALIDADA",
             "estado_estimativa_recuperacao": "BASE_INSUFICIENTE"},
        ])
        connection.execute(insert(variation), [
            {"id_uc": "UC-1", "variacao_kwh": None},
            {"id_uc": "UC-2", "variacao_kwh": 5},
            {"id_uc": "UC-0", "variacao_kwh": 0},
        ])
        connection.execute(insert(profile), [
            {"id_uc": "UC-1", "status": "ATIVA"},
            {"id_uc": "UC-2", "status": "ATIVA"},
            {"id_uc": "UC-0", "status": "ATIVA"},
        ])
        connection.execute(insert(monthly), [
            {"id_uc": "UC-1", "competencia": month, "consumo_kwh": value,
             "qtd_leituras_observadas": 1, "qtd_leituras_validas": 1}
            for month, value in [("2024-08", 100), ("2024-09", 100), ("2024-10", 100),
                                 ("2024-11", 50), ("2024-12", 50), ("2025-01", 50)]
        ])
        connection.execute(insert(monthly), [
            {"id_uc": "UC-1", "competencia": month, "consumo_kwh": 300,
             "qtd_leituras_observadas": 1, "qtd_leituras_validas": 1}
            for month in ("2023-11", "2023-12", "2024-01")
        ])

        context = SimpleNamespace(
            connection=connection, lote="fixture", schema_version="gold-csv-v2",
            fingerprint="a" * 64, imported_at=datetime(2026, 10, 31, tzinfo=timezone.utc),
        )
        repository = GoldInspectionRepository(context)
        first_page = build_gold_queue_response(repository, AnalyticsFilters(), 1, 1, "queue_position", "asc")
        second_page = build_gold_queue_response(repository, AnalyticsFilters(), 2, 1, "queue_position", "asc")
        third_page = build_gold_queue_response(repository, AnalyticsFilters(), 3, 1, "queue_position", "asc")
        filtered_first = build_gold_queue_response(
            repository, AnalyticsFilters(municipio="Cidade A"), 1, 1, "queue_position", "asc",
        )
        filtered_second = build_gold_queue_response(
            repository, AnalyticsFilters(municipio="Cidade A"), 2, 1, "queue_position", "asc",
        )
        descending = build_gold_queue_response(repository, AnalyticsFilters(), 1, 1, "queue_position", "desc")
        detail = build_gold_suspicion_response(repository, "UC-1")
        incomplete = build_gold_suspicion_response(repository, "UC-2")

    assert first_page.pagination.total == 3
    assert first_page.pagination.total_pages == 3
    assert [item.uc_id for page in (first_page, second_page, third_page) for item in page.data.items] == ["UC-0", "UC-2", "UC-1"]
    assert descending.data.items[0].uc_id == "UC-1"
    first, second = third_page.data.items[0], second_page.data.items[0]
    assert first.reason == "SEM HISTORICO DE CONSUMO"
    assert first.queue_position == 2
    assert first.evidence.priority_order is None
    assert first.evidence.historical_recovery_status == "SEM_REFERENCIA_VALIDADA"
    assert second.evidence.historical_recovery_mean_kwh_per_inspection == 13.5
    assert second.evidence.historical_recovery_reference == "global"
    assert second.potential_recoverable_energy_kwh is None
    assert second.evidence.estimated_recoverable_energy_kwh is None
    assert second.evidence.recovery_estimate_status == "ESTIMATIVA_UC_INDISPONIVEL"
    assert filtered_first.pagination.total == 2
    assert filtered_first.data.neighborhoods == [
        {"municipio": "Cidade A", "bairro": "Bairro A"},
        {"municipio": "Cidade A", "bairro": "Bairro B"},
        {"municipio": "Cidade B", "bairro": "Bairro C"},
    ]
    assert [item.uc_id for item in filtered_first.data.items + filtered_second.data.items] == ["UC-2", "UC-1"]
    assert "insuficiente" in first_page.data.items[0].recovery_unavailable_reason
    assert detail.data.consumption_comparison.baseline_kwh == 300
    assert detail.data.consumption_comparison.recent_kwh == 150
    assert detail.data.consumption_comparison.change_percent == -50
    assert detail.data.investigation_potential.potential_kwh == 750
    assert incomplete.data.consumption_comparison.recent_kwh is None
