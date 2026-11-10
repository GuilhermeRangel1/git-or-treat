"""App isolado para E2E de navegador TSQL-08 com PostgreSQL sintético.

Executar apenas no container descartável do teste. Não é importado pela API
normal nem adiciona rotas de suporte ao produto.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

from app.api.v1.endpoints.ai import get_question_gold_resources
from app.core.config import settings
from app.core.database import get_db
from app.core.passwords import hash_password
from app.db.base import Base
from app.main import app
from app.models.auth import AuthUser
from app.models.gold_v2 import TABLES
from app.schemas.genai_internal import AccessScope
from app.services.genai_audit import AuditStore  # noqa: F401 - ensure audit model import
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from tests.support.database import TestingSessionLocal, override_get_db, test_engine
from tests.test_genai_sql_public_route import BenchmarkCandidateClient

POSTGRES_URL = os.environ["TEST_TEXT_TO_SQL_URL"]
PASSWORD = "synthetic-browser-e2e-only"
FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "ai-agent"
    / "tests"
    / "fixtures"
    / "text_to_sql_f1_reference.json"
)


def _prepare_postgres():
    owner = create_engine(POSTGRES_URL, hide_parameters=True)
    with owner.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS gold_v2 CASCADE")
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS gold CASCADE")
        connection.exec_driver_sql("DROP ROLE IF EXISTS venergy_genai_reader")
        connection.exec_driver_sql("CREATE SCHEMA gold")
        connection.exec_driver_sql("CREATE SCHEMA gold_v2")
        connection.exec_driver_sql(
            "CREATE TABLE gold.publicacao_atual "
            "(schema_version text, lote text, publication_id text)"
        )
        connection.exec_driver_sql(
            "INSERT INTO gold.publicacao_atual VALUES "
            "('gold-csv-v2', 'GOLD_20261106T000000Z_aaaaaaaa', "
            "'12345678-1234-4123-8123-123456789abc')"
        )
        TABLES["diagnostico_receita"].create(connection)
        TABLES["consumo_receita_bairro"].create(connection)
        TABLES["consumo_mensal_uc"].create(connection)
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        rows = [
            {
                "competencia": row["competencia"],
                "municipio": row["municipio"],
                "classe_consumo": row["classe_consumo"],
                "subgrupo_tarifario": "FIXTURE",
                "bandeira_tarifaria": row["bandeira_tarifaria"],
                "possui_gd": "NAO",
                "receita_total_reais": row["receita_total_reais"],
            }
            for row in fixture["rows"]
        ]
        connection.execute(TABLES["diagnostico_receita"].insert(), rows)
        connection.exec_driver_sql(
            "CREATE ROLE venergy_genai_reader LOGIN NOSUPERUSER NOBYPASSRLS "
            "PASSWORD 'synthetic-test-only'"
        )
        connection.exec_driver_sql(
            "GRANT USAGE ON SCHEMA gold, gold_v2 TO venergy_genai_reader"
        )
        connection.exec_driver_sql(
            "GRANT SELECT ON gold.publicacao_atual, "
            "gold_v2.diagnostico_receita, gold_v2.consumo_receita_bairro, "
            "gold_v2.consumo_mensal_uc TO venergy_genai_reader"
        )
    reader = create_engine(
        make_url(POSTGRES_URL).set(
            username="venergy_genai_reader", password="synthetic-test-only"
        ),
        hide_parameters=True,
        pool_size=1,
        max_overflow=0,
    )
    return owner, reader, fixture


owner_engine, reader_engine, _fixture = _prepare_postgres()

Base.metadata.create_all(bind=test_engine)
app.dependency_overrides[get_db] = override_get_db
scope = AccessScope.model_validate(
    {
        "caller_ref": "session:" + "a" * 64,
        "profile_id": "v-energy-grid-360-gold",
        "source_id": "gold.local",
        "allowed_operations": ["read"],
        "allowed_metric_ids": ["billing.revenue"],
        "allowed_dimension_ids": [
            "geography.municipality",
            "customer.consumption_class",
        ],
    }
)
app.dependency_overrides[get_question_gold_resources] = lambda: (
    reader_engine,
    lambda: scope,
)
app.state.genai_question_client = BenchmarkCandidateClient(_fixture["cases"])
settings.APP_ENV = "development"
settings.ORDERS_AUTH_MODE = "session"
settings.ANALYTICS_SOURCE = "gold"
settings.GENAI_SQL_EXECUTION_ENABLED = True
settings.BACKEND_CORS_ORIGINS = ["http://127.0.0.1:5180"]
settings.BACKEND_ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

with TestingSessionLocal() as db:
    db.add(
        AuthUser(
            id=str(uuid4()),
            username="tsql8-browser-e2e",
            password_hash=hash_password(PASSWORD),
            permissions=[],
            profile="commercial",
            is_active=True,
        )
    )
    db.commit()
