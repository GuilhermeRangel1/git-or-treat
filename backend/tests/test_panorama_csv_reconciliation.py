"""Opt-in read-only reconciliation; never prints dataset values or identifiers."""
import csv
import json
import math
import os
from decimal import Decimal
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

import pytest


def test_final_csv_uc_counts_match_authenticated_api():
    directory = os.environ.get("PANORAMA_CSV_DIR")
    api = os.environ.get("PANORAMA_API_URL")
    credentials = os.environ.get("PANORAMA_CREDENTIALS_FILE")
    if not all((directory, api, credentials)):
        pytest.skip("Requires explicit CSV directory, API and local credentials file.")
    root = Path(directory)

    def rows(table):
        for file in (root / table).glob("*.csv"):
            with file.open(encoding="utf-8-sig", newline="") as stream:
                yield from csv.DictReader(stream, delimiter=";")

    cadastro = {row["id_uc"]: row for row in rows("visao_360_uc")}
    assert cadastro, "CSV cadastro must exist."
    diagnosis = list(rows("diagnostico_receita"))
    secrets = dict(line.split(": ", 1) for line in Path(credentials).read_text().splitlines() if ": " in line)
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    request = Request(api + "/auth/login", data=json.dumps({
        "username": secrets["Operator username"], "password": secrets["Operator password"],
    }).encode(), headers={"Content-Type": "application/json", "Origin": "http://localhost:5173"})
    with opener.open(request) as response:
        assert response.status == 200

    def get(params):
        with opener.open(api + "/panorama?" + urlencode(params)) as response:
            return json.load(response)

    initial = get({"comparacao": "anterior", "municipio": "todos", "classe": "todas"})
    periods = initial["data"]["opcoesFiltros"]["competencias"]
    period = periods[-1]
    reference = f"{int(period[:4]) - (period[5:] == '01'):04d}-{(int(period[5:]) - 2) % 12 + 1:02d}"
    municipality = initial["data"]["opcoesFiltros"]["municipios"][0]
    consumption_class = initial["data"]["opcoesFiltros"]["classes"][0]
    cases = [(None, None), (municipality, None), (None, consumption_class), (municipality, consumption_class)]
    expected = {(month, case): set() for month in (period, reference) for case in cases}

    def matches(row, case):
        return all(
            value is None
            or row.get(field, row.get("classe_consumo", "Não informado")) in (value,)
            for field, value in zip(("municipio", "classe"), case)
        )

    def aggregate(month, case, field):
        values = [
            Decimal(row[field])
            for row in diagnosis
            if row["competencia"] == month
            and matches(row, case)
            and row.get(field) not in (None, "", "\\N")
        ]
        return sum(values, Decimal(0)) if values else None

    def agrees(actual, expected):
        if expected is None:
            return actual is None
        return actual is not None and math.isclose(float(actual), float(expected), rel_tol=1e-10, abs_tol=1e-6)

    for row in rows("consumo_mensal_uc"):
        if row["competencia"] not in (period, reference) or row["tem_fatura"].lower() != "true":
            continue
        for case in cases:
            if matches(cadastro.get(row["id_uc"], {}), case):
                expected[(row["competencia"], case)].add(row["id_uc"])

    for case in cases:
        envelope = get({"competencia": period, "comparacao": "anterior", "municipio": case[0] or "todos", "classe": case[1] or "todas"})
        metrics = envelope["data"]["metricas"]
        assert metrics["ucsFaturadasNoMes"]["valorAtual"] == len(expected[(period, case)]), "Current billed UC count must reconcile with the CSV."
        if reference in periods:
            assert metrics["ucsFaturadasNoMes"]["valorAnterior"] == len(expected[(reference, case)]), "Reference billed UC count must reconcile with the CSV."
        assert metrics["ucsAtivas"]["valorAtual"] == sum(matches(row, case) for row in cadastro.values()), "Current registered UC count must reconcile with the CSV."
        assert metrics["ucsAtivas"]["valorAnterior"] is None
        assert metrics["energiaFaturada"]["valorAtual"] is None
        assert agrees(metrics["receitaFaturada"]["valorAtual"], aggregate(period, case, "receita_base_comparavel_reais")), "Current billed revenue must reconcile with the CSV."
        assert agrees(metrics["energiaConsumida"]["valorAtual"], aggregate(period, case, "consumo_base_comparavel_kwh")), "Current measured consumption must reconcile with the CSV."
        points = envelope["data"]["serieMensal"]
        expected_months = sorted({row["competencia"] for row in diagnosis if row["competencia"] <= period and matches(row, case)})
        assert [point["competencia"] for point in points] == expected_months, "Filtered series competencies must reconcile with the CSV."
        assert all(agrees(point["receitaFaturada"], aggregate(point["competencia"], case, "receita_base_comparavel_reais")) for point in points), "Filtered monthly revenue series must reconcile with the CSV."
        assert envelope["metadata"]["fingerprint"] == initial["metadata"]["fingerprint"]
