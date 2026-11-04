"""O cliente não escolhe proprietário ou permissões de uma conversa."""

from uuid import uuid4

import pytest
from app.schemas.ai_conversations import ConversationCreate, ConversationRename
from pydantic import ValidationError


@pytest.mark.parametrize("field", ["owner_id", "user_id", "permissions", "expires_at"])
def test_creation_rejects_client_authority(field):
    with pytest.raises(ValidationError):
        ConversationCreate.model_validate(
            {"request_id": str(uuid4()), field: "external"}
        )


@pytest.mark.parametrize("revision", [True, "1", 0, -1])
def test_rename_requires_explicit_positive_revision(revision):
    with pytest.raises(ValidationError):
        ConversationRename(title="Análise de receita", expected_revision=revision)


@pytest.mark.parametrize("title", ["   ", "Análise\x00de receita", "a" * 121])
def test_rename_rejects_empty_control_or_oversized_title(title):
    with pytest.raises(ValidationError):
        ConversationRename(title=title, expected_revision=1)
