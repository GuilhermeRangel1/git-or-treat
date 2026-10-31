"""Confere um lote candidato da Gold exportado em CSV e imprime somente agregados.

O script lê os arquivos em modo somente leitura e não grava nada no diretório do lote (o destino
de ``--json`` é recusado se estiver nele ou for um arquivo de entrada). A saída nunca inclui
linhas de dados nem identificadores de UC ou de alimentador. Só as dimensões de
``PUBLISHABLE_DIMENSIONS`` têm valores listados, e nunca quando o nome ou os valores parecem dado
pessoal; as demais colunas mostram apenas contagens, tipos e número de distintos.
Reconciliações com medida nula ou inválida saem como ``nao_verificavel`` e as janelas de 12
meses exigem competências contínuas.

Uso:
    python scripts/gold_coverage.py <diretório do lote>
    GOLD_DATA_DIR=<diretório do lote> python scripts/gold_coverage.py [--json <arquivo>]

Cada tabela é procurada em ``<dir>/<tabela>/<tabela>.csv`` (layout do carregador do Backend) ou,
na falta dele, nos ``*.csv`` de ``<dir>/<tabela>/`` (pasta de partes do Spark) ou em
``<dir>/<tabela>.csv`` (CSVs soltos). Se existir ``<dir>/manifest.json`` ou
``<dir>/manifesto/manifest.json`` (com os dois, vale o da raiz), a saída mostra só a
identificação técnica do lote e avisa quando o ambiente não é PROD ou quando
``tabelas_exportadas`` não bate com as tabelas encontradas.
"""

import argparse
import contextlib
import csv
import json
import os
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

csv.field_size_limit(10_000_000)

# Grão declarado pelo notebook Silver_to_gold (dicionário tables_gold_pk, branch feat/gold).
TABLE_KEYS = {
    "visao_360_uc": ("id_uc",),
    "fila_inspecao": ("id_uc",),
    "variacao_consumo_uc": ("id_uc",),
    "consumo_mensal_uc": ("id_uc", "competencia"),
    "consumo_receita_bairro": ("competencia", "municipio", "bairro", "classe_consumo"),
    "diagnostico_receita": (
        "competencia",
        "municipio",
        "classe_consumo",
        "subgrupo_tarifario",
        "bandeira_tarifaria",
        "possui_gd",
    ),
    "indicadores_dec_fec": ("id_alimentador", "competencia"),
}
# Ordem de leitura: visao_360_uc primeiro, porque fornece o município de cada UC.
TABLES = (
    "visao_360_uc",
    "fila_inspecao",
    "variacao_consumo_uc",
    "consumo_mensal_uc",
    "consumo_receita_bairro",
    "diagnostico_receita",
    "indicadores_dec_fec",
)
# Únicas colunas cujos valores podem aparecer na saída (allowlist); as demais nunca os publicam.
PUBLISHABLE_DIMENSIONS = {
    "municipio",
    "classe",
    "classe_consumo",
    "subgrupo",
    "subgrupo_tarifario",
    "bandeira_tarifaria",
    "possui_gd",
    "possui_geracao_solar",
    "status",
    "uf",
    "prioridade_inspecao",
    "queda_consumo_superior_30_pct",
}
DATE_KINDS = {"ano_mes", "data"}
SENSITIVE_TOKENS = {
    "cpf",
    "cnpj",
    "nome",
    "titular",
    "logradouro",
    "numero",
    "cep",
    "latitude",
    "longitude",
    "email",
    "telefone",
    "celular",
    "endereco",
    "complemento",
    "nascimento",
    "rg",
}
MONEY_OR_ENERGY = re.compile(r"(consumo|receita|kwh|reais|ticket|tarifa)")
LOW_CARDINALITY = 25
DISTINCT_CAP = 200_000
NUMERIC_SENTINELS = {
    Decimal(v) for v in ("-1", "-9", "-99", "-999", "-9999", "9999", "99999", "999999")
}
NULL_TOKENS = {"", "null", "none", "nan", "na", "n/a", "\\n"}
BOOL_TOKENS = {"true", "false", "sim", "não", "nao", "s", "n", "0", "1", "t", "f"}
YM = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
INT = re.compile(r"^-?\d+$")
DEC_DOT = re.compile(r"^-?\d+\.\d+(E-?\d+)?$", re.IGNORECASE)
DEC_COMMA = re.compile(r"^-?\d+,\d+$")
CPF_LIKE = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
CEP_LIKE = re.compile(r"^\d{5}-?\d{3}$")
EMAIL_LIKE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.IGNORECASE)
MONEY_TOLERANCE = Decimal("0.05")
ATENDIMENTO_COLUMNS = ("total_chamados_callcenter", "media_satisfacao_atendimento")
# Gold v2 preserva notas não negativas; nenhuma escala máxima foi homologada.
# Raiz do lote (exportador da Gold) ou subpasta manifesto/; com os dois, vale o da raiz.
MANIFEST_PATHS = (Path("manifest.json"), Path("manifesto") / "manifest.json")
# Só campos técnicos de identificação; nenhum valor de negócio do manifesto vai para a saída.
MANIFEST_FIELDS = ("ambiente", "lote", "run_id_silver", "lote_bronze_silver")


def _decimal(value: str) -> Decimal | None:
    if value is None or value.strip().lower() in NULL_TOKENS:
        return None
    try:
        return Decimal(value.strip().replace(",", "."))
    except InvalidOperation:
        return None


def _is_null(value: str) -> bool:
    return value.strip().lower() in NULL_TOKENS


def _measure(value: str | None) -> tuple[Decimal | None, str | None]:
    """Converte uma medida da reconciliação; o segundo item diz se ela é nula ou inválida."""
    if value is None or _is_null(value):
        return None, "nulo"
    try:
        number = Decimal(value.strip().replace(",", "."))
    except InvalidOperation:
        return None, "invalido"
    return (number, None) if number.is_finite() else (None, "invalido")


def _normalize_name(text: str) -> str:
    """Grafia comparável: desfaz mojibake latin-1/UTF-8, tira acentos, caixa e espaços extras."""
    with contextlib.suppress(UnicodeEncodeError, UnicodeDecodeError):
        text = text.encode("latin-1").decode("utf-8")
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    return " ".join(stripped.upper().split())


def _is_sensitive_name(name: str) -> bool:
    return bool(SENSITIVE_TOKENS & set(name.lower().strip("_").split("_")))


def _looks_personal(value: str) -> bool:
    return bool(CPF_LIKE.search(value) or CEP_LIKE.match(value) or EMAIL_LIKE.search(value))


class ColumnProfile:
    """Agregados de uma coluna, sem guardar linhas."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.nulls = 0
        self.empty = 0
        self.kinds: Counter[str] = Counter()
        self.values: Counter[str] = Counter()
        self.distinct_overflow = False
        self.minimum: Decimal | None = None
        self.maximum: Decimal | None = None
        self.total = Decimal(0)
        self.zeros = 0
        self.negatives = 0
        self.sentinels = 0
        self.out_of_range_dates = 0
        self.min_text: str | None = None
        self.max_text: str | None = None
        self.cpf_like = 0
        self.cep_like = 0
        self.email_like = 0

    def add(self, raw: str) -> None:
        value = raw.strip()
        if _is_null(value):
            self.nulls += 1
            self.empty += value == ""
            return
        if not self.distinct_overflow:
            self.values[value] += 1
            if len(self.values) > DISTINCT_CAP:
                self.distinct_overflow = True
                self.values.clear()
        kind = self._kind(value)
        self.kinds[kind] += 1
        if kind in {"inteiro", "decimal_ponto", "decimal_virgula"}:
            number = _decimal(value)
            self.total += number
            self.minimum = number if self.minimum is None else min(self.minimum, number)
            self.maximum = number if self.maximum is None else max(self.maximum, number)
            self.zeros += number == 0
            self.negatives += number < 0
            self.sentinels += kind == "inteiro" and number in NUMERIC_SENTINELS
        elif kind in {"ano_mes", "data"}:
            self.min_text = value if self.min_text is None else min(self.min_text, value)
            self.max_text = value if self.max_text is None else max(self.max_text, value)
            # Data fora de 1950-2099 é data inválida na origem, não marcador de ausência.
            self.out_of_range_dates += kind == "data" and not ("1950" <= value[:4] < "2100")
        elif kind == "texto":
            self.cpf_like += bool(CPF_LIKE.search(value))
            self.cep_like += bool(CEP_LIKE.match(value))
            self.email_like += bool(EMAIL_LIKE.search(value))

    @staticmethod
    def _kind(value: str) -> str:
        lowered = value.lower()
        if lowered in {"true", "false"}:
            return "booleano"
        if INT.match(value):
            return "inteiro"
        if DEC_DOT.match(value):
            return "decimal_ponto"
        if DEC_COMMA.match(value):
            return "decimal_virgula"
        if YM.match(value):
            return "ano_mes"
        if DATE.match(value):
            return "data"
        if lowered in BOOL_TOKENS:
            return "booleano_texto"
        return "texto"

    def summary(self, rows: int) -> dict:
        distinct = None if self.distinct_overflow else len(self.values)
        result = {
            "nulos": self.nulls,
            "nulos_pct": round(100 * self.nulls / rows, 2) if rows else 0.0,
            "vazios": self.empty,
            "tipos_inferidos": dict(self.kinds),
            "distintos": distinct if distinct is not None else f">{DISTINCT_CAP}",
        }
        if self.minimum is not None:
            result.update(
                minimo=float(self.minimum),
                maximo=float(self.maximum),
                soma=str(self.total),
                zeros=self.zeros,
                negativos=self.negatives,
                sentinelas_numericas=self.sentinels,
            )
        if self.min_text is not None:
            # Mínimo e máximo de texto só em coluna inteira de data/competência, nunca texto livre.
            if set(self.kinds) <= DATE_KINDS:
                result.update(minimo_texto=self.min_text, maximo_texto=self.max_text)
            result["datas_fora_de_1950_2099"] = self.out_of_range_dates
        if self.cpf_like or self.cep_like or self.email_like:
            result.update(
                padrao_cpf=self.cpf_like, padrao_cep=self.cep_like, padrao_email=self.email_like
            )
        low = distinct is not None and distinct <= LOW_CARDINALITY
        if low and self._publishable():
            result["valores"] = dict(sorted(self.values.items()))
        return result

    def _publishable(self) -> bool:
        """Allowlist de dimensões; nome ou valor com cara de dado pessoal veta a publicação."""
        return (
            self.name in PUBLISHABLE_DIMENSIONS
            and not _is_sensitive_name(self.name)
            and not (self.cpf_like or self.cep_like or self.email_like)
            and not any(_looks_personal(value) for value in self.values)
        )


def find_table_files(base: Path, table: str) -> list[Path]:
    folder = base / table
    if (folder / f"{table}.csv").is_file():
        return [folder / f"{table}.csv"]
    if folder.is_dir():
        parts = sorted(p for p in folder.glob("*.csv") if p.is_file())
        if parts:
            return parts
    if (base / f"{table}.csv").is_file():
        return [base / f"{table}.csv"]
    return []


def read_manifest(base: Path, present: list[str]) -> dict | None:
    """Lê o manifesto do lote e devolve só a identificação técnica e os avisos."""
    found = [relative for relative in MANIFEST_PATHS if (base / relative).is_file()]
    if not found:
        return None
    result: dict = {"arquivo": found[0].as_posix()}
    avisos = []
    if len(found) > 1:
        avisos.append(
            f"manifesto em dois caminhos: usado {found[0].as_posix()}, "
            f"ignorado {found[1].as_posix()}"
        )
    try:
        data = json.loads((base / found[0]).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {**result, "avisos": [*avisos, "manifesto ilegível: JSON inválido"]}
    if not isinstance(data, dict):
        return {**result, "avisos": [*avisos, "manifesto ilegível: o topo não é um objeto"]}
    for field in MANIFEST_FIELDS:
        value = data.get(field)
        if value is None:
            result[field] = "ausente"
        elif isinstance(value, (str, int)) and not isinstance(value, bool):
            result[field] = str(value)
        else:
            result[field] = "formato_inesperado"
    if str(data.get("ambiente", "")).strip().upper() != "PROD":
        avisos.append(f"ambiente do manifesto não é PROD: {result['ambiente']}")
    exported = data.get("tabelas_exportadas")
    # Em objeto, só as chaves (nomes de tabela) são lidas; os valores podem ter contagens.
    if isinstance(exported, dict):
        exported = list(exported)
    if isinstance(exported, list) and all(isinstance(name, str) for name in exported):
        result["tabelas_exportadas"] = sorted(exported)
        missing = sorted(set(present) - set(exported))
        extra = sorted(set(exported) - set(present))
        if missing or extra or len(present) != len(TABLES):
            avisos.append(
                "tabelas_exportadas não batem com as tabelas encontradas: "
                f"faltam no manifesto {missing}, só no manifesto {extra}, "
                f"encontradas {len(present)} de {len(TABLES)}"
            )
    else:
        result["tabelas_exportadas"] = "ausente" if exported is None else "formato_inesperado"
        avisos.append("manifesto sem lista de tabelas_exportadas legível")
    result["avisos"] = avisos
    return result


def iter_rows(files: list[Path]):
    """Gera (cabeçalho, linha); as partes precisam repetir o mesmo cabeçalho."""

    header: list[str] | None = None
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=";", quotechar='"')
            current = next(reader, None)
            if current is None:
                continue
            if header is None:
                header = current
            elif current != header:
                raise ValueError(f"cabeçalho divergente entre partes de {path.parent.name}")
            for row in reader:
                yield header, row


class Recon:
    """Acumuladores para as reconciliações entre tabelas."""

    def __init__(self) -> None:
        self.ucs: dict[str, set[str]] = defaultdict(set)
        self.uc_municipio: dict[str, str] = {}
        self.uc_gd: dict[str, dict[str, str]] = defaultdict(dict)
        self.uc_media: dict[str, dict[str, Decimal | None]] = defaultdict(dict)
        self.uc_alimentador: dict[str, str] = {}
        self.uc_status: dict[str, str] = {}
        self.uc_classe: dict[str, str] = {}
        # (tabela) -> competência -> [consumo, receita, ucs]
        self.by_comp: dict[str, dict[str, list[Decimal]]] = defaultdict(
            lambda: defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
        )
        self.by_comp_mun: dict[str, dict[tuple[str, str], list[Decimal]]] = defaultdict(
            lambda: defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
        )
        self.by_comp_class: dict[str, dict[tuple[str, str], list[Decimal]]] = defaultdict(
            lambda: defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
        )
        self.monthly_per_uc: Counter[str] = Counter()
        self.monthly_sum_per_uc: dict[str, Decimal] = defaultdict(Decimal)
        self.monthly_null_consumo = 0
        self.monthly_bad_consumo_ucs: set[str] = set()
        # (tabela) -> "<medida>_nulo" / "<medida>_invalido" -> linhas; nunca entram como zero.
        self.measure_issues: dict[str, Counter[str]] = defaultdict(Counter)
        self.variacao = Counter()
        self.fila = Counter()
        self.fila_priority_by_rule: Counter[tuple[str, str]] = Counter()
        self.decfec = Counter()
        self.decfec_months: dict[str, set[str]] = defaultdict(set)
        self.decfec_muns: dict[str, set[str]] = defaultdict(set)
        self.decfec_total_ucs: dict[str, set[str]] = defaultdict(set)
        self.decfec_values: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
        self.diag_gd_by_comp: dict[str, Counter[str]] = defaultdict(Counter)
        self.diag = Counter()
        self.class_values: dict[str, set[str]] = defaultdict(set)
        self.municipios: dict[str, set[str]] = defaultdict(set)
        # Exemplos do PRD §7.6: (competência, município, bairro, classe) -> [consumo, receita].
        self.bairro_cells: dict[tuple[str, str, str, str], list[Decimal]] = defaultdict(
            lambda: [Decimal(0), Decimal(0)]
        )
        self.gd_drop_by_municipio: Counter[str] = Counter()
        # C14: só contadores de estado e de inconsistência; nenhuma UC nem valor é guardado.
        self.atendimento: Counter[str] = Counter()


def _get(row: list[str], idx: dict[str, int], column: str) -> str | None:
    position = idx.get(column)
    if position is None or position >= len(row):
        return None
    return row[position].strip()


def _track(recon: Recon, table: str, measure: str, raw: str | None) -> Decimal | None:
    number, issue = _measure(raw)
    if issue:
        recon.measure_issues[table][f"{measure}_{issue}"] += 1
    return number


def _accumulate(bucket: list[Decimal], values) -> None:
    for i, value in enumerate(values):
        if value is not None:
            bucket[i] += value


def _issues(recon: Recon, *tables: str) -> dict[str, dict[str, int]]:
    """Contagens de medidas nulas ou inválidas das tabelas que tiverem alguma."""
    return {
        table: dict(sorted(recon.measure_issues[table].items()))
        for table in tables
        if recon.measure_issues.get(table)
    }


def _unverifiable(issues: dict) -> dict:
    return {"estado": "nao_verificavel", "medidas_nulas_ou_invalidas": issues}


def feed(recon: Recon, table: str, row: list[str], idx: dict[str, int]) -> None:
    g = lambda column: _get(row, idx, column)  # noqa: E731
    uc = g("id_uc")
    if uc:
        recon.ucs[table].add(uc)
    if g("municipio") is not None:
        recon.municipios[table].add(g("municipio"))
    for column in ("classe", "classe_consumo"):
        if g(column) is not None:
            recon.class_values[table].add(g(column))

    if table in {"visao_360_uc", "fila_inspecao"}:
        gd_column = "possui_gd" if table == "visao_360_uc" else "possui_geracao_solar"
        recon.uc_gd[table][uc] = g(gd_column)
        recon.uc_media[table][uc] = _decimal(g("media_consumo_historico") or "")
    if table == "visao_360_uc":
        recon.uc_municipio[uc] = g("municipio")
        recon.uc_alimentador[uc] = g("alimentador")
        recon.uc_status[uc] = g("status")
        recon.uc_classe[uc] = g("classe")
        if all(column in idx for column in ATENDIMENTO_COLUMNS):
            _feed_atendimento(recon, g)
    elif table == "fila_inspecao":
        _feed_fila(recon, g)
    elif table == "variacao_consumo_uc":
        recon.uc_gd[table][uc] = g("possui_gd")
        _feed_variacao(recon, g)
    elif table == "consumo_mensal_uc":
        comp = g("competencia")
        consumo = _track(recon, table, "consumo_kwh", g("consumo_kwh"))
        receita = _track(recon, table, "receita_reais", g("receita_reais"))
        recon.monthly_per_uc[uc] += 1
        if consumo is None:
            recon.monthly_null_consumo += 1
            recon.monthly_bad_consumo_ucs.add(uc)
        else:
            recon.monthly_sum_per_uc[uc] += consumo
        municipio = recon.uc_municipio.get(uc, "<UC fora da visao_360_uc>")
        classe = recon.uc_classe.get(uc, "<UC fora da visao_360_uc>")
        for bucket in (
            recon.by_comp[table][comp],
            recon.by_comp_mun[table][(comp, municipio)],
            recon.by_comp_class[table][(comp, classe)],
        ):
            _accumulate(bucket, (consumo, receita, Decimal(1)))
    elif table in {"consumo_receita_bairro", "diagnostico_receita"}:
        comp = g("competencia")
        consumo = _track(recon, table, "consumo_kwh", g("consumo_total_kwh"))
        receita = _track(recon, table, "receita_reais", g("receita_total_reais"))
        ucs = _track(recon, table, "ucs", g("qtd_ucs_distintas_faturadas_no_mes"))
        classe = g("classe_consumo")
        for bucket in (
            recon.by_comp[table][comp],
            recon.by_comp_mun[table][(comp, g("municipio"))],
            recon.by_comp_class[table][(comp, classe)],
        ):
            _accumulate(bucket, (consumo, receita, ucs))
        if table == "consumo_receita_bairro":
            cell = recon.bairro_cells[(comp, g("municipio"), g("bairro"), classe)]
            _accumulate(cell, (consumo, receita))
        if table == "diagnostico_receita":
            _feed_diag(recon, g, comp, consumo, receita, ucs)
    elif table == "indicadores_dec_fec":
        _feed_decfec(recon, g)


def _feed_fila(recon: Recon, g) -> None:
    realizadas = _decimal(g("total_inspecoes_realizadas") or "")
    irregulares = _decimal(g("total_inspecoes_irregulares") or "")
    media = _decimal(g("media_consumo_historico") or "")
    if realizadas is None:
        realized = "inspecoes_nulo"
    elif realizadas == 0:
        realized = "nunca_inspecionada"
    elif irregulares and irregulares > 0:
        realized = "com_irregularidade"
    else:
        realized = "inspecionada_sem_irregularidade"
    if media is None:
        consumption = "media_consumo_nula"
    elif media == 0:
        consumption = "media_consumo_zero"
    else:
        consumption = "media_consumo_positiva"
    recon.fila_priority_by_rule[(g("prioridade_inspecao"), f"{realized}/{consumption}")] += 1
    if irregulares is not None and realizadas is not None and irregulares > realizadas:
        recon.fila["irregulares_maior_que_realizadas"] += 1


def _feed_atendimento(recon: Recon, g) -> None:
    """Consistência interna de chamados e satisfação da UC; média ausente nunca vira zero."""
    table = "visao_360_uc"
    chamados = _track(recon, table, "chamados", g("total_chamados_callcenter"))
    # Média nula é estado válido (UC sem chamado ou sem nota); só a inválida bloqueia a conferência.
    media, media_issue = _measure(g("media_satisfacao_atendimento"))
    if media_issue == "invalido":
        recon.measure_issues[table]["media_satisfacao_invalido"] += 1
    if chamados is None or media_issue == "invalido":
        return
    c = recon.atendimento
    if chamados < 0:
        c["chamados_negativo"] += 1
        return
    if chamados != chamados.to_integral_value():
        c["chamados_nao_inteiro"] += 1
        return
    com_chamados = "com_chamados" if chamados > 0 else "sem_chamados"
    if media is None:
        c[f"{com_chamados}_sem_media"] += 1
        return
    c[f"{com_chamados}_com_media"] += 1
    if chamados == 0:
        c["media_presente_sem_chamados"] += 1
    if media < 0:
        c["media_negativa"] += 1


def _feed_variacao(recon: Recon, g) -> None:
    inicial = _decimal(g("consumo_medio_inicial") or "")
    final = _decimal(g("consumo_medio_final") or "")
    kwh = _decimal(g("variacao_kwh") or "")
    pct = _decimal(g("variacao_pct") or "")
    flag = (g("queda_consumo_superior_30_pct") or "").lower()
    meses_p1 = _decimal(g("meses_com_leitura_p1") or "")
    meses_p2 = _decimal(g("meses_com_leitura_p2") or "")
    c = recon.variacao
    c[f"flag={flag}"] += 1
    if flag == "true" and (g("possui_gd") or "").lower() == "sim":
        c["flag_true_com_gd_sim"] += 1
        recon.gd_drop_by_municipio[g("municipio")] += 1
    if inicial is None and final is None:
        c["sem_p1_e_sem_p2"] += 1
    elif inicial is None:
        c["sem_p1"] += 1
    elif final is None:
        c["sem_p2"] += 1
    if inicial is not None and inicial == 0:
        c["inicial_zero"] += 1
    if pct is None:
        c["pct_nulo"] += 1
        if inicial is not None and final is not None and inicial > 0:
            c["pct_nulo_inesperado"] += 1
    if kwh is None:
        c["kwh_nulo"] += 1
    if (
        inicial is not None
        and final is not None
        and kwh is not None
        and abs((final - inicial) - kwh) > Decimal("0.011")
    ):
        c["kwh_diverge_de_final_menos_inicial"] += 1
    if inicial and inicial > 0 and final is not None and pct is not None:
        recomputed = (final - inicial) / inicial * 100
        if abs(recomputed - pct) > Decimal("0.02"):
            c["pct_diverge_do_recalculo"] += 1
    if pct is not None and ((pct < -30) != (flag == "true")):
        c["flag_inconsistente_com_pct_arredondado"] += 1
    if pct is not None and pct == -30:
        c["pct_exatamente_menos_30"] += 1
    for label, months in (("p1", meses_p1), ("p2", meses_p2)):
        if months is not None:
            c[f"meses_{label}={int(months)}"] += 1


def _feed_diag(recon: Recon, g, comp, consumo, receita, ucs) -> None:
    recon.diag_gd_by_comp[comp][g("possui_gd")] += 1
    ticket = _decimal(g("ticket_medio_reais_por_uc") or "")
    medio = _decimal(g("consumo_medio_kwh_por_uc") or "")
    tarifa = _decimal(g("tarifa_media_efetiva") or "")
    c = recon.diag
    if tarifa is None:
        c["tarifa_nula"] += 1
    if consumo is None or receita is None or ucs is None:
        c["linhas_com_medida_nula_ou_invalida"] += 1
        return
    if ucs and ticket is not None and abs(receita / ucs - ticket) > Decimal("0.01"):
        c["ticket_diverge_receita_sobre_ucs"] += 1
    if ucs and medio is not None and abs(consumo / ucs - medio) > Decimal("0.01"):
        c["consumo_medio_diverge_consumo_sobre_ucs"] += 1
    if consumo and tarifa is not None and abs(receita / consumo - tarifa) > Decimal("0.0001"):
        c["tarifa_diverge_receita_sobre_consumo"] += 1
    if consumo == 0:
        c["consumo_zero"] += 1
        if tarifa is not None:
            c["tarifa_preenchida_com_consumo_zero"] += 1
    faturamentos = _decimal(g("soma_faturamentos_mensais") or "")
    if faturamentos is not None and faturamentos < ucs:
        c["faturamentos_menor_que_ucs"] += 1
    if faturamentos is not None and faturamentos != ucs:
        c["faturamentos_diferente_de_ucs"] += 1


def _feed_decfec(recon: Recon, g) -> None:
    alim = g("id_alimentador")
    recon.decfec_months[alim].add(g("competencia"))
    recon.decfec_muns[alim].add(g("municipio"))
    recon.decfec_total_ucs[alim].add(g("total_ucs_alimentador"))
    total = _decimal(g("total_ucs_alimentador") or "")
    interrompidas = _decimal(g("ucs_interrompidas") or "")
    freq = _decimal(g("frequencia_total_interrupcoes") or "")
    dur = _decimal(g("duracao_total_interrupcoes_horas") or "")
    dec = _decimal(g("DEC") or g("dec") or "")
    fec = _decimal(g("FEC") or g("fec") or "")
    if dec is not None and fec is not None:
        recon.decfec_values[(alim, g("competencia"))] = (dec, fec)
    c = recon.decfec
    if not total:
        c["denominador_nulo_ou_zero"] += 1
        return
    if interrompidas is not None and interrompidas > total:
        c["interrompidas_maior_que_total"] += 1
    if dur is not None and dec is not None and abs(dur / total - dec) > Decimal("0.0001"):
        c["dec_diverge_duracao_sobre_ucs"] += 1
    if freq is not None and fec is not None and abs(freq / total - fec) > Decimal("0.0001"):
        c["fec_diverge_frequencia_sobre_ucs"] += 1
    if freq is not None and interrompidas is not None and freq < interrompidas:
        c["frequencia_menor_que_interrompidas"] += 1


def profile_table(base: Path, table: str, recon: Recon) -> dict:
    files = find_table_files(base, table)
    if not files:
        return {"estado": "ausente"}
    profiles: dict[str, ColumnProfile] = {}
    idx: dict[str, int] = {}
    header: list[str] = []
    rows = 0
    short_rows = 0
    key_columns = TABLE_KEYS[table]
    keys: set[tuple] = set()
    duplicate_keys = 0
    null_key_rows = 0
    per_comp_rows: Counter[str] = Counter()
    for current_header, row in iter_rows(files):
        if not profiles:
            header = current_header
            idx = {name: i for i, name in enumerate(header)}
            profiles = {name: ColumnProfile(name) for name in header}
        rows += 1
        if len(row) != len(header):
            short_rows += 1
        for name, value in zip(header, row, strict=False):
            profiles[name].add(value)
        key = tuple(sys.intern(_get(row, idx, k) or "") for k in key_columns)
        if any(_is_null(part) for part in key):
            null_key_rows += 1
        elif key in keys:
            duplicate_keys += 1
        else:
            keys.add(key)
        if "competencia" in idx:
            per_comp_rows[_get(row, idx, "competencia")] += 1
        feed(recon, table, row, idx)
    missing_key = [k for k in key_columns if k not in idx]
    sensitive = [name for name in header if _is_sensitive_name(name)]
    result = {
        "estado": "presente",
        "arquivos": len(files),
        "linhas": rows,
        "linhas_com_colunas_divergentes": short_rows,
        "colunas": header,
        "chave_candidata": list(key_columns),
        "chave_colunas_ausentes": missing_key,
        "chave_linhas_com_nulo": null_key_rows,
        "chave_duplicatas": duplicate_keys,
        "chave_unica": not missing_key and duplicate_keys == 0 and null_key_rows == 0,
        "colunas_sensiveis_no_cabecalho": sensitive,
        "perfil": {name: p.summary(rows) for name, p in profiles.items()},
    }
    if per_comp_rows:
        result["competencias"] = _period_summary(per_comp_rows)
    return result


def _months_between(first: str, last: str) -> list[str]:
    year, month = map(int, first.split("-"))
    end = tuple(map(int, last.split("-")))
    months = []
    while (year, month) <= end:
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return months


def _period_summary(per_comp: Counter[str]) -> dict:
    valid = sorted(c for c in per_comp if c and YM.match(c))
    invalid = sum(n for c, n in per_comp.items() if not (c and YM.match(c)))
    if not valid:
        return {"competencias_validas": 0, "linhas_competencia_invalida": invalid}
    expected = _months_between(valid[0], valid[-1])
    counts = [per_comp[c] for c in valid]
    median = statistics.median(counts)
    return {
        "minima": valid[0],
        "maxima": valid[-1],
        "meses": len(valid),
        "meses_faltantes": [m for m in expected if m not in per_comp],
        "linhas_competencia_invalida": invalid,
        "linhas_por_mes_min": min(counts),
        "linhas_por_mes_mediana": median,
        "linhas_por_mes_max": max(counts),
        "meses_abaixo_de_80pct_da_mediana": {
            c: per_comp[c] for c in valid if per_comp[c] < 0.8 * median
        },
    }


def _compare_buckets(left: dict, right: dict, issues: dict) -> dict:
    """Compara somas por grupo; com medida nula ou inválida, não declara divergência alguma."""
    keys = set(left) | set(right)
    structure = {
        "grupos": len(keys),
        "grupos_so_na_primeira": sum(1 for k in keys if k not in right),
        "grupos_so_na_segunda": sum(1 for k in keys if k not in left),
    }
    if issues:
        return {**_unverifiable(issues), **structure}
    zero = [Decimal(0)] * 3
    worst = [Decimal(0)] * 3
    divergent = [0, 0, 0]
    for key in keys:
        a, b = left.get(key, zero), right.get(key, zero)
        for i, tolerance in enumerate((Decimal("0.5"), MONEY_TOLERANCE, Decimal(0))):
            diff = abs(a[i] - b[i])
            worst[i] = max(worst[i], diff)
            divergent[i] += diff > tolerance
    total_left = [sum(v[i] for v in left.values()) for i in range(3)]
    total_right = [sum(v[i] for v in right.values()) for i in range(3)]
    return {
        "estado": "verificada",
        **structure,
        "grupos_divergentes_consumo_kwh": divergent[0],
        "grupos_divergentes_receita_reais": divergent[1],
        "grupos_divergentes_ucs": divergent[2],
        "maior_diferenca_consumo_kwh": str(worst[0]),
        "maior_diferenca_receita_reais": str(worst[1]),
        "maior_diferenca_ucs": str(worst[2]),
        "total_consumo_kwh": [str(total_left[0]), str(total_right[0])],
        "total_receita_reais": [str(total_left[1]), str(total_right[1])],
        "total_ucs": [str(total_left[2]), str(total_right[2])],
    }


def reconcile(recon: Recon) -> dict:
    ucs = recon.ucs
    base = ucs.get("visao_360_uc", set())
    uc_sets = {}
    for table in ("fila_inspecao", "variacao_consumo_uc", "consumo_mensal_uc"):
        other = ucs.get(table, set())
        uc_sets[table] = {
            "ucs": len(other),
            "em_comum_com_visao_360": len(base & other),
            "so_na_tabela": len(other - base),
            "so_na_visao_360": len(base - other),
        }
    missing_monthly = base - ucs.get("consumo_mensal_uc", set())
    status_missing = Counter(recon.uc_status.get(uc) for uc in missing_monthly)
    months_per_uc = list(recon.monthly_per_uc.values())

    gd_pairs = {}
    visao_gd = recon.uc_gd.get("visao_360_uc", {})
    for table in ("fila_inspecao", "variacao_consumo_uc"):
        other = recon.uc_gd.get(table, {})
        common = visao_gd.keys() & other.keys()
        gd_pairs[table] = {
            "ucs_comparadas": len(common),
            "divergentes": sum(1 for uc in common if visao_gd[uc] != other[uc]),
        }

    visao_media = recon.uc_media.get("visao_360_uc", {})
    fila_media = recon.uc_media.get("fila_inspecao", {})
    common = visao_media.keys() & fila_media.keys()
    media_vs_fila = sum(
        1
        for uc in common
        if (visao_media[uc] is None) != (fila_media[uc] is None)
        or (visao_media[uc] is not None and abs(visao_media[uc] - fila_media[uc]) > Decimal("0.01"))
    )
    media_vs_monthly = Counter()
    for uc, media in visao_media.items():
        months = recon.monthly_per_uc.get(uc)
        if media is None:
            media_vs_monthly["media_nula_" + ("com_meses" if months else "sem_meses")] += 1
        elif not months:
            media_vs_monthly["media_preenchida_sem_meses_no_consumo_mensal"] += 1
        elif uc in recon.monthly_bad_consumo_ucs:
            media_vs_monthly["nao_verificavel_consumo_nulo_ou_invalido"] += 1
        else:
            mean = recon.monthly_sum_per_uc[uc] / months
            media_vs_monthly["confere" if abs(mean - media) <= 1 else "diverge_mais_de_1kwh"] += 1

    alim_visao = Counter(a for a in recon.uc_alimentador.values() if a)
    alim_decfec = set(recon.decfec_months)
    months_per_alim = [len(m) for m in recon.decfec_months.values()]
    denominator_vs_visao = Counter()
    for alim, totals in recon.decfec_total_ucs.items():
        observed = alim_visao.get(alim, 0)
        numbers = {_decimal(t) for t in totals} - {None}
        if len(numbers) > 1:
            denominator_vs_visao["denominador_varia_por_mes"] += 1
        elif numbers and numbers.pop() == observed:
            denominator_vs_visao["igual_a_ucs_da_visao_360"] += 1
        else:
            denominator_vs_visao["diferente_de_ucs_da_visao_360"] += 1

    by_comp, by_comp_mun, by_comp_class = recon.by_comp, recon.by_comp_mun, recon.by_comp_class
    diag_gd = Counter()
    for counter in recon.diag_gd_by_comp.values():
        diag_gd.update(counter)

    all_municipios = sorted(set().union(*recon.municipios.values())) if recon.municipios else []
    bairro_x_diag = _issues(recon, "consumo_receita_bairro", "diagnostico_receita")
    mensal_x_diag = _issues(recon, "consumo_mensal_uc", "diagnostico_receita")
    return {
        "medidas_nulas_ou_invalidas_por_tabela": _issues(recon, *TABLES),
        "ucs_por_tabela": {t: len(s) for t, s in ucs.items()},
        "ucs_x_visao_360": uc_sets,
        "visao_360_sem_consumo_mensal_por_status": dict(status_missing),
        "consumo_mensal_meses_por_uc": (
            {
                "min": min(months_per_uc),
                "mediana": statistics.median(months_per_uc),
                "max": max(months_per_uc),
            }
            if months_per_uc
            else {}
        ),
        "consumo_mensal_linhas_consumo_nulo": recon.monthly_null_consumo,
        "gd_x_visao_360": gd_pairs,
        "media_consumo_visao_x_fila_divergentes": media_vs_fila,
        "media_consumo_visao_x_media_do_consumo_mensal": dict(media_vs_monthly),
        "fila_prioridade_x_sinais": {
            f"{p} | {r}": n for (p, r), n in sorted(recon.fila_priority_by_rule.items())
        },
        "fila_checagens": dict(recon.fila),
        "variacao_checagens": dict(sorted(recon.variacao.items())),
        "diagnostico_checagens": dict(recon.diag),
        "diagnostico_possui_gd_valores": dict(diag_gd),
        "bairro_x_diagnostico_por_competencia": _compare_buckets(
            by_comp.get("consumo_receita_bairro", {}),
            by_comp.get("diagnostico_receita", {}),
            bairro_x_diag,
        ),
        "bairro_x_diagnostico_por_competencia_municipio": _compare_buckets(
            by_comp_mun.get("consumo_receita_bairro", {}),
            by_comp_mun.get("diagnostico_receita", {}),
            bairro_x_diag,
        ),
        "bairro_x_diagnostico_por_competencia_classe": _compare_buckets(
            by_comp_class.get("consumo_receita_bairro", {}),
            by_comp_class.get("diagnostico_receita", {}),
            bairro_x_diag,
        ),
        "consumo_mensal_x_diagnostico_por_competencia": _compare_buckets(
            by_comp.get("consumo_mensal_uc", {}),
            by_comp.get("diagnostico_receita", {}),
            mensal_x_diag,
        ),
        "consumo_mensal_com_municipio_da_visao_x_diagnostico": _compare_buckets(
            by_comp_mun.get("consumo_mensal_uc", {}),
            by_comp_mun.get("diagnostico_receita", {}),
            mensal_x_diag,
        ),
        "consumo_mensal_com_classe_da_visao_x_diagnostico": _compare_buckets(
            by_comp_class.get("consumo_mensal_uc", {}),
            by_comp_class.get("diagnostico_receita", {}),
            mensal_x_diag,
        ),
        "alimentadores": {
            "dec_fec": len(alim_decfec),
            "visao_360": len(alim_visao),
            "em_comum": len(alim_decfec & alim_visao.keys()),
            "so_dec_fec": len(alim_decfec - alim_visao.keys()),
            "so_visao_360": len(alim_visao.keys() - alim_decfec),
            "com_mais_de_um_municipio_no_dec_fec": sum(
                1 for m in recon.decfec_muns.values() if len(m) > 1
            ),
            "meses_por_alimentador": (
                {"min": min(months_per_alim), "max": max(months_per_alim)}
                if months_per_alim
                else {}
            ),
            "denominador_x_ucs_da_visao_360": dict(denominator_vs_visao),
        },
        "dec_fec_checagens": dict(recon.decfec),
        "municipios_por_tabela": {t: len(m) for t, m in recon.municipios.items()},
        "municipios_fora_de_alguma_tabela": [
            m
            for m in all_municipios
            if any(m not in values for values in recon.municipios.values())
        ],
        "classes_por_tabela": {t: sorted(v) for t, v in recon.class_values.items()},
    }


def _pct(new: Decimal, old: Decimal) -> float | None:
    return round(float((new - old) / old * 100), 2) if old else None


def exploratory_examples(recon: Recon) -> dict:
    """Recalcula as perguntas de exemplo do PRD §7.6 só para provar cobertura.

    Os valores não são métricas homologadas: as janelas (primeiros, penúltimos e últimos 12
    meses do lote) são escolha deste relatório e precisam de definição aprovada. Cada janela tem
    12 meses de calendário consecutivos; se faltar competência, nenhum percentual é calculado.
    """

    issues = _issues(recon, "consumo_receita_bairro")
    if issues:
        return _unverifiable(issues)
    present = {key[0] for key in recon.bairro_cells if key[0] and YM.match(key[0])}
    if len(present) < 24:
        return {"estado": "menos de 24 competências; janelas de 12 meses indisponíveis"}
    calendar = _months_between(min(present), max(present))
    calendar_windows = {
        "primeiros_12m": calendar[:12],
        "penultimos_12m": calendar[-24:-12],
        "ultimos_12m": calendar[-12:],
    }
    missing = {
        name: [m for m in window if m not in present] for name, window in calendar_windows.items()
    }
    if any(missing.values()):
        return {
            "estado": "janela incompleta",
            "janelas": {name: [w[0], w[-1]] for name, w in calendar_windows.items()},
            "meses_faltantes": {name: m for name, m in missing.items() if m},
        }
    windows = {name: set(window) for name, window in calendar_windows.items()}

    def total(predicate, index: int) -> dict[str, Decimal]:
        result = {}
        for name, window in windows.items():
            cells = recon.bairro_cells.items()
            result[name] = sum(
                (v[index] for k, v in cells if k[0] in window and predicate(k)), Decimal(0)
            )
        return result

    receita_total = total(lambda k: True, 1)
    consumo_total = total(lambda k: True, 0)
    all_classes = {
        "receita_ultimos_vs_primeiros_pct": _pct(
            receita_total["ultimos_12m"], receita_total["primeiros_12m"]
        ),
        "consumo_ultimos_vs_primeiros_pct": _pct(
            consumo_total["ultimos_12m"], consumo_total["primeiros_12m"]
        ),
    }
    by_class = {}
    for classe in sorted({key[3] for key in recon.bairro_cells}):
        receita = total(lambda k, c=classe: k[3] == c, 1)
        consumo = total(lambda k, c=classe: k[3] == c, 0)
        by_class[classe] = {
            "receita_ultimos_vs_primeiros_pct": _pct(
                receita["ultimos_12m"], receita["primeiros_12m"]
            ),
            "consumo_ultimos_vs_primeiros_pct": _pct(
                consumo["ultimos_12m"], consumo["primeiros_12m"]
            ),
            "receita_ultimos_vs_penultimos_pct": _pct(
                receita["ultimos_12m"], receita["penultimos_12m"]
            ),
            "consumo_ultimos_vs_penultimos_pct": _pct(
                consumo["ultimos_12m"], consumo["penultimos_12m"]
            ),
        }

    residential: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(
        lambda: dict.fromkeys(windows, Decimal(0))
    )
    for (comp, municipio, bairro, classe), (consumo, _) in recon.bairro_cells.items():
        if classe != "RESIDENCIAL":
            continue
        for name, window in windows.items():
            if comp in window:
                residential[(municipio, bairro)][name] += consumo
    worst = {}
    for baseline in ("penultimos_12m", "primeiros_12m"):
        if residential:
            (municipio, bairro), values = min(
                residential.items(), key=lambda item: item[1]["ultimos_12m"] - item[1][baseline]
            )
            worst[f"ultimos_vs_{baseline}"] = {
                "municipio": municipio,
                "bairro": bairro,
                "variacao_kwh": str(values["ultimos_12m"] - values[baseline]),
                "variacao_pct": _pct(values["ultimos_12m"], values[baseline]),
            }

    jaboatao = total(lambda k: k[1].startswith("JABOAT") and k[3] == "COMERCIAL", 1)
    return {
        "janelas": {name: [min(w), max(w)] for name, w in windows.items()},
        "todas_as_classes": all_classes,
        "por_classe": by_class,
        "bairro_residencial_com_maior_perda_kwh": worst,
        "receita_comercial_jaboatao": {
            "ultimos_vs_penultimos_pct": _pct(jaboatao["ultimos_12m"], jaboatao["penultimos_12m"]),
            "ultimos_vs_primeiros_pct": _pct(jaboatao["ultimos_12m"], jaboatao["primeiros_12m"]),
        },
        "ucs_gd_queda_30pct_por_municipio": dict(sorted(recon.gd_drop_by_municipio.items())),
    }


def candidate_controls(recon: Recon, tables: dict) -> list[dict]:
    """Controles agregados em rascunho; cada um precisa de aprovação independente.

    Nenhum controle identifica UC ou alimentador: o alimentador de maior DEC aparece só pelo
    valor. A competência e o município do controle mensal são escolhas deste relatório.
    """

    def control(cid, definition, table, columns, window, value):
        return {
            "id": cid,
            "definicao": definition,
            "tabela": table,
            "colunas": columns,
            "janela": window,
            "valor": value,
        }

    diag_comp = recon.by_comp.get("diagnostico_receita", {})
    diag_issues = _issues(recon, "diagnostico_receita")
    months = sorted(c for c in diag_comp if c and YM.match(c))
    full = f"{months[0]} a {months[-1]}" if months else "sem competência"
    span = _months_between(months[0], months[-1]) if months else []
    gaps = [m for m in span if m not in diag_comp]
    if gaps:
        full += f" (competências faltantes: {', '.join(gaps)})"
    last = months[-1] if months else None
    controls = []
    if diag_comp:
        controls.append(
            control(
                "C01",
                "Total de energia faturada e de receita faturada no lote",
                "diagnostico_receita",
                ["consumo_total_kwh", "receita_total_reais"],
                full,
                _unverifiable(diag_issues)
                if diag_issues
                else {
                    "consumo_kwh": str(sum(v[0] for v in diag_comp.values())),
                    "receita_reais": str(sum(v[1] for v in diag_comp.values())),
                },
            )
        )
        per_class: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
        for (_, classe), values in recon.by_comp_class["diagnostico_receita"].items():
            per_class[classe][0] += values[0]
            per_class[classe][1] += values[1]
        controls.append(
            control(
                "C02",
                "Energia e receita faturadas por classe no lote",
                "diagnostico_receita",
                ["classe_consumo", "consumo_total_kwh", "receita_total_reais"],
                full,
                _unverifiable(diag_issues)
                if diag_issues
                else {c: {"consumo_kwh": str(v[0]), "receita_reais": str(v[1])}
                      for c, v in sorted(per_class.items())},
            )
        )
    monthly = recon.by_comp.get("consumo_mensal_uc", {})
    if monthly:
        controls.append(
            control(
                "C03",
                "UC-meses com fatura e leitura (linhas da série mensal)",
                "consumo_mensal_uc",
                ["id_uc", "competencia"],
                full,
                str(sum(v[2] for v in monthly.values())),
            )
        )
    month_mun = recon.by_comp_mun.get("diagnostico_receita", {})
    if last:
        municipio = max(
            (m for c, m in month_mun if c == last), key=lambda m: month_mun[(last, m)][1]
        )
        values = month_mun[(last, municipio)]
        controls.append(
            control(
                "C04",
                "Energia e receita faturadas no último mês do lote, no município de maior receita",
                "diagnostico_receita",
                ["competencia", "municipio", "consumo_total_kwh", "receita_total_reais"],
                last,
                _unverifiable(diag_issues)
                if diag_issues
                else {"municipio": municipio, "consumo_kwh": str(values[0]),
                      "receita_reais": str(values[1])},
            )
        )
    if recon.uc_classe:
        controls.append(
            control(
                "C05",
                "UCs por classe na Visão 360",
                "visao_360_uc",
                ["id_uc", "classe"],
                "cadastro atual (sem competência)",
                dict(sorted(Counter(recon.uc_classe.values()).items())),
            )
        )
    priorities: Counter[str] = Counter()
    for (priority, _), count in recon.fila_priority_by_rule.items():
        priorities[priority] += count
    if priorities:
        controls.append(
            control(
                "C06",
                "UCs por faixa de prioridade da fila",
                "fila_inspecao",
                ["id_uc", "prioridade_inspecao"],
                "cadastro atual (sem competência)",
                dict(sorted(priorities.items())),
            )
        )
        controls.append(
            control(
                "C07",
                "Caso de zero: UCs na faixa ALTA - CONSUMO ZERO",
                "fila_inspecao",
                ["id_uc", "prioridade_inspecao"],
                "cadastro atual (sem competência)",
                priorities.get("ALTA - CONSUMO ZERO", 0),
            )
        )
    if "variacao_consumo_uc" in recon.ucs:
        drops = recon.gd_drop_by_municipio
        controls.append(
            control(
                "C08",
                "UCs com GD e queda de consumo acima de 30% (P2 contra P1), em Olinda e no total",
                "variacao_consumo_uc",
                ["id_uc", "municipio", "possui_gd", "queda_consumo_superior_30_pct"],
                "P1 = 2022-07 a 2023-06; P2 = 2025-07 a 2026-06 (fixos na Gold)",
                {"olinda": drops.get("OLINDA", 0), "total": sum(drops.values())},
            )
        )
        v = recon.variacao
        controls.append(
            control(
                "C09",
                "Caso de período parcial: UCs sem leitura em P1, em P2 ou nos dois",
                "variacao_consumo_uc",
                ["meses_com_leitura_p1", "meses_com_leitura_p2", "variacao_pct"],
                "P1 e P2",
                {
                    "sem_p1": v.get("sem_p1", 0),
                    "sem_p2": v.get("sem_p2", 0),
                    "sem_p1_e_p2": v.get("sem_p1_e_sem_p2", 0),
                    "variacao_pct_nula": v.get("pct_nulo", 0),
                },
            )
        )
    media = tables.get("visao_360_uc", {}).get("perfil", {}).get("media_consumo_historico")
    if media:
        controls.append(
            control(
                "C10",
                "Caso de nulo: UCs sem média de consumo histórico; quantas delas faltam na série",
                "visao_360_uc, consumo_mensal_uc",
                ["id_uc", "media_consumo_historico"],
                "cadastro atual (sem competência)",
                {
                    "ucs_media_nula": media["nulos"],
                    "das_quais_sem_serie_mensal": len(
                        {u for u, m in recon.uc_media["visao_360_uc"].items() if m is None}
                        - recon.ucs.get("consumo_mensal_uc", set())
                    ),
                },
            )
        )
    dec_months = sorted({comp for _, comp in recon.decfec_values if comp and YM.match(comp)})
    if dec_months:
        month = dec_months[-1]
        worst = max(
            (a for a, c in recon.decfec_values if c == month),
            key=lambda a: recon.decfec_values[(a, month)][0],
        )
        history = [v for (a, _), v in recon.decfec_values.items() if a == worst]
        worst_months = {c for a, c in recon.decfec_values if a == worst}
        missing = [m for m in _months_between(dec_months[0], month) if m not in worst_months]
        value = {
            "dec_mes": round(float(recon.decfec_values[(worst, month)][0]), 4),
            "fec_mes": round(float(recon.decfec_values[(worst, month)][1]), 4),
        }
        if missing:
            # Média de meses não contínuos não cobre a janela declarada: não é calculada.
            value["media_mensal"] = {"estado": "janela incompleta", "meses_faltantes": missing}
            window = f"{month}; média não calculada"
        else:
            value["dec_media_mensal"] = round(float(sum(h[0] for h in history) / len(history)), 4)
            value["fec_media_mensal"] = round(float(sum(h[1] for h in history) / len(history)), 4)
            window = f"{month}; média de {len(history)} meses"
        controls.append(
            control(
                "C11",
                "Alimentador de maior DEC no último mês: DEC e FEC do mês e média simples dos "
                "meses do lote (identificador omitido)",
                "indicadores_dec_fec",
                ["id_alimentador", "competencia", "DEC", "FEC"],
                window,
                value,
            )
        )
    bairro = recon.by_comp.get("consumo_receita_bairro", {})
    if bairro and diag_comp:
        c12_issues = _issues(recon, "consumo_receita_bairro", "diagnostico_receita")
        mismatch = (
            _unverifiable(c12_issues)
            if c12_issues
            else sum(1 for k in set(bairro) | set(diag_comp) if bairro.get(k) != diag_comp.get(k))
        )
        controls.append(
            control(
                "C12",
                "Competências em que bairro e diagnóstico divergem em kWh, R$ ou UC-meses",
                "consumo_receita_bairro, diagnostico_receita",
                ["competencia", "consumo_total_kwh", "receita_total_reais",
                 "qtd_ucs_distintas_faturadas_no_mes"],
                full,
                mismatch,
            )
        )
    bairro_info = tables.get("consumo_receita_bairro", {})
    if bairro_info.get("estado") == "presente":
        # O C12 compara totais por competência; bairro duplicado por grafia não altera os totais.
        pairs = {(key[1], key[2]) for key in recon.bairro_cells}
        normalized = {(_normalize_name(m or ""), _normalize_name(b or "")) for m, b in pairs}
        controls.append(
            control(
                "C13",
                "Linhas e bairros distintos (município × bairro) de consumo_receita_bairro; "
                "bairros que só diferem por acento, caixa ou encoding indicam duplicidade",
                "consumo_receita_bairro",
                ["competencia", "municipio", "bairro", "classe_consumo"],
                full if bairro else "sem competência",
                {
                    "linhas": bairro_info["linhas"],
                    "bairros_distintos": len(pairs),
                    "bairros_distintos_normalizados": len(normalized),
                    "possivel_duplicidade_de_bairro": len(normalized) < len(pairs),
                },
            )
        )
    visao_info = tables.get("visao_360_uc", {})
    if visao_info.get("estado") == "presente":
        controls.append(
            control(
                "C14",
                "Atendimento por UC: protocolos distintos (exato) e média das notas de "
                "satisfação (tolerância 0,005). Consistência interna neste controle e "
                "comparação com atendimentos_uc em atendimento_protocolos_x_visao_360; "
                "reconciliação independente Silver permanece separada",
                "visao_360_uc",
                ["id_uc", *ATENDIMENTO_COLUMNS],
                "cadastro atual (sem competência)",
                _atendimento_control(recon, visao_info),
            )
        )
    return controls


def _atendimento_control(recon: Recon, visao_info: dict) -> dict:
    """Só estados e contadores de inconsistência; nunca UC, identificador ou valor da coluna."""
    missing = [c for c in ATENDIMENTO_COLUMNS if c not in visao_info["colunas"]]
    if missing:
        return {"estado": "nao_verificavel", "colunas_ausentes": missing}
    issues = _issues(recon, "visao_360_uc")
    if issues:
        return _unverifiable(issues)
    c = recon.atendimento
    inconsistencies = {
        name: c.get(name, 0)
        for name in (
            "chamados_negativo",
            "chamados_nao_inteiro",
            "media_presente_sem_chamados",
            "media_negativa",
        )
    }
    return {
        "estado": "verificada",
        "ucs_por_estado": {
            name: c.get(name, 0)
            for name in (
                "sem_chamados_sem_media",
                "sem_chamados_com_media",
                "com_chamados_sem_media",
                "com_chamados_com_media",
            )
        },
        "inconsistencias": inconsistencies,
        "consistente": not any(inconsistencies.values()),
    }


def reconcile_attendance(base: Path) -> dict:
    """Recalcula C14 no grão do protocolo; publica só contadores de divergência.

    Esta comparação Gold detalhe/resumo não certifica a extração da Silver.
    Zero é nota válida; média sem notas permanece nula. Tolerância de Dados: 0,005.
    """
    expected = {}
    totals = defaultdict(lambda: [0, Decimal(0), 0])
    issues = Counter()
    protocols = set()
    for table, required in (
        ("visao_360_uc", ("id_uc", *ATENDIMENTO_COLUMNS)),
        ("atendimentos_uc", ("protocolo", "id_uc", "nota_satisfacao")),
    ):
        files = find_table_files(base, table)
        if not files:
            return {"estado": "nao_verificavel", "tabela_ausente": table}
        with files[0].open(encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle, delimiter=";", quotechar='"'), [])
        missing = sorted(set(required) - set(header))
        if len(header) != len(set(header)):
            return {"estado": "nao_verificavel", "motivo": "CABECALHO_DUPLICADO", "tabela": table}
        if missing:
            return {"estado": "nao_verificavel", "colunas_ausentes": missing, "tabela": table}
        for header, row in iter_rows(files):
            idx = {name: i for i, name in enumerate(header)}
            g = lambda column, row=row, idx=idx: _get(row, idx, column)  # noqa: E731
            uc = g("id_uc")
            if len(row) != len(header) or uc is None or _is_null(uc):
                issues["linha_ou_chave_invalida"] += 1
                continue
            if uc.upper().startswith("TESTE"):
                issues["uc_teste"] += 1
                continue
            if table == "visao_360_uc":
                count, count_issue = _measure(g("total_chamados_callcenter"))
                average, average_issue = _measure(g("media_satisfacao_atendimento"))
                if uc in expected:
                    issues["uc_duplicada"] += 1
                if (count_issue or count < 0 or count != count.to_integral_value()
                        or average_issue == "invalido" or (average is not None and average < 0)):
                    issues["resumo_invalido"] += 1
                    continue
                expected[uc] = (count, average)
            else:
                protocol = g("protocolo")
                if protocol is None or _is_null(protocol):
                    issues["protocolo_ausente"] += 1
                    continue
                if protocol in protocols:
                    issues["protocolo_duplicado"] += 1
                    continue
                protocols.add(protocol)
                value, issue = _measure(g("nota_satisfacao"))
                for flag in ("_nota_invalida", "_nota_negativa"):
                    if flag not in idx:
                        continue  # Compatibilidade com o controle legado sem flags.
                    raw_flag = g(flag)
                    if raw_flag not in {"true", "false", "True", "False"}:
                        issues["flag_nota_invalida"] += 1
                    elif raw_flag.lower() == "true" and value is not None:
                        issues["nota_contradiz_flag"] += 1
                if issue == "invalido" or (value is not None and value < 0):
                    issues["nota_invalida"] += 1
                    continue
                bucket = totals[uc]
                bucket[0] += 1
                if value is not None:
                    bucket[1] += value
                    bucket[2] += 1
    if issues:
        return {"estado": "nao_verificavel", "inconsistencias": dict(sorted(issues.items()))}
    count_diff = average_diff = 0
    for uc, (expected_count, expected_average) in expected.items():
        count, value_sum, rated = totals.get(uc, (0, Decimal(0), 0))
        count_diff += expected_count != count
        actual_average = value_sum / rated if rated else None
        if expected_average is None or actual_average is None:
            average_diff += expected_average != actual_average
        else:
            average_diff += abs(expected_average - actual_average) > Decimal("0.005")
    orphans = len(totals.keys() - expected.keys())
    return {
        "estado": "verificada",
        "ucs_com_contagem_divergente": count_diff,
        "ucs_com_media_divergente": average_diff,
        "ucs_fora_da_visao_360": orphans,
        "consistente": not (count_diff or average_diff or orphans),
        "tolerancia_media": "0.005",
    }


def attendance_monthly_control(base: Path, detail_check: dict) -> dict:
    """Compara observações mensais com a cobertura; não autentica declarações."""
    if detail_check.get("estado") != "verificada" or not detail_check.get("consistente"):
        return {"estado": "nao_verificavel", "motivo": "C14_NAO_RECONCILIADO"}
    monthly = Counter()
    undated = 0
    coverage = {}
    for table, required in (
        ("atendimentos_uc", ("data_abertura",)),
        ("cobertura_dominios", ("dominio", "competencia", "recorte", "estado_cobertura",
                              "qtd_registros", "qtd_sem_competencia", "zero_registros_confirmado")),
    ):
        files = find_table_files(base, table)
        if not files:
            return {"estado": "nao_verificavel", "tabela_ausente": table}
        with files[0].open(encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle, delimiter=";", quotechar='"'), [])
        if not set(required) <= set(header) or len(header) != len(set(header)):
            return {"estado": "nao_verificavel", "motivo": "SCHEMA_INCOMPATIVEL"}
        for header, row in iter_rows(files):
            idx = {name: i for i, name in enumerate(header)}
            if len(row) != len(header):
                return {"estado": "nao_verificavel", "motivo": "LINHA_MALFORMADA"}
            values = {name: _get(row, idx, name) for name in required}
            if table == "atendimentos_uc":
                raw = values["data_abertura"]
                if "_abertura_futura" in idx:
                    flag = _get(row, idx, "_abertura_futura")
                    if flag not in {"true", "false", "True", "False"}:
                        return {"estado": "nao_verificavel", "motivo": "FLAG_ABERTURA_INVALIDA"}
                    if flag.lower() == "true" and raw is not None and not _is_null(raw):
                        return {"estado": "nao_verificavel", "motivo": "ABERTURA_CONTRADIZ_FLAG"}
                if raw is None or _is_null(raw):
                    undated += 1
                    continue
                try:
                    date = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    # Timestamps Spark sem offset são UTC conforme o contrato Gold.
                    date = date.replace(tzinfo=UTC) if date.tzinfo is None else date.astimezone(UTC)
                except ValueError:
                    return {"estado": "nao_verificavel", "motivo": "DATA_INVALIDA"}
                monthly[date.strftime("%Y-%m")] += 1
                continue
            if values["dominio"] != "atendimentos" or values["recorte"] != "DOMINIO":
                continue
            month = values["competencia"]
            state = values["estado_cobertura"]
            count, count_issue = _measure(values["qtd_registros"])
            missing, missing_issue = _measure(values["qtd_sem_competencia"])
            zero = values["zero_registros_confirmado"]
            if (not month or not YM.fullmatch(month) or month in coverage
                    or state not in {"FECHADO", "PARCIAL", "AUSENTE", "NAO_CERTIFICADA"}
                    or count_issue or missing_issue or count < 0 or missing < 0
                    or count != count.to_integral_value() or missing != missing.to_integral_value()
                    or zero not in {"true", "false", "True", "False"}):
                return {"estado": "nao_verificavel", "motivo": "COBERTURA_INVALIDA"}
            coverage[month] = (state, count, missing, zero.lower() == "true")
    if not coverage:
        return {"estado": "nao_verificavel", "motivo": "COBERTURA_AUSENTE"}
    states = Counter()
    mismatches = confirmed = 0
    for month, (state, count, missing, zero) in coverage.items():
        states[state] += 1
        invalid = (count != monthly[month] or missing != undated
                   or (state == "AUSENTE" and count != 0)
                   or (state == "FECHADO" and undated != 0)
                   or zero != (state == "FECHADO" and count == 0))
        mismatches += invalid
        confirmed += zero and not invalid
    outside = len(monthly.keys() - coverage.keys())
    return {"estado": "verificada", "consistente": not (mismatches or outside),
            "meses_divergentes": mismatches, "meses_sem_cobertura": outside,
            "meses_por_estado": dict(sorted(states.items())), "meses_zero_confirmado": confirmed,
            "certificacao_origem": "NAO_VERIFICADA_POR_ESTE_CONTROLE"}


def build_report(base: Path) -> dict:
    recon = Recon()
    tables = {table: profile_table(base, table, recon) for table in TABLES}
    extras = sorted(
        p.name for p in base.iterdir() if p.name not in TABLES and not p.name.startswith(".")
    )
    lote_meta = [
        name
        for name in extras
        if any(token in name.lower() for token in ("manifest", "controle", "lote", "batch"))
    ]
    present = [table for table, info in tables.items() if info["estado"] == "presente"]
    reconciliations = reconcile(recon)
    reconciliations["atendimento_protocolos_x_visao_360"] = reconcile_attendance(base)
    reconciliations["atendimento_mensal_c15"] = attendance_monthly_control(
        base, reconciliations["atendimento_protocolos_x_visao_360"]
    )
    return {
        "tabelas": tables,
        "outros_itens_no_diretorio": len(extras),
        "manifesto_ou_controle_encontrado": lote_meta,
        "manifesto": read_manifest(base, present),
        "reconciliacoes": reconciliations,
        "exemplos_exploratorios_prd_7_6": exploratory_examples(recon),
        "controles_candidatos": candidate_controls(recon, tables),
    }


def _print(report: dict) -> None:
    print("# Conferência do lote candidato da Gold (somente agregados)\n")
    manifest = report["manifesto"]
    if manifest is None:
        found = report["manifesto_ou_controle_encontrado"] or "nenhum"
        print(f"Manifesto/controle do lote: {found}")
    else:
        identity = {key: value for key, value in manifest.items() if key != "avisos"}
        print(f"Manifesto do lote: {json.dumps(identity, ensure_ascii=False)}")
        for aviso in manifest["avisos"]:
            print(f"  AVISO: {aviso}")
    for table, info in report["tabelas"].items():
        print(f"\n## {table}")
        if info["estado"] != "presente":
            print("  AUSENTE")
            continue
        print(
            f"  linhas={info['linhas']} colunas={len(info['colunas'])} "
            f"linhas_colunas_divergentes={info['linhas_com_colunas_divergentes']}"
        )
        print(
            f"  chave={info['chave_candidata']} unica={info['chave_unica']} "
            f"duplicatas={info['chave_duplicatas']} nulos_na_chave={info['chave_linhas_com_nulo']} "
            f"colunas_da_chave_ausentes={info['chave_colunas_ausentes']}"
        )
        sensitive = info["colunas_sensiveis_no_cabecalho"] or "nenhuma"
        print(f"  colunas sensíveis no cabeçalho: {sensitive}")
        if "competencias" in info:
            print(f"  competências: {json.dumps(info['competencias'], ensure_ascii=False)}")
        for name, summary in info["perfil"].items():
            print(f"  - {name}: {json.dumps(summary, ensure_ascii=False)}")
    print("\n## Reconciliações")
    for name, value in report["reconciliacoes"].items():
        print(f"  - {name}: {json.dumps(value, ensure_ascii=False)}")
    print("\n## Exemplos exploratórios do PRD §7.6 (não homologados)")
    for name, value in report["exemplos_exploratorios_prd_7_6"].items():
        print(f"  - {name}: {json.dumps(value, ensure_ascii=False)}")
    print("\n## Controles candidatos (rascunho, não aprovados)")
    for item in report["controles_candidatos"]:
        value = json.dumps(item["valor"], ensure_ascii=False)
        print(f"  - {item['id']} {item['definicao']}: {value}")


def _json_target_error(base: Path, target: Path) -> str | None:
    """Recusa destino do --json dentro do lote (também via link ou ``..``) ou sobre uma entrada."""
    root = base.resolve()
    resolved = target.resolve()
    if resolved == root or root in resolved.parents:
        return f"--json não pode gravar dentro do diretório do lote: {target}"
    if target.exists():
        inputs = [path for table in (*TABLES, "atendimentos_uc", "cobertura_dominios")
                  for path in find_table_files(base, table)]
        inputs.extend(base / path for path in MANIFEST_PATHS if (base / path).is_file())
        if any(resolved == path.resolve() or os.path.samefile(target, path) for path in inputs):
            return f"--json não pode sobrescrever um arquivo de entrada: {target}"
    # Checa o pai como o sistema o verá na gravação: no Linux, "x/.." exige que x exista.
    if not target.parent.is_dir():
        return f"--json: o diretório de destino não existe: {target.parent}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", nargs="?", help="diretório do lote (padrão: GOLD_DATA_DIR)")
    parser.add_argument("--json", type=Path, help="grava os agregados também em JSON")
    args = parser.parse_args(argv)
    raw_dir = args.data_dir or os.environ.get("GOLD_DATA_DIR")
    if not raw_dir:
        parser.error("informe o diretório do lote ou defina GOLD_DATA_DIR")
    base = Path(raw_dir)
    if not base.is_dir():
        parser.error(f"diretório não encontrado: {base}")
    if args.json:
        problem = _json_target_error(base, args.json)
        if problem:
            parser.error(problem)
    report = build_report(base)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _print(report)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
