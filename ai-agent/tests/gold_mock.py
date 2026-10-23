"""SQLite sintético com as 4 tabelas da Gold v1, para testar a camada SQL com nomes reais.

TODOS OS DADOS AQUI SÃO SINTÉTICOS. Nenhuma linha vem do case, da Gold ou de pessoas reais:
UCs ``UC100000``..``UC100005``, alimentadores ``ALIM-FIC-01``/``02``, valores inventados e
CPF/nome já no formato mascarado do notebook (``000.***.***-00``, ``FICTICIO *******``).
Os nomes de município são públicos e servem só para exercitar filtros.

Nomes e tipos das colunas vêm do snapshot do dicionário v1
(``tests/fixtures/gold_dictionary_v1_snapshot.json``). As colunas pessoais e de pipeline
existem fisicamente no banco, como na Gold, para provar que o dicionário as bloqueia.
"""

import json
import sqlite3
import tomllib
from pathlib import Path
from typing import Any

from app.sql.dictionary import SqlDictionary, load_dictionary

GOLD_DICTIONARY_PATH = (
    Path(__file__).parents[1] / "app" / "sql" / "dictionary_gold.toml"
)
GOLD_SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "gold_dictionary_v1_snapshot.json"

# Tipo do dicionário v1 (Spark) -> tipo declarado no SQLite. "string" vira TEXT para não
# ganhar afinidade numérica; decimal mantém precisão e escala na declaração.
_SQLITE_TYPES = {
    "string": "TEXT",
    "long": "INTEGER",
    "double": "REAL",
    "date": "DATE",
    "boolean": "BOOLEAN",
    "timestamp": "TIMESTAMP",
}

JABOATAO = "JABOATAO DOS GUARARAPES"
RECIFE = "RECIFE"
OLINDA = "OLINDA"

# Prioridades com o texto gerado pelo notebook; "alta" corresponde às duas primeiras.
PRIORIDADES_ALTAS = ("ALTA - HISTORICO IRREGULAR", "ALTA - CONSUMO ZERO")


def _receita(
    competencia: str,
    municipio: str,
    classe: str,
    subgrupo: str,
    bandeira: str,
    gd: str,
    ucs: int,
    consumo: float,
    receita: float,
) -> dict[str, Any]:
    return {
        "competencia": competencia,
        "municipio": municipio,
        "classe_consumo": classe,
        "subgrupo_tarifario": subgrupo,
        "bandeira_tarifaria": bandeira,
        "possuo_gd": gd,
        "qtd_ucs_distintas_faturadas_no_mes": ucs,
        "soma_faturamentos_mensais": ucs,
        "consumo_total_kwh": consumo,
        "receita_total_reais": receita,
        "ticket_medio_reais_por_uc": round(receita / ucs, 6),
        "consumo_medio_kwh_por_uc": consumo / ucs,
        "tarifa_media_efetiva": receita / consumo,
    }


DIAGNOSTICO_RECEITA_ROWS = (
    _receita("2026-08", JABOATAO, "COMERCIAL", "B3", "VERDE", "Não", 2, 900.0, 720.00),
    _receita("2026-08", JABOATAO, "COMERCIAL", "B3", "VERDE", "Sim", 1, 300.0, 240.00),
    _receita("2026-08", JABOATAO, "RESIDENCIAL", "B1", "VERDE", "Não", 3, 600.0, 480.00),
    _receita("2026-08", RECIFE, "COMERCIAL", "B3", "VERDE", "Não", 1, 500.0, 400.00),
    _receita("2026-09", JABOATAO, "COMERCIAL", "B3", "AMARELA", "Não", 2, 800.0, 680.00),
    _receita("2026-09", JABOATAO, "RESIDENCIAL", "B1", "AMARELA", "Não", 3, 650.0, 552.50),
    _receita("2026-09", RECIFE, "COMERCIAL", "B3", "AMARELA", "Não", 1, 450.0, 382.50),
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


INDICADORES_DEC_FEC_ROWS = (
    _dec_fec("ALIM-FIC-01", JABOATAO, "2026-08", 4, 2, 3, 6.0),
    _dec_fec("ALIM-FIC-01", JABOATAO, "2026-09", 4, 1, 1, 2.0),
    _dec_fec("ALIM-FIC-02", RECIFE, "2026-08", 2, 2, 2, 5.0),
    _dec_fec("ALIM-FIC-02", RECIFE, "2026-09", 2, 0, 0, 0.0),
)


def _cadastro(index: int, bairro: str, municipio: str, classe: str, alimentador: str) -> dict:
    return {
        "id_uc": f"UC{100000 + index}",
        "cpf_cnpj": f"{index:03d}.***.***-{index:02d}",
        "nome_titular": "FICTICIO *******",
        "logradouro": "RUA FICTICIA",
        "numero": "S/N",
        "bairro": bairro,
        "municipio": municipio,
        "uf": "PE",
        "cep": "00000-000",
        "classe": classe,
        "subgrupo_tarifario": "B3" if classe == "COMERCIAL" else "B1",
        "alimentador": alimentador,
        "data_ligacao": f"2020-0{index + 1}-15",
        "status": "ATIVO",
        "latitude": None,
        "longitude": None,
    }


# (bairro, município, classe, alimentador, GD, média kWh, inspeções, irregulares, chamados)
_UCS = (
    ("CENTRO", JABOATAO, "COMERCIAL", "ALIM-FIC-01", "Não", 410.0, 2, 1, 3),
    ("PIEDADE", JABOATAO, "RESIDENCIAL", "ALIM-FIC-01", "Não", 0.0, 1, 0, 1),
    ("PIEDADE", JABOATAO, "RESIDENCIAL", "ALIM-FIC-01", "Não", 180.0, 0, 0, 0),
    ("BOA VIAGEM", RECIFE, "COMERCIAL", "ALIM-FIC-02", "Sim", 520.0, 1, 0, 2),
    ("BOA VIAGEM", RECIFE, "RESIDENCIAL", "ALIM-FIC-02", "Não", None, 1, 0, 0),
    ("CARMO", OLINDA, "RESIDENCIAL", "ALIM-FIC-02", "Sim", 95.0, 3, 0, 1),
)


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
        **_cadastro(i, bairro, municipio, classe, alimentador),
        "media_consumo_historico": media,
        "total_inspecoes_realizadas": realizadas,
        "total_inspecoes_irregulares": irregulares,
        "total_chamados_callcenter": chamados,
        "media_satisfacao_atendimento": 4.0,
        "possui_geracao_solar": gd,
        "prioridade_inspecao": _prioridade(media, realizadas, irregulares, gd),
    }
    for i, (bairro, municipio, classe, alimentador, gd, media, realizadas, irregulares, chamados)
    in enumerate(_UCS)
)

VISAO_360_UC_ROWS = tuple(
    {
        **_cadastro(i, bairro, municipio, classe, alimentador),
        "_cpf_cnpj_conflitante": False,
        "_nome_titular_conflitante": False,
        "_geo_invalida": True,
        "_ligacao_futura": False,
        "_ligacao_sentinela": False,
        "_arquivo_origem": "sintetico.csv",
        "_ordem_na_origem": i + 1,
        "_lote_id": "lote-sintetico",
        "_id_registro": i + 1,
        "_data_processamento": "2026-10-22T00:00:00",
        "_run_id": "run-sintetico",
        "possui_gd": gd,
        "total_chamados_callcenter": chamados,
        "media_satisfacao_atendimento": 4.0,
        "total_interrupcoes_sofridas": 1 if alimentador == "ALIM-FIC-01" else 0,
        "duracao_total_interrupcoes_horas": 2.0 if alimentador == "ALIM-FIC-01" else 0.0,
        "media_consumo_historico": media,
    }
    for i, (bairro, municipio, classe, alimentador, gd, media, _r, _i, chamados)
    in enumerate(_UCS)
)

GOLD_ROWS: dict[str, tuple[dict[str, Any], ...]] = {
    "diagnostico_receita": DIAGNOSTICO_RECEITA_ROWS,
    "indicadores_dec_fec": INDICADORES_DEC_FEC_ROWS,
    "fila_inspecao": FILA_INSPECAO_ROWS,
    "visao_360_uc": VISAO_360_UC_ROWS,
}


def load_gold_snapshot() -> dict[str, Any]:
    return json.loads(GOLD_SNAPSHOT_PATH.read_text(encoding="utf-8"))


def load_gold_metadata() -> dict[str, Any]:
    """TOML bruto, inclusive os metadados semânticos que o carregador ignora."""

    return tomllib.loads(GOLD_DICTIONARY_PATH.read_text(encoding="utf-8"))


def load_gold_dictionary() -> SqlDictionary:
    return load_dictionary(GOLD_DICTIONARY_PATH)


def build_gold_v1_sqlite(path: Path) -> Path:
    """Cria em ``path`` as 4 tabelas com nomes e tipos do v1 e as linhas sintéticas acima."""

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
