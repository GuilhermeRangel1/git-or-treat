from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.common import AnalyticalResponse, PaginatedResponse

router = APIRouter()


@router.get("", summary="Buscar Unidades Consumidoras")
def search_ucs(
    q: Optional[str] = Query(None, description="Termo de busca (ID da UC, documento, etc.)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Listagem com paginação e busca por UC (WEB-03)."""
    return PaginatedResponse(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
    )


@router.get("/{uc_id}", summary="Visão 360 da Unidade Consumidora")
def get_uc_360(uc_id: str, db: Session = Depends(get_db)):
    """
    Retorna histórico completo: dados cadastrais, faturamento,
    consumo, medidores, chamados, interrupções e status de GD.
    """
    # Exemplo com mock stub
    return AnalyticalResponse(
        data={
            "uc_id": uc_id,
            "status": "ATIVA",
            "detalhes": {},
            "historico_consumo": [],
            "faturas": [],
            "ocorrencias": [],
        }
    )
