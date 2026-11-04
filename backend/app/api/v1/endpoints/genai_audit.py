"""Ingresso interno de auditoria: só escrita, autenticada e sem leitura pública."""

from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas.genai_audit import GenAIAuditEvent
from app.services.genai_audit import AuditStore

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def require_audit_writer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    token = settings.GENAI_AUDIT_WRITE_TOKEN
    if token is None:
        raise HTTPException(503, "Auditoria indisponível.")
    if credentials is None or not compare_digest(
        credentials.credentials, token.get_secret_value(),
    ):
        raise HTTPException(401, "Chamador não autorizado.")


@router.post("/genai-audit-events", status_code=201, include_in_schema=False,
             dependencies=[Depends(require_audit_writer)])
def record_genai_event(
    event: GenAIAuditEvent,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    if request.headers.get("X-Correlation-ID") != event.correlation_id:
        raise HTTPException(422, "Correlação de auditoria incompatível.")
    engine = db.get_bind()
    if not isinstance(engine, Engine):
        raise HTTPException(503, "Auditoria indisponível.")
    try:
        reference = AuditStore(engine).record(event)
    except SQLAlchemyError:
        raise HTTPException(503, "Auditoria indisponível.") from None
    return {"audit_reference": reference}
