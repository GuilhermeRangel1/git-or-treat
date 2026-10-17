# Databricks notebook source
# MAGIC %md
# MAGIC # V-Energy Grid 360 — Perfilamento da Bronze
# MAGIC
# MAGIC **Objetivo:** medir a qualidade dos dados brutos **antes** de limpar.
# MAGIC Este notebook não altera nada — ele só **investiga** e monta um relatório de problemas.
# MAGIC
# MAGIC **Como ler o resultado:** cada seção abaixo procura um tipo de problema e imprime números.
# MAGIC O produto final é a tabela Delta **`quality.perfil_bronze`** (seção 10.1): ela vira o **plano de limpeza da Silver**
# MAGIC e a seção de limpeza do **dicionário de dados**.
# MAGIC
# MAGIC **As 5 famílias de problemas que vamos medir:**
# MAGIC 1. **Completude** — campos nulos/vazios
# MAGIC 2. **Unicidade** — linhas duplicadas (exatas ou na chave)
# MAGIC 3. **Integridade referencial** — registros órfãos (que apontam para UC/medidor inexistente)
# MAGIC 4. **Validade** — formatos inválidos e valores impossíveis (negativos, datas no futuro, etc.)
# MAGIC 5. **Consistência** — a mesma coisa escrita de formas diferentes
# MAGIC
# MAGIC E, além disso, **regras de negócio** específicas (ex.: fatura paga sem data de pagamento).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Configuração e funções auxiliares

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType, StructField, StructType
from datetime import datetime, timezone
import pandas as pd

CATALOG = "workspace"
SCHEMA = "bronze"
SCHEMA_QUALIDADE = f"{CATALOG}.quality"
ALVO = f"{CATALOG}.{SCHEMA}"
VOLUME_RELATORIOS = "/Volumes/workspace/default/venergy/relatorios"

TABELAS = [
    "unidades_consumidoras", "faturas", "leituras", "medidores",
    "ocorrencias_rede", "geracao_distribuida", "atendimentos", "inspecoes",
]
# Colunas que NÓS criamos na Bronze: ignoradas nas checagens. `_lote_id` é constante por execução
# e `_id_registro` é único por linha — nenhum dos dois é atributo do dado, então não entram em
# regra de qualidade (nulos, duplicatas, categorias, etc.). `_aba_origem` é a mesma coisa nas
# inspeções: registra de qual aba da planilha a linha veio, não é dado de negócio.
AUDITORIA = ["_arquivo_origem", "_aba_origem", "_lote_id", "_id_registro", "_data_carga"]

PROBLEMAS = []  # acumula o relatório final

def df(t):
    return spark.table(f"{ALVO}.{t}")

_COLS_BRUTAS = {}   # cache: as colunas de uma tabela não mudam durante a execução

def colunas_brutas(t):
    if t not in _COLS_BRUTAS:
        _COLS_BRUTAS[t] = df(t).columns
    return _COLS_BRUTAS[t]

def colunas(t):
    return [c for c in colunas_brutas(t) if c not in AUDITORIA]

def existe(t, c):
    """Guarda contra mudança de esquema: avisa e a regra é ignorada quando a coluna não existir."""
    if c in colunas_brutas(t):
        return True
    print(f"  AVISO: coluna {t}.{c} não existe nesta Bronze — regra ignorada.")
    return False

def vazio(c):
    """Considera nulo OU string vazia/espaços como 'faltante'."""
    return F.col(c).isNull() | (F.trim(F.col(c).cast("string")) == "")

def num_br(c):
    """Número como ele vem nos arquivos: 'R$ 1.234,56' -> 1234.56 ; '217 min' -> 217 ; '6.31' -> 6.31.
    O que não vira número devolve nulo — é a mesma regra que a Silver aplica, então o perfil mede
    exatamente o que ela vai tratar."""
    s = F.regexp_replace(F.trim(F.col(c).cast("string")), r"[^0-9,.\-]", "")   # tira R$, 'min', letras
    br = F.regexp_replace(F.regexp_replace(s, r"\.", ""), ",", ".")           # 1.234,56 -> 1234.56
    limpo = F.when(F.instr(s, ",") > 0, br).otherwise(s)
    return F.when(limpo.rlike(r"^-?\d+(\.\d+)?$"), limpo).cast("double")

def data_br(c):
    """Lê as datas dos arquivos. O conteúdo mistura ISO com dia/mês primeiro e três separadores
    (- / .), e a ordem dia/mês NÃO é confiável: '10-19-2024' só pode ser mês primeiro, enquanto
    '27/07/2024' só pode ser dia primeiro. Depois de normalizar o separador, tentamos as três ordens.

    Devolve uma tupla:
      data    — primeiro formato que casa; nulo se nenhum casar;
      ambigua — casa nos DOIS sentidos e eles dão datas diferentes (ex.: '11-05-2022' pode ser
                11 de maio ou 5 de novembro). É uma decisão de negócio, não um valor inválido:
                o perfil registra, não esconde.

    O primeiro ramo usa `try_cast` de propósito: `ocorrencias_rede` e `atendimentos` guardam
    **timestamp** (`2025-07-21 14:07:00`), e o `cast` para data derruba a hora sem reclamar.
    Os outros dois ramos precisam de formato explícito, senão `11-05-2022` nunca casaria.
    """
    base = f"regexp_replace(trim(`{c}`), '[/.]', '-')"

    def parse(fmt):
        return F.expr(f"try_to_date({base}, '{fmt}')")

    iso  = F.expr(f"try_cast({base} as date)")
    dia1, mes1 = parse("dd-MM-yyyy"), parse("MM-dd-yyyy")
    ambigua = dia1.isNotNull() & mes1.isNotNull() & (dia1 != mes1)
    return F.coalesce(iso, dia1, mes1), ambigua

def registra(tabela, verificacao, qtd, gravidade, comentario):
    """Guarda um problema encontrado no relatório final."""
    PROBLEMAS.append({
        "tabela": tabela, "verificacao": verificacao, "ocorrencias": int(qtd),
        "gravidade": gravidade, "observacao": comentario,
    })
    print(f"[{gravidade:^8}] {tabela:<24} {verificacao:<45} {int(qtd):>10,}")

def regra(tabela, verificacao, necessarias, gravidade_base, comentario, conta):
    """Roda a checagem só se as colunas necessárias existirem (guarda de esquema) e registra o resultado.
    `conta` é uma função sem argumento: a consulta não roda nem é montada quando falta coluna."""
    faltando = [c for c in necessarias if c not in colunas_brutas(tabela)]
    if faltando:
        print(f"  AVISO: '{verificacao}' ignorada — {tabela} sem: {', '.join(faltando)}")
        return
    q = conta()
    registra(tabela, verificacao, q, gravidade_base if q else "ok", comentario)

def mostra(pdf, titulo):
    """Exibe um resultado em pandas. Se estiver vazio, avisa em vez de tentar exibir (evita erro de schema vazio)."""
    print(f"\n--- {titulo} ---")
    if pdf is None or len(pdf) == 0:
        print("    (nada encontrado — nenhum problema deste tipo)")
    else:
        display(pdf)

def mostra_spark(d, titulo):
    """Exibe um DataFrame Spark. Se estiver vazio, avisa em vez de tentar exibir."""
    print(f"\n--- {titulo} ---")
    if d.limit(1).count() == 0:
        print("    (nada encontrado — nenhum problema deste tipo)")
    else:
        display(d)

print("Configuração ok. Tabelas:", len(TABELAS))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Estrutura das tabelas (schema)
# MAGIC Antes de checar qualidade, olhe **o que cada tabela tem**. Em especial `atendimentos`,
# MAGIC que veio **aninhado** do JSON — repare em campos que são `struct` ou `array`.

# COMMAND ----------

for t in TABELAS:
    print(f"\n===== {t} =====")
    df(t).printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Visão geral
# MAGIC Quantas linhas e colunas cada tabela tem, e quantas **linhas idênticas** (duplicata exata).
# MAGIC Se `duplicatas_exatas` > 0, significa que a mesma linha aparece mais de uma vez no arquivo original.

# COMMAND ----------

linhas = []
for t in TABELAS:
    d = df(t)
    total = d.count()
    # Duplicata EXATA = linhas iguais nos campos de DADO. Não usar dropDuplicates() sem argumento:
    # `_id_registro` é único por linha e faria a conta dar 0 duplicatas sempre (falso negativo).
    dup = total - d.dropDuplicates(colunas(t)).count()
    linhas.append({"tabela": t, "linhas": total, "colunas": len(colunas(t)), "duplicatas_exatas": dup})
    # C1: entra no relatório consolidado (antes só aparecia nesta tabela de tela).
    registra(t, "linhas duplicadas (idênticas em todos os campos)", dup, "MEDIA" if dup else "ok",
             "A Silver mantém uma e manda as cópias para a quarentena")

mostra(pd.DataFrame(linhas), "Visão geral")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Completude — valores nulos/vazios por coluna
# MAGIC Só lista colunas que têm algum valor faltante.
# MAGIC **Como interpretar:** um campo com 80% de nulo pode ser simplesmente "não se aplica"
# MAGIC (ex.: `data_retirada` de medidor ativo) — não é erro. O problema é nulo em campo **obrigatório**.

# COMMAND ----------

nulos = []
for t in TABELAS:
    d = df(t)
    total = d.count()
    for c in colunas(t):
        n = d.where(vazio(c)).count()
        if n > 0:
            pct = round(100 * n / total, 2)
            nulos.append({"tabela": t, "coluna": c, "nulos": n, "percentual": pct})
            # C1: entra no relatório consolidado. Gravidade MEDIA porque nulo pode ser "não se aplica"
            # (ex.: data_retirada de medidor ativo) — quem decide se é campo obrigatório é o negócio.
            registra(t, f"nulos em {c}", n, "MEDIA",
                     f"{pct}% da tabela — conferir se o campo é obrigatório")

if nulos:
    tabela_nulos = pd.DataFrame(nulos).sort_values(["tabela", "percentual"], ascending=[True, False])
    mostra(tabela_nulos, "Nulos por coluna")
else:
    print("Nenhum valor nulo/vazio encontrado em nenhuma coluna.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Unicidade — duplicatas na chave
# MAGIC Duplicata exata é rara; o problema comum é **a mesma chave repetida** (ex.: dois registros para o mesmo `id_uc`).
# MAGIC Chave repetida quebra joins e infla somas — é um dos erros que mais distorce o diagnóstico de receita.

# COMMAND ----------

CHAVES = {
    "unidades_consumidoras": ["id_uc"],
    "faturas": ["id_fatura"],
    "leituras": ["id_leitura"],
    "medidores": ["id_medidor"],
    "ocorrencias_rede": ["id_ocorrencia"],
    "geracao_distribuida": ["id_uc"],
    "atendimentos": ["protocolo"],
    "inspecoes": ["id_inspecao"],
}

for t, ch in CHAVES.items():
    if not all(existe(t, c) for c in ch):
        continue
    qtd = df(t).groupBy(*ch).count().where(F.col("count") > 1).count()
    registra(t, f"chave duplicada {ch}", qtd, "ALTA" if qtd else "ok",
             "Chave deveria ser única")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Integridade referencial — registros órfãos
# MAGIC Um "órfão" é um registro que aponta para algo que não existe.
# MAGIC Ex.: uma **leitura de UC que não está no cadastro** — se você fizer join na Silver, essa linha desaparece
# MAGIC silenciosamente (ou pior, infla um total). Por isso órfão vai para **quarentena**, não para o lixo.

# COMMAND ----------

ucs = df("unidades_consumidoras").select("id_uc").distinct()

def orfaos(tabela, chave, referencia, rotulo, gravidade="ALTA"):
    """C2: conta as DUAS coisas — entidades distintas e linhas afetadas.
    O rótulo antigo dizia 'registros órfãos' mas contava chaves distintas, o que engana quem lê
    (31 mil faturas órfãs podem ser 3 mil UCs distintas, ou o contrário)."""
    d = df(tabela)
    distintas = d.select(chave).distinct().join(referencia, chave, "left_anti").count()
    linhas_afetadas = d.join(referencia, chave, "left_anti").count()
    registra(tabela, rotulo, linhas_afetadas, gravidade if linhas_afetadas else "ok",
             f"{distintas:,} {chave}(s) distinta(s) em {linhas_afetadas:,} linha(s) afetada(s)")

for t in ["leituras", "faturas", "medidores", "ocorrencias_rede", "geracao_distribuida"]:
    if existe(t, "id_uc"):
        orfaos(t, "id_uc", ucs, "UC inexistente no cadastro (órfão)")

# id_medidor das leituras x cadastro de medidores
meds = df("medidores").select("id_medidor").distinct()
if existe("leituras", "id_medidor"):
    orfaos("leituras", "id_medidor", meds, "medidor inexistente no cadastro (órfão)")

# UCs de geração distribuída e de ocorrências que existem, mas o inverso também interessa:
if existe("unidades_consumidoras", "id_uc") and existe("leituras", "id_uc"):
    orfaos("unidades_consumidoras", "id_uc", df("leituras").select("id_uc").distinct(),
           "UC sem nenhuma leitura", gravidade="MEDIA")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Validade — datas
# MAGIC Para cada coluna de data: mínimo, máximo e três contagens:
# MAGIC 1. **inválida** — não casa com nenhum dos formatos do arquivo;
# MAGIC 2. **ambígua** — casa nos dois sentidos (dia primeiro e mês primeiro) e dá datas diferentes,
# MAGIC    como `11-05-2022`; não é dado podre, é decisão de negócio pendente;
# MAGIC 3. **no futuro** — sinal a investigar, não defeito provado.
# MAGIC
# MAGIC O arquivo **não usa um formato só**: mistura ISO com dia/mês primeiro e três separadores (`- / .`).
# MAGIC Ler tudo como ISO — o que este notebook fazia — inflava "inválida" com data perfeitamente válida.

# COMMAND ----------

DATAS = {
    "unidades_consumidoras": ["data_ligacao"],
    "faturas": ["data_emissao", "data_vencimento", "data_pagamento"],
    "leituras": ["data_leitura"],
    "medidores": ["data_instalacao", "data_retirada", "data_ultima_manutencao"],
    "ocorrencias_rede": ["data_abertura", "data_encerramento"],
    "geracao_distribuida": ["data_conexao"],
    "atendimentos": ["data_abertura", "data_fechamento"],
    "inspecoes": ["data"],
}

datas = []
for t, cols in DATAS.items():
    d = df(t)
    for c in cols:
        if not existe(t, c):
            continue
        p, amb = data_br(c)
        d2 = d.withColumn("_p", p).withColumn("_amb", amb)
        invalidas = d2.where(~vazio(c) & F.col("_p").isNull()).count()
        ambiguas = d2.where(F.col("_amb")).count()
        futuras = d2.where(F.col("_p") > F.current_date()).count()
        r = d2.where(F.col("_p").isNotNull()).agg(F.min("_p"), F.max("_p")).first()
        datas.append({"tabela": t, "coluna": c, "min": r[0], "max": r[1],
                      "invalidas": invalidas, "ambiguas": ambiguas, "no_futuro": futuras})
        registra(t, f"data inválida/impossível: {c}", invalidas,
                 "ALTA" if invalidas else "ok", "Não casa com nenhum formato conhecido")
        # Ambígua não é erro do dado: o arquivo simplesmente não diz a ordem dia/mês. Vai para o negócio.
        registra(t, f"data ambígua (dia/mês indefinido): {c}", ambiguas,
                 "MEDIA" if ambiguas else "ok",
                 "Casa nos dois sentidos; exige regra decidida, não chute")
        # C5: data no futuro é sinal a INVESTIGAR, não defeito provado — a competência corrente
        # pode legitimamente cair à frente da data da execução. Gravidade rebaixada.
        registra(t, f"data no futuro: {c} (investigar)", futuras,
                 "BAIXA" if futuras else "ok", "Pode ser competência corrente; conferir antes de tratar")
        if invalidas:
            print(f"  Exemplos de valores inválidos em {t}.{c}:")
            (d2.where(~vazio(c) & F.col("_p").isNull())
               .select(F.col(c).alias("valor_bruto"))
               .groupBy("valor_bruto").count()
               .orderBy(F.desc("count")).limit(10)
               .show(truncate=False))

mostra(pd.DataFrame(datas), "Datas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Validade — números
# MAGIC Para cada coluna numérica: mínimo, máximo e quantos **negativos**.
# MAGIC Consumo negativo, por exemplo, é fisicamente impossível — é erro de leitura ou de cadastro.

# COMMAND ----------

NUMERICAS = {
    "leituras": ["leitura_anterior", "leitura_atual", "consumo_kwh"],
    "faturas": ["valor_energia", "tributos", "valor_total"],
    "ocorrencias_rede": ["duracao_min"],
    "geracao_distribuida": ["potencia_kwp", "energia_injetada_kwh_media_mensal"],
    "unidades_consumidoras": ["latitude", "longitude"],
    "inspecoes": ["kwh_recuperado"],
    "atendimentos": ["nota_satisfacao"],
}

# C3: negativo vale para TODOS os campos numéricos, com duas exceções de julgamento:
#  - latitude/longitude: negativo é valor legítimo (hemisfério sul/oeste) — não é problema;
#  - valor_* de fatura: negativo pode ser estorno/ajuste — fica MEDIA, para conferir.
NEGATIVO_LEGITIMO = {"latitude", "longitude"}
NEGATIVO_IMPOSSIVEL = {"leitura_anterior", "leitura_atual", "consumo_kwh", "duracao_min",
                       "potencia_kwp", "energia_injetada_kwh_media_mensal",
                       "kwh_recuperado", "nota_satisfacao"}

numeros = []
for t, cols in NUMERICAS.items():
    d = df(t)
    for c in cols:
        if not existe(t, c):
            continue
        # C6: normaliza moeda/vírgula/sufixo antes de converter ('R$ 127,09' e '217 min' viram número).
        d2 = d.withColumn("_n", num_br(c))
        nao_num = d2.where(~vazio(c) & F.col("_n").isNull()).count()
        r = d2.where(F.col("_n").isNotNull()).agg(F.min("_n"), F.max("_n"), F.sum(F.when(F.col("_n") < 0, 1).otherwise(0))).first()
        negativos = int(r[2] or 0)
        numeros.append({"tabela": t, "coluna": c, "min": r[0], "max": r[1],
                        "negativos": negativos, "nao_numericos": nao_num})
        if nao_num:
            registra(t, f"valor não numérico: {c}", nao_num, "MEDIA", "Não converte para número")
            print(f"  Exemplos de valores não numéricos em {t}.{c}:")
            (d2.where(~vazio(c) & F.col("_n").isNull())
               .select(F.col(c).alias("valor_bruto"))
               .groupBy("valor_bruto").count()
               .orderBy(F.desc("count")).limit(10)
               .show(truncate=False))
        if negativos and c not in NEGATIVO_LEGITIMO:
            impossivel = c in NEGATIVO_IMPOSSIVEL
            registra(t, f"valor negativo: {c}", negativos, "ALTA" if impossivel else "MEDIA",
                     "Negativo fisicamente impossível" if impossivel
                     else "Verificar se é estorno/ajuste legítimo antes de tratar")

mostra(pd.DataFrame(numeros), "Números")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Consistência — categorias e variações de grafia
# MAGIC Aqui olhamos colunas de texto categóricas (município, bairro, classe, status...).
# MAGIC A segunda parte é a mais valiosa: **agrupa valores que são o mesmo texto escrito diferente**
# MAGIC (maiúsculas, espaços a mais). É o que precisa ser padronizado na Silver.

# COMMAND ----------

CATEGORICAS = {
    "unidades_consumidoras": ["municipio", "bairro", "classe", "subgrupo_tarifario", "status"],
    "faturas": ["bandeira_tarifaria", "status"],
    "leituras": ["tipo_leitura"],
    "medidores": ["modelo", "tipo", "status"],
    "ocorrencias_rede": ["tipo", "causa"],
    "geracao_distribuida": ["modalidade"],
    "atendimentos": ["assunto", "canal", "subassunto"],
    "inspecoes": ["resultado", "tipo_irregularidade", "inspetor"],
}

for t, cols in CATEGORICAS.items():
    for c in cols:
        if not existe(t, c):
            continue
        mostra_spark(df(t).where(~vazio(c)).groupBy(c).count().orderBy(F.desc("count")).limit(30),
                     f"{t}.{c}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 8.1. Mesmo valor, grafias diferentes
# MAGIC Agrupa pelo texto normalizado (**minúsculo, sem espaço extra**) e mostra os grupos com mais de uma
# MAGIC grafia. Roda em **todas** as colunas categóricas — não só em município e bairro.
# MAGIC
# MAGIC Limite conhecido: a normalização **não** remove acento nem hífen, então `eletrônico` não colapsa
# MAGIC com `eletronico`. O que aparece aqui é o mínimo de padronização que os dados exigem, não o
# MAGIC inventário completo.

# COMMAND ----------

def variantes(tabela, coluna):
    """Agrupa pelo texto normalizado e mostra grupos com mais de uma grafia (problema de padronização)."""
    d = df(tabela).where(~vazio(coluna)).select(F.col(coluna).alias("bruto"))
    norm = F.lower(F.regexp_replace(F.trim(F.col("bruto")), r"\s+", " "))
    g = (d.withColumn("normalizado", norm)
           .groupBy("normalizado")
           .agg(F.collect_set("bruto").alias("_v"), F.count("*").alias("linhas"))
           .where(F.size("_v") > 1)
           .withColumn("variantes", F.concat_ws(" | ", F.array_sort("_v")))
           .select("normalizado", "variantes", "linhas")
           .orderBy(F.desc("linhas")))
    return g

# Roda em TODAS as colunas categóricas. Antes eram só municipio e bairro — e o primeiro run real
# mostrou `classe`, `medidores.tipo` e `medidores.modelo` com variantes que nunca chegavam ao relatório.
for t, cols in CATEGORICAS.items():
    for c in cols:
        if not existe(t, c):
            continue
        v = variantes(t, c)
        qtd = v.count()
        registra(t, f"grafias diferentes em {c}", qtd, "MEDIA" if qtd else "ok",
                 "Mesmo valor escrito de formas diferentes")
        if qtd:
            # Já sabemos que não está vazio: evita o `limit(1).count()` extra do mostra_spark
            # (são 20 colunas categóricas × uma execução a mais em cada uma).
            print(f"\n--- Variantes de {t}.{c} ---")
            display(v)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Regras de negócio
# MAGIC Aqui entram checagens que só fazem sentido para o setor de energia.

# COMMAND ----------

# --- Leituras ---
# Negativos não têm regra aqui: a seção 7 cobre TODOS os campos numéricos (item C3), com gravidade
# por coluna. Duplicar a regra aqui só encheria o relatório com a mesma linha duas vezes.

# leitura atual menor que a anterior (medidor pode virar/zerar — mas precisa de critério)
regra("leituras", "leitura_atual < leitura_anterior", ["leitura_atual", "leitura_anterior"], "MEDIA",
      "Pode ser troca de medidor ou erro de leitura",
      lambda: df("leituras").where(num_br("leitura_atual") < num_br("leitura_anterior")).count())

regra("leituras", "mes_referencia fora do formato AAAA-MM", ["mes_referencia"], "MEDIA",
      "Padrão de competência",
      lambda: df("leituras").where(~F.col("mes_referencia").rlike(r"^\d{4}-\d{2}$")).count())

# --- Faturas ---
regra("faturas", "valor_total != valor_energia + tributos", ["valor_total", "valor_energia", "tributos"], "ALTA",
      "Inconsistência de composição do valor",
      lambda: df("faturas").where(F.abs(num_br("valor_total") - (num_br("valor_energia") + num_br("tributos"))) > 0.01).count())

regra("faturas", "pagamento antes da emissão", ["data_pagamento", "data_emissao"], "ALTA",
      "Data de pagamento anterior à emissão da fatura",
      lambda: df("faturas").where(F.col("data_pagamento").isNotNull()
                                  & (data_br("data_pagamento")[0] < data_br("data_emissao")[0])).count())

regra("faturas", "status PAGA sem data_pagamento", ["status", "data_pagamento"], "MEDIA",
      "Status diz paga, mas não há data",
      lambda: df("faturas").where((F.upper(F.col("status")) == "PAGA") & vazio("data_pagamento")).count())

regra("faturas", "não paga com data_pagamento", ["status", "data_pagamento"], "MEDIA",
      "Data de pagamento preenchida mas status diferente",
      lambda: df("faturas").where((F.upper(F.col("status")) != "PAGA") & F.col("data_pagamento").isNotNull()).count())

regra("faturas", "mes_referencia fora do formato AAAA-MM", ["mes_referencia"], "MEDIA",
      "Padrão de competência",
      lambda: df("faturas").where(~F.col("mes_referencia").rlike(r"^\d{4}-\d{2}$")).count())

# --- Ocorrências ---
regra("ocorrencias_rede", "ocorrência sem data de encerramento", ["data_encerramento"], "MEDIA",
      "Interrupção em aberto",
      lambda: df("ocorrencias_rede").where(vazio("data_encerramento")).count())

regra("ocorrencias_rede", "encerrada mas sem duração", ["duracao_min", "data_encerramento"], "MEDIA",
      "Afeta o cálculo de DEC",
      lambda: df("ocorrencias_rede").where(vazio("duracao_min") & ~vazio("data_encerramento")).count())

# --- Cadastro ---
regra("unidades_consumidoras", "cpf_cnpj vazio", ["cpf_cnpj"], "MEDIA",
      "Campo sensível (LGPD) e possivelmente obrigatório",
      lambda: df("unidades_consumidoras").where(vazio("cpf_cnpj")).count())

regra("unidades_consumidoras", "status fora do domínio esperado", ["status"], "MEDIA",
      "Ver valores distintos na seção 8",
      lambda: df("unidades_consumidoras").where(~F.upper(F.col("status")).isin("ATIVA", "DESATIVADA", "SUSPENSA", "CORTADA")).count())

regra("unidades_consumidoras", "id_uc duplicado no cadastro", ["id_uc"], "ALTA",
      "Duas linhas para a mesma UC",
      lambda: df("unidades_consumidoras").select("id_uc").count() - df("unidades_consumidoras").select("id_uc").distinct().count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Relatório consolidado de problemas
# MAGIC Esta é a saída principal do perfilamento. Ela vira:
# MAGIC - o **plano de limpeza** da camada Silver;
# MAGIC - a seção "decisões de limpeza" do **dicionário de dados**;
# MAGIC - o material para você justificar cada tratamento na apresentação.

# COMMAND ----------

COLS_RELATORIO = ["tabela", "verificacao", "ocorrencias", "gravidade", "observacao"]
relatorio = pd.DataFrame(PROBLEMAS, columns=COLS_RELATORIO)
if len(relatorio) > 0:
    relatorio = relatorio.sort_values(["gravidade", "tabela"], ascending=[True, False])
    display(relatorio)
else:
    print("Nenhum problema registrado — dado surpreendentemente limpo. Revise as células anteriores.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 10.1. Persistência do relatório
# MAGIC O relatório é **insumo da Silver**, então precisa existir fora da tela: vai para a tabela Delta
# MAGIC `quality.perfil_bronze`, que passa a ser a **fonte da verdade** do plano de limpeza.
# MAGIC
# MAGIC A gravação **não** fica dentro de `try/except`. Antes, uma falha de escrita era engolida com um
# MAGIC "o resultado está na tela" — e a Silver ficava sem insumo sem ninguém perceber. Se falhar agora,
# MAGIC a execução falha à vista.

# COMMAND ----------

TABELA_RELATORIO = f"{SCHEMA_QUALIDADE}.perfil_bronze"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_QUALIDADE}")

ESQUEMA_RELATORIO = StructType([
    StructField("tabela", StringType(), False),
    StructField("verificacao", StringType(), False),
    StructField("ocorrencias", IntegerType(), False),
    StructField("gravidade", StringType(), False),
    StructField("observacao", StringType(), True),
])

relatorio_spark = spark.createDataFrame(relatorio, schema=ESQUEMA_RELATORIO)

(relatorio_spark
   .withColumn("_data_perfilamento", F.lit(datetime.now(timezone.utc)).cast("timestamp"))
   .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
   .saveAsTable(TABELA_RELATORIO))
print(f"OK  {TABELA_RELATORIO}  {relatorio_spark.count():,} linhas")

# Cópia em CSV no volume, só para baixar e anexar na documentação. A persistência garantida é a tabela
# Delta acima; se o volume não existir, o aviso diz isso — em vez de fingir que salvou.
try:
    (relatorio_spark.coalesce(1).write.mode("overwrite").option("header", True)
       .csv(f"{VOLUME_RELATORIOS}/perfilamento_bronze"))
    print(f"CSV em {VOLUME_RELATORIOS}/perfilamento_bronze")
except Exception as e:
    print(f"CSV não gerado ({e}). O relatório está em {TABELA_RELATORIO}.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Como decidir o que fazer com cada problema
# MAGIC O relatório acima é a **lista de sintomas**. A decisão de tratamento é sua (e vai para o dicionário):
# MAGIC
# MAGIC | Problema | Decisão comum | Quando NÃO usar |
# MAGIC |---|---|---|
# MAGIC | Duplicata exata | Remover | Se a duplicata carrega informação (ex.: dois pagamentos), investigar |
# MAGIC | Órfão (UC inexistente) | Mover para tabela de **quarentena** | Nunca apagar sem rastro |
# MAGIC | Nulo em campo opcional | Manter como nulo | — |
# MAGIC | Nulo em campo obrigatório | Investigar com o negócio antes de imputar | Imputar média sem justificar |
# MAGIC | Data inválida | Quarentena ou corrigir com regra clara | Corrigir "no chute" |
# MAGIC | Data no futuro | **Investigar** (pode ser competência corrente) | Tratar como erro sem evidência |
# MAGIC | Data ambígua (`11-05-2022`) | **Decidir a regra com o negócio**; até lá, quarentena | Assumir dia ou mês "porque sempre foi assim" |
# MAGIC | Grafia divergente | Padronizar (ex.: Title Case) | — |
# MAGIC | Consumo negativo | Verificar se é troca de medidor antes de tratar | Tratar como furto sem evidência |
# MAGIC
# MAGIC **Próximo passo:** com este relatório em mãos, montar a Silver tratando cada item,
# MAGIC registrando a decisão na coluna `observacao` do dicionário.
