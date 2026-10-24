"""Small related fixture set; amounts are demonstration controls, not Gold facts."""

DATA_VERSION = "dev03-v1"
UPDATED_AT = "2026-10-21T00:00:00Z"
DATA_LIMITATION = "Dados sintéticos; não constituem diagnóstico da V-Energy."
# Revenue coverage is declared independently of observed invoice/reading rows.
REVENUE_BILLED_AMOUNT_COVERAGE = {"2025-01", "2025-02"}
REVENUE_BILLED_ENERGY_COVERAGE = {"2025-01", "2025-02"}
REVENUE_PAID_AMOUNT_COVERAGE = {"2025-01", "2025-02"}
REVENUE_MEASURED_ENERGY_COVERAGE = {"2025-01", "2025-02"}
# Complete interruption observation window; zero events within it is a known zero.
CONTINUITY_COVERAGE_START = "2025-01"
CONTINUITY_COVERAGE_END = "2025-02"

UNITS = [
    {"uc_id": "UC-1001", "customer_reference": "CLI-DEMO-01", "customer_name": "Pessoa Demonstração 01", "municipio": "Recife", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-01", "status": "active"},
    {"uc_id": "UC-1002", "customer_reference": "CLI-DEMO-02", "customer_name": "Pessoa Demonstração 02", "municipio": "Recife", "bairro": "Boa Vista", "classe": "Comercial", "alimentador": "AL-01", "status": "active"},
    {"uc_id": "UC-1003", "customer_reference": "CLI-DEMO-03", "customer_name": "Pessoa Demonstração 03", "municipio": "Olinda", "bairro": "Casa Caiada", "classe": "Residencial", "alimentador": "AL-02", "status": "active"},
    {"uc_id": "UC-1004", "customer_reference": "CLI-DEMO-04", "customer_name": "Pessoa Demonstração 04", "municipio": "Recife", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-03", "status": "active"},
    {"uc_id": "UC-1005", "customer_reference": "CLI-DEMO-05", "customer_name": "Pessoa Demonstração 05", "municipio": "Paulista", "bairro": "Jardim", "classe": "Residencial", "alimentador": "AL-02", "status": "active"},
    {"uc_id": "UC-1006", "customer_reference": "CLI-DEMO-06", "customer_name": "Pessoa Demonstração 06", "municipio": "Recife", "bairro": "Casa Forte", "classe": "Residencial", "alimentador": "AL-03", "status": "active"},
    {"uc_id": "UC-1007", "customer_reference": "CLI-DEMO-07", "customer_name": "Pessoa Demonstração 07", "municipio": "Recife", "bairro": "Boa Vista", "classe": "Comercial", "alimentador": "AL-03", "status": "active"},
    {"uc_id": "UC-1008", "customer_reference": "CLI-DEMO-08", "customer_name": "Pessoa Demonstração 08", "municipio": "Recife", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-03", "status": "active"},
    {"uc_id": "UC-1009", "customer_reference": "CLI-DEMO-09", "customer_name": "Pessoa Demonstração 09", "municipio": "Recife", "bairro": "Casa Forte", "classe": "Residencial", "alimentador": "AL-03", "status": "active"},
    {"uc_id": "UC-1010", "customer_reference": "CLI-DEMO-10", "customer_name": "Pessoa Demonstração 10", "municipio": "Recife", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-03", "status": "active"},
]

# Billed and paid amounts are invoice-grain facts; null means payment is unknown.
INVOICES = [
    {"invoice_id": "F-1001-01", "uc_id": "UC-1001", "competencia": "2025-01", "billed_amount": 100.0, "paid_amount": 100.0, "billed_energy_kwh": 90.0, "due_date": "2025-02-10", "payment_date": "2025-02-08", "payment_status": "paid"},
    {"invoice_id": "F-1002-01", "uc_id": "UC-1002", "competencia": "2025-01", "billed_amount": 70.0, "paid_amount": 70.0, "billed_energy_kwh": 60.0, "due_date": "2025-02-10", "payment_date": "2025-02-08", "payment_status": "paid"},
    {"invoice_id": "F-1002-02", "uc_id": "UC-1002", "competencia": "2025-02", "billed_amount": 82.0, "paid_amount": 70.0, "billed_energy_kwh": 80.0, "due_date": "2025-03-10", "payment_date": "2025-03-05", "payment_status": "partial"},
    {"invoice_id": "F-1003-01", "uc_id": "UC-1003", "competencia": "2025-01", "billed_amount": 0.0, "paid_amount": 0.0, "billed_energy_kwh": 0.0, "due_date": "2025-02-10", "payment_date": None, "payment_status": "unknown"},
    {"invoice_id": "F-1001-02", "uc_id": "UC-1001", "competencia": "2025-02", "billed_amount": 105.0, "paid_amount": 105.0, "billed_energy_kwh": 95.0, "due_date": "2025-03-10", "payment_date": "2025-03-08", "payment_status": "paid"},
    {"invoice_id": "F-1003-02", "uc_id": "UC-1003", "competencia": "2025-02", "billed_amount": 80.0, "paid_amount": 80.0, "billed_energy_kwh": 70.0, "due_date": "2025-03-10", "payment_date": "2025-03-08", "payment_status": "paid"},
    {"invoice_id": "F-1006-01", "uc_id": "UC-1006", "competencia": "2025-01", "billed_amount": 90.0, "paid_amount": 90.0, "billed_energy_kwh": 80.0, "due_date": "2025-02-10", "payment_date": "2025-02-08", "payment_status": "paid"},
    {"invoice_id": "F-1006-02", "uc_id": "UC-1006", "competencia": "2025-02", "billed_amount": 95.0, "paid_amount": 95.0, "billed_energy_kwh": 85.0, "due_date": "2025-03-10", "payment_date": "2025-03-08", "payment_status": "paid"},
    {"invoice_id": "F-1007-01", "uc_id": "UC-1007", "competencia": "2025-01", "billed_amount": 110.0, "paid_amount": 110.0, "billed_energy_kwh": 100.0, "due_date": "2025-02-10", "payment_date": "2025-02-08", "payment_status": "paid"},
    {"invoice_id": "F-1007-02", "uc_id": "UC-1007", "competencia": "2025-02", "billed_amount": 120.0, "paid_amount": 115.0, "billed_energy_kwh": 110.0, "due_date": "2025-03-10", "payment_date": "2025-03-08", "payment_status": "partial"},
    {"invoice_id": "F-1008-01", "uc_id": "UC-1008", "competencia": "2025-01", "billed_amount": 130.0, "paid_amount": 130.0, "billed_energy_kwh": 120.0, "due_date": "2025-02-10", "payment_date": "2025-02-08", "payment_status": "paid"},
    {"invoice_id": "F-1008-02", "uc_id": "UC-1008", "competencia": "2025-02", "billed_amount": 135.0, "paid_amount": 135.0, "billed_energy_kwh": 125.0, "due_date": "2025-03-10", "payment_date": "2025-03-08", "payment_status": "paid"},
    {"invoice_id": "F-1009-01", "uc_id": "UC-1009", "competencia": "2025-01", "billed_amount": 140.0, "paid_amount": 140.0, "billed_energy_kwh": 130.0, "due_date": "2025-02-10", "payment_date": "2025-02-08", "payment_status": "paid"},
    {"invoice_id": "F-1009-02", "uc_id": "UC-1009", "competencia": "2025-02", "billed_amount": 145.0, "paid_amount": 145.0, "billed_energy_kwh": 135.0, "due_date": "2025-03-10", "payment_date": "2025-03-08", "payment_status": "paid"},
    {"invoice_id": "F-1010-01", "uc_id": "UC-1010", "competencia": "2025-01", "billed_amount": 160.0, "paid_amount": 160.0, "billed_energy_kwh": 150.0, "due_date": "2025-02-10", "payment_date": "2025-02-08", "payment_status": "paid"},
    {"invoice_id": "F-1010-02", "uc_id": "UC-1010", "competencia": "2025-02", "billed_amount": 165.0, "paid_amount": 165.0, "billed_energy_kwh": 155.0, "due_date": "2025-03-10", "payment_date": "2025-03-08", "payment_status": "paid"},
]

# Measurement-grain facts are independent from invoices.
READINGS = [
    {"uc_id": "UC-1001", "competencia": "2025-01", "measured_energy_kwh": 100.0, "status": "available"},
    {"uc_id": "UC-1001", "competencia": "2025-02", "measured_energy_kwh": 90.0, "status": "available"},
    {"uc_id": "UC-1002", "competencia": "2025-01", "measured_energy_kwh": 80.0, "status": "available"},
    {"uc_id": "UC-1002", "competencia": "2025-02", "measured_energy_kwh": 82.0, "status": "available"},
    {"uc_id": "UC-1003", "competencia": "2025-01", "measured_energy_kwh": 0.0, "status": "available"},
    {"uc_id": "UC-1003", "competencia": "2025-02", "measured_energy_kwh": 10.0, "status": "available"},
    {"uc_id": "UC-1004", "competencia": "2025-01", "measured_energy_kwh": 45.0, "status": "available"},
    {"uc_id": "UC-1004", "competencia": "2025-02", "measured_energy_kwh": None, "status": "missing"},
]

METERS = [
    {"meter_id": "MED-01", "uc_id": "UC-1001", "installed_at": "2022-03-01", "removed_at": None},
    {"meter_id": "MED-02", "uc_id": "UC-1002", "installed_at": "2021-07-15", "removed_at": None},
    {"meter_id": "MED-03", "uc_id": "UC-1003", "installed_at": "2024-01-10", "removed_at": None},
    {"meter_id": "MED-04", "uc_id": "UC-1004", "installed_at": "2020-05-02", "removed_at": "2025-01-31"},
]

GENERATION = [{"uc_id": "UC-1002", "capacity_kw": 4.2, "status": "active"}]

INTERRUPTIONS = [
    {"event_id": "EV-01", "uc_id": "UC-1001", "feeder_id": "AL-01", "competencia": "2025-01", "duration_hours": 2.0},
    {"event_id": "EV-02", "uc_id": "UC-1002", "feeder_id": "AL-01", "competencia": "2025-02", "duration_hours": 1.0},
    {"event_id": "EV-03", "uc_id": "UC-1003", "feeder_id": "AL-02", "competencia": "2025-02", "duration_hours": 3.0},
]

CALLS = [
    {"call_id": "CH-01", "uc_id": "UC-1001", "opened_at": "2025-01-12", "category": "billing"},
    {"call_id": "CH-02", "uc_id": "UC-1001", "opened_at": "2025-02-05", "category": "continuity"},
    {"call_id": "CH-03", "uc_id": "UC-1003", "opened_at": "2025-02-03", "category": "billing"},
]

FEEDERS = [
    {"feeder_id": "AL-01", "municipios": ["Recife"], "territory_status": "single_municipality", "denominator_uc_count": 2},
    {"feeder_id": "AL-02", "municipios": ["Olinda", "Paulista"], "territory_status": "multi_municipal", "denominator_uc_count": 2},
    {"feeder_id": "AL-03", "municipios": ["Recife"], "territory_status": "single_municipality", "denominator_uc_count": None},
]

SUSPICIONS = [
    {"uc_id": "UC-1004", "reason": "Lacuna de leitura e medidor retirado", "indicators": ["reading_gap", "meter_removed"],
     "estimate_evidence": {"baseline_kwh": 90.0, "observed_kwh": 45.0, "horizon_months": 1,
                           "reference": "Cenário sintético DEV-05: referência hipotética de 90 kWh/mês e leitura conhecida de janeiro/2025 de 45 kWh. Fevereiro sem leitura não é imputado; projeção de um mês, não total da janela."}},
    {"uc_id": "UC-1002", "reason": "Variação de consumo com geração distribuída; investigar contexto", "indicators": ["consumption_variation", "distributed_generation"],
     "estimate_evidence": {"baseline_kwh": None, "observed_kwh": 82.0, "horizon_months": 1,
                           "reference": "Leitura de fevereiro/2025: 82 kWh. Referência comparável ajustada para GD indisponível."}},
]

# Controls: invoices total BRL 1,727 and payments with known values total
# BRL 1,710 (Jan 800, Feb 927); billed energy is 1,585 kWh. Jan–Feb measured
# energy remains 407 kWh across the eight reading rows with known values.
