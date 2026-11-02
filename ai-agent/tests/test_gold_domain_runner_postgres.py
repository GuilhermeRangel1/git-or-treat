"""GENAI-10A: adaptador PostgreSQL do runner contra banco descartável (opt-in).

Defina ``GENAI10A_TEST_POSTGRES_DSN`` para um banco cujo nome termina em ``_test``. O teste cria um
schema ``gold_v2`` mínimo com linhas sintéticas, executa regras e controles da matriz pelo adaptador
real e remove o schema ao final. Recusa rodar se ``gold_v2`` já existir.
"""

import importlib.util
import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

DSN = os.environ.get("GENAI10A_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(
    not DSN, reason="defina GENAI10A_TEST_POSTGRES_DSN para um PostgreSQL descartável *_test"
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_gold_domain_scenarios.py"
_spec = importlib.util.spec_from_file_location("run_gold_domain_scenarios_pg", SCRIPT)
runner = importlib.util.module_from_spec(_spec)
sys.modules["run_gold_domain_scenarios_pg"] = runner
_spec.loader.exec_module(runner)
MATRIX = runner.load_json(runner.DEFAULT_MATRIX)


@pytest.fixture
def synthetic_gold():
    with psycopg.connect(DSN, autocommit=True) as admin:
        name = admin.execute("SELECT current_database()").fetchone()[0]
        assert name.endswith("_test"), "use somente um banco descartável *_test"
        exists = admin.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'gold_v2'"
        ).fetchone()
        assert exists is None, "gold_v2 já existe; o teste não altera schemas existentes"
        admin.execute("CREATE SCHEMA gold_v2")
        try:
            admin.execute(
                "CREATE TABLE gold_v2.diagnostico_receita (competencia text, municipio text, "
                "classe_consumo text, receita_total_reais numeric(20,2), "
                "consumo_total_kwh double precision)"
            )
            admin.execute(
                "INSERT INTO gold_v2.diagnostico_receita VALUES "
                "('2000-02', 'Recife', 'RESIDENCIAL', 50.00, 5), "
                "('2000-03', 'Recife', 'RESIDENCIAL', 100.25, 10), "
                "('2000-03', 'Recife', 'COMERCIAL', 20.00, 2), "
                "('2000-03', 'Olinda', 'RESIDENCIAL', 30.00, NULL)"
            )
            yield
        finally:
            admin.execute("DROP SCHEMA gold_v2 CASCADE")


def test_matrix_rules_and_controls_run_through_the_read_only_adapter(synthetic_gold):
    db = runner.PsycopgControlDatabase(DSN)
    try:
        period = runner.resolve_period(MATRIX, "ULTIMA_COMPETENCIA_RECEITA", db, {})
        assert period == {"competencia": "2000-03", "mes_extenso": "março", "ano": "2000"}
        c04 = db.fetch_all("controle:C04", MATRIX["controles"]["C04"]["sql"],
                           {"competencia": "2000-03"})
        assert (c04[0]["municipio"], c04[0]["valor"]) == ("Recife", Decimal("120.25"))
        window = db.fetch_all(
            "controle:CTL-FAT-MUN-JANELA", MATRIX["controles"]["CTL-FAT-MUN-JANELA"]["sql"],
            {"inicio": "2000-01", "fim": "2000-03", "municipio": "Recife"},
        )
        assert [(row["competencia"], row["valor"]) for row in window] == [
            ("2000-02", Decimal("50.00")), ("2000-03", Decimal("120.25"))]
        null_consumption = db.fetch_all(
            "amostra:RECORTE_CONSUMO_NULO", MATRIX["regras_amostra"]["RECORTE_CONSUMO_NULO"]["sql"],
            {"competencia": "2000-03"},
        )
        assert null_consumption == [{"municipio": "Olinda", "classe": "RESIDENCIAL"}]
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            db.fetch_all("escrita", "INSERT INTO gold_v2.diagnostico_receita VALUES "
                         "('2000-04', 'Recife', 'RESIDENCIAL', 1, 1)", {})
        timeout = db.fetch_all("prazo", "SELECT current_setting('statement_timeout') AS valor", {})
        assert timeout == [{"valor": "5s"}]
    finally:
        db.close()
    with psycopg.connect(DSN) as check:
        assert check.execute("SELECT COUNT(*) FROM gold_v2.diagnostico_receita").fetchone()[0] == 4
