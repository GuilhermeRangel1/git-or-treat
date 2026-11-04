"""Expiração imediata nas leituras; remoção física na inicialização e a cada hora."""

import asyncio
import logging

from sqlalchemy.exc import SQLAlchemyError

from app.services.ai_conversations import purge_history

logger = logging.getLogger(__name__)


async def maintain_history_retention(engine):
    while True:
        try:
            await asyncio.to_thread(purge_history, engine)
        except SQLAlchemyError:
            logger.warning(
                "Expurgo do histórico indisponível; verificar operação administrativa."
            )
        await asyncio.sleep(3600)
