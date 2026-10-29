import os

# Define banco de testes antes de carregar configurações do app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from app.main import app
from app.core.config import settings
from app.core.database import Base, get_db
from tests.support.database import (
    override_get_db,
    test_engine,
)
from tests.support.client import client_with_overrides


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Cria esquema antes dos testes e remove após
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def clean_test_db():
    with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    yield
    with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture
def client(clean_test_db, monkeypatch):
    # O ambiente local pode usar demo; os testes de acesso selecionam seu modo.
    # Fixtures demo/OIDC substituem estes valores explicitamente após client.
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ORDERS_AUTH_MODE", "service")
    with client_with_overrides(app, {get_db: override_get_db}) as test_client:
        yield test_client
