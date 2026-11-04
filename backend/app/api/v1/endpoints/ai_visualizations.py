"""Verificação de exportação de agregados já exibidos; não consulta medidas."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.v1.endpoints.ai import AIQuestionRoute, _question_error
from app.core.database import get_db
from app.core.genai_gold_database import get_question_gold_resources
from app.repositories.gold_publication import (
    GoldPublicationChanged,
    GoldPublicationUnavailable,
    current_publication,
)
from app.schemas.genai_internal import AccessScope
from app.schemas.visual_export import VisualExportPermission, VisualExportRequest
from app.services.genai_expected_publication import (
    ExpectedPublicationMismatch,
    resolve_expected_batch_ref,
)

router = APIRouter(route_class=AIQuestionRoute)


@router.post("/visualizations/verify", response_model=VisualExportPermission)
def verify_export(
    payload: VisualExportRequest,
    request: Request,
    resources: Annotated[
        tuple[Engine, Callable[[], AccessScope]] | None,
        Depends(get_question_gold_resources),
    ],
    db: Annotated[Session, Depends(get_db)],
):
    if resources is None:
        raise HTTPException(503, "Exportação Gold indisponível.")
    engine, resolve = resources
    scope = resolve()
    if (
        scope.source_id != "gold.local"
        or scope.profile_id != "v-energy-grid-360-gold"
        or "read" not in scope.allowed_operations
        or payload.metric not in scope.allowed_metric_ids
        or not set(payload.dimension_ids) <= scope.allowed_dimension_ids
    ):
        raise HTTPException(403, "Exportação não autorizada.")
    try:
        expected = payload.batch_reference
        if payload.expected_publication is not None:
            expected = resolve_expected_batch_ref(
                db.get_bind(), payload.expected_publication
            )
        with engine.connect() as connection:
            current_publication(connection, expected)
    except (GoldPublicationChanged, ExpectedPublicationMismatch):
        return _question_error(
            request,
            status_code=409,
            code="invalid_context",
            retryable=False,
            message="Os dados mudaram. Atualize a consulta antes de baixar.",
        )
    except GoldPublicationUnavailable:
        return _question_error(
            request,
            status_code=503,
            code="service_unavailable",
            retryable=False,
            message="Não foi possível conferir a publicação dos dados.",
        )
    if resolve() != scope:
        raise HTTPException(403, "O acesso mudou durante a exportação.")
    return VisualExportPermission()
