"""Base sintética do Panorama (WEB-01).

Os registros reproduzem os controles declarados no PRD e no protótipo Figma
(Receita Faturada R$ 76.500 em 2024-04 contra R$ 80.000 em 2024-03). São valores
de demonstração: não constituem diagnóstico da V-Energy nem resultado da Gold.
"""

DATA_VERSION = "Lote Gold 2024.04-sintetico-v1"
UPDATED_AT = "2024-04-30T18:00:00Z"
DATA_LIMITATION = "Base sintética de demonstração alinhada aos controles do PRD WEB-01; não representa a Gold."

# Grão: competência x município x classe.
# 2024-04 (Total: Faturado R$ 76.500 | Pago R$ 74.200 | Consumo 90.000 kWh | Faturado 90.000 kWh | UCs 1.248)
# 2024-03 (Total: Faturado R$ 80.000 | Pago R$ 78.500 | Consumo 100.000 kWh | Faturado 100.000 kWh | UCs 1.250)
# 2024-05 é a competência em aberto, com faturamento ainda incompleto.
PANORAMA_RECORDS = [
    {"competencia": "2024-04", "municipio": "Recife", "classe": "Residencial", "receita_faturada": 21000.0, "receita_paga": 20300.0, "energia_consumida_kwh": 25000.0, "energia_faturada_kwh": 25000.0, "ucs_ativas": 520, "dec_horas": 1.20, "fec_vezes": 0.80},
    {"competencia": "2024-04", "municipio": "Recife", "classe": "Comercial", "receita_faturada": 12000.0, "receita_paga": 11800.0, "energia_consumida_kwh": 14000.0, "energia_faturada_kwh": 14000.0, "ucs_ativas": 80, "dec_horas": 1.15, "fec_vezes": 0.75},
    {"competencia": "2024-04", "municipio": "Recife", "classe": "Industrial", "receita_faturada": 5000.0, "receita_paga": 5000.0, "energia_consumida_kwh": 6000.0, "energia_faturada_kwh": 6000.0, "ucs_ativas": 20, "dec_horas": 1.00, "fec_vezes": 0.60},
    {"competencia": "2024-04", "municipio": "Olinda", "classe": "Residencial", "receita_faturada": 12500.0, "receita_paga": 12100.0, "energia_consumida_kwh": 14500.0, "energia_faturada_kwh": 14500.0, "ucs_ativas": 310, "dec_horas": 1.45, "fec_vezes": 0.95},
    {"competencia": "2024-04", "municipio": "Olinda", "classe": "Comercial", "receita_faturada": 7000.0, "receita_paga": 6900.0, "energia_consumida_kwh": 8500.0, "energia_faturada_kwh": 8500.0, "ucs_ativas": 50, "dec_horas": 1.40, "fec_vezes": 0.90},
    {"competencia": "2024-04", "municipio": "Olinda", "classe": "Industrial", "receita_faturada": 3000.0, "receita_paga": 3000.0, "energia_consumida_kwh": 3500.0, "energia_faturada_kwh": 3500.0, "ucs_ativas": 10, "dec_horas": 1.30, "fec_vezes": 0.85},
    {"competencia": "2024-04", "municipio": "Jaboatão dos Guararapes", "classe": "Residencial", "receita_faturada": 8500.0, "receita_paga": 8200.0, "energia_consumida_kwh": 10000.0, "energia_faturada_kwh": 10000.0, "ucs_ativas": 220, "dec_horas": 1.50, "fec_vezes": 0.95},
    {"competencia": "2024-04", "municipio": "Jaboatão dos Guararapes", "classe": "Comercial", "receita_faturada": 5500.0, "receita_paga": 5400.0, "energia_consumida_kwh": 6000.0, "energia_faturada_kwh": 6000.0, "ucs_ativas": 30, "dec_horas": 1.42, "fec_vezes": 0.92},
    {"competencia": "2024-04", "municipio": "Jaboatão dos Guararapes", "classe": "Industrial", "receita_faturada": 2000.0, "receita_paga": 1500.0, "energia_consumida_kwh": 2500.0, "energia_faturada_kwh": 2500.0, "ucs_ativas": 8, "dec_horas": 1.38, "fec_vezes": 0.90},
    {"competencia": "2024-03", "municipio": "Recife", "classe": "Residencial", "receita_faturada": 22800.0, "receita_paga": 22300.0, "energia_consumida_kwh": 29000.0, "energia_faturada_kwh": 29000.0, "ucs_ativas": 522, "dec_horas": 1.30, "fec_vezes": 0.88},
    {"competencia": "2024-03", "municipio": "Recife", "classe": "Comercial", "receita_faturada": 12000.0, "receita_paga": 11900.0, "energia_consumida_kwh": 15000.0, "energia_faturada_kwh": 15000.0, "ucs_ativas": 80, "dec_horas": 1.25, "fec_vezes": 0.80},
    {"competencia": "2024-03", "municipio": "Recife", "classe": "Industrial", "receita_faturada": 5000.0, "receita_paga": 5000.0, "energia_consumida_kwh": 6000.0, "energia_faturada_kwh": 6000.0, "ucs_ativas": 20, "dec_horas": 1.10, "fec_vezes": 0.65},
    {"competencia": "2024-03", "municipio": "Olinda", "classe": "Residencial", "receita_faturada": 13400.0, "receita_paga": 13100.0, "energia_consumida_kwh": 17000.0, "energia_faturada_kwh": 17000.0, "ucs_ativas": 310, "dec_horas": 1.55, "fec_vezes": 1.05},
    {"competencia": "2024-03", "municipio": "Olinda", "classe": "Comercial", "receita_faturada": 7000.0, "receita_paga": 6900.0, "energia_consumida_kwh": 9000.0, "energia_faturada_kwh": 9000.0, "ucs_ativas": 50, "dec_horas": 1.48, "fec_vezes": 0.98},
    {"competencia": "2024-03", "municipio": "Olinda", "classe": "Industrial", "receita_faturada": 3000.0, "receita_paga": 3000.0, "energia_consumida_kwh": 3500.0, "energia_faturada_kwh": 3500.0, "ucs_ativas": 10, "dec_horas": 1.40, "fec_vezes": 0.90},
    {"competencia": "2024-03", "municipio": "Jaboatão dos Guararapes", "classe": "Residencial", "receita_faturada": 9300.0, "receita_paga": 8900.0, "energia_consumida_kwh": 11000.0, "energia_faturada_kwh": 11000.0, "ucs_ativas": 220, "dec_horas": 1.60, "fec_vezes": 1.05},
    {"competencia": "2024-03", "municipio": "Jaboatão dos Guararapes", "classe": "Comercial", "receita_faturada": 5500.0, "receita_paga": 5400.0, "energia_consumida_kwh": 6500.0, "energia_faturada_kwh": 6500.0, "ucs_ativas": 30, "dec_horas": 1.50, "fec_vezes": 1.00},
    {"competencia": "2024-03", "municipio": "Jaboatão dos Guararapes", "classe": "Industrial", "receita_faturada": 2000.0, "receita_paga": 2000.0, "energia_consumida_kwh": 3000.0, "energia_faturada_kwh": 3000.0, "ucs_ativas": 8, "dec_horas": 1.45, "fec_vezes": 0.95},
    {"competencia": "2024-05", "municipio": "Recife", "classe": "Residencial", "receita_faturada": 14000.0, "receita_paga": 8000.0, "energia_consumida_kwh": 16000.0, "energia_faturada_kwh": 16000.0, "ucs_ativas": 520, "dec_horas": 0.80, "fec_vezes": 0.40},
    {"competencia": "2024-05", "municipio": "Recife", "classe": "Comercial", "receita_faturada": 8000.0, "receita_paga": 5000.0, "energia_consumida_kwh": 9000.0, "energia_faturada_kwh": 9000.0, "ucs_ativas": 80, "dec_horas": 0.70, "fec_vezes": 0.35},
    {"competencia": "2024-05", "municipio": "Olinda", "classe": "Residencial", "receita_faturada": 9000.0, "receita_paga": 4500.0, "energia_consumida_kwh": 10000.0, "energia_faturada_kwh": 10000.0, "ucs_ativas": 310, "dec_horas": 0.90, "fec_vezes": 0.45},
]

# Competência em aberto: o faturamento ainda não consolidou o ciclo.
INCOMPLETE_PERIOD = "2024-05"

# Série histórica exibida no Panorama.
HISTORY_PERIODS = ("2024-03", "2024-04")
HISTORY_LABELS = {"2024-03": "Mar/24", "2024-04": "Abr/24"}
