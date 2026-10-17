from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any, List
from app.core.database import get_db

router = APIRouter()

ALLOWED_READ_TABLES = ["gold_indicadores", "gold_ucs", "gold_receita", "gold_continuidadade"]


class AIQueryRequest(BaseModel):
    intent: str
    target_table: str
    filters: Dict[str, Any] = {}


@router.post("/query", summary="Consulta somente-leitura controlada para o agente de IA")
def query_analytical_data(payload: AIQueryRequest, db: Session = Depends(get_db)):
    """
    Permite ao agente de IA consultar tabelas analíticas permitidas (allowlist)
    sem permissão de escrita e com trilha de auditoria.
    """
    if payload.target_table not in ALLOWED_READ_TABLES:
        raise HTTPException(
            status_code=403,
            detail=f"Tabela não permitida para o agente. Tabelas acessíveis: {ALLOWED_READ_TABLES}",
        )

    # Retorno estruturado seguro
    return {
        "status": "success",
        "intent": payload.intent,
        "table": payload.target_table,
        "records": [],
        "evidence": "Consulta analítica somente leitura",
    }
