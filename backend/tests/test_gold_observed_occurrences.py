from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine

from app.models.gold_v2_load import TABLES
from app.repositories.gold_operations import GoldOperationsRepository


def test_occurrences_respect_feeder_period_pagination_and_missing_duration():
    engine = create_engine("sqlite:///:memory:", execution_options={"schema_translate_map": {"gold_v2": None}})
    table = TABLES["ocorrencias_uc"]
    with engine.begin() as connection:
        table.create(connection)
        for event, uc, feeder, opened, duration in [
            ("E1", "U1", "F1", datetime(2025, 1, 1, tzinfo=timezone.utc), 60),
            ("E2", "U2", "F1", datetime(2025, 1, 31, tzinfo=timezone.utc), None),
            ("E3", "U3", "F2", datetime(2025, 1, 1, tzinfo=timezone.utc), 10),
            ("E4", "U4", "F1", datetime(2025, 2, 1, tzinfo=timezone.utc), 10),
            ("E5", "U5", "F1", None, 10),
        ]:
            connection.execute(table.insert().values(id_ocorrencia=event, id_uc=uc, alimentador=feeder, data_abertura=opened, duracao_min=duration))
        repository = GoldOperationsRepository(SimpleNamespace(connection=connection))
        first, total = repository.occurrences("F1", "2025-01", "2025-01", 1, 1)
        second, total_again = repository.occurrences("F1", "2025-01", "2025-01", 2, 1)
        assert total == total_again == 2
        assert first[0]["event_id"] == "E2" and first[0]["duration_hours"] is None
        assert second[0]["event_id"] == "E1" and second[0]["duration_hours"] == 1
    engine.dispose()
