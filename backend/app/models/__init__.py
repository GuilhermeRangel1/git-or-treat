"""SQLAlchemy database models."""
from app.models.base import TimestampMixin
from app.models.operational import InspectionOrder, OrderStatus, OperationalOrderHistory, OrderAction
from app.models.analytical import GoldIndicador
from app.models import gold_v1  # Registra o contrato CSV observado nas migrações.

__all__ = ["TimestampMixin", "InspectionOrder", "OrderStatus", "OperationalOrderHistory", "OrderAction", "GoldIndicador"]
