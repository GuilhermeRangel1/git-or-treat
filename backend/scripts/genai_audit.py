"""Operação administrativa da trilha: consulta, reprodução autorizada e expurgo."""

import argparse
import getpass
import json
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine as operational_engine
from app.schemas.genai_internal import AccessScope, QuestionPlanResponse
from app.schemas.genai_plan import LogicalReadPlan, QuestionPlanStatus
from app.services.genai_audit import AuditStore
from app.services.genai_executor import GoldExecutionDenied

AUDIT_OPERATOR_ROLE = "venergy_genai_audit_operator"
_TRANSPORT_OPTIONS = frozenset({
    "sslmode", "sslrootcert", "sslcert", "sslkey", "channel_binding", "application_name",
})


def _create_audit_engine():
    """Constrói conexão separada, limitada ao operador da trilha no mesmo banco."""
    if settings.GENAI_AUDIT_DATABASE_URL is None:
        raise ValueError("Acesso administrativo de auditoria não configurado.")
    url = make_url(settings.GENAI_AUDIT_DATABASE_URL.get_secret_value())
    operational = make_url(settings.DATABASE_URL)
    if (
        url.drivername != "postgresql+psycopg"
        or url.username != AUDIT_OPERATOR_ROLE
        or not url.password
        or not url.host
        or not url.database
        or (url.host, url.port, url.database)
        != (operational.host, operational.port, operational.database)
        or not set(url.query) <= _TRANSPORT_OPTIONS
        or any(not isinstance(value, str) for value in url.query.values())
    ):
        raise ValueError("Credencial administrativa de auditoria incompatível.")
    return create_engine(
        url, hide_parameters=True, echo=False, pool_pre_ping=True,
        pool_size=1, max_overflow=0, pool_timeout=2,
        connect_args={"connect_timeout": 5},
    )


def _resolve_session_scope(token: str, plan: LogicalReadPlan | None = None) -> AccessScope:
    """Relê a sessão atual e traduz apenas a permissão de leitura Gold."""
    if settings.ORDERS_AUTH_MODE != "session":
        raise ValueError("Reprodução exige autenticação individual.")

    from app.core.genai_gold_access import GOLD_DIMENSIONS, GOLD_METRICS
    from app.core.order_access import READ
    from app.services.auth import permissions_for, resolve_session

    with Session(operational_engine) as db:
        identity = resolve_session(db, token)
        if identity is None:
            raise ValueError("Sessão inválida.")
        user, _session = identity
        if READ not in permissions_for(user):
            raise ValueError("Leitura Gold não autorizada.")
        actor = f"user:{user.id}"
    metric_ids = GOLD_METRICS if plan is None else frozenset({plan.metric_id})
    dimension_ids = GOLD_DIMENSIONS if plan is None else frozenset(plan.dimension_ids)
    if not metric_ids <= GOLD_METRICS or not dimension_ids <= GOLD_DIMENSIONS:
        raise ValueError("Plano fora do escopo Gold permitido.")
    return AccessScope(
        caller_ref="session:" + sha256(actor.encode()).hexdigest(),
        profile_id="v-energy-grid-360-gold",
        source_id="gold.local",
        allowed_operations=frozenset({"read"}),
        allowed_metric_ids=metric_ids,
        allowed_dimension_ids=dimension_ids,
    )


def _verify_reference(reference: str, plan_path: Path, audit_store: AuditStore) -> bool:
    """Reexecuta somente após autenticar de novo a pessoa dona da referência."""
    from app.core.genai_gold_database import create_genai_gold_engine
    from app.services.genai_deadline import GenAIRequestDeadline
    from app.services.genai_planning import GoldPlanningResult
    from app.services.genai_publication import GoldPublicationContext
    from app.services.genai_replay import verify_audited_execution

    session_token = getpass.getpass("Sessão individual atual (cookie grid360_session): ")
    identity_scope = _resolve_session_scope(session_token)
    events = audit_store.read_reference(reference)
    backend_row = next((row for row in reversed(events)
                        if row["service"] == "backend"
                        and (row["event"].get("artifact") or {}).get("result_digest")), None)
    if backend_row is None:
        raise GoldExecutionDenied
    if backend_row["event"].get("caller_ref") != identity_scope.caller_ref:
        raise GoldExecutionDenied

    plan = LogicalReadPlan.model_validate(json.loads(plan_path.read_text(encoding="utf-8")))
    scope = _resolve_session_scope(session_token, plan)
    correlation_id = backend_row["correlation_id"]
    response = QuestionPlanResponse(
        correlation_id=correlation_id,
        status=QuestionPlanStatus.PLANNED,
        plan=plan,
        plan_fingerprint=plan.fingerprint(),
    )
    reader = create_genai_gold_engine(scope)
    try:
        publication = GoldPublicationContext.capture(reader)
        planned = GoldPlanningResult(
            response=response,
            publication=publication,
            access_scope=scope,
            deadline=GenAIRequestDeadline.start(35),
        )

        def resolve_current_scope():
            return _resolve_session_scope(session_token, plan)

        return verify_audited_execution(
            audit_store, reference, reader, planned,
            resolve_scope=resolve_current_scope,
        )
    finally:
        reader.dispose()


def _verify_insight_reference(reference: str, request_path: Path, audit_store: AuditStore) -> bool:
    from app.core.genai_gold_database import create_genai_gold_engine
    from app.schemas.ai_insight import PanoramaInsightRequest
    from app.services.gold_panorama_coordination import verify_audited_panorama_insight
    session_token = getpass.getpass("Sessão individual atual (cookie grid360_session): ")
    scope = _resolve_session_scope(session_token)
    request = PanoramaInsightRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    reader = create_genai_gold_engine(scope)
    try:
        return verify_audited_panorama_insight(audit_store, reference, reader, operational_engine,
            request, resolve_scope=lambda: _resolve_session_scope(session_token))
    finally:
        reader.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--reference", help="Consulta eventos sanitizados por referência.")
    action.add_argument("--verify-reference", help="Reproduz execução com sessão atual e plano privado.")
    action.add_argument("--verify-insight-reference", help="Recalcula contexto do insight Gold autorizado.")
    action.add_argument("--purge", action="store_true")
    parser.add_argument("--insight-request-file", type=Path,
        help="JSON privado com filtros e lote originais, sem valores observados.")
    parser.add_argument(
        "--plan-file", type=Path,
        help="JSON privado com o LogicalReadPlan original; usado somente com --verify-reference.",
    )
    args = parser.parse_args()
    if args.plan_file is not None and args.verify_reference is None:
        parser.error("--plan-file só pode ser usado com --verify-reference.")
    if args.verify_reference is not None and args.plan_file is None:
        parser.error("--verify-reference exige --plan-file.")

    if bool(args.verify_insight_reference) != bool(args.insight_request_file):
        parser.error("--verify-insight-reference exige --insight-request-file e vice-versa.")
    audit_engine = None
    try:
        audit_engine = _create_audit_engine()
        store = AuditStore(audit_engine)
        if args.purge:
            result = {"removed": store.purge()}
        elif args.reference:
            result = store.read_reference(args.reference)
        elif args.verify_insight_reference:
            reproduced = _verify_insight_reference(args.verify_insight_reference, args.insight_request_file, store)
            result = {"audit_reference": args.verify_insight_reference, "reproduced": reproduced}
            if not reproduced:
                raise ValueError("Contexto de insight divergente.")
        else:
            reproduced = _verify_reference(args.verify_reference, args.plan_file, store)
            result = {"audit_reference": args.verify_reference, "reproduced": reproduced}
            if not reproduced:
                raise ValueError("Reprodução divergente.")
        print(json.dumps(result, default=str, ensure_ascii=False))
        return 0
    except (SQLAlchemyError, ValueError, OSError, EOFError, GoldExecutionDenied):
        print("Operação de auditoria indisponível ou não autorizada.", file=sys.stderr)
        return 1
    finally:
        if audit_engine is not None:
            audit_engine.dispose()
        operational_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
