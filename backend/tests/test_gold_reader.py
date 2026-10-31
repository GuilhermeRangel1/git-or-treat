"""Permissões reais: banco efêmero e credenciais artificiais, nunca o banco local."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from alembic import command
from app.models.gold_load import TABLES
from app.repositories.gold_publication import (
    GoldPublicationUnavailable,
    current_publication,
    publication_lineage,
)
from app.services.genai_publication import GoldPublicationContext
from app.services.gold_import import import_gold
from tests.support.migrations import alembic_config, migrated_database
from tests.test_gold_import import batch  # noqa: F401 - fixture pytest compartilhada


def test_reader_has_only_approved_selects_and_a_server_timeout(batch):  # noqa: F811 - fixture pytest
    admin_url = os.getenv("TEST_GOLD_READER_ADMIN_URL")
    migrator_url = os.getenv("TEST_POSTGRES_URL")
    if not admin_url or not migrator_url:
        pytest.skip("Configure TEST_GOLD_READER_ADMIN_URL para gold_reader_test descartável.")
    admin_address = make_url(admin_url)
    assert admin_address.get_backend_name() == "postgresql" and admin_address.database == "gold_reader_test"
    migrator_address = make_url(migrator_url)
    assert (admin_address.host, admin_address.port) == (migrator_address.host, migrator_address.port)
    owner = create_engine(migrator_address.set(database="gold_reader_test"), hide_parameters=True)
    admin = create_engine(admin_address, hide_parameters=True)
    password = uuid4().hex  # somente no servidor descartável
    reader = None
    try:
        with owner.connect() as connection, migrated_database(connection):
            imported = import_gold(owner, batch)
            script = (Path(__file__).parents[1] / "scripts/provision_gold_reader.sql").read_text(encoding="utf-8")
            sql = "\n".join(line for line in script.splitlines() if not line.startswith("\\"))
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as administrator:
                administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql(sql)  # provisionamento repetível
                # Um papel preexistente não pode trazer acesso de outro schema.
                administrator.exec_driver_sql("CREATE SCHEMA operational_extra")
                administrator.exec_driver_sql("CREATE TABLE operational_extra.private_records (id integer)")
                administrator.exec_driver_sql("GRANT USAGE ON SCHEMA operational_extra TO venergy_gold_reader")
                administrator.exec_driver_sql("GRANT SELECT ON operational_extra.private_records TO venergy_gold_reader")
                with pytest.raises(DBAPIError):
                    administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql("ROLLBACK")
                administrator.exec_driver_sql("REVOKE ALL ON operational_extra.private_records FROM venergy_gold_reader")
                administrator.exec_driver_sql("GRANT CREATE ON SCHEMA operational_extra TO venergy_gold_reader")
                with pytest.raises(DBAPIError):
                    administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql("ROLLBACK")
                administrator.exec_driver_sql("REVOKE CREATE ON SCHEMA operational_extra FROM venergy_gold_reader")
                administrator.exec_driver_sql("ALTER TABLE operational_extra.private_records OWNER TO venergy_gold_reader")
                with pytest.raises(DBAPIError):
                    administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql("ROLLBACK")
                administrator.exec_driver_sql("DROP TABLE operational_extra.private_records")
                administrator.exec_driver_sql("DROP SCHEMA operational_extra")
                administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql("GRANT INSERT ON gold.gold_consumo_mensal_uc TO PUBLIC")
                with pytest.raises(DBAPIError):
                    administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql("ROLLBACK")
                administrator.exec_driver_sql("REVOKE INSERT ON gold.gold_consumo_mensal_uc FROM PUBLIC")
                administrator.exec_driver_sql("CREATE TABLE gold.extra_private (id integer)")
                administrator.exec_driver_sql("GRANT SELECT ON gold.extra_private TO PUBLIC")
                with pytest.raises(DBAPIError):
                    administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql("ROLLBACK")
                administrator.exec_driver_sql("DROP TABLE gold.extra_private")
                administrator.exec_driver_sql(sql)
                administrator.exec_driver_sql(f"ALTER ROLE venergy_gold_reader PASSWORD '{password}'")
            reader = create_engine(admin_address.set(username="venergy_gold_reader", password=password), hide_parameters=True)
            publication = GoldPublicationContext.capture(reader)
            assert publication.planning_fields(reader)["batch_ref"] == imported["batch_ref"]
            with publication.execution_snapshot(reader) as snapshot:
                assert current_publication(snapshot).batch_ref == publication.batch_ref
                assert snapshot.scalar(text("SHOW transaction_read_only")) == "on"
            assert publication.synthesis_fields(reader)["expected_batch_ref"] == (
                imported["batch_ref"]
            )
            with reader.connect() as restricted:
                assert restricted.scalar(text("SHOW statement_timeout")) == "5s"
                assert restricted.scalar(text("SHOW default_transaction_read_only")) == "on"
                assert len(restricted.execute(select(TABLES["consumo_mensal_uc"])).all()) == 2
                assert current_publication(restricted).batch_ref == imported["batch_ref"]
                lineage = publication_lineage(restricted, imported["batch_ref"])
                assert set(lineage) == {"run_id_silver", "lote_bronze_silver"}
                with pytest.raises(GoldPublicationUnavailable):
                    current_publication(restricted, imported["batch_ref"].replace(imported["publication_id"], str(uuid4())))
            for forbidden in [
                "INSERT INTO gold.gold_consumo_mensal_uc (id_uc, competencia) VALUES ('FAKE-WRITE','2025-01')",
                "SELECT * FROM public.operational_inspection_orders",
                "SELECT * FROM public.operational_order_history",
                "SELECT * FROM public.gold_carga_atual",
                "SELECT * FROM public.gold_carga_tentativas",
                "CREATE TABLE gold.forbidden (id integer)",
            ]:
                with reader.connect() as restricted:
                    restricted.exec_driver_sql("SET TRANSACTION READ WRITE")
                    with pytest.raises(DBAPIError) as error:
                        restricted.exec_driver_sql(forbidden)
                    assert error.value.orig.sqlstate == "42501"
            with reader.connect() as restricted:
                with pytest.raises(DBAPIError) as error:
                    restricted.exec_driver_sql("SELECT pg_sleep(6)")
                assert error.value.orig.sqlstate == "57014"
            # O observador v2 usa somente a view mínima e as tabelas já permitidas.
            from app.models.gold_v2_load import BATCH
            from app.models.gold_v2_load import TABLES as V2_TABLES
            from app.services.gold_attendance_readiness import (
                observe_attendance_readiness,
            )
            with owner.begin() as write:
                write.execute(BATCH.update().values(schema_version="gold-csv-v2"))
                write.execute(V2_TABLES["visao_360_uc"].insert(), {
                    "id_uc":"UC_FAKE", "total_chamados_callcenter":0,
                    "media_satisfacao_atendimento":None})
                origin = write.execute(select(BATCH.c.origem)).scalar_one()
                write.execute(V2_TABLES["cobertura_dominios"].insert(), {
                    "dominio":"atendimentos", "competencia":"2001-01", "recorte":"DOMINIO",
                    "qtd_registros":0,"qtd_sem_competencia":0,"zero_registros_confirmado":False,
                    "estado_cobertura":"NAO_CERTIFICADA", "run_id_silver":origin["run_id_silver"],
                    "lote_bronze_silver":origin["lote_bronze_silver"]})
            facts = observe_attendance_readiness(reader, requested_periods=("2001-01",),
                approved_controls=frozenset({"C14", "C15"}))
            assert facts["control_results"]["C14"]["status"] == "passed"
            assert facts["control_results"]["C15"]["status"] == "passed"
            # ACL acompanha ALTER SET SCHEMA: downgrade precisa retirar o grant.
            command.downgrade(alembic_config(connection), "goldv1000002")
            connection.commit()
            with reader.connect() as restricted:
                with pytest.raises(DBAPIError) as error:
                    restricted.exec_driver_sql("SELECT * FROM public.gold_consumo_mensal_uc")
                assert error.value.orig.sqlstate == "42501"
            command.upgrade(alembic_config(connection), "head")
            connection.commit()
    finally:
        if reader is not None:
            reader.dispose()
        owner.dispose()
        admin.dispose()
