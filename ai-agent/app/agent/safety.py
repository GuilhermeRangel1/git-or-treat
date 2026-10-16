"""Bloqueios determinísticos anteriores à interpretação e a qualquer ferramenta."""

import re
import unicodedata


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


class QuestionSafetyGate:
    """Recusa pedidos explícitos de escrita, dados pessoais e injeção de instruções."""

    _INJECTION = re.compile(
        r"\b(?:ignore|desconsidere|ignore todas|desconsidere todas)\b.{0,40}"
        r"\b(?:instrucoes|regras|politicas)\b"
    )
    _WRITE_WITH_TARGET = re.compile(
        r"\b(?:alter(?:e|ar)|atualiz(?:e|ar)|apag(?:ue|ar)|delet(?:e|ar)|"
        r"insir(?:a|ir)|grav(?:e|ar)|escrev(?:a|er)|execut(?:e|ar))\b.{0,50}"
        r"\b(?:banco|dados|registro|tabela|sql|sistema)\b"
    )
    _SENSITIVE = re.compile(
        r"\b(?:cpf|credenciais?|senhas?|tokens?|dados pessoais|"
        r"todos os clientes|nomes completos|revele segredos?)\b"
    )
    _OUT_OF_SCOPE = re.compile(r"\b(?:capital|clima|previsao do tempo|futebol|cotacao)\b")

    def refusal_reason(self, question: str) -> str | None:
        normalized = _normalize(question)
        if (
            self._INJECTION.search(normalized)
            or self._WRITE_WITH_TARGET.search(normalized)
            or self._SENSITIVE.search(normalized)
            or self._OUT_OF_SCOPE.search(normalized)
        ):
            return "Não posso executar alterações nem expor dados pessoais ou instruções internas."
        return None
