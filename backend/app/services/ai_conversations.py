"""Persistência operacional com propriedade, retenção e reserva idempotente."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import case, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ai_conversations import CONVERSATIONS as C
from app.models.ai_conversations import EXCHANGES as E
from app.schemas.ai import AIQuestionResponse, AIQuestionText
from app.services.conversation_memory import (
    ConversationMemory,
    MemoryRequest,
    select_memory,
)
from app.services.genai_documentation import document_response_is_current

QUESTION_TEXT = TypeAdapter(AIQuestionText)


def now():
    return datetime.now(UTC)


def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class ConversationStore:
    def __init__(self, db: Session, owner: str):
        self.db, self.owner = db, owner

    def owned(self, conversation: str, *, lock=False):
        query = select(C).where(
            C.c.id == conversation, C.c.owner_id == self.owner, C.c.expires_at > now()
        )
        row = (
            self.db.execute(query.with_for_update() if lock else query)
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(404, "Conversa indisponível.")
        return row

    def summary(self, row):
        count = self.db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        case((E.c.question.is_not(None), 1), else_=0)
                        + case((E.c.response.is_not(None), 1), else_=0)
                    ),
                    0,
                )
            ).where(E.c.conversation_id == row["id"])
        )
        return {
            key: row[key]
            for key in (
                "id",
                "title",
                "revision",
                "created_at",
                "updated_at",
                "expires_at",
            )
        } | {"message_count": count}

    def create(self, request_id: str):
        row = (
            self.db.execute(
                select(C).where(
                    C.c.owner_id == self.owner, C.c.request_id == request_id
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            timestamp = now()
            try:
                with self.db.begin_nested():
                    self.db.execute(
                        insert(C).values(
                            id=str(uuid4()),
                            owner_id=self.owner,
                            request_id=request_id,
                            title="Nova conversa",
                            revision=1,
                            created_at=timestamp,
                            updated_at=timestamp,
                            expires_at=timestamp + timedelta(days=30),
                        )
                    )
            except IntegrityError:
                pass  # A restrição por proprietário/request resolve criação simultânea.
            self.db.commit()
            row = (
                self.db.execute(
                    select(C).where(
                        C.c.owner_id == self.owner, C.c.request_id == request_id
                    )
                )
                .mappings()
                .one()
            )
        return self.summary(self.owned(row["id"]))

    def listing(self, offset=0):
        rows = (
            self.db.execute(
                select(C)
                .where(C.c.owner_id == self.owner, C.c.expires_at > now())
                .order_by(C.c.updated_at.desc(), C.c.id)
                .offset(offset)
                .limit(51)
            )
            .mappings()
            .all()
        )
        return {
            "items": [self.summary(row) for row in rows[:50]],
            "has_more": len(rows) > 50,
        }

    def detail(self, conversation, scope):
        row = self.owned(conversation)
        exchanges = (
            self.db.execute(
                select(E)
                .where(E.c.conversation_id == row["id"])
                .order_by(E.c.sequence)
                .limit(200)
            )
            .mappings()
            .all()
        )
        items = []
        for entry in exchanges:
            response = None
            question = None
            available = entry["format_version"] == 1 and entry["scope_digest"] == scope
            if available:
                try:
                    if entry["question"] is not None:
                        question = QUESTION_TEXT.validate_python(entry["question"])
                    if entry["response"] is not None:
                        parsed = AIQuestionResponse.model_validate(entry["response"])
                        if not document_response_is_current(parsed):
                            available = False
                        response = parsed.model_dump(mode="json", exclude={"continuation_token"})
                except (ValidationError, TypeError):
                    available = False
            items.append(
                {
                    "request_id": entry["request_id"],
                    "state": entry["state"] if available else "unavailable",
                    "question": question if available else None,
                    "response": response if available else None,
                }
            )
        return {
            "conversation": self.summary(row),
            "exchanges": items,
            "historical": True,
        }

    def rename(self, conversation, title, revision):
        row = self.owned(conversation, lock=True)
        if row["revision"] != revision:
            raise HTTPException(409, "A conversa mudou. Atualize antes de renomear.")
        self.db.execute(
            update(C)
            .where(C.c.id == row["id"], C.c.owner_id == self.owner)
            .values(title=title, revision=revision + 1)
        )
        self.db.commit()
        return self.summary(self.owned(conversation))

    def remove(self, conversation):
        self.owned(conversation, lock=True)
        self.db.execute(delete(E).where(E.c.conversation_id == conversation))
        self.db.execute(
            delete(C).where(C.c.id == conversation, C.c.owner_id == self.owner)
        )
        self.db.commit()

    def reserve(self, conversation, request_id, question, scope):
        row = self.owned(conversation, lock=True)
        fingerprint = sha256(question.encode()).hexdigest()
        previous = (
            self.db.execute(
                select(E).where(
                    E.c.conversation_id == conversation, E.c.request_id == request_id
                )
            )
            .mappings()
            .first()
        )
        if previous is not None:
            if (
                previous["request_digest"] != fingerprint
                or previous["scope_digest"] != scope
            ):
                raise HTTPException(
                    409, "O envio não corresponde à tentativa original."
                )
            if previous["state"] == "completed":
                try:
                    result = AIQuestionResponse.model_validate(previous["response"])
                    if not document_response_is_current(result):
                        raise ValueError("Definição histórica desatualizada.")
                except (ValueError, TypeError):
                    raise HTTPException(
                        409, "Resposta histórica indisponível. Faça uma nova consulta."
                    ) from None
                self.db.commit()
                return result, None, None
            if aware(previous["lease_until"]) > now():
                raise HTTPException(
                    409,
                    "Esta pergunta ainda está sendo processada. Aguarde antes de tentar novamente.",
                )
        pending = self.db.scalar(
            select(E.c.id).where(
                E.c.conversation_id == conversation,
                E.c.state == "pending",
                E.c.lease_until > now(),
            )
        )
        if pending:
            raise HTTPException(409, "Aguarde a pergunta anterior terminar.")
        attempt = str(uuid4())
        if previous is None:
            count = self.db.scalar(
                select(func.count())
                .select_from(E)
                .where(E.c.conversation_id == conversation)
            )
            if count >= 200:
                raise HTTPException(
                    409, "Esta conversa atingiu o limite. Inicie outra conversa."
                )
            self.db.execute(
                insert(E).values(
                    id=str(uuid4()),
                    conversation_id=conversation,
                    request_id=request_id,
                    sequence=row["revision"],
                    attempt_id=attempt,
                    format_version=1,
                    request_digest=fingerprint,
                    scope_digest=scope,
                    state="pending",
                    question=None,
                    lease_until=now() + timedelta(seconds=90),
                )
            )
        else:
            self.db.execute(
                update(E)
                .where(E.c.id == previous["id"])
                .values(
                    state="pending",
                    question=None,
                    attempt_id=attempt,
                    lease_until=now() + timedelta(seconds=90),
                )
            )
        self.db.execute(
            update(C)
            .where(C.c.id == conversation, C.c.owner_id == self.owner)
            .values(revision=row["revision"] + 1)
        )
        self.db.commit()  # Nenhum lock permanece durante SQL/modelo.
        context = self.context(conversation, scope)
        self.db.commit()  # Encerra também a transação de leitura antes do modelo.
        return None, context, attempt

    def context(self, conversation, scope):
        self.owned(conversation)
        rows = (
            self.db.execute(
                select(E)
                .where(
                    E.c.conversation_id == conversation,
                    E.c.state == "completed",
                    E.c.scope_digest == scope,
                )
                .order_by(E.c.sequence.desc())
                .limit(200)
            )
            .mappings()
            .all()
        )
        valid = []
        for row in rows:
            if row["format_version"] != 1 or not isinstance(row["response"], dict):
                break
            try:
                response = AIQuestionResponse.model_validate(row["response"])
            except (ValidationError, TypeError):
                break
            question = row["question"]
            if question is not None and (
                not isinstance(question, str) or not question.strip() or len(question) > 1000
            ):
                break
            valid.append({**row, "response": response.model_dump(mode="json")})

        # Uma explicação conceitual não deve deixar a consulta numérica anterior
        # ativa como se fosse o assunto atual. Retomadas explícitas ainda a encontram.
        latest_document = next((index for index, row in enumerate(valid)
                                if any(item["source"] == "documentation.indicators"
                                       for item in row["response"]["evidence"])), None)
        anchor_rows = valid if latest_document is None else valid[:latest_document]
        anchor = next(
            (
                row
                for row in anchor_rows
                if row["response"]["status"] in {"answered", "no_evidence", "needs_clarification"}
                and isinstance(row["anchor"], str)
                and 0 < len(row["anchor"]) <= 1000
                and isinstance(row["batch"], str)
                and 0 < len(row["batch"]) <= 200
            ),
            None,
        )
        recent = valid[0] if valid else None
        return anchor, recent

    def memory(
        self, conversation: str, scope: str, reference: MemoryRequest,
    ) -> ConversationMemory:
        self.owned(conversation)
        # Não filtrar por escopo antes da seleção: isso trocaria a numeração e
        # poderia recuperar outra consulta no lugar daquela solicitada.
        rows = self.db.execute(
            select(E.c.request_id, E.c.sequence, E.c.format_version, E.c.scope_digest,
                   E.c.response, E.c.question, E.c.anchor, E.c.batch)
            .where(E.c.conversation_id == conversation, E.c.state == "completed")
            .order_by(E.c.sequence.desc()).limit(200)
        ).mappings().all()
        return select_memory(rows, reference, scope)

    def finish(
        self,
        conversation,
        request_id,
        attempt,
        question,
        result,
        anchor=None,
        batch=None,
    ):
        self.owned(conversation, lock=True)
        safe = result.status not in {"refused", "recoverable_error"}
        changed = self.db.execute(
            update(E)
            .where(
                E.c.conversation_id == conversation,
                E.c.request_id == request_id,
                E.c.attempt_id == attempt,
            )
            .values(
                state="completed"
                if result.status != "recoverable_error"
                else "interrupted",
                question=question if safe else "Pergunta não armazenada.",
                response=result.model_dump(mode="json", exclude={"continuation_token"}),
                anchor=anchor,
                batch=batch,
                lease_until=now(),
            )
        )
        if changed.rowcount != 1:
            self.db.rollback()
            raise HTTPException(
                409, "A tentativa foi substituída. Atualize a conversa."
            )
        self.db.execute(
            update(C)
            .where(C.c.id == conversation, C.c.owner_id == self.owner)
            .values(updated_at=now(), expires_at=now() + timedelta(days=30))
        )
        self.db.commit()

    def interrupt(self, conversation, request_id, attempt):
        # Excluir durante a consulta nunca recria a conversa nem a mensagem.
        if self.db.scalar(
            select(C.c.id).where(C.c.id == conversation, C.c.owner_id == self.owner)
        ):
            self.db.execute(
                update(E)
                .where(
                    E.c.conversation_id == conversation,
                    E.c.request_id == request_id,
                    E.c.attempt_id == attempt,
                )
                .values(state="interrupted", question=None, response=None, lease_until=now())
            )
            self.db.commit()


def purge_history(engine):
    with Session(engine) as db:
        expired = select(C.c.id).where(C.c.expires_at <= now())
        db.execute(delete(E).where(E.c.conversation_id.in_(expired)))
        db.execute(delete(C).where(C.c.expires_at <= now()))
        db.commit()
