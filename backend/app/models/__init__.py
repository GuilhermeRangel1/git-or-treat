"""SQLAlchemy database models."""
from app.models.base import TimestampMixin
from app.models.operational import InspectionOrder, OrderStatus, OperationalOrderHistory, OrderAction
from app.models.analytical import GoldIndicador
from app.models import gold_load  # Registra o contrato atual sem alterar snapshots Alembic.

__all__ = ["TimestampMixin", "InspectionOrder", "OrderStatus", "OperationalOrderHistory", "OrderAction", "GoldIndicador"]
