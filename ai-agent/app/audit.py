"""Adaptador de escrita durável pela API interna; sem credencial de banco na GenAI."""

import re
from dataclasses import asdict

import httpx

from app.ports.events import AuditUnavailable, CoreEvent


class BackendEventSink:
    durable = True

    def __init__(self, url: str, token: str, *, transport=None):
        endpoint = httpx.URL(url)
        if (endpoint.scheme not in {"http", "https"} or endpoint.userinfo
            or endpoint.query or endpoint.fragment
            or endpoint.path != "/api/v1/internal/genai-audit-events"
            or len(token) < 32):
            raise ValueError("Configuração de auditoria inválida.")
        self._url = url
        self._token = token
        self._transport = transport

    def record(self, event: CoreEvent) -> None:
        if event.correlation_id is None:
            raise AuditUnavailable("Evento sem correlação.")
        try:
            with httpx.Client(timeout=2, follow_redirects=False,
                              transport=self._transport, trust_env=False) as client:
                response = client.post(self._url, json=asdict(event), headers={
                    "Authorization": f"Bearer {self._token}",
                    "X-Correlation-ID": event.correlation_id,
                })
            payload = response.json()
            if (response.status_code != 201 or set(payload) != {"audit_reference"}
                or not isinstance(payload["audit_reference"], str)
                or re.fullmatch(r"[a-f0-9]{32}", payload["audit_reference"]) is None):
                raise ValueError("Confirmação inválida.")
        except (httpx.HTTPError, ValueError, TypeError):
            raise AuditUnavailable("Auditoria indisponível.") from None
