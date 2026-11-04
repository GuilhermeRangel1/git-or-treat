"""Reconhece a abertura e o tamanho pedidos, sem escolher dados ou autorizar planos."""

import re
from dataclasses import dataclass

_CARDINALS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
    "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18,
    "dezenove": 19, "vinte": 20,
}
_TENS = {"vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
         "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90, "cento": 100}
_UNITS = "um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove"
_NUMBER = (r"(?:[0-9]+|(?:" + "|".join(_TENS) + r")(?:\s+e\s+(?:" + _UNITS
           + r"))?|cem|zero|" + "|".join(_CARDINALS) + r")")


def _count(word: str) -> int:
    if word.isdigit():
        return int(word)
    if word in {"cem", "zero"}:
        return 100 if word == "cem" else 0
    return sum(_CARDINALS.get(part, _TENS.get(part, 0)) for part in word.split(" e "))


@dataclass(frozen=True)
class RankingReference:
    start: int
    end: int
    limit: int | None
    explicit_count: bool


def ranking_reference(text: str, aliases: tuple[str, ...]) -> RankingReference | None:
    """Recebe texto/aliases normalizados; não apaga qualificadores após a dimensão."""
    alternatives = "|".join(re.escape(alias) for alias in sorted(aliases, key=len, reverse=True))
    pattern = (
        r"\b(?:(?P<which>qual|quais)\s+(?:(?:foi|foram|e|sao)\s+)?"
        r"(?:(?:o|a|os|as)\s+)?(?:(?P<which_number>" + _NUMBER + r")\s+)?"
        r"|(?:top|os|as)\s+(?P<top_number>" + _NUMBER + r")\s+)"
        r"(?P<dimension>" + alternatives + r")(?!\w)"
    )
    for match in re.finditer(pattern, text):
        tail = text[match.end():]
        number = match["which_number"] or match["top_number"]
        if not re.search(r"\b(?:mais|menos|maior|menor|cresceu|caiu|perdeu|reduziu|"
                         r"aumentou|melhores|piores)\b", tail) and not number:
            continue
        limit = _count(number) if number else (
            None if match["which"] == "quais" else 1
        )
        return RankingReference(match.start(), match.end(), limit, number is not None)
    return None
