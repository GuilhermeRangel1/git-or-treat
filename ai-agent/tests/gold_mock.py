"""SQLite sintético com as 7 tabelas da Gold v1, para testar a camada SQL com nomes reais.

TODOS OS DADOS AQUI SÃO SINTÉTICOS. Nenhuma linha vem do case, da Gold ou de pessoas reais:
UCs ``UC100000``..``UC100005``, alimentadores ``ALIM-FIC-01``..``03``, municípios e bairros
``FICTICIO`` e valores inventados. Só os nomes das colunas e das categorias geradas pelas
regras da Gold (``Sim``/``Não``, prioridades) seguem o dicionário.

Nomes, tipos e chaves das colunas vêm do snapshot do dicionário v1
(``tests/fixtures/gold_dictionary_v1_snapshot.json``). As tabelas financeiras partem do mesmo
consumo mensal por UC (``_MENSAL``), como na Gold: receita e energia reconciliam entre
``consumo_mensal_uc``, ``consumo_receita_bairro`` e ``diagnostico_receita``.
"""

import json
import sqlite3
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.sql.dictionary import SqlDictionary, load_dictionary

GOLD_DICTIONARY_PATH = (
    Path(__file__).parents[1] / "app" / "sql" / "dictionary_gold.toml"
)
GOLD_SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "gold_dictionary_v1_snapshot.json"

# Tipo do snapshot -> tipo declarado no SQLite. "string" vira TEXT para não ganhar afinidade
# numérica; decimal mantém precisão e escala na declaração.
_SQLITE_TYPES = {
    "string": "TEXT",
    "long": "INTEGER",
    "double": "REAL",
    "date": "DATE",
    "boolean": "BOOLEAN",
}

MUNICIPIO_A = "MUNICIPIO FICTICIO A"
MUNICIPIO_B = "MUNICIPIO FICTICIO B"
MUNICIPIO_C = "MUNICIPIO FICTICIO C"

# Prioridades com o texto gerado pelo notebook; "alta" corresponde às duas com prefixo ALTA.
PRIORIDADES_ALTAS = ("ALTA - HISTORICO IRREGULAR", "ALTA - CONSUMO ZERO")

# (bairro, município, classe, alimentador, GD, média kWh, inspeções, irregulares, chamados)
_UCS = (
    ("BAIRRO FICTICIO 1", MUNICIPIO_A, "COMERCIAL", "ALIM-FIC-01", "Não", 410.0, 2, 1, 3),
    ("BAIRRO FICTICIO 2", MUNICIPIO_A, "RESIDENCIAL", "ALIM-FIC-01", "Não", 0.0, 1, 0, 1),
    ("BAIRRO FICTICIO 2", MUNICIPIO_A, "RESIDENCIAL", "ALIM-FIC-01", "Não", 180.0, 0, 0, 0),
    ("BAIRRO FICTICIO 3", MUNICIPIO_B, "COMERCIAL", "ALIM-FIC-02", "Sim", 520.0, 1, 0, 2),
    ("BAIRRO FICTICIO 3", MUNICIPIO_B, "RESIDENCIAL", "ALIM-FIC-02", "Não", None, 1, 0, 0),
    ("BAIRRO FICTICIO 4", MUNICIPIO_C, "RESIDENCIAL", "ALIM-FIC-03", "Sim", 95.0, 3, 0, 1),
)


def _id_uc(index: int) -> str:
    return f"UC{100000 + index}"


def _cadastro(index: int) -> dict[str, Any]:
    bairro, municipio, classe, alimentador, *_ = _UCS[index]
    return {
        "id_uc": _id_uc(index),
        "municipio": municipio,
        "bairro": bairro,
        "uf": "XX",
        "classe": classe,
        "subgrupo": _subgrupo(classe),
        "alimentador": alimentador,
        "data_ligacao": f"2020-0{index + 1}-15",
        "status": "ATIVO",
    }


def _subgrupo(classe: str) -> str:
    return "B3" if classe == "COMERCIAL" else "B1"


def _prioridade(media: float | None, realizadas: int, irregulares: int, gd: str) -> str:
    """Mesma ordem de regras do notebook Silver_to_gold (fila_inspecao)."""

    if irregulares > 0:
        return "ALTA - HISTORICO IRREGULAR"
    if media is None:
        return "REVISAR - SEM HISTORICO DE CONSUMO"
    if media == 0 and gd == "Não":
        return "ALTA - CONSUMO ZERO"
    if realizadas == 0:
        return "MEDIA - NUNCA INSPECIONADO"
    return "BAIXA"


FILA_INSPECAO_ROWS = tuple(
    {
        **_cadastro(i),
        "possui_geracao_solar": gd,
        "total_inspecoes_realizadas": realizadas,
        "total_inspecoes_irregulares": irregulares,
        "media_consumo_historico": media,
        "prioridade_inspecao": _prioridade(media, realizadas, irregulares, gd),
    }
    for i, (_b, _m, _c, _a, gd, media, realizadas, irregulares, _ch) in enumerate(_UCS)
)

VISAO_360_UC_ROWS = tuple(
    {
        **_cadastro(i),
        "possui_gd": gd,
        "total_chamados_callcenter": chamados,
        "media_satisfacao_atendimento": 4.0 if chamados else None,
        "total_interrupcoes_sofridas": 1 if alimentador == "ALIM-FIC-01" else 0,
        "duracao_total_interrupcoes_horas": 2.0 if alimentador == "ALIM-FIC-01" else 0.0,
        "media_consumo_historico": media,
    }
    for i, (_b, _m, _c, alimentador, gd, media, _r, _i, chamados) in enumerate(_UCS)
)

# Pares UC/competência com fatura e leitura: (índice da UC, competência, bandeira, faturas,
# kWh, R$). A UC 4 não tem leitura e por isso não aparece nas tabelas financeiras.
_MENSAL = (
    (0, "2026-08", "VERDE", 2, 400.0, 320.00),
    (1, "2026-08", "VERDE", 1, 0.0, 30.00),
    (2, "2026-08", "VERDE", 1, 200.0, 160.00),
    (3, "2026-08", "VERDE", 1, 500.0, 400.00),
    (5, "2026-08", "VERDE", 1, 100.0, 80.00),
    (0, "2026-09", "AMARELA", 1, 300.0, 255.00),
    (1, "2026-09", "AMARELA", 1, 0.0, 30.00),
    (2, "2026-09", "AMARELA", 1, 150.0, 127.50),
    (3, "2026-09", "AMARELA", 1, 520.0, 442.00),
    (5, "2026-09", "AMARELA", 1, 90.0, 76.50),
)

CONSUMO_MENSAL_UC_ROWS = tuple(
    {"id_uc": _id_uc(i), "competencia": competencia, "consumo_kwh": kwh, "receita_reais": reais}
    for i, competencia, _bandeira, _faturas, kwh, reais in _MENSAL
)


def _aggregate(key_of) -> dict[tuple, dict[str, float]]:
    groups: dict[tuple, dict[str, float]] = defaultdict(
        lambda: {"ucs": 0, "faturas": 0, "kwh": 0.0, "reais": 0.0}
    )
    for i, competencia, bandeira, faturas, kwh, reais in _MENSAL:
        group = groups[key_of(i, competencia, bandeira)]
        group["ucs"] += 1
        group["faturas"] += faturas
        group["kwh"] += kwh
        group["reais"] += reais
    return groups


def _diagnostico_key(i: int, competencia: str, bandeira: str) -> tuple:
    _bairro, municipio, classe, _alimentador, gd, *_ = _UCS[i]
    return competencia, municipio, classe, _subgrupo(classe), bandeira, gd


DIAGNOSTICO_RECEITA_ROWS = tuple(
    {
        "competencia": competencia,
        "municipio": municipio,
        "classe_consumo": classe,
        "subgrupo_tarifario": subgrupo,
        "bandeira_tarifaria": bandeira,
        "possui_gd": gd,
        "qtd_ucs_distintas_faturadas_no_mes": g["ucs"],
        "soma_faturamentos_mensais": g["faturas"],
        "consumo_total_kwh": g["kwh"],
        "receita_total_reais": g["reais"],
        "ticket_medio_reais_por_uc": g["reais"] / g["ucs"],
        "consumo_medio_kwh_por_uc": g["kwh"] / g["ucs"],
        "tarifa_media_efetiva": g["reais"] / g["kwh"] if g["kwh"] else None,
    }
    for (competencia, municipio, classe, subgrupo, bandeira, gd), g in _aggregate(
        _diagnostico_key
    ).items()
)

CONSUMO_RECEITA_BAIRRO_ROWS = tuple(
    {
        "competencia": competencia,
        "municipio": municipio,
        "bairro": bairro,
        "classe_consumo": classe,
        "consumo_total_kwh": g["kwh"],
        "receita_total_reais": g["reais"],
        "qtd_ucs_distintas_faturadas_no_mes": g["ucs"],
    }
    for (competencia, municipio, bairro, classe), g in _aggregate(
        lambda i, competencia, _bandeira: (competencia, _UCS[i][1], _UCS[i][0], _UCS[i][2])
    ).items()
)


def _dec_fec(
    alimentador: str, municipio: str, competencia: str, total: int, afetadas: int,
    eventos: int, horas: float,
) -> dict[str, Any]:
    return {
        "id_alimentador": alimentador,
        "municipio": municipio,
        "competencia": competencia,
        "total_ucs_alimentador": total,
        "ucs_interrompidas": afetadas,
        "frequencia_total_interrupcoes": eventos,
        "duracao_total_interrupcoes_horas": horas,
        "DEC": horas / total,
        "FEC": eventos / total,
    }


# Só alimentador/mês com ocorrência gera linha, como na Gold: ALIM-FIC-02 não tem 2026-09.
INDICADORES_DEC_FEC_ROWS = (
    _dec_fec("ALIM-FIC-01", MUNICIPIO_A, "2026-08", 3, 2, 3, 6.0),
    _dec_fec("ALIM-FIC-01", MUNICIPIO_A, "2026-09", 3, 3, 3, 1.5),
    _dec_fec("ALIM-FIC-02", MUNICIPIO_B, "2026-08", 2, 2, 2, 5.0),
)

# (índice da UC, média P1, meses P1, média P2, meses P2, variação kWh, variação %, queda > 30%)
_VARIACAO = (
    (0, 420.0, 12, 300.0, 12, -120.0, -28.57, False),
    (1, 50.0, 12, 0.0, 12, -50.0, -100.0, True),
    (2, 200.0, 10, 160.0, 12, -40.0, -20.0, False),
    (3, 800.0, 12, 520.0, 12, -280.0, -35.0, True),
    (4, None, 0, None, 0, None, None, False),
    (5, 150.0, 12, 95.0, 11, -55.0, -36.67, True),
)

VARIACAO_CONSUMO_UC_ROWS = tuple(
    {
        "id_uc": _id_uc(i),
        "municipio": _UCS[i][1],
        "bairro": _UCS[i][0],
        "possui_gd": _UCS[i][4],
        "consumo_medio_inicial": inicial,
        "meses_com_leitura_p1": meses_p1,
        "consumo_medio_final": final,
        "meses_com_leitura_p2": meses_p2,
        "variacao_kwh": kwh,
        "variacao_pct": pct,
        "queda_consumo_superior_30_pct": queda,
    }
    for i, inicial, meses_p1, final, meses_p2, kwh, pct, queda in _VARIACAO
)

GOLD_ROWS: dict[str, tuple[dict[str, Any], ...]] = {
    "diagnostico_receita": DIAGNOSTICO_RECEITA_ROWS,
    "indicadores_dec_fec": INDICADORES_DEC_FEC_ROWS,
    "fila_inspecao": FILA_INSPECAO_ROWS,
    "visao_360_uc": VISAO_360_UC_ROWS,
    "consumo_receita_bairro": CONSUMO_RECEITA_BAIRRO_ROWS,
    "variacao_consumo_uc": VARIACAO_CONSUMO_UC_ROWS,
    "consumo_mensal_uc": CONSUMO_MENSAL_UC_ROWS,
}


def load_gold_snapshot() -> dict[str, Any]:
    return json.loads(GOLD_SNAPSHOT_PATH.read_text(encoding="utf-8"))


def load_gold_metadata() -> dict[str, Any]:
    """TOML bruto, inclusive os metadados semânticos que o carregador ignora."""

    return tomllib.loads(GOLD_DICTIONARY_PATH.read_text(encoding="utf-8"))


def load_gold_dictionary() -> SqlDictionary:
    return load_dictionary(GOLD_DICTIONARY_PATH)


def build_gold_v1_sqlite(path: Path) -> Path:
    """Cria em ``path`` as 7 tabelas com nomes e tipos do v1 e as linhas sintéticas acima."""

    tables = load_gold_snapshot()["tables"]
    connection = sqlite3.connect(path)
    try:
        for name, spec in tables.items():
            columns = spec["columns"]
            definitions = ", ".join(
                f'"{column}" {_sqlite_type(v1_type)}' for column, v1_type in columns.items()
            )
            key = ", ".join(f'"{column}"' for column in spec["key"])
            connection.execute(f'CREATE TABLE "{name}" ({definitions}, PRIMARY KEY ({key}))')
            placeholders = ", ".join("?" for _ in columns)
            connection.executemany(
                f'INSERT INTO "{name}" VALUES ({placeholders})',
                [tuple(row[column] for column in columns) for row in GOLD_ROWS[name]],
            )
        connection.commit()
    finally:
        connection.close()
    return path


def _sqlite_type(v1_type: str) -> str:
    if v1_type.startswith("decimal("):
        return v1_type.upper()
    return _SQLITE_TYPES[v1_type]
