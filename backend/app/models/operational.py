from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class OrderStatus(str, Enum):
    PENDING = "PENDENTE"
    IN_PROGRESS = "EM_ANDAMENTO"
    COMPLETED = "CONCLUIDA"
    CANCELLED = "CANCELADA"


class OrderAction(str, Enum):
    CREATED = "CRIACAO"
    STATUS_UPDATED = "ATUALIZACAO_STATUS"
    RESULT_REGISTERED = "REGISTRO_RESULTADO"
    CANCELLED = "CANCELAMENTO"


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
    cancellation_reason = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    idempotency_key = Column(String(100), nullable=True, unique=True, index=True)

    history = relationship(
        "OperationalOrderHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OperationalOrderHistory.created_at.asc()",
    )

    __table_args__ = (
        Index("idx_orders_status_priority", "status", "priority"),
    )


class OperationalOrderHistory(Base):
    """
    Trilha de auditoria das alterações nas ordens de inspeção (WEB-05).
    Registra data/hora, transições de status, ações executadas e notas de campo.
    """
    __tablename__ = "operational_order_history"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    order_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("operational_inspection_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status = Column(SQLEnum(OrderStatus, native_enum=False, length=20), nullable=True)
    new_status = Column(SQLEnum(OrderStatus, native_enum=False, length=20), nullable=False)
    action = Column(SQLEnum(OrderAction, native_enum=False, length=30), nullable=False)
    notes = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    order = relationship("InspectionOrder", back_populates="history")
