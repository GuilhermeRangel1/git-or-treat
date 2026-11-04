"""Base SQLite de teste com dados inventados no formato provisório de gold_indicadores."""

import sqlite3
from pathlib import Path

from app.sql.dictionary import SqlDictionary, load_dictionary

TEST_DICTIONARY_PATH = Path(__file__).parent / "fixtures" / "sql_dictionary_test.toml"

# Valores fictícios, sem relação com a V-Energy ou com qualquer município real.
GOLD_ROWS = [
    ("2025-01", "Municipio Ficticio A", "Bairro Alfa", "residencial", 1000.50, 4200.0, 120),
    ("2025-01", "Municipio Ficticio A", "Bairro Beta", "comercial", 2500.00, 7300.0, 35),
    ("2025-01", "Municipio Ficticio B", "Bairro Gama", "residencial", 800.25, 3100.0, 98),
    ("2025-02", "Municipio Ficticio A", "Bairro Alfa", "residencial", 950.00, 3900.0, 119),
    ("2025-02", "Municipio Ficticio A", "Bairro Beta", "comercial", 2650.75, 7600.0, 36),
    ("2025-02", "Municipio Ficticio B", "Bairro Gama", "residencial", 820.00, 3150.0, 99),
    ("2025-03", "Municipio Ficticio A", "Bairro Alfa", "residencial", 970.10, 4000.0, 121),
    ("2025-03", "Municipio Ficticio B", "Bairro Gama", "comercial", 1200.00, 2900.0, 12),
]

CADASTRO_ROWS = [
    ("UC-0001", "Municipio Ficticio A", "000.000.000-00", "Pessoa Ficticia Um"),
    ("UC-0002", "Municipio Ficticio B", "111.111.111-11", "Pessoa Ficticia Dois"),
]


def load_test_dictionary() -> SqlDictionary:
    return load_dictionary(TEST_DICTIONARY_PATH)


def build_gold_sqlite(path: Path) -> Path:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE gold_indicadores (
                competencia TEXT NOT NULL,
                municipio TEXT NOT NULL,
                bairro TEXT NOT NULL,
                classe TEXT NOT NULL,
                receita_total REAL NOT NULL,
                energia_consumida_kwh REAL NOT NULL,
                ucs_ativas INTEGER NOT NULL
            );
            CREATE TABLE cadastro_teste (
                uc_id TEXT PRIMARY KEY,
                municipio TEXT NOT NULL,
                cpf_cnpj TEXT NOT NULL,
                nome_titular TEXT NOT NULL
            );
            CREATE TABLE interna_nao_listada (segredo TEXT);
            """
        )
        connection.executemany(
            "INSERT INTO gold_indicadores VALUES (?, ?, ?, ?, ?, ?, ?)", GOLD_ROWS
        )
        connection.executemany("INSERT INTO cadastro_teste VALUES (?, ?, ?, ?)", CADASTRO_ROWS)
        connection.execute("INSERT INTO interna_nao_listada VALUES ('nao deve sair')")
        connection.commit()
    finally:
        connection.close()
    return path
