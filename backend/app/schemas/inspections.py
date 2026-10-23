from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.models.operational import OrderStatus
from app.schemas.analytics import Pagination
from app.schemas.order_snapshot import OrderSnapshotV1

UCIdentifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
OrderReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OrderText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class QueueOrderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_version: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    rule_version: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    priority: Literal["BAIXA", "MEDIA", "ALTA"] = "MEDIA"
    notes: OrderText | None = None


class OrderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uc_id: UCIdentifier
    reason: OrderReason
    priority: Literal["BAIXA", "MEDIA", "ALTA"] = "MEDIA"
    notes: OrderText | None = None


class OrderUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus | None = None
    notes: OrderText | None = None
    result: OrderText | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set or self.model_fields_set == {"status"} and self.status is None:
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self


class OrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uc_id: str
    reason: str
    priority: str
    status: OrderStatus
    notes: str | None
    result: str | None
    created_at: datetime
    updated_at: datetime
    suspicion_reference: str | None = None


class OrderResponse(OrderSummary):
    suspicion_snapshot: OrderSnapshotV1 | None = None


class OrderPage(BaseModel):
    items: list[OrderSummary]
    pagination: Pagination


class OrderConflictDetail(BaseModel):
    code: str
    message: str
    order_id: int | None = None


class OrderConflictResponse(BaseModel):
    detail: str
    error: OrderConflictDetail
