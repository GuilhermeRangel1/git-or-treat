from enum import Enum
from sqlalchemy import Column, String, Integer, BigInteger, Text, JSON, DateTime, ForeignKey, Enum as SQLEnum, Index, text, func
from app.db.base import Base
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
    # Persiste os nomes do enum (PENDING etc.) como VARCHAR; não cria CHECK por padrão.
    status = Column(SQLEnum(OrderStatus, native_enum=False, length=20), default=OrderStatus.PENDING, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    suspicion_reference = Column(String(64), nullable=True)
    suspicion_snapshot = Column(JSON, nullable=True)
    idempotency_key = Column(String(128), nullable=True)
    request_fingerprint = Column(String(64), nullable=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    cancellation_reason = Column(Text, nullable=True)

    __mapper_args__ = {"version_id_col": version}

    __table_args__ = (
        Index("idx_orders_status_priority", "status", "priority"),
        Index("uq_orders_idempotency", "idempotency_key", unique=True),
        Index("uq_orders_active_uc", "uc_id", unique=True,
              postgresql_where=text("status IN ('PENDING', 'IN_PROGRESS')"),
              sqlite_where=text("status IN ('PENDING', 'IN_PROGRESS')")),
    )


class OrderAction(str, Enum):
    CREATED = "CRIACAO"
    STATUS_UPDATED = "ATUALIZACAO_STATUS"
    RESULT_REGISTERED = "REGISTRO_RESULTADO"
    CANCELLED = "CANCELAMENTO"


class OperationalOrderHistory(Base):
    __tablename__ = "operational_order_history"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    order_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("operational_inspection_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status = Column(SQLEnum(OrderStatus, native_enum=False, length=20), nullable=True)
    new_status = Column(SQLEnum(OrderStatus, native_enum=False, length=20), nullable=False)
    action = Column(SQLEnum(OrderAction, native_enum=False, length=30), nullable=False)
    notes = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    actor = Column(String(255), nullable=True)
    order_version = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)
