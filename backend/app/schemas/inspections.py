from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.operational import OrderStatus


class OrderCreateRequest(BaseModel):
    uc_id: str
    reason: str
    priority: str = "MEDIA"
    notes: Optional[str] = None


class OrderUpdateRequest(BaseModel):
    status: Optional[OrderStatus] = None
    notes: Optional[str] = None
    result: Optional[str] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uc_id: str
    reason: str
    priority: str
    status: OrderStatus
    notes: Optional[str]
    result: Optional[str]
    created_at: datetime
    updated_at: datetime
