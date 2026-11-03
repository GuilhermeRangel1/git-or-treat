"""Corpus interno versionado, derivado das definições aprovadas do FAQ Gold v2."""

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from app.ports.documentation import DocumentChunk
from app.schemas.access import AccessContext

CORPUS = Path(__file__).resolve().parents[1] / "corpora/indicators.json"


class IndicatorDocumentation:
    def __init__(self, path: Path = CORPUS):
        self.path = path

    def authorized_chunks(
        self,
        access: AccessContext,
        today: date,
    ) -> tuple[DocumentChunk, ...]:
        if (
            access.profile_id != "v-energy-grid-360-gold"
            or access.source_id != "gold.local"
            or "read" not in access.allowed_operations
        ):
            return ()
        # Sem cache derivado: retirada/versão/permissão passam a valer na próxima leitura.
        if self.path.stat().st_size > 65536:
            raise ValueError("corpus acima do limite de bytes")
        corpus = json.loads(self.path.read_text(encoding="utf-8"))
        if corpus["catalogVersion"] != "gold-catalog-v2":
            return ()
        entries = corpus["entries"]
        version = hashlib.sha256(
            json.dumps(
                entries,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()[:12]
        if corpus["version"] != version:
            raise ValueError("versão documental divergente do conteúdo")
        if len(entries) > 24:
            raise ValueError("corpus acima do limite permitido")
        identities = Counter(entry["id"] for entry in entries)
        if any(count != 1 for count in identities.values()):
            raise ValueError("identidade documental em conflito")
        chunks = []
        for entry in entries:
            if (
                identities[entry["id"]] != 1
                or entry["status"] != "active"
                or "assistente" not in entry["screens"]
                or entry["audience"] != "Pessoas usuárias do portal interno"
                or date.fromisoformat(entry["validFrom"]) > today
                or entry["validUntil"] is not None
                and date.fromisoformat(entry["validUntil"]) < today
            ):
                continue
            metrics = frozenset(item["metricId"] for item in entry["definitions"])
            if not metrics or not metrics <= access.allowed_metric_ids:
                continue
            text = "\n".join(f"{item['label']}: {item['text']}" for item in entry["definitions"])
            if len(text.encode("utf-8")) > 4096:
                raise ValueError("trecho acima do limite permitido")
            chunks.append(
                DocumentChunk(
                    id=entry["id"],
                    title=corpus["source"],
                    section=entry["question"],
                    version=corpus["version"],
                    owner=entry["owner"],
                    text=text,
                    metric_ids=metrics,
                    keywords=tuple(entry["keywords"]),
                )
            )
        return tuple(chunks)
