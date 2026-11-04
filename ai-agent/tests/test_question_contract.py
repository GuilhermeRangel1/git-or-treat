import pytest
from pydantic import ValidationError

from app.schemas.questions import QuestionRequest


def test_question_request_defaults_to_the_current_contract_version() -> None:
    request = QuestionRequest(question="Qual foi o consumo?")

    assert request.contract_version == "v1"


def test_question_request_accepts_an_explicit_supported_version() -> None:
    request = QuestionRequest(question="Qual foi o consumo?", contract_version="v1")

    assert request.contract_version == "v1"


@pytest.mark.parametrize("version", [None, "v2", "1"])
def test_question_request_rejects_null_or_unsupported_versions(version) -> None:
    with pytest.raises(ValidationError):
        QuestionRequest(question="Qual foi o consumo?", contract_version=version)
