"""SQLAlchemy metadata registry shared by the ORM models and Alembic."""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
