"""Checagens sintáticas de números afirmados contra evidência fornecida."""

import re
from decimal import Decimal, InvalidOperation

_NUMBER = re.compile(r"(?<!\w)[+-]?\d[\d.,]*(?:\s*%)?(?!\w)")


def _decimal_token(value: str) -> Decimal | None:
    normalized = value.strip().replace("%", "").replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        left, right = normalized.rsplit(",", maxsplit=1)
        normalized = f"{left.replace(',', '')}.{right}"
    elif normalized.count(".") > 1 or (
        normalized.count(".") == 1 and len(normalized.rsplit(".", maxsplit=1)[1]) == 3
    ):
        normalized = normalized.replace(".", "")
    try:
        return Decimal(normalized).normalize()
    except InvalidOperation:
        return None


def _evidence_numbers(value: object) -> set[Decimal]:
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, (int, float, Decimal)):
        try:
            return {Decimal(str(value)).normalize()}
        except InvalidOperation:
            return set()
    if isinstance(value, str):
        return {
            number
            for match in _NUMBER.finditer(value)
            if (number := _decimal_token(match.group())) is not None
        }
    if isinstance(value, dict):
        return set().union(*(_evidence_numbers(item) for item in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(_evidence_numbers(item) for item in value))
    return set()


def contains_only_evidence_numbers(answer: str, records: list[dict[str, object]]) -> bool:
    """Confere presença de tokens; não verifica fórmula nem sentido do texto."""

    allowed = _evidence_numbers(records)
    claimed = [
        number
        for match in _NUMBER.finditer(answer)
        if (number := _decimal_token(match.group())) is not None
    ]
    return all(number in allowed for number in claimed)
