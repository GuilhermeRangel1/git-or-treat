import pytest
from pydantic import ValidationError

import app.main
from app.agent.interpreter import QuestionInterpreter
from app.config import Settings
from app.schemas.domain_profile import DomainProfile
from app.schemas.interpretation import InterpretationStatus


def profile_data() -> dict:
    return {
        "profile_id": "weather-demo",
        "contract_version": "v1",
        "domains": [{"id": "weather", "label": "Clima", "example_questions": ["Quanto choveu?"]}],
        "metrics": [
            {
                "id": "weather.rainfall",
                "domain_id": "weather",
                "aliases": ["chuva", "precipitação"],
                "unit": "milímetros demonstrativos",
                "granularities": ["month"],
                "dimension_ids": ["geography.municipality"],
                "sensitivity": "internal",
            },
            {
                "id": "weather.temperature",
                "domain_id": "weather",
                "aliases": ["temperatura"],
                "unit": "graus demonstrativos",
                "granularities": ["month"],
                "dimension_ids": ["geography.municipality"],
                "sensitivity": "internal",
            },
        ],
        "dimensions": [
            {
                "id": "geography.municipality",
                "label": "Município",
                "role": "geography",
                "aliases": ["município", "cidade"],
                "value_type": "string",
                "operators": ["eq", "in"],
                "sensitivity": "internal",
                "values": [
                    {"value": "Recife", "aliases": ["Recife"]},
                    {"value": "Olinda", "aliases": ["Olinda"]},
                ],
            }
        ],
        "period_phrases": ["este mês", "mês passado"],
        "comparison_terms": ["comparar", "variação"],
        "correction_terms": ["não", "na verdade", "corrigindo"],
        "follow_up_starters": ["e", "também", "agora"],
        "direction_terms": ["aumento", "queda"],
        "ambiguities": [{"phrases": ["tempo"], "clarification": "Você quer chuva ou temperatura?"}],
        "clarifications": {
            "missing_metric": "Qual indicador climático?",
            "multiple_domains": "Qual assunto climático primeiro?",
            "multiple_metrics": "Você quer consultar chuva ou temperatura?",
            "unknown_geography": "Confirme o município conhecido.",
            "multiple_geographies": "Qual município?",
            "multiple_classes": "Qual classe?",
            "missing_period": "Qual período?",
            "comparison_baseline": "Qual período de base?",
            "multiple_periods": "Quer comparar os períodos?",
        },
        "operations": ["read"],
    }


def test_profile_injection_changes_vocabulary_without_changing_interpreter() -> None:
    interpreter = QuestionInterpreter(profile=DomainProfile.model_validate(profile_data()))

    result = interpreter.interpret("Qual foi a chuva este mês em Recife?")

    assert result.status is InterpretationStatus.READY
    assert result.intent is not None
    assert result.intent.domain == "weather"
    assert result.intent.metric_id == "weather.rainfall"
    assert result.intent.metric_phrase == "chuva"
    assert result.intent.dimension_ids == ["geography.municipality"]
    assert result.intent.geography_phrase == "Recife"
    assert result.intent.period_phrase == "este mês"


def test_interpreter_asks_when_question_matches_multiple_metrics_in_one_domain() -> None:
    interpreter = QuestionInterpreter(profile=DomainProfile.model_validate(profile_data()))

    result = interpreter.interpret("Qual chuva e temperatura teve este mês?")

    assert result.status is InterpretationStatus.NEEDS_CLARIFICATION
    assert result.intent is None
    assert result.clarification_question == "Você quer consultar chuva ou temperatura?"


def test_application_composition_passes_the_supplied_profile(monkeypatch) -> None:
    profile = DomainProfile.model_validate(profile_data())
    received_profiles = []

    class ProfileRecordingInterpreter:
        def __init__(self, profile):
            received_profiles.append(profile)

    monkeypatch.setattr(app.main, "QuestionInterpreter", ProfileRecordingInterpreter)
    app.main.create_app(settings=Settings(_env_file=None), domain_profile=profile)

    assert received_profiles == [profile]


def test_profile_rejects_duplicate_ids_and_ambiguous_metric_aliases() -> None:
    data = profile_data()
    data["metrics"].append(
        {
            **data["metrics"][0],
            "id": "weather.other",
            "aliases": ["chuva"],
        }
    )

    with pytest.raises(ValidationError, match="alias"):
        DomainProfile.model_validate(data)

    data = profile_data()
    data["domains"].append({"id": "weather", "label": "Clima alternativo"})
    with pytest.raises(ValidationError, match="duplicado"):
        DomainProfile.model_validate(data)


def test_profile_rejects_missing_references_unsupported_operations_and_versions() -> None:
    data = profile_data()
    data["metrics"][0]["domain_id"] = "unknown"
    with pytest.raises(ValidationError, match="domínio"):
        DomainProfile.model_validate(data)

    data = profile_data()
    data["operations"] = ["write"]
    with pytest.raises(ValidationError):
        DomainProfile.model_validate(data)

    data = profile_data()
    data["contract_version"] = "v2"
    with pytest.raises(ValidationError):
        DomainProfile.model_validate(data)


def test_profile_rejects_incomplete_catalog_and_ambiguous_dimension_values() -> None:
    data = profile_data()
    data["metrics"] = []
    with pytest.raises(ValidationError):
        DomainProfile.model_validate(data)

    data = profile_data()
    data["dimensions"][0]["values"].append({"value": "Recife antigo", "aliases": ["Olinda"]})
    with pytest.raises(ValidationError, match="valor"):
        DomainProfile.model_validate(data)


def test_profile_rejects_filter_operators_incompatible_with_the_value_type() -> None:
    data = profile_data()
    data["dimensions"][0]["value_type"] = "boolean"

    with pytest.raises(ValidationError, match="operador incompatível"):
        DomainProfile.model_validate(data)
