"""Small related fixture set; amounts are demonstration controls, not Gold facts."""

DATA_VERSION = "dev01-v1"
UPDATED_AT = "2026-10-20T00:00:00Z"
DATA_LIMITATION = "Dados sintéticos; não constituem diagnóstico da V-Energy."
# Complete interruption observation window; zero events within it is a known zero.
CONTINUITY_COVERAGE_START = "2025-01"
CONTINUITY_COVERAGE_END = "2025-02"

UNITS = [
    {"uc_id": "UC-1001", "customer_reference": "CLI-DEMO-01", "customer_name": "Pessoa Demonstração 01", "municipio": "Recife", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-01", "status": "active"},
    {"uc_id": "UC-1002", "customer_reference": "CLI-DEMO-02", "customer_name": "Pessoa Demonstração 02", "municipio": "Recife", "bairro": "Boa Vista", "classe": "Comercial", "alimentador": "AL-01", "status": "active"},
    {"uc_id": "UC-1003", "customer_reference": "CLI-DEMO-03", "customer_name": "Pessoa Demonstração 03", "municipio": "Olinda", "bairro": "Casa Caiada", "classe": "Residencial", "alimentador": "AL-02", "status": "active"},
    {"uc_id": "UC-1004", "customer_reference": "CLI-DEMO-04", "customer_name": "Pessoa Demonstração 04", "municipio": "Recife", "bairro": "Centro", "classe": "Residencial", "alimentador": "AL-03", "status": "active"},
    {"uc_id": "UC-1005", "customer_reference": "CLI-DEMO-05", "customer_name": "Pessoa Demonstração 05", "municipio": "Paulista", "bairro": "Jardim", "classe": "Residencial", "alimentador": "AL-02", "status": "active"},
]

# Billed and paid amounts are invoice-grain facts; null means payment is unknown.
INVOICES = [
    {"invoice_id": "F-1001-01", "uc_id": "UC-1001", "competencia": "2025-01", "billed_amount": 100.0, "paid_amount": 100.0, "billed_energy_kwh": 90.0, "due_date": "2025-02-10", "payment_date": "2025-02-08", "payment_status": "paid"},
    {"invoice_id": "F-1002-02", "uc_id": "UC-1002", "competencia": "2025-02", "billed_amount": 82.0, "paid_amount": 70.0, "billed_energy_kwh": 80.0, "due_date": "2025-03-10", "payment_date": "2025-03-05", "payment_status": "partial"},
    {"invoice_id": "F-1003-01", "uc_id": "UC-1003", "competencia": "2025-01", "billed_amount": 0.0, "paid_amount": 0.0, "billed_energy_kwh": 0.0, "due_date": "2025-02-10", "payment_date": None, "payment_status": "unknown"},
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
    {"uc_id": "UC-1004", "priority": 0.92, "reason": "Queda de leitura e medidor retirado", "potential_recoverable_energy_kwh": 45.0, "indicators": ["reading_gap", "meter_removed"]},
    {"uc_id": "UC-1002", "priority": 0.61, "reason": "Variação de consumo e geração distribuída", "potential_recoverable_energy_kwh": None, "indicators": ["consumption_variation", "distributed_generation"]},
]

# Controls: invoices total BRL 182 and observed payments BRL 170 (Jan 100,
# Feb invoice 82 with 70 paid, plus Jan zero); Jan–Feb
# measured energy is 407 kWh across the eight reading rows with known values.
