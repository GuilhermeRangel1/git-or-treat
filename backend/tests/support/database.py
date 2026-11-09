"""Isolated SQLAlchemy resources shared by backend tests."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

LOAD_TEST_DATABASE = os.getenv("TEST_TEXT_TO_SQL_LOAD") == "1"
_load_directory = TemporaryDirectory() if LOAD_TEST_DATABASE else None
TEST_DATABASE_URL = (
    f"sqlite:///{Path(_load_directory.name) / 'auth.db'}"
    if _load_directory is not None else "sqlite:///:memory:"
)

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool if LOAD_TEST_DATABASE else StaticPool,
    execution_options={
        "schema_translate_map": {
            "gold": None,
            "gold_v2": None,
            "gold_cadastro": None,
        }
    },
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
