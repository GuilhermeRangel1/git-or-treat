from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.config import settings

router = APIRouter()


@router.get("/health", summary="Status da API e verificação de dependências")
def health_check(db: Session = Depends(get_db)):
    """Verifica se o backend e o banco de dados estão operacionais."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_ok = False

    return {
        "status": "online" if db_ok else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "connected" if db_ok else "disconnected",
    }
