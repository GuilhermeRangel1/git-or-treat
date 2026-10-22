"""Bloqueios determinísticos anteriores à interpretação e a qualquer ferramenta.

As regras operam sobre o texto normalizado (NFKC, com letras cirílicas e gregas
parecidas trocadas pelas latinas, em minúsculas, sem acentos, sem comentários SQL de
bloco, com cada sequência de espaços, tabs e quebras de linha reduzida a um
separador e com letras isoladas em sequência juntadas). Os caracteres invisíveis são
avaliados de duas formas, removidos e trocados por espaço, e a pergunta é recusada
se qualquer das duas versões casar com uma regra. Quase
todas as regras leem o texto em uma linha só, então as janelas entre termos e os
espaços dos padrões atravessam quebras de linha; só os marcadores de papel leem o
texto com as quebras mantidas. Todas as janelas entre termos são limitadas
(`.{0,N}`) para evitar backtracking excessivo. O gate é uma camada heurística: a
barreira real são o planejador, a política de leitura, o modelo sem números livres
e a camada SQL somente leitura.
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
# Lista curta e explícita de letras cirílicas e gregas que imitam latinas.
_HOMOGLYPHS = str.maketrans(
    {
        chr(code): latin
        for code, latin in (
            # Cirílico: а е о р с х у і ј ѕ ԁ e maiúsculas.
            (0x0430, "a"), (0x0435, "e"), (0x043E, "o"), (0x0440, "p"), (0x0441, "c"),
            (0x0445, "x"), (0x0443, "y"), (0x0456, "i"), (0x0458, "j"), (0x0455, "s"),
            (0x0501, "d"), (0x0410, "A"), (0x0415, "E"), (0x041E, "O"), (0x0420, "P"),
            (0x0421, "C"), (0x0425, "X"), (0x0423, "Y"), (0x0406, "I"), (0x0408, "J"),
            (0x0405, "S"), (0x0500, "D"),
            # Latim "g" de script (ɡ).
            (0x0261, "g"),
            # Grego: ο ν α ε ρ τ υ χ e maiúsculas.
            (0x03BF, "o"), (0x03BD, "v"), (0x03B1, "a"), (0x03B5, "e"), (0x03C1, "p"),
            (0x03C4, "t"), (0x03C5, "u"), (0x03C7, "x"), (0x039F, "O"), (0x039D, "N"),
            (0x0391, "A"), (0x0395, "E"), (0x03A1, "P"), (0x03A4, "T"), (0x03A5, "Y"),
            (0x03A7, "X"),
        )
    }
)
# Quatro ou mais letras isoladas separadas por um espaço (ou tab, ou quebra de linha),
# ponto ou hífen ("d r o p", "d.r.o.p"). Três letras ("a b c") e listas como "A, B e
# C" ficam como estão. Roda antes de reduzir os espaços, para que mais de um espaço
# continue separando palavras ("D R O P   T A B L E").
_SPACED_LETTERS = re.compile(r"(?<![a-z0-9])[a-z](?:[\s.-][a-z]){3,}(?![a-z0-9])")
_WHITESPACE = re.compile(r"\s+")
# Os mesmos separadores de linha de `str.splitlines`.
_LINE_BREAKS = frozenset("\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029")


@dataclass(frozen=True, slots=True)
class _NormalizedText:
    # Em uma linha só, para quase todas as regras.
    flat: str
    # Com as quebras de linha mantidas, para marcadores no início de linha.
    lines: str


def _collapse_whitespace(match: re.Match[str]) -> str:
    return "\n" if _LINE_BREAKS.intersection(match.group()) else " "


def _normalize(value: str, *, invisible: str = "") -> _NormalizedText:
    visible = _INVISIBLE.sub(invisible, unicodedata.normalize("NFKC", value))
    latin = visible.translate(_HOMOGLYPHS)
    decomposed = unicodedata.normalize("NFD", latin.casefold())
    text = "".join(char for char in decomposed if not unicodedata.combining(char))
    text = _SQL_BLOCK_COMMENT.sub(" ", text)
    text = _SPACED_LETTERS.sub(lambda match: re.sub(r"[\s.-]", "", match.group()), text)
    text = _WHITESPACE.sub(_collapse_whitespace, text)
    return _NormalizedText(flat=text.replace("\n", " "), lines=text)


# "Sistema" só é armazenamento quando não é a rede ("sistema elétrico").
_SYSTEM = (
    r"sistema(?!\s+(?:eletrico|de distribuicao|de transmissao|de energia|de medicao|"
    r"interligado|de potencia)\b)"
)
# Alvos de armazenamento, em português, inglês e espanhol. "base" não conta em
# "com base no/na/em".
_STORAGE = (
    rf"banco|bases?(?!\s+(?:n[oa]s?|em)\b)|tabelas?|registros?|{_SYSTEM}|cadastros?|"
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
# Regras ou instruções sobre um assunto analítico ("regras de arredondamento") não
# são as instruções do agente. Qualquer outro qualificador ("de conduta", "do
# sistema", "de segurança", "de negócio") continua recusado.
_ANALYTIC_SUBJECT = (
    r"arredondamento|calculo|agregacao|agrupamento|ordenacao|filtros?|periodos?|"
    r"conversao|unidades?|faturamento|cobranca|tarifas?|competencia|datas?|"
    r"formatacao de numeros?|fuso(?: horario)?"
)
_UNQUALIFIED = rf"(?!\s+d[eoa]s?\s+(?:{_ANALYTIC_SUBJECT})\b)"
_INSTRUCTIONS = (
    r"instrucoes|instrucao|instrucciones|instructions?|regras|reglas|rules|politicas|"
    r"policies|diretrizes|orientacoes|restricoes|directions|guidelines|prompt"
)
_PRIVILEGED_ROLE = r"administrador|admin|desenvolvedor|developer|root|superusuario|dba|hacker|dan"
_PERSON = (
    r"clientes?|titular(?:es)?|consumidor(?:es)?|pessoas?|moradore?s?|usuarios?|"
    r"responsave(?:l|is)|proprietarios?|dono|customers?|clients?|users?|owners?|holders?"
)
_RANKING = r"maior|menor|mais|menos|maiores|menores"


@dataclass(frozen=True, slots=True)
class SafetyRule:
    name: str
    pattern: re.Pattern[str]
    reads_lines: bool = False

    def matches(self, text: _NormalizedText) -> bool:
        return self.pattern.search(text.lines if self.reads_lines else text.flat) is not None


def _rule(name: str, *alternatives: str, reads_lines: bool = False) -> SafetyRule:
    # DOTALL deixa as janelas `.{0,N}` atravessarem quebras de linha também no texto
    # com as quebras mantidas.
    return SafetyRule(name, re.compile("|".join(alternatives), re.DOTALL), reads_lines)


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
        r"powershell|cmd|whoami|echo|nc|kill|mv|cp|dd|mkfs)\b[^`]{0,80}`",
    ),
    # Truques de injeção de SQL; "--", "or" e "and" soltos em frases normais passam.
    _rule(
        "sql_injection_trick",
        r"['\"]\s{0,3}\b(?:or|and)\b[^=]{0,12}=",
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
    # Marcadores de papel e tags de contexto forjados. Lê o texto com as quebras de
    # linha mantidas: "sistema:" só é marcador no início de uma linha.
    _rule(
        "injection_markup",
        r"\b(?:system|assistant|developer)\s*:",
        r"(?:^|\n)\s*(?:sistema|assistente|desenvolvedor)\s*:",
        r"</?\s*(?:contexto|context|system|sistema|instrucoes|instructions|prompt|"
        r"user|usuario|assistant|assistente|developer)\b[^<>]{0,40}>",
        r"<\|[a-z_]{1,30}\|>|\[/?(?:inst|sys|system)\]|<<\s*/?sys\s*>>",
        reads_lines=True,
    ),
    _rule(
        "injection_reveal_prompt",
        r"\b(?:prompt (?:do|de) sistema|system prompt|(?:seu|teu|your) prompt|"
        r"instrucoes (?:do sistema|internas|ocultas|iniciais)|mensagem do sistema|"
        r"regras internas)\b",
        r"\b(?:suas|tuas|your) (?:instrucoes|instructions|diretrizes|regras|rules)\b"
        rf"{_UNQUALIFIED}",
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
        r"\b(?:apag(?:ue|uem|ar|asse|assem)|delet(?:e|em|ar|asse|assem)|"
        r"zer(?:e|em|a|ar|asse|assem)|trunc(?:a|ar)|"
        r"trunqu(?:e|em)|truncate|destru(?:a|ir)|sobrescrev(?:a|er)|drop(?:e|em|ar)?|"
        r"borr(?:a|e|en|ar)|erase|wipe|overwrite|destroy)\b"
        rf"(?:.{{0,50}}\b(?:{_DESTRUCTIVE_TARGET})\b|{_ENTITY_OBJECT})",
    ),
    # Verbos que também têm uso analítico ("remova o filtro") exigem alvo de armazenamento.
    _rule(
        "write_remove",
        r"\b(?:remov(?:a|am|er|esse|essem)|remove|exclu(?:a|ir|isse|issem)|elimin(?:a|e|ar)|"
        r"execut(?:e|ar)|limp(?:e|em|ar|asse|assem)|apag(?:a|am)|renome(?:ie|iem|ar)|rename)\b"
        rf"(?:.{{0,50}}\b(?:{_STORAGE}|tudo|colunas?)\b|{_ENTITY_OBJECT})",
    ),
    # "Altere a análise com os dados de 2024" e "Update the chart with 2024 data"
    # passam; dados só contam com gravação.
    _rule(
        "write_alter",
        r"\b(?:alter(?:e|ar|asse|assem)|atualiz(?:e|ar|asse|assem)|modifiqu(?:e)|modificar|edit(?:e|ar)|"
        r"substitu(?:a|ir)|troqu(?:e)|trocar|corrij(?:a)|corrigir|update|alter|modify|"
        r"change)\b.{0,50}"
        rf"(?:\b(?:{_STORAGE})\b|\b(?:dados|valores?)\b.{{0,40}}\b(?:{_PERSIST})\b)",
    ),
    # "Salve o relatório em PDF" exporta; salvar só grava dado sem alvo de exportação
    # por perto. Alvo de armazenamento continua recusado em qualquer caso.
    _rule(
        "write_insert",
        r"\b(?:insir(?:a)|inserir|insert|grav(?:e|ar)|salv(?:e|ar)|persist(?:a|ir)|"
        r"cadastr(?:e|em|ar)|registr(?:e|em|ar))\b.{0,50}"
        rf"\b(?:{_STORAGE})\b",
        r"\b(?:insir(?:a)|inserir|insert|grav(?:e|ar)|persist(?:a|ir)|"
        r"cadastr(?:e|em|ar)|registr(?:e|em|ar)|"
        r"salv(?:e|ar)\b(?!.{0,30}\b(?:relatorios?|graficos?|painel|paineis|pdf|csv|xlsx|"
        r"excel|imagem|png)\b))\b.{0,50}"
        r"\b(?:dados|valores?|novos?|novas?|clientes?|consumidor(?:es)?|usuarios?)\b",
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
    # Número sem máscara só conta como documento com a palavra cpf/cnpj, que casa
    # dentro de outra palavra porque a junção de letras isoladas cola o artigo
    # ("o c p f" vira "ocpf"). "Documento" só é pessoal quando é da pessoa
    # ("documento de referência da tarifa" passa).
    _rule(
        "pii_document",
        r"cpf|cnpj|\bc(?:\.\s?|[\s-])p(?:\.\s?|[\s-])f\b",
        r"\bdocumentos?(?: de (?:identidade|identificacao)| pessoa(?:l|is))?\s+d[oa]s?\s+"
        rf"(?:{_PERSON})\b",
        r"\bdocumentos? (?:de identidade|de identificacao|pessoa(?:l|is))\b",
        r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
        r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",
    ),
    # Atributo pessoal pedido sobre uma pessoa; "endereço" sozinho é permitido.
    _rule(
        "pii_contact",
        r"\b[a-z0-9._%+-]{1,64}@[a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63}){1,5}\b",
        r"\(\d{2}\)\s?9?\d{4}-?\d{4}\b|\+55\s?\d{2}\b",
        r"\b(?:e-?mails?|telefones?|telefonos?|fones?|celular(?:es)?|whatsapp|zap|enderecos?|"
        r"rg|data de nascimento|nomes? d[oa]s?|rendas?|salarios?|profiss(?:ao|oes)|correos?|"
        r"correios? eletronicos?|numeros? de (?:contato|telefone|celular)|"
        r"direccion(?:es)?|phone(?: numbers?)?|address(?:es)?|full names?|salary|income)\b"
        rf".{{0,40}}\b(?:{_PERSON})\b",
        # "Contato" só com determinante e pessoa ("o contato do cliente"); "quantos
        # contatos de atendimento" e "clientes têm contato registrado" passam.
        rf"\b(?:o|os|seu|seus|um)\s+contatos?\s+d[oa]s?\s+(?:{_PERSON})\b",
        # Ordem inversa num pedido de lista: "liste os clientes e seus telefones".
        # Endereço e nome só com "e"; "consumo dos clientes com endereço em X" passa.
        r"\b(?:list(?:e|ar)|mostr(?:e|ar)|exib(?:a|ir)|trag(?:a)|traz(?:er)?|me de|passe|"
        r"informe|show|give)\b.{0,20}"
        rf"\b(?:{_PERSON})\b.{{0,20}}"
        r"(?:\b(?:e|and)\s+(?:(?:seus|suas|os|as|respectivos|respectivas|their)\s+)?"
        r"(?:e-?mails?|telefones?|fones?|celular(?:es)?|whatsapp|zap|enderecos?|nomes?|"
        r"phones?|address(?:es)?|names?)\b|"
        r"\b(?:com|with)\s+(?:(?:seus|suas|os|as|their)\s+)?"
        r"(?:e-?mails?|telefones?|fones?|celular(?:es)?|whatsapp|zap|phones?)\b)",
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
    # "Quem são os clientes com maior consumo" e "os maiores consumidores" são
    # rankings agregados; "quem é o titular da UC" pede a identidade.
    _rule(
        "pii_identity",
        r"\b(?:dados pessoais|nomes? completos?|todos os clientes)\b",
        rf"\bdados (?:cadastrais|de cadastro)\b.{{0,15}}\b(?:{_PERSON})\b",
        r"\bquem (?:e|sao|seria|era|eram)\s+"
        r"(?:(?!(?:maiores|menores|principais)\b)\S{1,20}\s+){0,3}"
        rf"(?:{_PERSON})\b(?!\s+(?:com|de|que)\s+(?:o |a )?(?:{_RANKING})\b)",
        r"\bquem (?:mora|moram|reside|residem|vive|vivem|habita|habitam|paga|pagam)\b.{0,30}"
        r"\b(?:ucs?|unidades? consumidoras?|casas?|residencias?|imove(?:l|is)|apartamentos?)\b",
        r"\bonde (?:mora|moram|reside|residem|vive|vivem)\b",
    ),
)


SECURITY_RULE_NAMES = tuple(rule.name for rule in _SECURITY_RULES)

# Mensagens fixas do próprio serviço voltam no contexto como turno "assistant". Só o
# texto idêntico é aceito: a recusa ("…expor dados pessoais ou instruções internas")
# não carrega ataque, mas qualquer acréscimo volta a passar pelas regras.
_SERVICE_MESSAGES = frozenset(
    _normalize(map_failure(code).message).flat for code in FailureCode
)


class QuestionSafetyGate:
    """Recusa pedidos explícitos de escrita, segredos, dados pessoais e injeção de instruções."""

    def __init__(self, *, out_of_scope_terms: tuple[str, ...] = ()) -> None:
        terms = [re.escape(_normalize(item).flat) for item in out_of_scope_terms]
        self._out_of_scope = (
            re.compile(rf"\b(?:{'|'.join(terms)})\b") if terms else None
        )

    def matched_rule(self, question: str) -> str | None:
        """Nome da primeira regra que casa; nunca devolve trecho da pergunta."""
        removed = _normalize(question)
        if removed.flat.strip() in _SERVICE_MESSAGES:
            return None
        # Invisível dentro da palavra ("dr​op") só casa removido; no lugar do
        # espaço ("Apague​os registros") só casa trocado por espaço.
        spaced = _normalize(question, invisible=" ")
        versions = (removed,) if spaced == removed else (removed, spaced)
        for rule in _SECURITY_RULES:
            if any(rule.matches(version) for version in versions):
                return rule.name
        if self._out_of_scope is not None and any(
            self._out_of_scope.search(version.flat) for version in versions
        ):
            return OUT_OF_SCOPE_RULE
        return None

    def refusal_code(self, question: str) -> SafetyRefusalCode | None:
        rule = self.matched_rule(question)
        if rule is None:
            return None
        if rule == OUT_OF_SCOPE_RULE:
            return SafetyRefusalCode.OUT_OF_SCOPE
        return SafetyRefusalCode.SECURITY_VIOLATION
