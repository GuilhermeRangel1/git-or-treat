"""Confere medidas citadas contra observações estruturadas autorizadas."""

import json
import re
from decimal import ROUND_HALF_UP, Decimal, DecimalException

from app.providers.protocols import BoundQuantitativeClaim, GeneratedAnswer

_NUMBER_TOKEN = re.compile(
    r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:[eE][+-]?\d+)?(?!\w)"
)

def _number_candidates(token: str) -> set[Decimal]:
    """Interpreta números decimais e formatos agrupados usuais em pt-BR/en-US."""

    sign = Decimal(-1) if token.startswith("-") else Decimal(1)
    unsigned = token.lstrip("+-")
    if not unsigned:
        return set()
    exponent = ""
    exponent_match = re.search(r"[eE][+-]?\d+$", unsigned)
    if exponent_match is not None:
        exponent = exponent_match.group()
        unsigned = unsigned[: exponent_match.start()]

    try:
        if "," in unsigned and "." in unsigned:
            decimal_separator = "," if unsigned.rfind(",") > unsigned.rfind(".") else "."
            grouping_separator = "." if decimal_separator == "," else ","
            whole, fraction = unsigned.rsplit(decimal_separator, maxsplit=1)
            if decimal_separator in whole:
                return set()
            groups = whole.split(grouping_separator)
            if len(groups) > 1 and (
                groups[0] == "0"
                or not 1 <= len(groups[0]) <= 3
                or any(len(group) != 3 for group in groups[1:])
            ):
                return set()
            normalized = f"{''.join(groups)}.{fraction}{exponent}"
            return {sign * Decimal(normalized)}

        separator = "," if "," in unsigned else "." if "." in unsigned else None
        if separator is None:
            return {sign * Decimal(f"{unsigned}{exponent}")}

        groups = unsigned.split(separator)
        candidates: set[Decimal] = set()
        if len(groups) == 2:
            candidates.add(sign * Decimal(f"{groups[0]}.{groups[1]}{exponent}"))
            if (
                groups[0] != "0"
                and 1 <= len(groups[0]) <= 3
                and len(groups[1]) == 3
            ):
                candidates.add(sign * Decimal(f"{''.join(groups)}{exponent}"))
        elif all(len(group) == 3 for group in groups[1:]):
            if 1 <= len(groups[0]) <= 3:
                candidates.add(sign * Decimal(f"{''.join(groups)}{exponent}"))
        return {value for value in candidates if value.is_finite()}
    except (DecimalException, ValueError):
        return set()


def _numeric_candidates(value: object) -> set[Decimal]:
    """Coleta números de um texto ou de campos permitidos da evidência selecionada."""

    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value))
        except DecimalException:
            return set()
        return {number} if number.is_finite() else set()
    if isinstance(value, str):
        return set().union(
            *(_number_candidates(match.group()) for match in _NUMBER_TOKEN.finditer(value))
        )
    if isinstance(value, dict):
        return set().union(*(_numeric_candidates(item) for item in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(_numeric_candidates(item) for item in value))
    return set()


def _has_unsupported_numeric_claim(
    generated: GeneratedAnswer,
    observations: dict[str, dict[str, object]],
) -> bool:
    """Detecta números no rascunho que não constam nas observações selecionadas."""

    if generated.status != "answered":
        return False
    claims = [
        _number_candidates(match.group())
        for match in _NUMBER_TOKEN.finditer(generated.answer)
    ]
    if not claims:
        return False

    supported: set[Decimal] = set()
    for observation_id in generated.observation_ids:
        row = observations.get(observation_id)
        if row is None:
            continue
        for field in ("value", "period", "dimensions"):
            supported.update(_numeric_candidates(row.get(field)))
    # Chamado apenas depois de validar a ligação e o arredondamento das claims.
    supported.update(Decimal(str(claim.value)) for claim in generated.claims)
    return any(not claim.intersection(supported) for claim in claims)


def _filters_match(
    claimed: dict[str, object],
    expected: dict[str, object],
    operators: dict[str, str],
) -> bool:
    if claimed.keys() != expected.keys():
        return False
    for key, expected_value in expected.items():
        claimed_value = claimed[key]
        if (
            operators.get(key, "eq") == "in"
            and isinstance(claimed_value, list)
            and isinstance(expected_value, list)
        ):
            # Serializar cada escalar preserva bool/int/float/string e evita
            # ordenar tipos heterogêneos. Duplicatas não mudam a seleção IN.
            if {json.dumps(item, ensure_ascii=False) for item in claimed_value} != {
                json.dumps(item, ensure_ascii=False) for item in expected_value
            }:
                return False
        elif json.dumps(claimed_value, ensure_ascii=False) != json.dumps(
            expected_value, ensure_ascii=False
        ):
            return False
    return True


def has_unsupported_claims(
    generated: GeneratedAnswer,
    observations: dict[str, dict[str, object]],
    *,
    metric: str,
    period: str,
    filters: dict[str, object],
    filter_operators: dict[str, str] | None = None,
    context_id: str | None = None,
) -> bool:
    """Compara cada afirmação ao seu ID, sem unir números de linhas diferentes.

    O texto livre é descartado pelo consumidor. A checagem lexical é auxiliar;
    não demonstra a semântica de prosa arbitrária nem autoriza percentual derivado.
    """
    if generated.status != "answered":
        return False
    for claim in generated.claims:
        row = observations.get(claim.observation_id)
        if row is None or claim.observation_id not in generated.observation_ids:
            return True
        if isinstance(claim, BoundQuantitativeClaim):
            # Emitida por request, após autorização. Não deriva de valores pessoais,
            # não serve como credencial e não pode ser reutilizada em outro contexto.
            if context_id is None or claim.context_id != context_id:
                return True
        elif (
            claim.metric != metric
            or claim.unit != row["unit"]
            or claim.period != str(row.get("period", period))
            or not _filters_match(claim.filters, filters, filter_operators or {})
            or json.dumps(claim.dimensions, sort_keys=True, ensure_ascii=False)
            != json.dumps(row.get("dimensions", {}), sort_keys=True, ensure_ascii=False)
            or not claim.filter_operators.keys() <= filters.keys()
            or any(
                claim.filter_operators.get(key, "eq")
                != (filter_operators or {}).get(key, "eq") for key in filters
            )
        ):
            return True
        try:
            expected = Decimal(str(row["value"]))
            if claim.decimal_places is not None:
                expected = expected.quantize(
                    Decimal(1).scaleb(-claim.decimal_places), rounding=ROUND_HALF_UP
                )
            if Decimal(str(claim.value)) != expected:
                return True
        except (DecimalException, ValueError, TypeError):
            return True
    return _has_unsupported_numeric_claim(generated, observations)
