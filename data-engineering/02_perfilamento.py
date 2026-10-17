# Databricks notebook source
# MAGIC %md
# MAGIC # V-Energy Grid 360 — Perfilamento da Bronze
# MAGIC
# MAGIC **Objetivo:** medir a qualidade dos dados brutos **antes** de limpar.
# MAGIC Este notebook não altera nada — ele só **investiga** e monta um relatório de problemas.
# MAGIC
# MAGIC **Como ler o resultado:** cada seção abaixo procura um tipo de problema e imprime números.
# MAGIC O produto final é a tabela da última célula (`relatorio_problemas`): ela vira o **plano de limpeza da Silver**
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
import pandas as pd

CATALOG = "workspace"
SCHEMA = "bronze"
ALVO = f"{CATALOG}.{SCHEMA}"
VOLUME_RELATORIOS = "/Volumes/workspace/default/venergy/relatorios"

TABELAS = [
    "unidades_consumidoras", "faturas", "leituras", "medidores",
    "ocorrencias_rede", "geracao_distribuida", "atendimentos", "inspecoes",
]
# Colunas que NÓS criamos na Bronze: ignoradas nas checagens. `_lote_id` é constante por execução
# e `_id_registro` é único por linha — nenhum dos dois é atributo do dado, então não entram em
# regra de qualidade (nulos, duplicatas, categorias, etc.).
AUDITORIA = ["_arquivo_origem", "_lote_id", "_id_registro", "_data_carga"]

PROBLEMAS = []  # acumula o relatório final

def df(t):
    return spark.table(f"{ALVO}.{t}")

def colunas(t):
    return [c for c in df(t).columns if c not in AUDITORIA]

def vazio(c):
    """Considera nulo OU string vazia/espaços como 'faltante'."""
    return F.col(c).isNull() | (F.trim(F.col(c).cast("string")) == "")

def try_num(c):
    """Converte para número SEM estourar erro: valor inválido vira nulo (modo ANSI do Databricks)."""
    return F.expr(f"try_cast(`{c}` as double)")

def try_dt(c):
    """Converte para data SEM estourar erro: valor inválido vira nulo (modo ANSI do Databricks)."""
    return F.expr(f"try_cast(`{c}` as date)")

def registra(tabela, verificacao, qtd, gravidade, comentario):
    """Guarda um problema encontrado no relatório final."""
    PROBLEMAS.append({
        "tabela": tabela, "verificacao": verificacao, "ocorrencias": int(qtd),
        "gravidade": gravidade, "observacao": comentario,
    })
    print(f"[{gravidade:^8}] {tabela:<24} {verificacao:<45} {int(qtd):>10,}")

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
            nulos.append({"tabela": t, "coluna": c, "nulos": n, "percentual": round(100 * n / total, 2)})

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
}

for t, ch in CHAVES.items():
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

for t in ["leituras", "faturas", "medidores", "ocorrencias_rede", "geracao_distribuida"]:
    qtd = df(t).select("id_uc").distinct().join(ucs, "id_uc", "left_anti").count()
    registra(t, "UC inexistente no cadastro (órfão)", qtd, "ALTA" if qtd else "ok",
             "Registro aponta para UC que não existe em unidades_consumidoras")

# id_medidor das leituras x cadastro de medidores
meds = df("medidores").select("id_medidor").distinct()
qtd = df("leituras").select("id_medidor").distinct().join(meds, "id_medidor", "left_anti").count()
registra("leituras", "medidor inexistente no cadastro (órfão)", qtd, "ALTA" if qtd else "ok",
         "id_medidor não encontrado em medidores")

# UCs de geração distribuída e de ocorrências que existem, mas o inverso também interessa:
qtd = df("unidades_consumidoras").select("id_uc").distinct() \
        .join(df("leituras").select("id_uc").distinct(), "id_uc", "left_anti").count()
registra("unidades_consumidoras", "UC sem nenhuma leitura", qtd, "MEDIA" if qtd else "ok",
         "UC cadastrada que nunca teve medição")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Validade — datas
# MAGIC Para cada coluna de data: minimo, maximo, quantas **não são parseáveis** e quantas estão **no futuro**.
# MAGIC Data no futuro em competência passada é sinal de erro de digitação ou de regra de negócio mal aplicada.

# COMMAND ----------

DATAS = {
    "unidades_consumidoras": ["data_ligacao"],
    "faturas": ["data_emissao", "data_vencimento", "data_pagamento"],
    "leituras": ["data_leitura"],
    "medidores": ["data_instalacao", "data_retirada", "data_ultima_manutencao"],
    "ocorrencias_rede": ["data_abertura", "data_encerramento"],
    "geracao_distribuida": ["data_conexao"],
}

datas = []
for t, cols in DATAS.items():
    d = df(t)
    for c in cols:
        d2 = d.withColumn("_p", try_dt(c))
        invalidas = d2.where(~vazio(c) & F.col("_p").isNull()).count()
        futuras = d2.where(F.col("_p") > F.current_date()).count()
        r = d2.where(F.col("_p").isNotNull()).agg(F.min("_p"), F.max("_p")).first()
        datas.append({"tabela": t, "coluna": c, "min": r[0], "max": r[1],
                      "nao_parseaveis": invalidas, "no_futuro": futuras})
        registra(t, f"data inválida/impossível: {c}", invalidas + futuras,
                 "ALTA" if (invalidas + futuras) else "ok", "Formato ou data no futuro")
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
}

numeros = []
for t, cols in NUMERICAS.items():
    d = df(t)
    for c in cols:
        d2 = d.withColumn("_n", try_num(c))
        nao_num = d2.where(~vazio(c) & F.col("_n").isNull()).count()
        r = d2.where(F.col("_n").isNotNull()).agg(F.min("_n"), F.max("_n"), F.sum(F.when(F.col("_n") < 0, 1).otherwise(0))).first()
        numeros.append({"tabela": t, "coluna": c, "min": r[0], "max": r[1],
                        "negativos": int(r[2] or 0), "nao_numericos": nao_num})
        if nao_num:
            registra(t, f"valor não numérico: {c}", nao_num, "MEDIA", "Não converte para número")
            print(f"  Exemplos de valores não numéricos em {t}.{c}:")
            (d2.where(~vazio(c) & F.col("_n").isNull())
               .select(F.col(c).alias("valor_bruto"))
               .groupBy("valor_bruto").count()
               .orderBy(F.desc("count")).limit(10)
               .show(truncate=False))

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
    "inspecoes": ["_aba_origem"],
}

for t, cols in CATEGORICAS.items():
    for c in cols:
        if c not in df(t).columns:
            continue
        mostra_spark(df(t).where(~vazio(c)).groupBy(c).count().orderBy(F.desc("count")).limit(30),
                     f"{t}.{c}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 8.1. Mesmo valor, grafias diferentes
# MAGIC Agrupa pelo texto normalizado (minúsculo, sem espaço extra). Se um grupo tem mais de uma grafia, é problema de padronização.

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

for t, c in [("unidades_consumidoras", "municipio"), ("unidades_consumidoras", "bairro")]:
    qtd = variantes(t, c).count()
    registra(t, f"grafias diferentes em {c}", qtd, "MEDIA" if qtd else "ok", "Mesmo valor escrito de formas diferentes")
    mostra_spark(variantes(t, c), f"Variantes de {t}.{c}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Regras de negócio
# MAGIC Aqui entram checagens que só fazem sentido para o setor de energia.

# COMMAND ----------

# --- Leituras ---
# consumo negativo
q = df("leituras").where(try_num("consumo_kwh") < 0).count()
registra("leituras", "consumo_kwh negativo", q, "ALTA" if q else "ok", "Fisicamente impossível")

# leitura atual menor que a anterior (medidor pode virar/zerar — mas precisa de critério)
q = df("leituras").where(try_num("leitura_atual") < try_num("leitura_anterior")).count()
registra("leituras", "leitura_atual < leitura_anterior", q, "MEDIA" if q else "ok", "Pode ser troca de medidor ou erro de leitura")

# --- Faturas ---
q = df("faturas").where(F.abs(try_num("valor_total") - (try_num("valor_energia") + try_num("tributos"))) > 0.01).count()
registra("faturas", "valor_total != valor_energia + tributos", q, "ALTA" if q else "ok", "Inconsistência de composição do valor")

q = df("faturas").where(F.col("data_pagamento").isNotNull() & (try_dt("data_pagamento") < try_dt("data_emissao"))).count()
registra("faturas", "pagamento antes da emissão", q, "ALTA" if q else "ok", "Data de pagamento anterior à emissão da fatura")

q = df("faturas").where((F.upper(F.col("status")) == "PAGA") & vazio("data_pagamento")).count()
registra("faturas", "status PAGA sem data_pagamento", q, "MEDIA" if q else "ok", "Status diz paga, mas não há data")

q = df("faturas").where((F.upper(F.col("status")) != "PAGA") & F.col("data_pagamento").isNotNull()).count()
registra("faturas", "não paga com data_pagamento", q, "MEDIA" if q else "ok", "Data de pagamento preenchida mas status diferente")

q = df("faturas").where(~F.col("mes_referencia").rlike(r"^\d{4}-\d{2}$")).count()
registra("faturas", "mes_referencia fora do formato AAAA-MM", q, "MEDIA" if q else "ok", "Padrão de competência")

q = df("leituras").where(~F.col("mes_referencia").rlike(r"^\d{4}-\d{2}$")).count()
registra("leituras", "mes_referencia fora do formato AAAA-MM", q, "MEDIA" if q else "ok", "Padrão de competência")

# --- Ocorrências ---
q = df("ocorrencias_rede").where(try_num("duracao_min") < 0).count()
registra("ocorrencias_rede", "duracao_min negativa", q, "ALTA" if q else "ok", "Duração não pode ser negativa")

q = df("ocorrencias_rede").where(vazio("data_encerramento")).count()
registra("ocorrencias_rede", "ocorrência sem data de encerramento", q, "MEDIA" if q else "ok", "Interrupção em aberto")

q = df("ocorrencias_rede").where(vazio("duracao_min") & ~vazio("data_encerramento")).count()
registra("ocorrencias_rede", "encerrada mas sem duração", q, "MEDIA" if q else "ok", "Afeta o cálculo de DEC")

# --- Cadastro ---
q = df("unidades_consumidoras").where(vazio("cpf_cnpj")).count()
registra("unidades_consumidoras", "cpf_cnpj vazio", q, "MEDIA" if q else "ok", "Campo sensível (LGPD) e possivelmente obrigatório")

q = df("unidades_consumidoras").where(~F.upper(F.col("status")).isin("ATIVA", "DESATIVADA", "SUSPENSA", "CORTADA")).count()
registra("unidades_consumidoras", "status fora do domínio esperado", q, "MEDIA" if q else "ok", "Ver valores distintos na seção 8")

q = df("unidades_consumidoras").select("id_uc").count() - df("unidades_consumidoras").select("id_uc").distinct().count()
registra("unidades_consumidoras", "id_uc duplicado no cadastro", q, "ALTA" if q else "ok", "Duas linhas para a mesma UC")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Relatório consolidado de problemas
# MAGIC Esta é a saída principal do perfilamento. Ela será **exportada** e vira:
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

# Exporta para CSV no volume (para baixar e guardar em docs/)
try:
    r = spark.createDataFrame(relatorio)
    (r.coalesce(1).write.mode("overwrite").option("header", True)
       .csv(f"{VOLUME_RELATORIOS}/perfilamento_bronze"))
    print(f"Relatório salvo em {VOLUME_RELATORIOS}/perfilamento_bronze")
except Exception as e:
    print("Não foi possível salvar o CSV (sem problema, o resultado está na tela):", e)

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
# MAGIC | Grafia divergente | Padronizar (ex.: Title Case) | — |
# MAGIC | Consumo negativo | Verificar se é troca de medidor antes de tratar | Tratar como furto sem evidência |
# MAGIC
# MAGIC **Próximo passo:** com este relatório em mãos, montar a Silver tratando cada item,
# MAGIC registrando a decisão na coluna `observacao` do dicionário.
