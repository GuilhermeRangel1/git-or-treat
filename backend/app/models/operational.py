from enum import Enum
from sqlalchemy import Column, String, Integer, BigInteger, Text, JSON, Enum as SQLEnum, Index, text
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

    __table_args__ = (
        Index("idx_orders_status_priority", "status", "priority"),
        Index("uq_orders_idempotency", "idempotency_key", unique=True),
        Index("uq_orders_active_suspicion", "suspicion_reference", unique=True,
              postgresql_where=text("status IN ('PENDING', 'IN_PROGRESS')"),
              sqlite_where=text("status IN ('PENDING', 'IN_PROGRESS')")),
    )
