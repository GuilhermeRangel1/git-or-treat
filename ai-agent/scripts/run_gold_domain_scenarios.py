"""Executa a matriz GENAI-10A pelo fluxo Gold e compara com controles SQL independentes.

Uso:
    python scripts/run_gold_domain_scenarios.py --dry-run
    python scripts/run_gold_domain_scenarios.py [--ids FAT-01,CON-01] [--domain faturamento]
                                                [--output-dir ../work/genai10a] [--strict]

Configuração somente por variáveis de ambiente (valores nunca são impressos ou gravados):
``GENAI10A_BACKEND_URL`` (raiz do Backend, sem credenciais na URL), ``GENAI10A_ORIGIN``
(origem permitida em ``BACKEND_CORS_ORIGINS``), ``GENAI10A_USERNAME``/``GENAI10A_PASSWORD``
(conta de leitura com ``orders:read``) e ``GENAI10A_CONTROL_DSN`` (conexão PostgreSQL somente
leitura para os controles). Opcionais: ``GENAI10A_DENIED_USERNAME``/``GENAI10A_DENIED_PASSWORD``
(conta sem permissão, para o caso de acesso negado).

O runner resolve períodos e amostras na publicação vigente pelas regras da matriz, pergunta pela
rota pública ``POST /api/v1/ai/questions``, executa o controle em transação ``READ ONLY`` e
classifica cada caso pelos critérios de regressão da matriz. No stdout saem apenas ID, classe,
estado e tipos de divergência, além da cobertura por domínio. Valores, amostras resolvidas e
referências de execução são gravados somente em ``work/genai10a/<execução>/``. Respostas
completas, credenciais e DSNs não são gravados.

Sai com 0 sem falhas inesperadas, 1 com FAIL ou erro de execução, 2 com configuração inválida e,
com ``--strict``, 3 quando algum domínio obrigatório continua pendente.
"""

import argparse
import calendar
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = REPO_ROOT / "ai-agent" / "tests" / "fixtures" / "gold_domain_scenarios.json"
CATALOG_PATH = REPO_ROOT / "backend" / "app" / "catalogs" / "gold_v2.json"
WORK_ROOT = REPO_ROOT / "work"
DEFAULT_OUTPUT = WORK_ROOT / "genai10a"
CLASSES = ("PASS", "FAIL", "FALHA_CONHECIDA", "BLOQUEADO", "SEM_AMOSTRA_NO_LOTE", "NAO_EXECUTADO")
NON_NUMERIC_STATES = {
    "bloqueado", "ambiguidade", "recusa", "acesso_negado", "indisponibilidade", "nulo",
    "base_zero", "ausencia", "filtro_sem_suporte",
}
FICTITIOUS_PLACES = {"Lumenia"}
MONTH = frozenset({"competencia", "mes_extenso", "ano"})
WINDOW = frozenset({"inicio", "fim"})
PAIR = frozenset({"p0", "p1", "mes_p0", "ano_p0", "mes_p1", "ano_p1"})
PERIOD_PROVIDES = {
    "SEM_PERIODO": frozenset(),
    "HISTORICO_ACUMULADO": frozenset(),
    "JANELAS_FIXAS_VARIACAO": frozenset(),
    "ULTIMA_COMPETENCIA_RECEITA": MONTH,
    "ULTIMA_COMPETENCIA_CONSUMO": MONTH,
    "ULTIMA_COMPETENCIA_DEC_FEC": MONTH,
    "ULTIMA_COMPETENCIA_ATENDIMENTO": MONTH,
    "ULTIMA_COMPETENCIA_FECHADA_ATENDIMENTO": MONTH,
    "COMPETENCIA_APOS_ULTIMA": MONTH,
    "ULTIMO_TRIMESTRE_RECEITA": WINDOW,
    "ANO_CORRENTE_PARCIAL": WINDOW,
    "PAR_ANO_A_ANO_RECEITA": PAIR,
}
MONTH_NAMES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
    "setembro", "outubro", "novembro", "dezembro",
)
ENV_REQUIRED = (
    "GENAI10A_BACKEND_URL", "GENAI10A_ORIGIN", "GENAI10A_USERNAME", "GENAI10A_PASSWORD",
    "GENAI10A_CONTROL_DSN",
)
_PLACEHOLDER = re.compile(r"\{([a-z_0-9]+)\}")
_SQL_PARAM = re.compile(r"(?<![:\w]):([a-z_][a-z0-9_]*)")
_NUMBER = re.compile(r"-?\d[\d.,]*")


class ControlDatabase(Protocol):
    def fetch_all(self, name: str, sql: str, params: dict) -> list[dict]: ...


class FlowClient(Protocol):
    def ask(self, question: str, context: list[dict]) -> tuple[int, dict | None]: ...


class NoSample(Exception):
    """A regra não encontrou recorte no lote; o caso fica pendente."""


class MatrixError(Exception):
    """A matriz ou o catálogo não permitem executar o caso."""


@dataclass
class Outcome:
    id: str
    dominio: str
    obrigatorio: bool
    classe: str = "NAO_EXECUTADO"
    estado_esperado: str = ""
    status_publico_esperado: str = ""
    status_observado: str | None = None
    http_status: int | None = None
    divergencias: list[str] = field(default_factory=list)
    motivo: str | None = None
    parametros: dict = field(default_factory=dict)
    valores_esperados: list[str] = field(default_factory=list)
    numeros_extraidos: list[str] = field(default_factory=list)
    referencia_execucao: str | None = None
    erro_execucao: bool = False


# Matriz, catálogo e validação sem rede -------------------------------------------------------

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_rounding(catalog: dict) -> dict[str, int]:
    return {metric["metric_id"]: metric["rounding"]["decimals"] for metric in catalog["metrics"]}


def to_pyformat(sql: str) -> str:
    """Converte ``:nome`` em ``%(nome)s`` do psycopg, sem tocar em ``::`` ou literais."""
    return _SQL_PARAM.sub(r"%(\1)s", sql.replace("%", "%%"))


def control_for(matrix: dict, case: dict) -> dict | None:
    ref = case["controle"]["ref"]
    return matrix["controles"][ref] if ref else None


def is_numeric(case: dict) -> bool:
    return "numero" in case["tipo_verificacao"] and case["modo_execucao"] == "fluxo_integrado"


def executes_numeric(case: dict) -> bool:
    """Número só é comparado sem bloqueio e em estado numérico; o resto confere estado."""
    return (is_numeric(case) and case["bloqueio"] is None
            and case["estado_esperado"] not in NON_NUMERIC_STATES)


def validate_matrix(matrix: dict, catalog: dict) -> dict[str, list[str]]:
    """Erros por ID; a matriz é executável quando todos os casos não têm erros."""
    rounding = catalog_rounding(catalog)
    dim_params = matrix["parametros_por_dimensao"]
    classes = set(matrix["criterios_regressao"]["classes_resultado"])
    errors: dict[str, list[str]] = {}
    if classes != set(CLASSES):
        errors["_matriz"] = [f"classes de resultado divergentes: {sorted(classes ^ set(CLASSES))}"]
    for case in matrix["casos"]:
        problems = []
        rule = case["periodo"]["regra"]
        if rule not in matrix["regras_periodo"] or rule not in PERIOD_PROVIDES:
            problems.append(f"regra de período sem implementação: {rule}")
        provides = set(PERIOD_PROVIDES.get(rule, ()))
        sample = case["amostra"]
        if sample is not None:
            if sample not in matrix["regras_amostra"]:
                problems.append(f"regra de amostra ausente: {sample}")
            else:
                definition = matrix["regras_amostra"][sample]
                known = provides | {"nome"} | set(dim_params.values())
                missing = set(definition["entrada"]) - known
                if missing:
                    problems.append(f"amostra {sample} sem entrada: {sorted(missing)}")
                provides |= set(definition["saida"])
        provides |= {dim_params[item["dimensao"]] for item in case["filtros"]
                     if item["dimensao"] in dim_params}
        texts = [case["pergunta"], *(turn["content"] for turn in case["contexto"])]
        texts += [item["valor"] for item in case["filtros"]]
        missing = {name for text in texts for name in _PLACEHOLDER.findall(text)} - provides
        if missing:
            problems.append(f"marcadores sem origem: {sorted(missing)}")
        control = control_for(matrix, case)
        if executes_numeric(case):
            if control is None or not control.get("sql"):
                problems.append("caso numérico sem SQL de controle")
            else:
                params = set(_SQL_PARAM.findall(control["sql"]))
                if params - provides:
                    problems.append(f"controle sem parâmetros: {sorted(params - provides)}")
                mapping = control.get("valor_por_metrica")
                column = mapping.get(case["metrica"]) if mapping else "valor"
                if column not in control["saida"]:
                    problems.append("controle sem coluna de valor para a métrica")
            if case["metrica"] is not None and case["metrica"] not in rounding:
                problems.append(f"métrica fora do catálogo v2: {case['metrica']}")
        if problems:
            errors[case["id"]] = problems
    return errors


# Períodos, amostras e marcadores -------------------------------------------------------------

def _shift(month: str, delta: int) -> str:
    year, number = int(month[:4]), int(month[5:7])
    index = year * 12 + number - 1 + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _month_vars(month: str, suffix: str = "") -> dict:
    return {f"mes{suffix}" if suffix else "mes_extenso": MONTH_NAMES[int(month[5:7]) - 1],
            f"ano{suffix}" if suffix else "ano": month[:4]}


def resolve_period(matrix: dict, rule: str, db: ControlDatabase, cache: dict) -> dict:
    if rule in cache:
        return cache[rule]
    definition = matrix["regras_periodo"][rule]
    result: dict = {}
    if definition.get("sql"):
        rows = db.fetch_all(f"periodo:{rule}", definition["sql"], {})
        month = rows[0].get("competencia") if rows else None
        if not month:
            raise NoSample(f"período {rule} sem competência no lote")
        result = {"competencia": month, **_month_vars(month)}
    elif definition.get("deriva_de"):
        month = resolve_period(matrix, definition["deriva_de"], db, cache)["competencia"]
        if rule == "COMPETENCIA_APOS_ULTIMA":
            later = _shift(month, 1)
            result = {"competencia": later, **_month_vars(later)}
        elif rule == "ULTIMO_TRIMESTRE_RECEITA":
            result = {"inicio": _shift(month, -2), "fim": month}
        elif rule == "ANO_CORRENTE_PARCIAL":
            if month.endswith("-12"):
                raise NoSample("ano corrente completo; não há período parcial")
            result = {"inicio": f"{month[:4]}-01", "fim": month}
        elif rule == "PAR_ANO_A_ANO_RECEITA":
            previous = _shift(month, -12)
            result = {"p0": previous, "p1": month,
                      **_month_vars(previous, "_p0"), **_month_vars(month, "_p1")}
    cache[rule] = result
    return result


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(plain.casefold().split())


def resolve_parameters(matrix: dict, case: dict, db: ControlDatabase, cache: dict) -> dict:
    params = dict(resolve_period(matrix, case["periodo"]["regra"], db, cache))
    dim_params = matrix["parametros_por_dimensao"]
    sample = case["amostra"]
    if sample is not None:
        published = cache.get("_municipios")
        if published is None:
            rule = matrix["regras_amostra"]["MUNICIPIO_DO_CASE"]
            rows = db.fetch_all("amostra:MUNICIPIO_DO_CASE", rule["sql"], {})
            published = cache["_municipios"] = [row["municipio"] for row in rows]
        for item in case["filtros"]:
            if item["dimensao"] != "geography.municipality" or _PLACEHOLDER.search(item["valor"]):
                continue
            if item["valor"] in FICTITIOUS_PLACES:
                continue
            match = [value for value in published if normalize(value) == normalize(item["valor"])]
            if len(match) != 1:
                raise NoSample("município do case ausente ou ambíguo na publicação")
            params["municipio"] = match[0]
    for item in case["filtros"]:
        name = dim_params.get(item["dimensao"])
        if name and not _PLACEHOLDER.search(item["valor"]) and name not in params:
            params[name] = item["valor"]
    if sample is not None and sample != "MUNICIPIO_DO_CASE":
        rule = matrix["regras_amostra"][sample]
        rows = db.fetch_all(f"amostra:{sample}", rule["sql"],
                            {name: params[name] for name in rule["entrada"] if name in params})
        if not rows or any(rows[0].get(name) in (None, "") for name in rule["saida"]):
            raise NoSample(f"amostra {sample} sem recorte no lote")
        params.update({name: rows[0][name] for name in rule["saida"]})
    return params


def render(text: str, params: dict) -> str:
    return _PLACEHOLDER.sub(lambda match: str(params[match.group(1)]), text)


# Valores esperados, números e estados --------------------------------------------------------

def rounded(value, decimals: int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_EVEN)


def expected_values(matrix: dict, case: dict, params: dict, db: ControlDatabase,
                    decimals: int) -> list[Decimal]:
    control = control_for(matrix, case)
    sql_params = {name: params[name] for name in set(_SQL_PARAM.findall(control["sql"]))}
    rows = db.fetch_all(f"controle:{case['controle']['ref']}", control["sql"], sql_params)
    if not rows:
        raise NoSample("controle sem linhas no recorte")
    for column, param in control.get("conferencia", {}).items():
        if rows[0].get(column) != params.get(param):
            raise MatrixError("controle e amostra apontam recortes diferentes")
    label = control.get("rotulo_resultado")
    if label:
        if not rows[0].get(label):
            raise NoSample("controle sem rótulo do grupo")
        params["_rotulo_controle"] = str(rows[0][label])
    mapping = control.get("valor_por_metrica")
    column = mapping[case["metrica"]] if mapping else "valor"
    if control.get("valores_por_rotulo"):
        if len(rows) != 1 or rows[0].get("estado_decomposicao") != "CALCULADA_BASE_COMUM":
            raise NoSample("decomposição sem estado calculado único no recorte")
        params["_rotulos_numericos"] = {
            label: rows[0].get(name) for label, name in control["valores_por_rotulo"].items()
        }
        first, end_first, last, end_last = [rows[0][key] for key in control["periodo_publicado"]]
        params["_periodo_publicado"] = f"P0 {first} a {end_first}; P1 {last} a {end_last}"
    elif control.get("colunas_numericas"):
        params["_comparacao_esperada"] = dict(rows[0])
    numeric_columns = control.get("colunas_numericas", [column])
    optional = set(control.get("colunas_opcionais", []))
    values = [row.get(name) for row in rows for name in numeric_columns
              if name not in optional or row.get(name) is not None]
    if any(value is None for value in values):
        raise NoSample("controle sem valor numérico no recorte")
    return [rounded(value, decimals) for value in values]


def parse_numbers(text: str | None) -> list[Decimal]:
    """Lê números em pt-BR ou en-US; separador ambíguo gera as duas leituras."""
    found: list[Decimal] = []
    for token in _NUMBER.findall(text or ""):
        token = token.rstrip(".,")
        candidates = set()
        if "," in token and "." in token:
            decimal_mark = "," if token.rfind(",") > token.rfind(".") else "."
            thousands = "." if decimal_mark == "," else ","
            candidates.add(token.replace(thousands, "").replace(decimal_mark, "."))
        elif "," in token:
            candidates.add(token.replace(".", "").replace(",", "."))
            candidates.add(token.replace(",", ""))
        else:
            candidates.add(token)
            if token.count(".") >= 1:
                candidates.add(token.replace(".", ""))
        for candidate in candidates:
            try:
                found.append(Decimal(candidate))
            except InvalidOperation:
                continue
    return found


def observed_status(http_status: int, body: dict | None) -> str:
    if http_status == 200 and body and isinstance(body.get("status"), str):
        return body["status"]
    code = ((body or {}).get("error") or {}).get("code") or "transport"
    return f"error:{code}"


def status_matches(expected: str, observed: str) -> bool:
    return observed in {item.strip() for item in expected.split("|")}


def period_matches(case: dict, period: str, params: dict) -> bool:
    """Confere a janela resolvida, sem aceitar apenas a presença de texto."""
    if "_periodo_publicado" in params:
        return normalize(period) == normalize(params["_periodo_publicado"])
    if case["periodo"]["regra"] == "HISTORICO_ACUMULADO":
        return normalize(period) == normalize("histórico acumulado")
    if case["periodo"]["regra"] == "JANELAS_FIXAS_VARIACAO":
        return normalize(period) == normalize("P1 2022-07 a 2023-06 versus P2 2025-07 a 2026-06")
    start = params.get("inicio", params.get("competencia", params.get("p0")))
    end = params.get("fim", params.get("competencia", params.get("p1")))
    if not start or not end:
        return False
    year, month = map(int, end.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    accepted = {f"{start}-01 a {end}-{last_day:02d}"}
    if start == end:
        accepted.add(f"{MONTH_NAMES[month - 1]} de {year}")
    return normalize(period) in {normalize(value) for value in accepted}


def numeric_divergences(case: dict, body: dict, expected: list[Decimal], tolerance: Decimal,
                        params: dict, dim_params: dict) -> tuple[list[str], list[Decimal]]:
    divergences = []
    context = body.get("analysis_context") or {}
    if case["metrica"] and context.get("metric") != case["metrica"]:
        divergences.append("interpretacao")
    filters = context.get("filters") or {}
    for item in case["filtros"]:
        name = dim_params.get(item["dimensao"])
        wanted = params.get(name) if name else item["valor"]
        if normalize(filters.get(item["dimensao"], "")) != normalize(wanted):
            divergences.append("plano")
            break
    if not period_matches(case, context.get("period") or "", params):
        divergences.append("plano")
    evidence = body.get("evidence") or []
    if (not evidence or any(item.get("is_demo") for item in evidence)
            or context.get("unit") != case["unidade"] or not context.get("period")
            or not body.get("audit_reference")):
        divergences.append("fundamentacao")
    label = params.get("_rotulo_controle")
    if label and normalize(label) not in normalize(body.get("answer") or ""):
        divergences.append("plano")
    for label, expected_value in params.get("_rotulos_numericos", {}).items():
        match = re.search(re.escape(normalize(label)) + r":\s*([+-]?[0-9][0-9.,]*)",
                          normalize(body.get("answer") or ""))
        observed_values = parse_numbers(match.group(1)) if match else []
        if expected_value is None or not any(
            abs(value - Decimal(str(expected_value))) <= tolerance for value in observed_values
        ):
            divergences.append("numero")
    comparison = params.get("_comparacao_esperada")
    if comparison:
        answer = normalize(body.get("answer") or "")
        labels = {
            "valor": (params["p0"], case["unidade"]),
            "valor_final": (params["p1"], case["unidade"]),
            "variacao": (f"Variação absoluta de {params['p0']} a {params['p1']}", case["unidade"]),
            "percentual": (f"Variação percentual de {params['p0']} a {params['p1']}", "%"),
        }
        for column, (label, unit) in labels.items():
            match = re.search(re.escape(normalize(label))
                              + r"(?:,[^:\n]{1,200})?:\s*([+-]?[0-9][0-9.,]*)\s*"
                              + re.escape(normalize(unit)), answer)
            wanted = comparison.get(column)
            observed = parse_numbers(match.group(1)) if match else []
            if wanted is None:
                if observed:
                    divergences.append("numero")
            elif not any(abs(value - Decimal(str(wanted))) <= tolerance for value in observed):
                divergences.append("numero")
    numbers = parse_numbers(body.get("answer"))
    if not all(any(abs(number - value) <= tolerance for number in numbers) for value in expected):
        divergences.append("numero")
    return divergences, numbers


# Execução e classificação --------------------------------------------------------------------

def run_case(matrix: dict, catalog: dict, case: dict, client: FlowClient | None,
             db: ControlDatabase | None, cache: dict, denied: FlowClient | None = None) -> Outcome:
    outcome = Outcome(case["id"], case["dominio"], case["obrigatorio"],
                      estado_esperado=case["estado_esperado"],
                      status_publico_esperado=case["status_publico_esperado"])
    if case["modo_execucao"] == "regressao_tecnica":
        refs = case["referencias"].get("regressao_tecnica", [])
        outcome.motivo = "regressão técnica: " + ", ".join(refs) if refs else "regressão técnica"
        return outcome
    asker = client
    if case["estado_esperado"] == "acesso_negado":
        if denied is None:
            outcome.motivo = "configure GENAI10A_DENIED_USERNAME e GENAI10A_DENIED_PASSWORD"
            return outcome
        asker = denied
    tolerance_rule = matrix["tolerancias"][case["tolerancia"]]
    decimals = catalog_rounding(catalog).get(case["metrica"], 2)
    try:
        params = resolve_parameters(matrix, case, db, cache)
        outcome.parametros = {key: str(value) for key, value in params.items()}
        expected: list[Decimal] = []
        numeric = executes_numeric(case)
        if numeric:
            expected = expected_values(matrix, case, params, db, decimals)
            outcome.valores_esperados = [str(value) for value in expected]
        question = render(case["pergunta"], params)
        context = [{"role": turn["role"], "content": render(turn["content"], params)}
                   for turn in case["contexto"]]
        http_status, body = asker.ask(question, context)
    except NoSample as exc:
        outcome.classe, outcome.motivo = "SEM_AMOSTRA_NO_LOTE", str(exc)
        return outcome
    except MatrixError as exc:
        outcome.classe, outcome.motivo = "FAIL", str(exc)
        outcome.divergencias.append("numero")
        return _known(matrix, outcome)
    except Exception as exc:  # noqa: BLE001 - nenhuma mensagem pode carregar dados ou segredos.
        outcome.motivo, outcome.erro_execucao = f"erro de execução: {type(exc).__name__}", True
        return outcome
    outcome.http_status = http_status
    outcome.status_observado = observed_status(http_status, body)
    outcome.referencia_execucao = (body or {}).get("audit_reference")
    answered = outcome.status_observado == "answered" and bool((body or {}).get("answer"))
    expected_status = case["status_publico_esperado"]
    if case["bloqueio"] is not None:
        expected_status = case["bloqueio"]["estado_publico_atual"]
    # Estado diferente, ou número onde o esperado é esclarecimento/recusa/bloqueio, é FAIL.
    wrong_state = not status_matches(expected_status, outcome.status_observado)
    unexpected_number = answered and case["estado_esperado"] in NON_NUMERIC_STATES
    if wrong_state or unexpected_number:
        outcome.divergencias.append("recusa")
    elif numeric and answered:
        tolerance = Decimal(str(tolerance_rule["absoluta"]))
        divergences, numbers = numeric_divergences(
            case, body, expected, tolerance, params, matrix["parametros_por_dimensao"],
        )
        outcome.divergencias.extend(divergences)
        outcome.numeros_extraidos = [str(number) for number in numbers]
    if outcome.divergencias:
        outcome.classe = "FAIL"
        return _known(matrix, outcome)
    outcome.classe = "BLOQUEADO" if case["bloqueio"] is not None else "PASS"
    return outcome


def _known(matrix: dict, outcome: Outcome) -> Outcome:
    known = {item["id"] for item in matrix["criterios_regressao"]["falhas_conhecidas"]}
    if outcome.id in known:
        outcome.classe = "FALHA_CONHECIDA"
    return outcome


def summarize(matrix: dict, outcomes: list[Outcome]) -> dict:
    domains = {}
    for domain in sorted({case["dominio"] for case in matrix["casos"]}):
        items = [outcome for outcome in outcomes if outcome.dominio == domain]
        required = [case for case in matrix["casos"]
                    if case["dominio"] == domain and case["obrigatorio"]]
        by_id = {outcome.id: outcome for outcome in items}
        missing = [case["id"] for case in required if case["id"] not in by_id]
        unapproved = [case["id"] for case in required if is_numeric(case)
                      and (case["controle"]["estado_do_controle"] != "aprovado"
                           or not case["controle"]["aprovado_por"].strip())]
        pending = [case["id"] for case in required
                   if case["id"] not in by_id or by_id[case["id"]].classe != "PASS"]
        domains[domain] = {
            "classes": dict(Counter(outcome.classe for outcome in items)),
            "coberto": bool(required) and not pending and not unapproved,
            "obrigatorios_fora_de_pass": pending,
            "obrigatorios_nao_executados": missing,
            "controles_sem_aprovacao": unapproved,
        }
    return {
        "dominios": domains,
        "dominios_obrigatorios_pendentes": [
            domain for domain in matrix["dominios_obrigatorios"]
            if not domains.get(domain, {}).get("coberto")
        ],
        "falhas_inesperadas": [o.id for o in outcomes if o.classe == "FAIL"],
        "falhas_conhecidas": [o.id for o in outcomes if o.classe == "FALHA_CONHECIDA"],
        "erros_execucao": [o.id for o in outcomes if o.erro_execucao],
    }


def print_report(outcomes: list[Outcome], summary: dict, stream=None) -> None:
    stream = stream or sys.stdout
    for outcome in outcomes:
        state = outcome.status_observado or "-"
        divergences = ",".join(outcome.divergencias) or "-"
        print(f"{outcome.id} {outcome.classe} estado={state} divergencias={divergences}",
              file=stream)
    print("Cobertura por domínio:", file=stream)
    for domain, data in summary["dominios"].items():
        classes = ", ".join(f"{name} {count}" for name, count in sorted(data["classes"].items()))
        status = "coberto" if data["coberto"] else "pendente"
        print(f"  {domain}: {status} ({classes})", file=stream)
    print("Falhas inesperadas: " + (", ".join(summary["falhas_inesperadas"]) or "nenhuma"),
          file=stream)
    print("Falhas conhecidas: " + (", ".join(summary["falhas_conhecidas"]) or "nenhuma"),
          file=stream)
    print("Erros de execução: " + (", ".join(summary["erros_execucao"]) or "nenhum"), file=stream)
    print("Domínios obrigatórios pendentes: "
          + (", ".join(summary["dominios_obrigatorios_pendentes"]) or "nenhum"), file=stream)


def safe_output_dir(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(WORK_ROOT.resolve()):
        raise ValueError("a saída precisa ficar em work/, ignorado pelo Git")
    return resolved


def write_results(output_dir: Path, outcomes: list[Outcome], summary: dict) -> Path:
    run_dir = safe_output_dir(output_dir) / datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    payload = [outcome.__dict__ for outcome in outcomes]
    (run_dir / "resultados.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "resumo.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return run_dir


def run_matrix(matrix: dict, catalog: dict, cases: list[dict], client: FlowClient,
               db: ControlDatabase, denied: FlowClient | None = None) -> list[Outcome]:
    cache: dict = {}
    return [run_case(matrix, catalog, case, client, db, cache, denied) for case in cases]


# Adaptadores reais ---------------------------------------------------------------------------

class HttpFlowClient:
    """Sessão individual pela API pública; nada da resposta é registrado além do envelope."""

    def __init__(self, base_url: str, origin: str, *, transport=None, timeout: float = 45.0):
        import httpx

        if "@" in base_url.split("//", 1)[-1].split("/", 1)[0]:
            raise ValueError("a URL do Backend não pode conter credenciais")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport,
            follow_redirects=False,
            headers={"Origin": origin, "Content-Type": "application/json"},
        )

    def login(self, username: str, password: str) -> None:
        response = self._client.post("/api/v1/auth/login",
                                     json={"username": username, "password": password})
        if response.status_code != 200:
            raise PermissionError(f"login recusado (HTTP {response.status_code})")

    def ask(self, question: str, context: list[dict]) -> tuple[int, dict | None]:
        response = self._client.post("/api/v1/ai/questions",
                                     json={"question": question, "context": context})
        try:
            body = response.json()
        except ValueError:
            body = None
        return response.status_code, body if isinstance(body, dict) else None

    def close(self) -> None:
        self._client.close()


class PsycopgControlDatabase:
    """Consultas de controle em transação somente leitura, com prazo no servidor."""

    def __init__(self, dsn: str, *, statement_timeout_ms: int = 5000):
        import psycopg
        from psycopg.rows import dict_row

        self._connection = psycopg.connect(dsn, autocommit=False, row_factory=dict_row)
        self._connection.read_only = True
        self._timeout = int(statement_timeout_ms)

    def fetch_all(self, name: str, sql: str, params: dict) -> list[dict]:
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL statement_timeout = {self._timeout}")
                cursor.execute(to_pyformat(sql), params)
                return list(cursor.fetchall())
        finally:
            self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def select_cases(matrix: dict, ids: str | None, domain: str | None) -> list[dict]:
    wanted = {item.strip() for item in ids.split(",")} if ids else None
    cases = [case for case in matrix["casos"]
             if (wanted is None or case["id"] in wanted)
             and (domain is None or case["dominio"] == domain)]
    if wanted and wanted - {case["id"] for case in cases}:
        raise ValueError("IDs ausentes da matriz: "
                         + ", ".join(sorted(wanted - {case["id"] for case in cases})))
    return cases


def main(argv: list[str] | None = None, environ: dict | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ids", help="IDs separados por vírgula")
    parser.add_argument("--domain", help="executa apenas um domínio")
    parser.add_argument("--dry-run", action="store_true", help="valida matriz e controles sem rede")
    parser.add_argument("--strict", action="store_true",
                        help="sai com 3 se algum domínio obrigatório continuar pendente")
    args = parser.parse_args(argv)
    environ = os.environ if environ is None else environ
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    matrix, catalog = load_json(args.matrix), load_json(args.catalog)
    try:
        cases = select_cases(matrix, args.ids, args.domain)
        safe_output_dir(args.output_dir)
    except ValueError as exc:
        print(f"Configuração inválida: {exc}")
        return 2
    errors = validate_matrix(matrix, catalog)
    if args.dry_run:
        for case in cases:
            problems = errors.get(case["id"])
            print(f"{case['id']} {'ERRO ' + '; '.join(problems) if problems else 'OK'}")
        for problem in errors.get("_matriz", []):
            print(f"_matriz ERRO {problem}")
        counts = Counter(case["dominio"] for case in cases)
        print("Casos por domínio: " + ", ".join(f"{d} {n}" for d, n in sorted(counts.items())))
        return 1 if errors else 0
    if errors:
        print("Matriz não executável; rode --dry-run para ver os erros.")
        return 2
    missing = [name for name in ENV_REQUIRED if not environ.get(name)]
    if missing:
        print("Variáveis ausentes: " + ", ".join(missing))
        return 2

    client = denied = db = None
    try:
        client = HttpFlowClient(environ["GENAI10A_BACKEND_URL"], environ["GENAI10A_ORIGIN"])
        client.login(environ["GENAI10A_USERNAME"], environ["GENAI10A_PASSWORD"])
        if environ.get("GENAI10A_DENIED_USERNAME") and environ.get("GENAI10A_DENIED_PASSWORD"):
            denied = HttpFlowClient(environ["GENAI10A_BACKEND_URL"], environ["GENAI10A_ORIGIN"])
            denied.login(environ["GENAI10A_DENIED_USERNAME"], environ["GENAI10A_DENIED_PASSWORD"])
        db = PsycopgControlDatabase(environ["GENAI10A_CONTROL_DSN"])
    except Exception as exc:  # noqa: BLE001 - não repassar URL, DSN ou mensagem do driver.
        print(f"Falha ao preparar a execução: {type(exc).__name__}")
        for resource in (client, denied, db):
            if resource is not None:
                resource.close()
        return 2
    try:
        outcomes = run_matrix(matrix, catalog, cases, client, db, denied)
    finally:
        for resource in (client, denied, db):
            if resource is not None:
                resource.close()
    summary = summarize(matrix, outcomes)
    run_dir = write_results(args.output_dir, outcomes, summary)
    print_report(outcomes, summary)
    print(f"Resultados gravados em {run_dir.relative_to(REPO_ROOT).as_posix()}")
    if summary["falhas_inesperadas"] or summary["erros_execucao"]:
        return 1
    if args.strict and summary["dominios_obrigatorios_pendentes"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
