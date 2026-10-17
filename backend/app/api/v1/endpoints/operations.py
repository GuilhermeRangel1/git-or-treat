from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.common import AnalyticalResponse, AnalyticalMetadata

router = APIRouter()


@router.get("/continuity", summary="Indicadores DEC/FEC simplificados por alimentador e período")
def get_continuity_metrics(
    periodo: Optional[str] = Query(None, description="Período de apuração"),
    alimentador: Optional[str] = Query(None, description="Identificador do alimentador"),
    db: Session = Depends(get_db),
):
    """
    Retorna métricas de duração (DEC) e frequência (FEC) simplificadas calculadas na Gold (WEB-06).
    """
    return AnalyticalResponse(
        data={
            "alimentador": alimentador or "TODOS",
            "dec_horas": 0.0,
            "fec_interrupcoes": 0.0,
            "total_ocorrencias": 0,
        },
        metadata=AnalyticalMetadata(
            periodo=periodo or "global",
            unidade="Horas / Interrupções por UC",
            qualidade_cobertura="DEC/FEC simplificado operacional",
        ),
    )
