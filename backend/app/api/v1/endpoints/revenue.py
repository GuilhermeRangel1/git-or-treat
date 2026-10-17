from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.common import AnalyticalResponse, AnalyticalMetadata

router = APIRouter()


@router.get("", summary="Série temporal de receita e decomposição preço-volume")
def get_revenue_analysis(
    competencia_inicio: Optional[str] = Query(None, description="Competência inicial (YYYY-MM)"),
    competencia_fim: Optional[str] = Query(None, description="Competência final (YYYY-MM)"),
    db: Session = Depends(get_db),
):
    """
    Retorna série histórica de receita e análise preço-volume (WEB-02).
    """
    return AnalyticalResponse(
        data={
            "faturado_total": 0.0,
            "arrecadado_total": 0.0,
            "preco_medio_kwh": 0.0,
            "variacao_preco_volume": {
                "efeito_preco": 0.0,
                "efeito_volume": 0.0,
            },
            "serie_mensal": [],
        },
        metadata=AnalyticalMetadata(
            periodo=f"{competencia_inicio or 'inicio'} ate {competencia_fim or 'fim'}",
            unidade="BRL",
        ),
    )
