# Databricks notebook source
# MAGIC %md
# MAGIC # V-Energy Grid 360 — Camada Bronze
# MAGIC
# MAGIC **Objetivo:** ingerir as 8 fontes do dataset e gravar como tabelas Delta em `bronze.*`,
# MAGIC **preservando o conteúdo original** (sem tratar nada — limpeza é trabalho da Silver).
# MAGIC
# MAGIC **O que este notebook faz:**
# MAGIC - Lê todos os arquivos do Volume apontado em `RAW`
# MAGIC - Adiciona colunas de auditoria: `_arquivo_origem` e `_data_carga`
# MAGIC - Grava uma tabela Delta por fonte (modo overwrite, para poder reexecutar)
# MAGIC
# MAGIC **Particularidades tratadas:**
# MAGIC - `faturas.csv` usa **ponto e vírgula** como separador
# MAGIC - `atendimentos.json` é um **array JSON identado** (precisa de `multiLine`) e fica **aninhado** na Bronze
# MAGIC - `leituras/` são **5 arquivos por ano** (2022–2026), unidos numa única tabela
# MAGIC - `inspecoes.xlsx` tem **3 abas** (`ago-set`, `dez`, `out-nov`) — consolidamos e guardamos `_aba_origem`
# MAGIC - CSVs são lidos como **string** (nada de inferir tipo na Bronze; tipo é decisão da Silver)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Dependências
# MAGIC `openpyxl` é necessário para ler o Excel de inspeções (não vem instalado por padrão).
# MAGIC Rode esta célula **antes de tudo** e, se reiniciar o Python, rode de novo.
# MAGIC Se depois do install o import ainda falhar, rode `dbutils.library.restartPython()` e execute o notebook do início.

# COMMAND ----------

# MAGIC %pip install openpyxl

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0.1. Parâmetros
# MAGIC Ajuste apenas `CATALOG` e `RAW` se necessário.
# MAGIC
# MAGIC Layout esperado do Volume (suba os arquivos exatamente assim):
# MAGIC ```
# MAGIC /Volumes/workspace/default/venergy/
# MAGIC ├── unidades_consumidoras.csv
# MAGIC ├── faturas.csv
# MAGIC ├── medidores.csv
# MAGIC ├── ocorrencias_rede.csv
# MAGIC ├── geracao_distribuida.csv
# MAGIC ├── inspecoes.xlsx
# MAGIC ├── atendimentos.json
# MAGIC └── leituras/
# MAGIC     ├── leituras_2022.csv ... leituras_2026.csv
# MAGIC ```

# COMMAND ----------

CATALOG = "workspace"          # na Free Edition o catálogo padrão é "workspace"
RAW = "/Volumes/workspace/default/venergy"   # ajuste se o seu Volume tiver outro nome

SCHEMA = "bronze"
ALVO = f"{CATALOG}.{SCHEMA}"

# COMMAND ----------

# Cria o schema da camada (idempotente)
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {ALVO}")
print(f"Schema pronto: {ALVO}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Funções auxiliares
# MAGIC - `add_audit`: colunas de rastreabilidade (qual arquivo veio, quando foi carregado)
# MAGIC - `write_bronze`: grava a tabela Delta e mostra a contagem de linhas
# MAGIC - `read_csv`: leitura padrão de CSV como texto, com suporte a separador e multiLine

# COMMAND ----------

from pyspark.sql import functions as F
from datetime import datetime, timezone

DATA_CARGA = datetime.now(timezone.utc)

def add_audit(df, origem):
    return (df
            .withColumn("_arquivo_origem", F.lit(origem))
            .withColumn("_data_carga", F.lit(DATA_CARGA).cast("timestamp")))

def write_bronze(df, tabela, origem):
    out = add_audit(df, origem)
    (out.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{ALVO}.{tabela}"))
    print(f"OK  {ALVO}.{tabela:<24} {out.count():>10,} linhas")

def read_csv(nome_arquivo, sep=","):
    return (spark.read
            .option("header", True)
            .option("inferSchema", False)   # Bronze = tudo string, preserva o original
            .option("sep", sep)
            .option("multiLine", True)
            .option("encoding", "UTF-8")
            .csv(f"{RAW}/{nome_arquivo}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. CSVs simples (separador vírgula)

# COMMAND ----------

for arquivo, tabela in [
    ("unidades_consumidoras.csv", "unidades_consumidoras"),
    ("medidores.csv",             "medidores"),
    ("ocorrencias_rede.csv",      "ocorrencias_rede"),
    ("geracao_distribuida.csv",   "geracao_distribuida"),
]:
    write_bronze(read_csv(arquivo), tabela, arquivo)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. `faturas.csv` — separador **ponto e vírgula**

# COMMAND ----------

write_bronze(read_csv("faturas.csv", sep=";"), "faturas", "faturas.csv")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. `leituras/` — 5 arquivos por ano, unidos numa tabela só
# MAGIC Cada linha guarda de qual arquivo anual ela veio (em `_arquivo_origem`).

# COMMAND ----------

leituras = None
for ano in range(2022, 2027):
    arquivo = f"leituras/leituras_{ano}.csv"
    df_ano = read_csv(arquivo)
    df_ano = df_ano.withColumn("_arquivo_origem", F.lit(arquivo))
    leituras = df_ano if leituras is None else leituras.unionByName(df_ano)

(leituras.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{ALVO}.leituras"))
print(f"OK  {ALVO}.leituras  {leituras.count():>10,} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. `atendimentos.json` — array JSON identado
# MAGIC `multiLine=true` por ser um único array formatado. Mantemos a estrutura **aninhada**:
# MAGIC desaninhar é trabalho da Silver.

# COMMAND ----------

atendimentos = (spark.read
                .option("multiLine", True)
                .json(f"{RAW}/atendimentos.json"))

write_bronze(atendimentos, "atendimentos", "atendimentos.json")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. `inspecoes.xlsx` — 3 abas consolidas
# MAGIC Spark não lê Excel nativamente, então usamos pandas + openpyxl e convertemos para Spark.
# MAGIC Guardamos `_aba_origem` para não perder de qual aba cada linha veio.

# COMMAND ----------

import pandas as pd

caminho_xlsx = f"{RAW}/inspecoes.xlsx"
abas = pd.read_excel(caminho_xlsx, sheet_name=None, dtype=str)  # dicionário {nome_aba: DataFrame}

partes = []
for nome_aba, dfp in abas.items():
    dfp = dfp.where(pd.notnull(dfp), None)
    dfp["_aba_origem"] = nome_aba
    partes.append(dfp)
    print(f"aba '{nome_aba}': {len(dfp):,} linhas | colunas: {list(dfp.columns)}")

inspecoes_pd = pd.concat(partes, ignore_index=True)
inspecoes = spark.createDataFrame(inspecoes_pd)

write_bronze(inspecoes, "inspecoes", "inspecoes.xlsx")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Conferência final
# MAGIC Lista as tabelas criadas e as contagens. Use isso no print do README.

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {ALVO}"))

# COMMAND ----------

for linha in spark.sql(f"SHOW TABLES IN {ALVO}").collect():
    nome = linha["tableName"]
    print(f"{nome:<26} {spark.table(f'{ALVO}.{nome}').count():>12,} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Próximos passos
# MAGIC 1. Conferir os números acima contra o esperado (unidades ~46 mil, leituras ~2,18 mi, faturas ~2,18 mi, atendimentos ~319 mil, ocorrências ~180 mil).
# MAGIC 2. Rodar o **perfilamento** (nulos, duplicatas, órfãos, datas inválidas) direto nestas tabelas bronze.
# MAGIC 3. Anotar cada problema encontrado — isso vira a seção de limpeza do dicionário de dados e a base da camada Silver.
