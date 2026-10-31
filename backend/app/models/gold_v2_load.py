"""Registro de runtime para o snapshot físico Gold v2."""
from app.db.base import Base
from app.models import gold_load, gold_v2

SCHEMA_VERSION = "gold-csv-v2"
TABLES = {name: table.to_metadata(Base.metadata) for name, table in gold_v2.TABLES.items()}
BATCH = gold_load.BATCH
ATTEMPTS = gold_load.ATTEMPTS
