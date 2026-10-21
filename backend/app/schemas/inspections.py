from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.operational import OrderAction, OrderStatus


class OrderCreateRequest(BaseModel):
    uc_id: str
    reason: str
    priority: str = "MEDIA"
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None

    @field_validator("uc_id", "reason")
    @classmethod
    def validate_non_empty(cls, v: str, info) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"O campo '{info.field_name}' não pode ser vazio.")
        return v.strip()

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        valid = {"BAIXA", "MEDIA", "ALTA", "CRITICA"}
        if not isinstance(v, str) or v.upper() not in valid:
            raise ValueError(f"Prioridade inválida. Valores aceitos: {', '.join(sorted(valid))}")
        return v.upper()


class OrderUpdateRequest(BaseModel):
    status: Optional[OrderStatus] = None
    notes: Optional[str] = None
    result: Optional[str] = None
    version: Optional[int] = None


class OrderResultRequest(BaseModel):
    result: str
    notes: Optional[str] = None
    version: Optional[int] = None

    @field_validator("result")
    @classmethod
    def validate_result(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("O registro de resultado de campo não pode ser vazio.")
        return v.strip()


class OrderCancelRequest(BaseModel):
    reason: Optional[str] = None
    version: Optional[int] = None


class OrderHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    previous_status: Optional[OrderStatus] = None
    new_status: OrderStatus
    action: OrderAction
    notes: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uc_id: str
    reason: str
    priority: str
    status: OrderStatus
    notes: Optional[str] = None
    result: Optional[str] = None
    cancellation_reason: Optional[str] = None
    version: int = 1
    idempotency_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime
