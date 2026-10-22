"""Bloqueios determinísticos anteriores à interpretação e a qualquer ferramenta.

As regras operam sobre o texto normalizado (NFKC, sem caracteres invisíveis, em
minúsculas, sem acentos e sem comentários SQL de bloco). Todas as janelas entre
termos são limitadas (`.{0,N}`) para evitar backtracking excessivo.
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from app.schemas.responses import FailureCode, map_failure


class SafetyRefusalCode(StrEnum):
    SECURITY_VIOLATION = "security_violation"
    OUT_OF_SCOPE = "out_of_scope"


OUT_OF_SCOPE_RULE = "out_of_scope"

# Caracteres de largura zero, hífen suave, controles bidirecionais e tags Unicode.
_INVISIBLE = re.compile(
    "[\u00ad\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\U000e0000-\U000e007f]"
)
_SQL_BLOCK_COMMENT = re.compile(r"/\*.{0,200}?\*/", re.DOTALL)


def _normalize(value: str) -> str:
    visible = _INVISIBLE.sub("", unicodedata.normalize("NFKC", value))
    decomposed = unicodedata.normalize("NFD", visible.casefold())
    text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _SQL_BLOCK_COMMENT.sub(" ", text)


# Alvos de armazenamento, em português, inglês e espanhol. "base" não conta em
# "com base no/na/em".
_STORAGE = (
    r"banco|bases?(?!\s+(?:n[oa]s?|em)\b)|tabelas?|registros?|sistema|cadastros?|"
    r"sql|query|script|arquivos?|tables?|tablas?|databases?|db|records?|rows?"
)
# Destruir ou zerar também vale para os dados e métricas do domínio.
_DESTRUCTIVE_TARGET = (
    rf"{_STORAGE}|tudo|dados|datos|all (?:the )?data|valores?|informacoes|faturamento|"
    r"consumo|medicoes|leituras|interrupcoes|atendimentos?"
)
# Entidades do domínio como objeto direto do verbo ("delete a UC-1001"). Não conta
# quando o pedido é sobre a visualização ("Exclua a UC 1001 da análise").
_ENTITY_OBJECT = (
    r"(?:\s+(?:o|a|os|as|um|uma|todos|todas|esse|essa|esses|essas|este|esta|the|all)){0,3}"
    r"\s+(?:ucs?(?:[\s-]?\d{1,12})?|clientes?|faturas?|medidor(?:es)?|ocorrencias?)\b"
    r"(?!.{0,30}\b(?:da|do|dos|das)\s+(?:comparacao|calculo|analise|grafico|filtro|"
    r"resultado|media|total|painel|tela|tabela comparativa)\b)"
)
# Complemento que transforma "altere os dados" em gravação.
_PERSIST = (
    r"salv(?:e|ar|ando)|grav(?:e|ar|ando)|permanentemente|definitivamente|"
    r"persist\w{0,6}|commit|na (?:fonte|origem)"
)
# Regras ou instruções qualificadas por um assunto ("regras de arredondamento")
# não são as instruções do agente; "do sistema" e "de segurança" continuam sendo.
_UNQUALIFIED = r"(?!\s+d[eoa]s?\s+(?!sistema|seguranca|acesso|privacidade)\w)"
_INSTRUCTIONS = (
    r"instrucoes|instrucao|instrucciones|instructions?|regras|reglas|rules|politicas|"
    r"policies|diretrizes|orientacoes|restricoes|directions|guidelines|prompt"
)
_PRIVILEGED_ROLE = r"administrador|admin|desenvolvedor|developer|root|superusuario|dba|hacker|dan"
_PERSON = (
    r"clientes?|titular(?:es)?|consumidor(?:es)?|pessoas?|moradore?s?|usuarios?|"
    r"responsave(?:l|is)|proprietarios?|dono|customers?|clients?|users?|owners?|holders?"
)


@dataclass(frozen=True, slots=True)
class SafetyRule:
    name: str
    pattern: re.Pattern[str]


def _rule(name: str, *alternatives: str) -> SafetyRule:
    return SafetyRule(name, re.compile("|".join(alternatives)))


# A ordem define qual nome `matched_rule` devolve quando mais de uma regra casa.
_SECURITY_RULES = (
    # Exige estrutura de comando; "select" ou "delete" soltos não bastam.
    _rule(
        "sql_command",
        r"\b(?:drop|truncate|alter|create)\s+(?:table|database|schema|view|index|user|role)\b",
        r"\bdelete\s+from\b|\binsert\s+into\b|\bmerge\s+into\b",
        r"\bupdate\s+[\w.\"]{1,64}\s+set\b",
        r"\bselect\s+(?:distinct\s+)?[\w.()*\"]{1,64}(?:\s*,\s*[\w.()*\"]{1,64}){0,30}"
        r"\s+from\s+\w",
        r"\b(?:grant|revoke)\s+\w{1,30}\s+on\b",
    ),
    # Comando de shell ou código executável, mesmo junto de uma pergunta válida.
    _rule(
        "code_execution",
        r"\brm\s+-{1,2}[a-z]{1,10}\b",
        r"\bos\.(?:system|popen|exec\w{0,4}|spawn\w{0,4}|remove|unlink)\s*\(",
        r"\bsubprocess\b|__import__|\b(?:eval|exec)\s*\(",
        r"\bimport\s+(?:os|sys|subprocess|shutil|socket|pty)\b",
        r"\bfrom\s+(?:os|sys|subprocess)\s+import\b",
        r"\b(?:powershell|pwsh)\b|\bcmd(?:\.exe)?\s+/c\b|\b(?:bash|sh|zsh)\s+-c\b",
        r"\b(?:curl|wget|sudo)\s",
        r"`\s{0,3}(?:rm|ls|cat|curl|wget|bash|sh|sudo|chmod|chown|python\d?|node|"
        r"powershell|cmd|whoami|echo|nc|kill|mv|cp|dd|mkfs)\b[^`\n]{0,80}`",
    ),
    # Truques de injeção de SQL; "--", "or" e "and" soltos em frases normais passam.
    _rule(
        "sql_injection_trick",
        r"['\"]\s{0,3}\b(?:or|and)\b[^=\n]{0,12}=",
        r"\bor\s+['\"]?(\w{1,10})['\"]?\s*=\s*['\"]?\1['\"]?(?!\w)",
        r"['\"]\s{0,3}\)?\s{0,3};\s{0,3}--",
        r"\bunion\s+(?:all\s+)?select\b",
    ),
    # Trecho longo em base64 ou hexadecimal (40+ caracteres sem espaço, com ao menos
    # um dígito) e pedidos para decodificar e executar. UC, protocolo e data são curtos.
    _rule(
        "encoded_payload",
        r"(?<![a-z0-9+/])(?=[a-z+/=]{0,60}\d)[a-z0-9+/]{40,}",
        r"\b(?:decodifiqu(?:e|em)|decodificar|descodifiqu(?:e|em)|decode|decodifica)\b.{0,30}"
        r"\b(?:execut\w{0,4}|run|rode|rodar|exec\w{0,4}|siga|follow|obedec\w{0,4})\b",
        r"\brot-?13\b",
    ),
    # Envio ou busca fora do serviço: URL, webhook, upload e envio por canal externo.
    _rule(
        "external_access",
        r"\b(?:https?|ftp)://|\bwww\.[a-z0-9-]{1,63}\.",
        r"(?<![@\w.-])[a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63}){0,3}"
        r"\.(?:com|net|org|io|xyz|ru|info|dev|app|br)\b(?![.@])",
        r"\bwebhooks?\b|\bupload\b",
        r"\b(?:envi(?:e|em|ar)|mand(?:e|em|ar)|encaminh(?:e|em|ar)|dispar(?:e|em|ar)|"
        r"send|forward|post|envia|manda)\b.{0,40}"
        r"\b(?:e-?mails?|correo|url|link|endpoint|servidor|server|whatsapp|slack|telegram|"
        r"para fora)\b",
    ),
    # "Chave" só conta com contexto de API, acesso ou segredo; "chave primária" passa.
    _rule(
        "secrets",
        r"\b(?:credenciais?|senhas?|passwords?|contrasenas?|tokens?|segredos?|secrets?|"
        r"api[\s_-]?keys?|access[\s_-]?keys?|private[\s_-]?keys?|"
        r"(?:chaves?|claves?) (?:d[ea] (?:la )?)?(?:api|acesso|acceso|secretas?|privadas?|"
        r"autenticacao)|"
        r"variave(?:l|is) de ambiente|environment variables?|env vars?)\b",
        r"(?:^|[^\w.])\.env\b",
        r"(?:api_?key|secret_?key|access_?key)s?\b|_(?:token|secret|password)\b",
    ),
    _rule(
        "injection_ignore",
        r"\b(?:ignor(?:e|a|em|ar|ando)|desconsider(?:e|a|em|ar|ando)|"
        r"esquec(?:a|e|am|er|endo)|desprez(?:e|a|em|ar|ando)|olvid(?:a|e|en|ar)|"
        r"disregard|forget|override|"
        r"bypass|burl(?:e|a|ar)|contorn(?:e|a|ar))\b.{0,40}"
        rf"\b(?:{_INSTRUCTIONS})\b{_UNQUALIFIED}",
        r"\b(?:ignor\w{0,4}|desconsider\w{0,4}|esquec\w{0,4}|disregard|forget)\b.{0,15}"
        r"\b(?:tudo|everything)\s+(?:acima|above|antes)\b",
    ),
    _rule(
        "injection_role",
        r"\ba partir de agora\b.{0,20}\b(?:voce|seja|aja|atue|finja|responda)\b",
        r"\b(?:from now on|you are now|pretend (?:to be|you are)|do anything now)\b",
        r"\b(?:finja|fingir) (?:que (?:voce )?(?:e|seja)|ser)\b",
        rf"\bvoce (?:agora )?(?:e|sera|vai ser) (?:um|uma|o|a) (?:{_PRIVILEGED_ROLE})\b",
        rf"\b(?:aja|atue|age|comporte-se|act)\s+(?:como|as)\s+(?:(?:um|uma|o|a|an?)\s+)?"
        rf"(?:{_PRIVILEGED_ROLE})\b",
        # "sem limites" só é troca de papel quando dirigido ao agente.
        r"\b(?:voce|responda|aja|atue|seja|opere|funcione|you|answer|act)\b.{0,30}"
        r"\bsem (?:limites|restricoes|regras|filtros|censura)\b(?!\s+d[eoa]s?\s+\w)",
        r"\b(?:modo|mode) (?:sem (?:filtros|limites|restricoes|regras|censura)|depuracao|"
        r"debug|desenvolvedor|developer|administrador|admin|deus|god|irrestrito)\b",
        r"\b(?:debug|developer|god|dan) mode\b",
        r"\bjailbreak\b",
    ),
    # Marcadores de papel e tags de contexto forjados.
    _rule(
        "injection_markup",
        r"\b(?:system|assistant|developer)\s*:",
        r"(?:^|\n)\s*(?:sistema|assistente|desenvolvedor)\s*:",
        r"</?\s*(?:contexto|context|system|sistema|instrucoes|instructions|prompt|"
        r"user|usuario|assistant|assistente|developer)\b[^<>]{0,40}>",
        r"<\|[a-z_]{1,30}\|>|\[/?(?:inst|sys|system)\]|<<\s*/?sys\s*>>",
    ),
    _rule(
        "injection_reveal_prompt",
        r"\b(?:prompt (?:do|de) sistema|system prompt|(?:seu|teu|your) prompt|"
        r"instrucoes (?:do sistema|internas|ocultas|iniciais)|mensagem do sistema|"
        r"regras internas)\b",
        r"\b(?:suas|tuas|your) (?:instrucoes|instructions|diretrizes|regras|rules)\b",
        r"\b(?:revel(?:e|ar)|mostr(?:e|ar)|list(?:e|ar)|repit(?:a|ir)|exib(?:a|ir)|"
        r"imprim(?:a|ir)|diga|informe|reveal|show|print|repeat|tell me)\b.{0,20}"
        rf"\b(?:instrucoes|instructions|diretrizes|guidelines|regras|rules)\b{_UNQUALIFIED}",
        r"\b(?:repit(?:a|ir)|repeat|imprim(?:a|ir)|print|mostr(?:e|ar)|show)\b.{0,15}"
        r"\b(?:tudo|everything|o texto|the text)\s+(?:acima|above)\b",
        # Pedidos indiretos: prompt, configuração, contexto ou o que veio antes.
        r"\bprompts?\b",
        r"\b(?:seu|teu|your) contexto\b|\b(?:your|the) context\b|"
        r"\bcontexto (?:inicial|completo|do sistema|da conversa)\b",
        r"\b(?:suas|tuas|your) (?:configuracoes|configuracao|settings|configuration)\b",
        r"\bcomo voce (?:foi|esta) (?:configurad[oa]|programad[oa]|instruid[oa])\b|"
        r"\bhow (?:were|are) you (?:configured|programmed|instructed|set up)\b",
        r"\b(?:o que|what)\b.{0,20}\b(?:voce recebeu|you received|te (?:enviaram|passaram))\b|"
        r"\b(?:antes desta|antes dessa|before this) (?:mensagem|message)\b",
    ),
    _rule(
        "write_destructive",
        r"\b(?:apag(?:ue|uem|ar)|delet(?:e|em|ar)|zer(?:e|em|a|ar)|trunc(?:a|ar)|"
        r"trunqu(?:e|em)|truncate|destru(?:a|ir)|sobrescrev(?:a|er)|drop(?:e|em|ar)?|"
        r"borr(?:a|e|en|ar)|erase|wipe|overwrite|destroy)\b"
        rf"(?:.{{0,50}}\b(?:{_DESTRUCTIVE_TARGET})\b|{_ENTITY_OBJECT})",
    ),
    # Verbos que também têm uso analítico ("remova o filtro") exigem alvo de armazenamento.
    _rule(
        "write_remove",
        r"\b(?:remov(?:a|er)|remove|exclu(?:a|ir)|elimin(?:a|e|ar)|execut(?:e|ar)|"
        r"limp(?:e|em|ar)|apag(?:a|am)|renome(?:ie|iem|ar)|rename)\b"
        rf"(?:.{{0,50}}\b(?:{_STORAGE}|tudo|colunas?)\b|{_ENTITY_OBJECT})",
    ),
    # "Altere a análise com os dados de 2024" e "Update the chart with 2024 data"
    # passam; dados só contam com gravação.
    _rule(
        "write_alter",
        r"\b(?:alter(?:e|ar)|atualiz(?:e|ar)|modifiqu(?:e)|modificar|edit(?:e|ar)|"
        r"substitu(?:a|ir)|troqu(?:e)|trocar|corrij(?:a)|corrigir|update|alter|modify|"
        r"change)\b.{0,50}"
        rf"(?:\b(?:{_STORAGE})\b|\b(?:dados|valores?)\b.{{0,40}}\b(?:{_PERSIST})\b)",
    ),
    _rule(
        "write_insert",
        r"\b(?:insir(?:a)|inserir|insert|grav(?:e|ar)|salv(?:e|ar)|persist(?:a|ir)|"
        r"cadastr(?:e|em|ar)|registr(?:e|em|ar))\b.{0,50}"
        rf"\b(?:{_STORAGE}|dados|valores?|novos?|novas?|clientes?|consumidor(?:es)?|"
        r"usuarios?)\b",
    ),
    # "Crie uma tabela comparativa" e "Adicione o filtro" passam.
    _rule(
        "write_create",
        r"\b(?:cri(?:e|ar)|adicion(?:e|ar)|create|add)\b.{0,30}"
        r"\b(?:registros?|cadastros?|records?|rows?|banco|base de dados|database|"
        r"(?:um|uma|novos?|novas?|a|new) (?:clientes?|usuarios?|consumidor(?:es)?|ucs?|"
        r"customers?|users?))\b",
    ),
    # "Escreva" só é escrita quando aponta para onde gravar.
    _rule(
        "write_to_storage",
        r"\bescrev(?:a|er)\b.{0,40}\b(?:em|n[oa]s?|para)\s+"
        rf"(?:(?:o|a|os|as|um|uma)\s+)?(?:{_STORAGE})\b",
    ),
    _rule(
        "data_export",
        r"\bdump\b",
        r"\b(?:backup|export(?:e|ar)|baix(?:e|ar)|extra(?:ia|ir)|copi(?:e|ar))\b.{0,40}"
        rf"\b(?:{_STORAGE}|tudo|todos os (?:dados|registros|clientes)|dados d[oa]s? clientes?)\b",
    ),
    # Número sem máscara só conta como documento com a palavra cpf/cnpj.
    _rule(
        "pii_document",
        r"\b(?:cpfs?|cnpjs?)\b",
        r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
        r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",
    ),
    # Atributo pessoal pedido sobre uma pessoa; "endereço" sozinho é permitido.
    _rule(
        "pii_contact",
        r"\b[a-z0-9._%+-]{1,64}@[a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63}){1,5}\b",
        r"\(\d{2}\)\s?9?\d{4}-?\d{4}\b|\+55\s?\d{2}\b",
        r"\b(?:e-?mails?|telefones?|telefonos?|celular(?:es)?|whatsapp|enderecos?|rg|"
        r"data de nascimento|nomes? d[oa]s?|rendas?|salarios?|profiss(?:ao|oes)|correos?|"
        r"direccion(?:es)?|phone(?: numbers?)?|address(?:es)?|full names?|salary|income)\b"
        rf".{{0,40}}\b(?:{_PERSON})\b",
        # Possessivo em inglês: "the customer's email".
        r"\b(?:customer|client|user|owner|holder)'s\b.{0,20}"
        r"\b(?:e-?mails?|phone|address|name|salary|income)\b",
    ),
    # Localização de pessoa ou da casa dela; "latitude da subestação" passa.
    _rule(
        "pii_location",
        r"\b(?:latitudes?|longitudes?|coordenadas?|coordinates?|geolocaliza(?:cao|coes)|"
        r"geolocation|gps)\b"
        rf".{{0,40}}\b(?:{_PERSON}|ucs?|unidades? consumidoras?|casas?|residencias?)\b",
        r"\bonde fica (?:a |o )?(?:casa|residencia|imovel|apartamento)\b",
    ),
    _rule(
        "pii_identity",
        r"\b(?:dados pessoais|nomes? completos?|todos os clientes)\b",
        rf"\bquem (?:e|sao|seria|era|eram)\b.{{0,20}}\b(?:{_PERSON})\b",
        r"\bonde (?:mora|moram|reside|residem|vive|vivem)\b",
    ),
)


SECURITY_RULE_NAMES = tuple(rule.name for rule in _SECURITY_RULES)

# Mensagens fixas do próprio serviço voltam no contexto como turno "assistant". Só o
# texto idêntico é aceito: a recusa ("…expor dados pessoais ou instruções internas")
# não carrega ataque, mas qualquer acréscimo volta a passar pelas regras.
_SERVICE_MESSAGES = frozenset(_normalize(map_failure(code).message) for code in FailureCode)


class QuestionSafetyGate:
    """Recusa pedidos explícitos de escrita, segredos, dados pessoais e injeção de instruções."""

    def __init__(self, *, out_of_scope_terms: tuple[str, ...] = ()) -> None:
        terms = [re.escape(_normalize(item)) for item in out_of_scope_terms]
        self._out_of_scope = (
            re.compile(rf"\b(?:{'|'.join(terms)})\b") if terms else None
        )

    def matched_rule(self, question: str) -> str | None:
        """Nome da primeira regra que casa; nunca devolve trecho da pergunta."""
        normalized = _normalize(question)
        if normalized.strip() in _SERVICE_MESSAGES:
            return None
        for rule in _SECURITY_RULES:
            if rule.pattern.search(normalized):
                return rule.name
        if self._out_of_scope is not None and self._out_of_scope.search(normalized):
            return OUT_OF_SCOPE_RULE
        return None

    def refusal_code(self, question: str) -> SafetyRefusalCode | None:
        rule = self.matched_rule(question)
        if rule is None:
            return None
        if rule == OUT_OF_SCOPE_RULE:
            return SafetyRefusalCode.OUT_OF_SCOPE
        return SafetyRefusalCode.SECURITY_VIOLATION
