"""Regras determinísticas para preservar o domínio nas entradas analíticas."""

import re
import unicodedata

OUT_OF_DOMAIN_MESSAGE = (
    "Essa pergunta está fora do domínio de energia elétrica atendido pelo assistente."
)

_OUTSIDE_DOMAIN = re.compile(
    r"\b(?:receita|faturamento|vendas?)\s+(?:de|do|da)\s+"
    r"(?:energia(?: eletrica)?\s+(?:e|ou)\s+(?:de|do|da)\s+)?"
    r"(?:miojo|macarrao instantaneo|bolo|lasanha|pizza|hamburguer)\b"
    r"|\b(?:receita culinaria|previsao do tempo|placar d[eo] jogo)\b"
)


def is_explicitly_outside_energy_domain(question: str) -> bool:
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return _OUTSIDE_DOMAIN.search(normalized) is not None
