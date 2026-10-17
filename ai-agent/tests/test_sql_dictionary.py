import copy
import tomllib

import pytest

from app.sql.dictionary import (
    DEFAULT_DICTIONARY_PATH,
    DictionaryError,
    load_dictionary,
    parse_dictionary,
)
from app.sql.validator import validate_sql
from tests.sql_support import TEST_DICTIONARY_PATH


def raw_test_dictionary() -> dict:
    return tomllib.loads(TEST_DICTIONARY_PATH.read_text(encoding="utf-8"))


def test_default_dictionary_loads_and_is_marked_provisional() -> None:
    dictionary = load_dictionary(DEFAULT_DICTIONARY_PATH)

    assert dictionary.status == "provisorio"
    assert "gold_indicadores" in dictionary.tables
    assert {"cpf_cnpj", "nome_titular"} <= dictionary.sensitive_columns
    for table in dictionary.tables.values():
        assert not set(table.columns) & dictionary.sensitive_columns


def test_default_dictionary_validates_a_simple_query() -> None:
    dictionary = load_dictionary()

    query = validate_sql(
        "SELECT classe, SUM(energia_consumida_kwh) FROM gold_indicadores GROUP BY classe",
        dictionary,
        "postgres",
    )

    assert query.applied_limit == dictionary.limits.max_rows


def test_renaming_a_table_only_requires_the_dictionary(tmp_path) -> None:
    text = TEST_DICTIONARY_PATH.read_text(encoding="utf-8").replace(
        "gold_indicadores", "gold_indicadores_v2"
    )
    path = tmp_path / "renomeado.toml"
    path.write_text(text, encoding="utf-8")
    dictionary = load_dictionary(path)

    assert validate_sql("SELECT bairro FROM gold_indicadores_v2", dictionary, "sqlite")
    with pytest.raises(Exception, match="unknown_table"):
        validate_sql("SELECT bairro FROM gold_indicadores", dictionary, "sqlite")


def test_column_both_allowed_and_sensitive_is_rejected() -> None:
    raw = raw_test_dictionary()
    raw["tables"]["cadastro_teste"]["columns"]["cpf_cnpj"] = "text"

    with pytest.raises(DictionaryError, match="sensível"):
        parse_dictionary(raw)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw.pop("limits"),
        lambda raw: raw["limits"].update(max_rows=0),
        lambda raw: raw["limits"].update(timeout_ms=True),
        lambda raw: raw.update(tables={}),
        lambda raw: raw["tables"].update({"pg_tabela": {"columns": {"a": "int"}}}),
        lambda raw: raw["tables"].update({"Maiuscula": {"columns": {"a": "int"}}}),
        lambda raw: raw["tables"]["gold_indicadores"].update(columns={}),
        lambda raw: raw["policy"].update(allowed_functions="sum"),
        lambda raw: raw.pop("version"),
    ],
)
def test_malformed_dictionary_is_rejected(mutate) -> None:
    raw = copy.deepcopy(raw_test_dictionary())
    mutate(raw)

    with pytest.raises(DictionaryError):
        parse_dictionary(raw)


def test_missing_file_is_reported(tmp_path) -> None:
    with pytest.raises(DictionaryError):
        load_dictionary(tmp_path / "ausente.toml")
