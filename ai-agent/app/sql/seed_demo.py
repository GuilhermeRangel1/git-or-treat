"""Cria uma base SQLite descartável com valores inventados para a demonstração."""

import argparse
import sqlite3
from pathlib import Path

_ROWS = (
    ("2025-01", "Municipio Ficticio A", "Bairro Alfa", "residencial", 1000.50, 4200.0, 120, 2, 4),
    ("2025-01", "Municipio Ficticio A", "Bairro Beta", "comercial", 2500.00, 7300.0, 35, 1, 3),
    ("2025-01", "Municipio Ficticio B", "Bairro Gama", "residencial", 800.25, 3100.0, 98, 0, 2),
    ("2025-02", "Municipio Ficticio A", "Bairro Alfa", "residencial", 950.00, 3900.0, 119, 1, 5),
    ("2025-02", "Municipio Ficticio A", "Bairro Beta", "comercial", 2650.75, 7600.0, 36, 0, 2),
    ("2025-02", "Municipio Ficticio B", "Bairro Gama", "residencial", 820.00, 3150.0, 99, 1, 1),
    ("2025-03", "Municipio Ficticio A", "Bairro Alfa", "residencial", 970.10, 4000.0, 121, 0, 3),
    ("2025-03", "Municipio Ficticio B", "Bairro Gama", "comercial", 1200.00, 2900.0, 12, 2, 1),
)


def build_demo_database(path: Path) -> Path:
    """Cria a base somente se o caminho ainda não existir."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=rwc", uri=True)
    try:
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='gold_indicadores'"
        ).fetchone():
            raise FileExistsError(path)
        connection.execute(
            """CREATE TABLE gold_indicadores (
                competencia TEXT NOT NULL,
                municipio TEXT NOT NULL,
                bairro TEXT NOT NULL,
                classe TEXT NOT NULL,
                receita_total REAL NOT NULL,
                energia_consumida_kwh REAL NOT NULL,
                ucs_ativas INTEGER NOT NULL,
                interrupcoes INTEGER NOT NULL,
                chamados INTEGER NOT NULL
            )"""
        )
        connection.executemany(
            "INSERT INTO gold_indicadores VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", _ROWS
        )
        connection.commit()
    finally:
        connection.close()
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cria a base SQLite artificial do chat.")
    parser.add_argument("output", type=Path)
    options = parser.parse_args()
    build_demo_database(options.output)
