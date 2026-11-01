from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, Field, model_validator, field_validator

from app.models.operational import OrderStatus, OrderAction
from app.schemas.analytics import Pagination
from app.schemas.order_snapshot import OrderSnapshotV1, OrderSnapshotV2

UCIdentifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
OrderReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OrderText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class QueueOrderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_version: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    source_fingerprint: Annotated[str | None, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")] = None
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
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"version": 1, "status": "EM_ANDAMENTO"},
        {"version": 2, "notes": "Visita agendada"},
    ]})

    status: Literal[OrderStatus.PENDING, OrderStatus.IN_PROGRESS, OrderStatus.COMPLETED] | None = Field(None, description="Para cancelar, use POST /orders/{id}/cancel com confirmação do ID.")
    notes: OrderText | None = None
    result: OrderText | None = None
    version: int = Field(ge=1, strict=True, description="Versão atual retornada pela consulta da ordem. Recarregue após conflito 409.", examples=[1])

    @model_validator(mode="after")
    def validate_update(self):
        fields = self.model_fields_set - {"version"}
        if not fields or fields == {"status"} and self.status is None:
            raise ValueError("Informe ao menos um campo para atualizar.")
        if self.result is not None and not self.result.strip():
            raise ValueError("Resultado não pode estar vazio.")
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
    version: int
    cancellation_reason: str | None = None


class OrderResponse(OrderSummary):
    suspicion_snapshot: OrderSnapshotV1 | OrderSnapshotV2 | None = None


class OrderPage(BaseModel):
    items: list[OrderSummary]
    pagination: Pagination


class OrderConflictDetail(BaseModel):
    code: str
    message: str
    order_id: int | None = None


class OrderConflictResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "detail": "Ordem alterada por outra solicitação. Consulte novamente.",
        "error": {"code": "version_conflict", "message": "Ordem alterada por outra solicitação. Consulte novamente.", "order_id": 42},
    }]})
    detail: str
    error: OrderConflictDetail


class OrderAccessResponse(BaseModel):
    actor: str
    auth_mode: Literal["demo", "service", "session"]
    permissions: list[Literal["orders:read", "orders:write"]]


class OrderResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"version": 2, "result": "Sem irregularidade", "notes": "Inspeção realizada"},
    ]})
    result: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    notes: OrderText | None = None
    version: int = Field(ge=1, strict=True, description="Versão atual retornada pela consulta da ordem. Recarregue após conflito 409.", examples=[1])


class OrderCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"version": 1, "confirmed_order_id": 42, "reason": "Inspeção desnecessária"},
    ]})
    confirmed_order_id: int = Field(ge=1, strict=True)
    reason: OrderText | None = None
    version: int = Field(ge=1, strict=True, description="Versão atual retornada pela consulta da ordem. Recarregue após conflito 409.", examples=[1])


class OrderHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    previous_status: OrderStatus | None
    new_status: OrderStatus
    action: OrderAction
    notes: str | None
    details: str | None
    actor: str | None
    order_version: int | None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def history_timestamp_is_utc(cls, value: datetime) -> datetime:
        # SQLite CURRENT_TIMESTAMP is UTC but its driver returns a naive value.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
