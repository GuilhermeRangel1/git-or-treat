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
_SHARED_MONTH_NAME = "|".join(name.replace("ç", "[cç]") for name in _MONTH_NAMES)
_SHARED_YEAR = re.compile(
    r"(?<!\w)(?P<first>" + _SHARED_MONTH_NAME + r")"
    r"(?P<link>\s+(?:e|a|at[eé]|com|para|versus)\s+)(?P<second>" + _SHARED_MONTH_NAME + r")"
    r"\s+(?:de\s+)?(?P<year>[0-9]{4})(?![\w-])",
    re.IGNORECASE,
)
_SLASH_MONTH = re.compile(
    r"(?<![\w/.-])(?P<month>0?[1-9]|1[0-2]|" + _SHARED_MONTH_NAME + r")"
    r"\s*/\s*(?P<year>[0-9]{4})(?![\w/-])", re.IGNORECASE,
)
_MONTHLY_PREFIX = re.compile(
    r"\b(?:no\s+m[eê]s(?:\s+de)?|na\s+compet[eê]ncia(?:\s+de)?)\s+"
    r"(?=(?:" + _SHARED_MONTH_NAME + r")\s+(?:de\s+)?[0-9]{4}"
    r"|[0-9]{4}-(?:0[1-9]|1[0-2]))", re.IGNORECASE,
)


def normalize_calendar_phrases(text: str) -> str:
    """Normaliza grafias mensais equivalentes, acentos Unicode e espaço em branco.

    Os dois meses pertencem ao ano escrito. Uma virada de ano continua exigindo
    anos separados e a resolução existente valida ordem, calendário e cobertura.
    Notação mês/ano exige ano completo e não é extraída de uma data com dia.
    """
    text = " ".join(unicodedata.normalize("NFC", text).split())
    quarters = {"primeiro": 1, "segundo": 2, "terceiro": 3, "quarto": 4}

    def calendar_quarter(match: re.Match) -> str:
        token = match["quarter"].lower()
        quarter = int(token[0]) if token[0].isdigit() else quarters[token]
        start = (quarter - 1) * 3 + 1
        year = match["year"]
        return f"de {year}-{start:02d} a {year}-{start + 2:02d}"

    text = re.sub(
        r"\b(?P<quarter>[1-4](?:[º°o])?|primeiro|segundo|terceiro|quarto)"
        r"\s+trimestre\s+(?:de\s+)?(?P<year>[0-9]{4})(?![\w/-])",
        calendar_quarter, text, flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bde\s+(?P<year>[0-9]{4})\s+(?:em\s+)?(?P<month>"
        + _SHARED_MONTH_NAME + r")\b",
        lambda match: f"{match['month']} de {match['year']}",
        text,
        flags=re.IGNORECASE,
    )
    # Somente abreviações acompanhadas de ano: não altera nomes de locais nem
    # completa mês/ano ausente. A resolução posterior continua validando cobertura.
    abbreviations = dict(zip(
        ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"),
        _MONTH_NAMES, strict=True,
    ))
    text = re.sub(
        r"\b(" + "|".join(abbreviations) + r")\.?\s*(?:/|\s+(?:de\s+)?)"
        r"([0-9]{4})(?![\w/-])",
        lambda match: f"{abbreviations[match[1].lower()]} de {match[2]}",
        text, flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:no\s+)?m[eê]s\s+(0?[1-9]|1[0-2])\s+de\s+([0-9]{4})(?!\w)",
        lambda match: f"em {match[2]}-{int(match[1]):02d}", text, flags=re.IGNORECASE,
    )
    text = _SHARED_YEAR.sub(
        lambda match: (
            f"{match['first']} de {match['year']}{match['link']}"
            f"{match['second']} de {match['year']}"
        ),
        text,
    )

    def slash_month(match: re.Match) -> str:
        token = _normalize(match["month"])
        month = int(token) if token.isdigit() else _MONTH_NUMBERS[token]
        return f"{match['year']}-{month:02d}"

    return _MONTHLY_PREFIX.sub("em ", _SLASH_MONTH.sub(slash_month, text))


def expand_short_calendar_year(text: str, competencies: tuple[str, ...]) -> str:
    """Expande ano curto apenas quando o lote autorizado determina um único século."""
    years = {period[:4] for period in competencies if re.fullmatch(r"[0-9]{4}-[0-9]{2}", period)}
    month = (r"(?:0?[1-9]|1[0-2]|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|"
             + _SHARED_MONTH_NAME + r")")
    pattern = re.compile(
        rf"(?<![\w/.-])(?P<month>{month})\.?\s*/\s*(?P<year>[0-9]{{2}})(?![\w/.-])",
        re.IGNORECASE,
    )

    def expand(match: re.Match) -> str:
        candidates = {year for year in years if year.endswith(match["year"])}
        if len(candidates) != 1:
            return match[0]
        return f"{match['month']}/{next(iter(candidates))}"

    return pattern.sub(expand, text)


def complete_contextual_period(text: str, context: list) -> str:
    """Completa só continuações curtas a partir de um único mês explícito.

    Um intervalo ou comparação anterior não escolhe silenciosamente um ano.
    Calendário/cobertura continuam sendo aprovados pelo resolvedor de janela.
    """
    normalized = _normalize(text).strip(" ?!.")
    month = re.fullmatch(
        r"(?:(?:e|agora|na verdade|corrigindo)[,:]?\s+)?"
        r"(?:(?:em|no mes de|mes de)\s+)?(" + _SHARED_MONTH_NAME + r")",
        normalized,
    )
    comparison = re.fullmatch(
        r"(?:e\s+)?compar(?:e|ar)\s+com\s+(?:o\s+)?(?:mes|periodo)\s+anterior",
        normalized,
    )
    previous_month_request = re.fullmatch(
        r"(?:e\s+)?(?:em|no)\s+(?:o\s+)?m[eê]s\s+(?:anterior|passado)",
        normalized,
    )
    year_correction = re.fullmatch(
        r"(?:na verdade|corrigindo)[,:]?\s+(?:em\s+)?([0-9]{4})", normalized,
    )
    if all(match is None for match in (
        month, comparison, year_correction, previous_month_request,
    )):
        return text
    for turn in reversed(context):
        if turn.role != "user":
            continue
        phrases = explicit_monthly_phrases(normalize_calendar_phrases(turn.content))
        if not phrases:
            return text
        bounds = _explicit_bounds(phrases[0])
        if len(phrases) != 1 or bounds is None or bounds[0] != bounds[1]:
            return text
        year, number = bounds[0]
        if year_correction is not None:
            return f"E em {int(year_correction[1]):04d}-{number:02d}?"
        if month is not None:
            return f"E em {year:04d}-{_MONTH_NUMBERS[_normalize(month[1])]:02d}?"
        previous_year, previous_month = (year - 1, 12) if number == 1 else (year, number - 1)
        if comparison is None:
            return f"E em {previous_year:04d}-{previous_month:02d}?"
        return (f"E compare entre {previous_year:04d}-{previous_month:02d} "
                f"e {year:04d}-{number:02d}.")
    return text


_NAMED_MONTH = r"(?:" + "|".join(_MONTH_NUMBERS) + r")\s+(?:de\s+)?[0-9]{4}"
_MONTH_TOKEN = rf"(?:{_NAMED_MONTH}|[0-9]{{4}}-(?:0[1-9]|1[0-2]))"
_EXPLICIT_PERIOD = re.compile(
    rf"(?<!\w)(?:(?:de\s+)?{_MONTH_TOKEN}\s+(?:a|ate)\s+{_MONTH_TOKEN}"
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


def complete_yearless_months(text: str, year: str) -> str | None:
    """Aplica o ano explicitamente respondido a meses que ainda não têm ano."""
    if re.search(r"\b[0-9]{4}\b", text):
        return None
    pattern = r"\b(?:" + _SHARED_MONTH_NAME + r")\b"
    if not re.search(pattern, text, flags=re.IGNORECASE):
        return None
    return re.sub(pattern, lambda m: f"{m[0]} de {year}", text, flags=re.IGNORECASE)


def yearless_month_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Localiza meses escritos sem presumir ano nem convertê-los em janela válida."""
    if re.search(r"\b[0-9]{4}\b", text):
        return ()
    return tuple(match.span() for match in re.finditer(
        r"\b(?:" + _SHARED_MONTH_NAME + r")\b", text, re.IGNORECASE,
    ))


def missing_year_question(text: str, *, comparison: bool) -> str | None:
    """Pede só o ano de meses nomeados, sem inferir o ano da publicação."""
    months = [text[start:end] for start, end in yearless_month_spans(text)]
    if not months or len(months) > 2:
        return None
    label = " e ".join(month.lower() for month in months)
    if len(months) == 2:
        operation = "comparar" if comparison else "consultar"
        return (f"De qual ano você quer {operation} {label}? "
                "Se forem anos diferentes, informe o ano de cada mês.")
    return f"De qual ano você quer consultar {label}?"


def has_incomplete_calendar_period(text: str) -> bool:
    """Impede aproveitar apenas o extremo reconhecido de um intervalo incompleto."""
    normalized = _normalize(text)
    matches = list(_EXPLICIT_PERIOD.finditer(normalized))
    if not matches:
        return False
    remaining = normalized
    for match in reversed(matches):
        remaining = remaining[:match.start()] + " " + remaining[match.end():]
    # Dois meses completos ligados por "entre ... e ..." não são intervalo incompleto.
    if len(matches) == 2 and all(re.fullmatch(_MONTH_TOKEN, m.group()) for m in matches):
        remaining = re.sub(r"\bentre\b", " ", remaining)
    return bool(re.search(
        r"\b(?:desde|ate|entre|" + "|".join(_MONTH_NUMBERS) + r")\b"
        r"|(?<!\w)(?:[0-9]{4}[-/][0-9]+|[0-9]{1,2}/[0-9]{2,})(?!\w)", remaining
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

    _ROLLING_MONTHS = {
        _normalize("últimos 12 meses"): 12,
        _normalize("último ano"): 12,
        _normalize("último trimestre"): 3,
        _normalize("últimos três meses"): 3,
        _normalize("últimos 3 meses"): 3,
        _normalize("últimos seis meses"): 6,
        _normalize("últimos 6 meses"): 6,
        _normalize("últimos nove meses"): 9,
        _normalize("últimos 9 meses"): 9,
    }
    _MONTH_COUNTS = {
        "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
        "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
        "onze": 11, "doze": 12, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
        "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "11": 11, "12": 12,
    }

    @classmethod
    def _months_ago(cls, phrase: str) -> int | None:
        normalized = _normalize(phrase).strip()
        if normalized in {"mes retrasado", "mes retrasada"}:
            return 2
        counts = "|".join(sorted(cls._MONTH_COUNTS, key=len, reverse=True))
        match = re.fullmatch(
            rf"(?:(?:ha)\s+)?(?P<count>{counts})\s+mes(?:es)?(?:\s+atras)?",
            normalized,
        )
        if match is None or not (normalized.startswith("ha ") or normalized.endswith(" atras")):
            return None
        return cls._MONTH_COUNTS[match["count"]]

    @classmethod
    def _rolling_month_count(cls, phrase: str) -> int | None:
        normalized = _normalize(phrase).strip()
        counts = "|".join(sorted(cls._MONTH_COUNTS, key=len, reverse=True))
        match = re.fullmatch(rf"ultimos\s+(?P<count>{counts})\s+meses?", normalized)
        return cls._MONTH_COUNTS[match["count"]] if match is not None else None

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
        elif (months := self._ROLLING_MONTHS.get(normalized)
              or self._rolling_month_count(normalized)) is not None:
            start = _shift_month(year, month, -(months - 1))
            expected = _months_between(start, (year, month))
        elif normalized == _normalize("ano passado"):
            start = (year - 1, 1)
            expected = _months_between(start, (year - 1, 12))
        elif normalized == _normalize("mês passado"):
            start = _shift_month(year, month, -1)
            expected = [start]
        elif (months_ago := self._months_ago(normalized)) is not None:
            start = _shift_month(year, month, -months_ago)
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


def monthly_period_label(period: str) -> str:
    """Competência já validada para uma frase legível em português."""
    year, month = period.split("-")
    return f"{_MONTH_NAMES[int(month) - 1]} de {year}"
