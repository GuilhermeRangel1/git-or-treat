"""Preparação de parâmetros F1; não aprova SQL nem autoriza execução."""

from datetime import date
from decimal import Decimal

from app.schemas.sql_generation import SqlParameter


class SqlParameterMismatch(ValueError):
    """Os nomes extraídos da consulta divergem do envelope de parâmetros."""


def prepare_sql_parameters(
    parameters: dict[str, SqlParameter], *, referenced_names: frozenset[str]
) -> dict[str, str | int | float | bool | date | Decimal]:
    """Recebe nomes do analisador SQL, nunca uma declaração de dependências do modelo.

    A conferência deve ocorrer antes de abrir uma conexão. O chamador ainda precisa
    validar AST, escopo, publicação e regras de negócio antes de executar a consulta.
    """
    if set(parameters) != referenced_names:
        raise SqlParameterMismatch("Parâmetros da consulta incompatíveis com o envelope.")
    result = {}
    for name, parameter in parameters.items():
        if parameter.type == "date":
            result[name] = date.fromisoformat(parameter.value)
        elif parameter.type == "decimal":
            result[name] = Decimal(parameter.value)
        else:
            result[name] = parameter.value
    return result
