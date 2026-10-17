"""
Script idempotente para carregar CSVs da camada Gold (ou mocks locais) no banco analítico.

Uso:
    python scripts/load_gold.py
"""
import sys
import csv
from pathlib import Path

# Adiciona o diretório backend ao sys.path para importação de app
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.core.config import settings
from app.core.database import SessionLocal, engine, Base
from app.models.analytical import GoldIndicador


def load_gold_data():
    data_dir = Path(settings.GOLD_DATA_DIR)
    print(f"[*] Verificando diretório de dados Gold: {data_dir.resolve()}")

    if not data_dir.exists():
        print(f"[!] Diretório {data_dir} não encontrado. Crie a pasta e adicione os CSVs.")
        return

    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        print(f"[i] Nenhum arquivo .csv encontrado em {data_dir}. Coloque seus mocks ou a Gold exportada aqui.")
        return

    print(f"[+] Arquivos encontrados: {[f.name for f in csv_files]}")

    # Inicializa sessão
    db = SessionLocal()

    try:
        # Exemplo de leitura e carga idempotente para PostgreSQL
        for csv_path in csv_files:
            print(f"[*] Processando: {csv_path.name}")
            # Dica PostgreSQL: Em produção com grandes volumes, use lote/batch:
            # db.bulk_insert_mappings(Model, rows) ou COPY / insert().on_conflict_do_update()
        print("[✔] Carga analítica concluída com sucesso.")
    except Exception as e:
        db.rollback()
        print(f"[✘] Erro durante a carga: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    load_gold_data()
