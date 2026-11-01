"""SQLAlchemy database models."""
from app.models.base import TimestampMixin
from app.models.operational import InspectionOrder, OrderStatus, OperationalOrderHistory, OrderAction
from app.models.analytical import GoldIndicador
from app.models.auth import AuthSession, AuthUser
from app.models import gold_load  # Registra o contrato atual sem alterar snapshots Alembic.
from app.models import gold_v2_load  # Registra o snapshot v2 em schema físico separado.
from app.models import genai_audit  # Registra a trilha operacional sem acesso pelo leitor Gold.

__all__ = ["TimestampMixin", "InspectionOrder", "OrderStatus", "OperationalOrderHistory", "OrderAction", "GoldIndicador", "AuthUser", "AuthSession"]
