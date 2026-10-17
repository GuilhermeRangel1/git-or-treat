from typing import Generic, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class AnalyticalMetadata(BaseModel):
    """Metadados de proveniência e contexto analítico conforme PRD."""
    unidade: Optional[str] = None
    periodo: Optional[str] = None
    filtros_aplicados: Dict[str, Any] = Field(default_factory=dict)
    lote_gold_versao: Optional[str] = None
    qualidade_cobertura: Optional[str] = None


class AnalyticalResponse(BaseModel, Generic[T]):
    """Envelope padrão para respostas que sustentam indicadores e métricas."""
    data: T
    metadata: AnalyticalMetadata = Field(default_factory=AnalyticalMetadata)


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope padrão para respostas paginadas."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
