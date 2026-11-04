import pytest

from app.agent.language_recovery import spelling_suggestions
from app.profiles.grid360_gold import GRID360_GOLD_PROFILE
from app.schemas.domain_profile import DimensionValue

VALUES = {
    "geography.municipality": ("Recife",),
    "geography.neighborhood": ("BAIRO", "LUMENIA"),
}


def _profile():
    dimensions = [
        dimension.model_copy(update={"values": tuple(
            DimensionValue(value=value, aliases=(value,)) for value in VALUES[dimension.id]
        )}) if dimension.id in VALUES else dimension
        for dimension in GRID360_GOLD_PROFILE.dimensions
    ]
    return GRID360_GOLD_PROFILE.model_copy(update={"dimensions": tuple(dimensions)})


@pytest.mark.parametrize("question", [
    "Qual bairro de Recife teve a maior queda de consumo entre maio e junho de 2026?",
    "Qual foi a receita faturada no bairro LUMENIA em Recife em junho de 2026?",
    "Quais bairros de Recife tiveram maior consumo em junho de 2026?",
])
def test_dimension_name_is_never_corrected_to_a_similar_value(question):
    assert not any("BAIRO" in item for item in spelling_suggestions(question, _profile()))


def test_real_typo_of_a_catalog_value_is_still_suggested():
    assert list(spelling_suggestions(
        "Qual foi a receita faturada no bairro LUMENIA em Reciffe em junho de 2026?",
        _profile(),
    )) == ["Qual foi a receita faturada no bairro LUMENIA em Recife em junho de 2026?"]
