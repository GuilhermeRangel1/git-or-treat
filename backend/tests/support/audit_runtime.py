"""Backend ASGI em processo TCP separado para a escrita durável da prova."""

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx

TOKEN = "synthetic-audit-token-for-integration-00000000"


@contextmanager
def audit_runtime(database_url):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "error", "--no-access-log"],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "DATABASE_URL": database_url, "GENAI_AUDIT_WRITE_TOKEN": TOKEN,
             "ANALYTICS_SOURCE": "unavailable"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError("Backend de auditoria encerrou antes da prova.")
            try:
                response = httpx.get(base_url + "/api/v1/health", timeout=0.2)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        else:
            raise AssertionError("Backend de auditoria não ficou disponível.")
        yield base_url + "/api/v1/internal/genai-audit-events"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
