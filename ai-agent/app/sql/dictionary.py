"""Carregamento do dicionário de tabelas, colunas e políticas da camada SQL."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

DEFAULT_DICTIONARY_PATH = Path(__file__).with_name("dictionary.toml")

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


class DictionaryError(ValueError):
    """O arquivo do dicionário está ausente, malformado ou contraditório."""


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: MappingProxyType[str, str]
    description: str = ""


@dataclass(frozen=True)
class SqlLimits:
    max_rows: int
    max_tables: int
    timeout_ms: int
    max_sql_chars: int


@dataclass(frozen=True)
class SqlDictionary:
    version: str
    status: str
    limits: SqlLimits
    tables: MappingProxyType[str, TableSpec]
    allowed_functions: frozenset[str]
    allowed_cast_types: frozenset[str]
    sensitive_columns: frozenset[str]
    reserved_prefixes: tuple[str, ...]

    def schema(self) -> dict[str, dict[str, str]]:
        """Esquema no formato do sqlglot, apenas com colunas permitidas."""

        return {name: dict(table.columns) for name, table in self.tables.items()}

    def is_reserved(self, identifier: str) -> bool:
        return identifier.casefold().startswith(self.reserved_prefixes)


def load_dictionary(path: Path | str = DEFAULT_DICTIONARY_PATH) -> SqlDictionary:
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise DictionaryError(f"não foi possível ler o dicionário: {exc}") from exc
    return parse_dictionary(raw)


def parse_dictionary(raw: dict[str, Any]) -> SqlDictionary:
    limits_raw = _table(raw, "limits")
    policy = _table(raw, "policy")
    tables_raw = _table(raw, "tables")

    limits = SqlLimits(
        max_rows=_positive_int(limits_raw, "max_rows"),
        max_tables=_positive_int(limits_raw, "max_tables"),
        timeout_ms=_positive_int(limits_raw, "timeout_ms"),
        max_sql_chars=_positive_int(limits_raw, "max_sql_chars"),
    )
    sensitive = _names(policy, "sensitive_columns")
    reserved = tuple(_names(policy, "reserved_prefixes", identifier=False))

    if not tables_raw:
        raise DictionaryError("o dicionário precisa declarar ao menos uma tabela")

    tables: dict[str, TableSpec] = {}
    for table_name, spec in tables_raw.items():
        _check_identifier(table_name, "tabela")
        if table_name.startswith(reserved):
            raise DictionaryError(f"tabela {table_name!r} usa prefixo reservado")
        if not isinstance(spec, dict):
            raise DictionaryError(f"tabela {table_name!r} malformada")
        columns = spec.get("columns")
        if not isinstance(columns, dict) or not columns:
            raise DictionaryError(f"tabela {table_name!r} precisa de colunas")
        for column, column_type in columns.items():
            _check_identifier(column, "coluna")
            if not isinstance(column_type, str) or not column_type:
                raise DictionaryError(f"coluna {table_name}.{column} sem tipo")
            if column in sensitive:
                raise DictionaryError(
                    f"coluna {table_name}.{column} está ao mesmo tempo permitida e sensível"
                )
            if column.startswith(reserved):
                raise DictionaryError(f"coluna {table_name}.{column} usa prefixo reservado")
        tables[table_name] = TableSpec(
            name=table_name,
            columns=MappingProxyType(dict(columns)),
            description=str(spec.get("description", "")),
        )

    version = raw.get("version")
    if not isinstance(version, str) or not version:
        raise DictionaryError("o dicionário precisa de 'version'")

    return SqlDictionary(
        version=version,
        status=str(raw.get("status", "")),
        limits=limits,
        tables=MappingProxyType(tables),
        allowed_functions=_names(policy, "allowed_functions"),
        allowed_cast_types=_names(policy, "allowed_cast_types"),
        sensitive_columns=sensitive,
        reserved_prefixes=reserved,
    )


def _table(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise DictionaryError(f"seção [{key}] ausente ou malformada")
    return value


def _positive_int(section: dict[str, Any], key: str) -> int:
    value = section.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise DictionaryError(f"limits.{key} precisa ser inteiro positivo")
    return value


def _names(section: dict[str, Any], key: str, identifier: bool = True) -> frozenset[str]:
    values = section.get(key)
    if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values):
        raise DictionaryError(f"policy.{key} precisa ser lista de textos")
    names = frozenset(v.casefold() for v in values)
    if identifier:
        for name in names:
            _check_identifier(name, key)
    return names


def _check_identifier(name: str, kind: str) -> None:
    if not isinstance(name, str) or not _IDENTIFIER.match(name):
        raise DictionaryError(f"{kind} {name!r} não é identificador simples em minúsculas")
