"""Autorização Gold derivada da sessão operacional existente do Backend."""

from collections.abc import Callable
from hashlib import sha256
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.order_access import READ, bearer, get_order_identity
from app.schemas.genai_internal import AccessScope

GOLD_METRICS = frozenset({
    "billing.revenue", "energy.consumption", "billing.average_ticket",
    "billing.effective_tariff", "energy.average_consumption_per_uc",
    "network.equivalent_interruption_duration",
    "network.equivalent_interruption_frequency",
})
GOLD_DIMENSIONS = frozenset({
    "geography.municipality", "geography.neighborhood", "customer.consumption_class",
    "tariff.subgroup", "tariff.flag", "generation.distributed", "network.feeder",
})


def get_genai_gold_access_resolver(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Callable[[], AccessScope]:
    """Relê sessão, usuário ativo e permissões em uma transação nova a cada uso.

    A conexão operacional resolve a identidade; nunca é entregue ao leitor Gold.
    Não reutiliza objetos/transaction snapshot do identity map da requisição.
    """
    bind = db.get_bind()
    if not isinstance(bind, Engine):
        raise HTTPException(503, "Identidade Gold indisponível.")

    def resolve() -> AccessScope:
        if settings.ORDERS_AUTH_MODE != "session":
            raise HTTPException(503, "Consulta Gold exige sessão individual.")
        try:
            with Session(bind) as current:
                identity = get_order_identity(request, credentials, current)
        except SQLAlchemyError:
            raise HTTPException(503, "Identidade Gold indisponível.") from None
        if identity.auth_mode != "session" or READ not in identity.permissions:
            raise HTTPException(403, "Acesso à Gold não autorizado.")
        return AccessScope(
            caller_ref="session:" + sha256(identity.actor.encode()).hexdigest(),
            profile_id="v-energy-grid-360-gold", source_id="gold.local",
            allowed_operations=frozenset({"read"}),
            allowed_metric_ids=GOLD_METRICS, allowed_dimension_ids=GOLD_DIMENSIONS,
        )

    resolve()
    return resolve


def get_question_gold_scope(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> AccessScope | None:
    """Preserva a demo sintética; modo Gold exige a identidade real do Backend."""
    if settings.ANALYTICS_SOURCE != "gold":
        return None
    return get_genai_gold_access_resolver(request, credentials, db)()
