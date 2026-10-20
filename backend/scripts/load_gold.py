"""
Esqueleto do futuro carregador CSV da camada Gold.

O script ainda não lê nem insere registros e não implementa idempotência.

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
        print(f"[!] Diretório {data_dir} não encontrado; nenhuma carga foi realizada.")
        return

    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        print(f"[i] Nenhum CSV encontrado em {data_dir}; nenhuma carga foi realizada.")
        return

    print(f"[+] Arquivos encontrados: {[f.name for f in csv_files]}")

    # Inicializa sessão
    db = SessionLocal()

    try:
        for csv_path in csv_files:
            print(f"[*] Arquivo encontrado, mas não processado: {csv_path.name}")
        print("[i] Leitura e inserção ainda não implementadas; nenhum registro foi gravado.")
    except Exception as e:
        db.rollback()
        print(f"[✘] Erro durante a carga: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    load_gold_data()
