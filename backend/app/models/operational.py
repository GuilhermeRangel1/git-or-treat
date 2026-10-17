from enum import Enum
from sqlalchemy import Column, String, Integer, BigInteger, Text, Enum as SQLEnum, Index
from app.core.database import Base
from app.models.base import TimestampMixin


class OrderStatus(str, Enum):
    PENDING = "PENDENTE"
    IN_PROGRESS = "EM_ANDAMENTO"
    COMPLETED = "CONCLUIDA"
    CANCELLED = "CANCELADA"


class InspectionOrder(Base, TimestampMixin):
    """
    Tabela operacional para ordens de inspeção geradas pelo portal (WEB-05).
    Mantida separada das tabelas analíticas Gold para preservar o ciclo de vida operacional.
    """
    __tablename__ = "operational_inspection_orders"

    # BigInteger previne estouro de inteiros em bancos relacionais com histórico longo
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    uc_id = Column(String(50), nullable=False, index=True)
    reason = Column(String(255), nullable=False)
    priority = Column(String(20), default="MEDIA", nullable=False, index=True)
    # native_enum=False armazena como VARCHAR com check constraint, facilitando futuras migrações sem lock de tipo
    status = Column(SQLEnum(OrderStatus, native_enum=False, length=20), default=OrderStatus.PENDING, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    result = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_orders_status_priority", "status", "priority"),
    )
