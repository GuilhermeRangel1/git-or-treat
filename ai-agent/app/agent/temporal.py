"""Resolve frases relativas para competências mensais publicadas no envelope confiável."""

import re
import unicodedata
from calendar import monthrange
from datetime import date

from app.schemas.domain_profile import CatalogGranularity
from app.schemas.read_plan import ReadWindow, WindowKind


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


class TemporalResolutionUnavailable(Exception):
    """A cobertura publicada não permite construir a janela pedida sem suposição."""


_MONTH_NAMES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)
_MONTH_NUMBERS = {_normalize(name): index for index, name in enumerate(_MONTH_NAMES, 1)}
_NAMED_MONTH = r"(?:" + "|".join(_MONTH_NUMBERS) + r")\s+(?:de\s+)?[0-9]{4}"
_MONTH_TOKEN = rf"(?:{_NAMED_MONTH}|[0-9]{{4}}-(?:0[1-9]|1[0-2]))"
_EXPLICIT_PERIOD = re.compile(
    rf"(?<!\w)(?:de\s+{_MONTH_TOKEN}\s+(?:a|ate)\s+{_MONTH_TOKEN}"
    rf"|{_MONTH_TOKEN}|ano\s+(?:de\s+)?[0-9]{{4}})(?![\w-])"
)


def explicit_monthly_phrases(text: str) -> tuple[str, ...]:
    """Extrai somente meses com ano explícito, intervalos mensais e anos nomeados.

    A normalização preserva o tamanho para os caracteres portugueses aceitos
    nestas expressões; os valores retornados são usados como frases de calendário.
    Não extrai dias, meses sem ano ou anos soltos.
    """
    normalized = _normalize(text)
    return tuple(match.group() for match in _EXPLICIT_PERIOD.finditer(normalized))


def has_incomplete_calendar_period(text: str) -> bool:
    """Impede aproveitar apenas o extremo reconhecido de um intervalo incompleto."""
    normalized = _normalize(text)
    matches = list(_EXPLICIT_PERIOD.finditer(normalized))
    if not matches:
        return False
    remaining = normalized
    for match in reversed(matches):
        remaining = remaining[:match.start()] + " " + remaining[match.end():]
    return bool(re.search(
        r"\b(?:desde|ate|entre|" + "|".join(_MONTH_NUMBERS) + r")\b", remaining
    ))


def _explicit_bounds(phrase: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    if re.fullmatch(r"ano\s+(?:de\s+)?[0-9]{4}", phrase):
        year = int(phrase.split()[-1])
        return (year, 1), (year, 12)
    tokens = re.findall(_MONTH_TOKEN, phrase)
    if not tokens or _EXPLICIT_PERIOD.fullmatch(phrase) is None:
        return None
    bounds = []
    for token in tokens:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}", token):
            year, month = map(int, token.split("-"))
        else:
            parts = token.split()
            year, month = int(parts[-1]), _MONTH_NUMBERS[parts[0]]
        bounds.append((year, month))
    return bounds[0], bounds[-1]


class GoldTemporalWindowResolver:
    """Converte janelas relativas em limites mensais inclusivos, sem preencher lacunas."""

    _TWELVE_MONTHS = frozenset({_normalize("últimos 12 meses"), _normalize("último ano")})
    _THREE_MONTHS = frozenset(
        {
            _normalize("último trimestre"),
            _normalize("últimos três meses"),
            _normalize("últimos 3 meses"),
        }
    )

    def resolve(
        self,
        phrase: str,
        competencies: tuple[str, ...] | None,
    ) -> ReadWindow:
        """`None` significa ausência de série mensal; tupla vazia, cobertura ainda não há."""

        normalized = _normalize(phrase)
        if normalized == "neste ano":
            normalized = "este ano"
        if normalized == _normalize("histórico acumulado"):
            return ReadWindow(kind=WindowKind.CATALOG_PHRASE, phrase=phrase)
        if competencies is None or not competencies:
            raise TemporalResolutionUnavailable(
                "A publicação não informa competências mensais para esse indicador."
            )

        latest = competencies[-1]
        year, month = (int(part) for part in latest.split("-"))
        explicit = _explicit_bounds(normalized)
        if explicit is not None:
            start, end = explicit
            if start[0] < 1 or end[0] < 1 or start > end:
                raise TemporalResolutionUnavailable(
                    "Informe meses e anos válidos em ordem crescente."
                )
            if (end[0] - start[0]) * 12 + end[1] - start[1] >= 1200:
                raise TemporalResolutionUnavailable("O intervalo excede o limite de competências.")
            expected = _months_between(start, end)
        elif normalized in self._TWELVE_MONTHS:
            start = _shift_month(year, month, -11)
            expected = _months_between(start, (year, month))
        elif normalized == _normalize("ano passado"):
            start = (year - 1, 1)
            expected = _months_between(start, (year - 1, 12))
        elif normalized in self._THREE_MONTHS:
            start = _shift_month(year, month, -2)
            expected = _months_between(start, (year, month))
        elif normalized == _normalize("mês passado"):
            start = _shift_month(year, month, -1)
            expected = [start]
        elif normalized == _normalize("este ano"):
            start = (year, 1)
            expected = _months_between(start, (year, month))
        else:
            raise TemporalResolutionUnavailable(
                "Ainda não há uma regra aprovada para resolver esse período."
            )

        available = set(competencies)
        missing = [f"{item_year:04d}-{item_month:02d}" for item_year, item_month in expected
                   if f"{item_year:04d}-{item_month:02d}" not in available]
        if missing:
            raise TemporalResolutionUnavailable(
                "A janela solicitada tem competências ausentes na publicação; "
                "escolha outro período completo."
            )

        end_year, end_month = expected[-1]
        return ReadWindow(
            kind=WindowKind.BOUNDED,
            start=date(start[0], start[1], 1),
            end=date(end_year, end_month, monthrange(end_year, end_month)[1]),
            granularity=CatalogGranularity.MONTH,
        )


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + delta
    return index // 12, index % 12 + 1


def _months_between(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    months: list[tuple[int, int]] = []
    current = start
    while current <= end:
        months.append(current)
        current = _shift_month(*current, 1)
    return months
