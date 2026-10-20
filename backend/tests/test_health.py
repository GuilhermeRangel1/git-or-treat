from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app


def database_override(session):
    def override():
        yield session

    return override


def test_health_reports_a_connected_database(client):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session = sessionmaker(bind=engine)()
    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = database_override(session)
    try:
        response = client.get("/api/v1/health")
    finally:
        app.dependency_overrides[get_db] = previous
        session.close()
        engine.dispose()

    assert response.status_code == 200
    assert response.json()["status"] == "online"
    assert response.json()["database"] == "connected"


def test_health_reports_a_disconnected_database_without_changing_http_status(client):
    class DisconnectedDatabase:
        def execute(self, statement):
            raise OperationalError(str(statement), {}, OSError("database unavailable"))

    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = database_override(DisconnectedDatabase())
    try:
        response = client.get("/api/v1/health")
    finally:
        app.dependency_overrides[get_db] = previous

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "disconnected"
    assert "database unavailable" not in response.text


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"
    assert response.json()["health"] == "/api/v1/health"


def test_kpis_endpoint_keeps_its_existing_placeholder_envelope(client):
    response = client.get("/api/v1/kpis")

    assert response.status_code == 200
    assert "data" in response.json()
    assert "metadata" in response.json()
