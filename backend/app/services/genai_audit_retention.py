"""Expurgo periódico, sem colocar conteúdo da trilha nos logs operacionais."""

import asyncio
import logging

from sqlalchemy.exc import SQLAlchemyError

from app.services.genai_audit import AuditStore

logger = logging.getLogger(__name__)


async def maintain_audit_retention(store: AuditStore) -> None:
    while True:
        try:
            await asyncio.to_thread(store.purge)
        except SQLAlchemyError:
            logger.warning("Expurgo da auditoria indisponível; verificar operação administrativa.")
        await asyncio.sleep(3600)
