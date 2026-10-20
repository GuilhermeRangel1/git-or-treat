from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AIQueryRequest(BaseModel):
    intent: str
    target_table: str
    filters: Dict[str, Any] = Field(default_factory=dict)


class AIQueryResponse(BaseModel):
    status: str
    intent: str
    table: str
    records: List[Dict[str, Any]]
    evidence: str
