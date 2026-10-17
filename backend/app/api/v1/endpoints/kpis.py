from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.common import AnalyticalResponse, AnalyticalMetadata

router = APIRouter()


@router.get("", summary="Listar indicadores agregados")
def get_kpis(
    competencia: Optional[str] = Query(None, description="Competência no formato YYYY-MM"),
    municipio: Optional[str] = Query(None, description="Filtro de município"),
    classe: Optional[str] = Query(None, description="Classe de consumo (Residencial, Comercial, etc.)"),
    db: Session = Depends(get_db),
):
    """
    Retorna métricas consolidadas (receita, consumo kWh, UCs ativas) sustentadas pela Gold.
    """
    # Placeholder que retorna envelope conceitual
    filtros = {k: v for k, v in {"competencia": competencia, "municipio": municipio, "classe": classe}.items() if v}
    return AnalyticalResponse(
        data={
            "receita_total": 0.0,
            "energia_consumida_kwh": 0.0,
            "ucs_ativas": 0,
        },
        metadata=AnalyticalMetadata(
            periodo=competencia or "todas",
            filtros_aplicados=filtros,
            unidade="BRL / kWh / UCs",
            qualidade_cobertura="Mock / Inicial",
        ),
    )
