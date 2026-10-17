# Databricks notebook source
# MAGIC %md
# MAGIC # V-Energy Grid 360 — Camada Bronze
# MAGIC
# MAGIC **Objetivo:** ingerir as 8 fontes do dataset e gravar como tabelas Delta em `bronze.*`,
# MAGIC **preservando o conteúdo original** (sem tratar nada — limpeza é trabalho da Silver).
# MAGIC
# MAGIC **O que este notebook faz:**
# MAGIC - Lê todos os arquivos do Volume apontado em `RAW`
# MAGIC - Adiciona colunas de auditoria: `_arquivo_origem`, `_lote_id`, `_id_registro`, `_data_carga`
# MAGIC   (e `_aba_origem` nas inspeções)
# MAGIC - Grava uma tabela Delta por fonte (modo overwrite, para poder reexecutar)
# MAGIC - Captura registros malformados via `columnNameOfCorruptRecord` (schema explícito 100% string)
# MAGIC   → linhas válidas vão para a tabela da fonte, linhas rejeitadas vão para `bronze.rejeitados`
# MAGIC - Faz a **reconciliação** de cada tabela — linhas lidas × rejeitadas × gravadas → `bronze.reconciliacao`
# MAGIC
# MAGIC **Particularidades tratadas:**
# MAGIC - `faturas.csv` usa **ponto e vírgula** como separador
# MAGIC - `atendimentos.json` é um **array JSON identado** (precisa de `multiLine`) e fica **aninhado** na Bronze
# MAGIC - `leituras/` são **5 arquivos por ano** (2022–2026), unidos numa única tabela (`allowMissingColumns=True`)
# MAGIC - `inspecoes.xlsx` tem **3 abas** (`ago-set`, `dez`, `out-nov`) — consolidamos e guardamos `_aba_origem`
# MAGIC - CSVs são lidos como **string** (nada de inferir tipo na Bronze; tipo é decisão da Silver)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Decisões desta versão
# MAGIC 1. **Captura de registro malformado por coluna, não por arquivo lateral.** A leitura usa
# MAGIC    `columnNameOfCorruptRecord` (`_corrupt_record`) com schema explícito 100% string: o texto do
# MAGIC    registro ruim fica na própria linha, sem o Spark escrever arquivo de rejeitados fora do Delta.
# MAGIC    Racional e alternativas em `docs/decisions/0001-reconciliacao-e-captura-de-registros-malformados.md`.
# MAGIC 2. **Auditoria de lote e linha:** `_arquivo_origem`, `_lote_id`, `_id_registro`, `_data_carga`
# MAGIC    (e `_aba_origem` nas inspeções). `_id_registro` é o id técnico do lote, não o número da linha
# MAGIC    física do arquivo.
# MAGIC 3. **União anual tolerante:** `unionByName(..., allowMissingColumns=True)` — coluna ausente em um
# MAGIC    ano vira `null` em vez de derrubar a leitura.
# MAGIC 4. **Reconciliação por tabela:** `bronze.reconciliacao` fecha linhas físicas de origem ×
# MAGIC    rejeitadas × gravadas, e `bronze.rejeitados` guarda o bruto rejeitado.
# MAGIC 5. **Abas do Excel validadas** (`ago-set`/`dez`/`out-nov`) e **encoding/separador documentados**
# MAGIC    por arquivo (tabela abaixo).
# MAGIC
# MAGIC ### Encoding e separador por arquivo (decisão; conferência é manual)
# MAGIC | Arquivo | Formato | Encoding | Separador | Decisão |
# MAGIC |---|---|---|---|---|
# MAGIC | `unidades_consumidoras.csv` | CSV | UTF-8 | `,` | `read_csv` padrão |
# MAGIC | `medidores.csv` | CSV | UTF-8 | `,` | `read_csv` padrão |
# MAGIC | `ocorrencias_rede.csv` | CSV | UTF-8 | `,` | `read_csv` padrão |
# MAGIC | `geracao_distribuida.csv` | CSV | UTF-8 | `,` | `read_csv` padrão |
# MAGIC | `faturas.csv` | CSV | UTF-8 | `;` | `read_csv(sep=";")` |
# MAGIC | `leituras/leituras_2022..2026.csv` | CSV | UTF-8 | `,` | 5 arquivos unidos por `unionByName` |
# MAGIC | `atendimentos.json` | JSON array (multiLine) | UTF-8 | — | `read_json_com_corrupt` (mantém aninhado) |
# MAGIC | `inspecoes.xlsx` | XLSX (3 abas) | — | — | pandas + openpyxl |
# MAGIC
# MAGIC > A Bronze **não** detecta sozinha mudança de encoding/separador — por isso a tabela acima fica
# MAGIC > documentada e a conferência é manual (seção 4.1 da revisão).

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
# MAGIC     └── leituras_2022.csv ... leituras_2026.csv
# MAGIC ```
# MAGIC
# MAGIC > A pasta temporária `_autoteste_corrupt/` (do autoteste da seção 1.1) é criada e **removida** aqui
# MAGIC > dentro — não deixa resíduo no Volume nem interfere nas leituras (todas usam caminho explícito).

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
# MAGIC - `add_audit`: colunas de rastreabilidade (arquivo, lote, id do registro, quando carregou)
# MAGIC - `write_bronze`: grava a tabela Delta, mostra e **devolve** a contagem de linhas
# MAGIC - `descobrir_colunas`: lê só o cabeçalho de um CSV (leve, sem inferir tipo) para montar o schema
# MAGIC - `read_csv` / `read_json_com_corrupt`: leitura com schema explícito + `columnNameOfCorruptRecord`
# MAGIC - `separar_validos_rejeitados`: divide a leitura em linhas válidas e linhas rejeitadas
# MAGIC - `contar_linhas_arquivo`: linhas brutas do arquivo de origem (base do "lidas" na reconciliação,
# MAGIC   **independente** da leitura Spark — não depende da coluna de corrupção em nada)
# MAGIC - `registrar_reconciliacao`: monta 1 linha da reconciliação (lidas × rejeitadas × gravadas + delta)
# MAGIC
# MAGIC > **O que conta como malformado** (`UnivocityParser.convert`, Spark 3.5.0, código-fonte):
# MAGIC > `if (tokens.length != parsedSchema.length)` → registro malformado; também valor que não converte
# MAGIC > para o tipo declarado e falha de sintaxe (aspas/JSON). Com PERMISSIVE a linha malformada tem seu
# MAGIC > texto bruto capturado na coluna de corrupção (`_corrupt_record`) e os demais campos saem nulos.
# MAGIC > O `CSVFileFormat` **remove** a coluna de corrupção do schema antes de comparar o nº de campos
# MAGIC > (`actualDataSchema = dataSchema.filterNot(_.name == columnNameOfCorruptRecord)`), então a linha
# MAGIC > válida não é afetada pelo campo extra.
# MAGIC >
# MAGIC > ⚠️ **Sobre `QUERY_ONLY_CORRUPT_RECORD_COLUMN` (e por que `to_json` não bastou):** o Spark
# MAGIC > Connect recusa um plano cujo requiredSchema final — **depois de otimizado** — se reduz a só
# MAGIC > `_corrupt_record`. Trocar `.select("_corrupt_record")` por
# MAGIC > `.select(to_json(struct(*df.columns)))` não resolve por si só: se a ação terminal é `.count()`,
# MAGIC > o otimizador constata que NENHUM valor de coluna é lido (count só precisa de cardinalidade) e
# MAGIC > descarta a projeção inteira, voltando a exigir só a coluna do filtro. A regra que realmente
# MAGIC > evita o erro: **nunca `.count()` direto num DataFrame cujo filtro dependa só de
# MAGIC > `_corrupt_record`.** Use `bruto.count()` (sem filtro) + aritmética para dados grandes, ou
# MAGIC > `.collect()` (que exige valores reais, não só cardinalidade) para dados pequenos de teste.
# MAGIC >
# MAGIC > ⚠️ **JSON: a inferência anexa `_corrupt_record`.** `JsonInferSchema.withCorruptField` adiciona a
# MAGIC > coluna de corrupção ao schema inferido quando acha registro malformado. Por isso
# MAGIC > `read_json_com_corrupt` **deduplica** a coluna antes de montar o schema final (senão o schema
# MAGIC > ficaria com duas colunas de mesmo nome). E, se a inferência devolver **só** a coluna de corrupção
# MAGIC > (sem campos de dados), a função **falha com erro claro** em vez de gravar uma tabela vazia.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType, TimestampType
from datetime import datetime, timezone
from uuid import uuid4

DATA_CARGA = datetime.now(timezone.utc)
LOTE_ID = f"{DATA_CARGA.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
COLUNA_CORROMPIDA = "_corrupt_record"

reconciliacao = []          # linhas da reconciliação desta execução (vira a tabela bronze.reconciliacao)
rejeitados_coletados = []   # lista de DataFrames com os registros malformados desta execução

def add_audit(df, origem):
    """Colunas de rastreabilidade.

    `_id_registro` é um id técnico único DENTRO do lote (o Spark não expõe o nº da linha física do
    arquivo de origem sem um custo proibitivo de reparse) — serve para localizar a linha na tabela,
    não para reconstruir a posição no arquivo. A posição física continua recuperável pela
    reconciliação (`linhas_arquivo`/`cabecalhos`) e pelo `_arquivo_origem`.
    """
    return (df
            .withColumn("_arquivo_origem", F.lit(origem))
            .withColumn("_lote_id", F.lit(LOTE_ID))
            .withColumn("_id_registro", F.monotonically_increasing_id())
            .withColumn("_data_carga", F.lit(DATA_CARGA).cast("timestamp")))

def write_bronze(df, tabela, origem):
    """Grava a tabela Delta e devolve a contagem de linhas gravadas (conta a tabela já escrita,
    não reavalia o DataFrame — evita reparsear o CSV/JSON de origem uma segunda vez).

    Esta é uma das formas seguras de contar um DataFrame derivado de `_corrupt_record`: escrever
    força a materialização de valores reais (um sink nunca pode ser podado a "zero colunas"), e
    contar a tabela JÁ GRAVADA é uma operação Delta comum, sem nenhuma relação com arquivo raw.
    """
    out = add_audit(df, origem)
    (out.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{ALVO}.{tabela}"))
    n = spark.table(f"{ALVO}.{tabela}").count()
    print(f"OK  {ALVO}.{tabela:<24} {n:>10,} linhas")
    return n

def descobrir_colunas(caminho_relativo, sep=","):
    """Lê só o cabeçalho do CSV para descobrir os nomes de coluna — leitura leve, sem inferir tipo
    (precisamos dos NOMES para montar o schema explícito; os TIPOS continuam todos string)."""
    colunas = (spark.read
               .option("header", True)
               .option("sep", sep)
               .option("multiLine", True)
               .option("encoding", "UTF-8")
               .csv(f"{RAW}/{caminho_relativo}")
               .limit(0)
               .columns)
    # Defensivo: a inferência de CSV hoje NÃO anexa a coluna de corrupção (CSVInferSchema.infer),
    # mas se isso mudar o nome não pode entrar no schema de dados — viraria coluna duplicada.
    colunas = [c for c in colunas if c != COLUNA_CORROMPIDA]
    if not colunas:
        raise ValueError(f"Sem colunas de dados em {caminho_relativo} (arquivo vazio ou sem cabeçalho?).")
    return colunas

def read_csv(caminho_relativo, sep=","):
    """Lê um CSV como texto (schema 100% string) com `_corrupt_record` para capturar malformados.

    Precisa de schema explícito porque `columnNameOfCorruptRecord` exige isso — e como a Bronze já
    lê tudo como string, nenhuma inferência de tipo é perdida com essa exigência.

    O DataFrame devolvido NÃO tem filtro nenhum ainda — `.count()` nele é seguro (ver
    `separar_validos_rejeitados` e os blocos de cada fonte para o porquê disso importar).
    """
    colunas = descobrir_colunas(caminho_relativo, sep)
    schema = StructType(
        [StructField(c, StringType(), True) for c in colunas]
        + [StructField(COLUNA_CORROMPIDA, StringType(), True)]
    )
    return (spark.read
            .schema(schema)
            .option("header", True)
            .option("sep", sep)
            .option("multiLine", True)
            .option("encoding", "UTF-8")
            .option("columnNameOfCorruptRecord", COLUNA_CORROMPIDA)
            .option("mode", "PERMISSIVE")
            .csv(f"{RAW}/{caminho_relativo}"))

def read_json_com_corrupt(caminho_relativo):
    """Lê um JSON (array identado) com `_corrupt_record` para capturar elementos malformados.

    JSON não tem um "cabeçalho" para extrair nomes de coluna como o CSV, então inferimos o schema
    numa primeira leitura (padrão do Spark para JSON) e reaproveitamos esse schema, com a coluna de
    corrupção adicionada, na leitura final. Mantém a estrutura aninhada do `atendimentos.json` —
    desaninhar é trabalho da Silver.

    ⚠️ A inferência de JSON **anexa** `_corrupt_record` quando encontra registro malformado
    (`JsonInferSchema.withCorruptField`). Deduplicamos para não montar schema com coluna repetida.
    E se a inferência não devolver nenhum campo de dados (só a coluna de corrupção), é sinal de
    arquivo malformado: falhamos com mensagem clara em vez de gravar tabela vazia por engano.
    """
    caminho = f"{RAW}/{caminho_relativo}"
    schema_inferido = spark.read.option("multiLine", True).json(caminho).schema
    campos_dados = [f for f in schema_inferido.fields if f.name != COLUNA_CORROMPIDA]
    if not campos_dados:
        raise ValueError(
            f"Não consegui inferir o schema de dados de {caminho_relativo}: só a coluna de corrupção "
            f"(`{COLUNA_CORROMPIDA}`) foi inferida, o que indica registro malformado no arquivo. "
            "A Bronze não vai gravar uma tabela vazia por engano — investigue o arquivo de origem.")
    schema_com_corrupto = StructType(
        campos_dados + [StructField(COLUNA_CORROMPIDA, StringType(), True)]
    )
    return (spark.read
            .schema(schema_com_corrupto)
            .option("multiLine", True)
            .option("columnNameOfCorruptRecord", COLUNA_CORROMPIDA)
            .option("mode", "PERMISSIVE")
            .json(caminho))

def separar_validos_rejeitados(df, tabela, arquivo_origem):
    """Divide uma leitura em (válidos sem a coluna de corrupção, rejeitados com a linha original
    inteira serializada em JSON em `_registro`).

    ⚠️ NUNCA chame `.count()` diretamente em `validos` ou `rejeitados` — ambos vêm de um `.filter()`
    que depende só de `_corrupt_record`, e `.count()` não precisa do valor de nenhuma outra coluna,
    então o otimizador pode podar a projeção inteira e cair em `QUERY_ONLY_CORRUPT_RECORD_COLUMN`
    (isso vale mesmo com `to_json(struct(*))` na projeção — ver nota da seção 1). Formas seguras de
    saber quantas linhas têm cada um:
      - escrever (`write_bronze`) e contar a tabela JÁ GRAVADA — é o que acontece com `validos`;
      - para o total: `bruto.count()` SEM filtro (seguro) menos `gravadas` dá `rejeitadas`, por
        aritmética — nunca contando `rejeitados` direto;
      - em dados pequenos de teste: `.collect()` em vez de `.count()` — `.collect()` exige o valor
        real de cada linha, então o otimizador não pode podar a projeção.
    """
    validos = df.filter(F.col(COLUNA_CORROMPIDA).isNull()).drop(COLUNA_CORROMPIDA)
    rejeitados = (df.filter(F.col(COLUNA_CORROMPIDA).isNotNull())
                    .select(F.to_json(F.struct(*df.columns)).alias("_registro"))
                    .withColumn("_tabela_origem", F.lit(tabela))
                    .withColumn("_origem_rejeitados", F.lit(arquivo_origem))
                    .withColumn("_lote_id", F.lit(LOTE_ID))
                    .withColumn("_data_carga", F.lit(DATA_CARGA).cast("timestamp")))
    return validos, rejeitados

def contar_linhas_arquivo(*caminhos):
    """Linhas brutas (físicas) dos arquivos de origem — a base do 'lidas' da reconciliação.

    Vale como 'linhas de dados' depois de descontar 1 cabeçalho por arquivo. Assumimos que nenhum
    campo tem quebra de linha dentro (verificado nos 10 CSVs do case: registros == linhas físicas);
    se essa premissa deixar de valer, o `delta` sai de 0 e o status vira `INVESTIGAR` — é o alarme
    desenhado para isso.

    No Databricks, `mode` NÃO pode ser definido junto com `badRecordsPath` (erro
    "If 'badRecordsPath' is specified, 'mode' is not allowed to set") — por isso nenhuma leitura
    aqui usa `badRecordsPath`.

    Esta contagem é por `spark.read.text(...)`, totalmente alheia ao schema com `_corrupt_record` —
    por isso serve como verificação INDEPENDENTE na reconciliação (não é derivada de `bruto.count()`
    nem de `gravadas`).
    """
    return sum(spark.read.text(f"{RAW}/{c}").count() for c in caminhos)

def registrar_reconciliacao(tabela, arquivo_origem, linhas_arquivo, cabecalhos, rejeitadas, gravadas,
                            status=None, linhas_dados=None):
    """Registra 1 linha da reconciliação.

    `linhas_dados` normalmente sai de `linhas_arquivo - cabecalhos` (contagem FÍSICA de linhas do
    arquivo, via `spark.read.text`). Para fontes sem conceito de "linha física" (JSON identado;
    Excel lido por pandas) ele pode ser passado direto e `linhas_arquivo` fica `None`.

    `delta = linhas_dados - gravadas - rejeitadas`. Como `rejeitadas = total_lido - gravadas` é
    derivado por aritmética (nunca de `.count()` na coluna de corrupção), o delta acaba medindo
    `linhas_dados - total_lido`: é o confronto entre a contagem FÍSICA independente
    (`spark.read.text`) e o número de linhas que o parser devolveu.
    """
    if linhas_dados is None and linhas_arquivo is not None:
        linhas_dados = linhas_arquivo - cabecalhos
    delta = None if linhas_dados is None else linhas_dados - gravadas - rejeitadas
    if status is None:
        if linhas_dados is None:
            status = "SEM_BASE"      # sem "linhas físicas" comparáveis (JSON multiLine)
        elif rejeitadas < 0:
            status = "INVESTIGAR"    # gravadas > total lido: sinal de bug na contagem
        elif delta == 0:
            status = "OK"
        elif rejeitadas > 0 and delta == -rejeitadas:
            status = "ATENCAO"       # guarda legada (PERMISSIVE); hoje inalcançável por construção
        else:
            status = "INVESTIGAR"
    reconciliacao[:] = [r for r in reconciliacao if r["_tabela"] != tabela]   # reexecução não duplica
    reconciliacao.append(dict(
        _tabela=tabela, _arquivo_origem=arquivo_origem,
        linhas_arquivo=linhas_arquivo, cabecalhos=cabecalhos, linhas_dados=linhas_dados,
        rejeitadas=rejeitadas, gravadas=gravadas, delta=delta,
        status=status, _data_carga=DATA_CARGA))
    print(f"REC {tabela:<24} lidas={(linhas_dados if linhas_dados is not None else 'n/d'):>10} "
          f"rejeitadas={rejeitadas:>6} gravadas={gravadas:>10} "
          f"delta={(delta if delta is not None else 'n/d'):>7}  {status}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.1. Autoteste de registros malformados
# MAGIC O Spark **ignora opções que não conhece**, sem erro — então "0 rejeitados" nas tabelas reais
# MAGIC só vale alguma coisa se o mecanismo de captura estiver comprovadamente funcionando neste
# MAGIC runtime. O autoteste roda as **mesmas funções de produção** (`read_csv`,
# MAGIC `read_json_com_corrupt`, `separar_validos_rejeitados`) contra arquivos com entradas
# MAGIC malformadas **garantidas por construção**, e confere a contagem exata.
# MAGIC
# MAGIC **CSV** — cabeçalho `id,nome` + 3 linhas de dados:
# MAGIC `1,ok` (válida), `3,ok,EXTRA` (3 campos ≠ 2) e `7` (1 campo ≠ 2). O Spark marca as duas
# MAGIC últimas como malformadas (`UnivocityParser.convert`: `tokens.length != schema.length`).
# MAGIC Esperado: **válidas = 1, rejeitadas = 2**.
# MAGIC
# MAGIC **JSON** — uma **pasta** com 2 documentos `multiLine`: `ok.json` = `{"id": "1", "nome": "ok"}`
# MAGIC (válido) e `ruim.json` = `{"id": "quebrado}` (string não fechada ⇒ erro de sintaxe garantido).
# MAGIC Esperado: **válidas = 1, rejeitadas = 1**.
# MAGIC
# MAGIC > ⚠️ Por que **dois arquivos** no JSON (e não um array com um elemento quebrado): a inferência
# MAGIC > de schema do JSON, ao ver um registro malformado, devolve **só** a coluna de corrupção e perde
# MAGIC > os campos de dados (`JsonInferSchema.handleJsonErrorsByParseMode` + `withCorruptField`). Com
# MAGIC > um arquivo válido ao lado, o schema de dados é aprendido por ele e o quebrado é capturado como
# MAGIC > rejeitado — que é exatamente o que se quer provar.
# MAGIC
# MAGIC **Aqui usamos `.collect()`, não `.count()`**, para medir válidos/rejeitados — com poucas
# MAGIC linhas de teste isso é barato, e `.collect()` exige o valor real de cada linha, então o
# MAGIC otimizador não pode podar a projeção (ver nota da seção 1).
# MAGIC
# MAGIC > **Classificação (deliberadamente estrita):** as entradas são malformadas **por construção**,
# MAGIC > então "nada foi marcado nos dois leitores" é **FALHA**, não "inconclusivo". `PARCIAL` é quando
# MAGIC > só um dos dois leitores honra a coluna. `ERRO` é quando o autoteste não chega a rodar.
# MAGIC
# MAGIC > **Histórico de versões (17/10):** v1 (aspas não fechadas) saiu `INCONCLUSIVO` — o parser
# MAGIC > aceitou a linha como válida (em `multiLine`, a aspa aberta engole o resto do arquivo e a
# MAGIC > contagem de campos até fecha). v2 (`abc` em coluna `INT` + `badRecordsPath`) provou a
# MAGIC > corrupção mas o `badRecordsPath` gravou 0 bytes → **mecanismo morto neste runtime**. v3–v6
# MAGIC > tentaram materializar de várias formas (`.count()` direto → `QUERY_ONLY_CORRUPT_RECORD_COLUMN`;
# MAGIC > `.cache()` → `NOT_SUPPORTED_WITH_SERVERLESS`; tabela/path de staging → `TABLE_OR_VIEW_NOT_FOUND`
# MAGIC > / `PATH_NOT_FOUND`). **v7** trocou a contagem por `bruto.count()` (sem filtro) + aritmética.
# MAGIC > **v8 (esta)**: consertou a inferência duplicada do JSON e usa entradas/contagens exatas.

# COMMAND ----------

def autoteste_corrupt_record():
    """Confirma que `columnNameOfCorruptRecord` captura registros malformados neste runtime,
    usando as mesmas funções que as 8 tabelas reais usam — não uma implementação à parte.

    Usa `.collect()` em vez de `.count()` para medir válidos/rejeitados (ver nota da seção 1.1).

    Devolve (status, rejeitadas_csv, rejeitadas_json, gravadas_total, detalhe), em que
    `gravadas_total` soma as linhas válidas dos dois leitores.
    """
    pasta_abs = f"{RAW}/_autoteste_corrupt"
    csv_rel = "_autoteste_corrupt/teste.csv"
    json_dir_rel = "_autoteste_corrupt/json"

    # (válidas, rejeitadas) — a corrupção é CERTA por construção da entrada
    esperado_csv = (1, 2)
    esperado_json = (1, 1)

    try:
        dbutils.fs.mkdirs(pasta_abs)
        dbutils.fs.mkdirs(f"{RAW}/{json_dir_rel}")
        dbutils.fs.put(f"{RAW}/{csv_rel}", "id,nome\n1,ok\n3,ok,EXTRA\n7\n", True)
        dbutils.fs.put(f"{RAW}/{json_dir_rel}/ok.json", '{"id": "1", "nome": "ok"}\n', True)
        dbutils.fs.put(f"{RAW}/{json_dir_rel}/ruim.json", '{"id": "quebrado}\n', True)  # string não fechada

        bruto_csv = read_csv(csv_rel)
        validos_csv, rejeitados_csv_df = separar_validos_rejeitados(bruto_csv, "_autoteste", csv_rel)
        gravadas_csv = len(validos_csv.collect())
        rejeitadas_csv = len(rejeitados_csv_df.collect())

        bruto_json = read_json_com_corrupt(json_dir_rel)
        validos_json, rejeitados_json_df = separar_validos_rejeitados(bruto_json, "_autoteste", json_dir_rel)
        gravadas_json = len(validos_json.collect())
        rejeitadas_json = len(rejeitados_json_df.collect())

        csv_ok = (gravadas_csv, rejeitadas_csv) == esperado_csv
        json_ok = (gravadas_json, rejeitadas_json) == esperado_json

        detalhe = (f"CSV: válidas={gravadas_csv} rejeitadas={rejeitadas_csv} "
                   f"(esperado {esperado_csv[0]}/{esperado_csv[1]}) | "
                   f"JSON: válidas={gravadas_json} rejeitadas={rejeitadas_json} "
                   f"(esperado {esperado_json[0]}/{esperado_json[1]})")

        gravadas_total = gravadas_csv + gravadas_json

        if csv_ok and json_ok:
            return "OK", rejeitadas_csv, rejeitadas_json, gravadas_total, detalhe + " | coluna honrada nos 2 leitores"
        if rejeitadas_csv == 0 and rejeitadas_json == 0:
            return "FALHA", rejeitadas_csv, rejeitadas_json, gravadas_total, \
                   detalhe + " | corrupção certa e nada marcado — mecanismo não vale aqui"
        divergiu = ", ".join(nome for nome, ok in (("CSV", csv_ok), ("JSON", json_ok)) if not ok)
        return "PARCIAL", rejeitadas_csv, rejeitadas_json, gravadas_total, detalhe + f" | divergiu em: {divergiu}"
    except Exception as e:
        return "ERRO", 0, 0, 0, f"autoteste falhou: {e}"
    finally:
        try:
            dbutils.fs.rm(pasta_abs, True)   # limpa o teste (não sobra lixo no Volume)
        except Exception:
            pass

# COMMAND ----------

_status_teste, _rej_csv_teste, _rej_json_teste, _grav_teste, _detalhe_teste = autoteste_corrupt_record()
print(f"AUTOTESTE registros malformados: {_status_teste} — {_detalhe_teste}")
if _status_teste != "OK":
    print("AVISO: sem mecanismo confiável, registro malformado passa batido em silêncio "
          "— `rejeitadas = 0` nas tabelas abaixo NÃO é garantia de nada.")

registrar_reconciliacao("_autoteste_badrecords", "_autoteste_corrupt/"
                        "{teste.csv,json/ok.json,json/ruim.json}",
                        linhas_arquivo=None, cabecalhos=0,
                        rejeitadas=_rej_csv_teste + _rej_json_teste, gravadas=_grav_teste,
                        status=f"AUTOTESTE_{_status_teste}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. CSVs simples (separador vírgula)
# MAGIC `total_lida = bruto.count()` é seguro (nenhum filtro na coluna de corrupção ainda).
# MAGIC `rejeitadas` sai por aritmética (`total_lida - gravadas`), nunca de `rejeitados.count()`.

# COMMAND ----------

for arquivo, tabela in [
    ("unidades_consumidoras.csv", "unidades_consumidoras"),
    ("medidores.csv",             "medidores"),
    ("ocorrencias_rede.csv",      "ocorrencias_rede"),
    ("geracao_distribuida.csv",   "geracao_distribuida"),
]:
    bruto = read_csv(arquivo)
    total_lida = bruto.count()
    validos, rejeitados = separar_validos_rejeitados(bruto, tabela, arquivo)
    gravadas = write_bronze(validos, tabela, arquivo)
    rejeitadas = total_lida - gravadas
    rejeitados_coletados.append(rejeitados)
    registrar_reconciliacao(tabela, arquivo,
                            linhas_arquivo=contar_linhas_arquivo(arquivo),
                            cabecalhos=1,
                            rejeitadas=rejeitadas,
                            gravadas=gravadas)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. `faturas.csv` — separador **ponto e vírgula**

# COMMAND ----------

bruto = read_csv("faturas.csv", sep=";")
total_lida = bruto.count()
validos, rejeitados = separar_validos_rejeitados(bruto, "faturas", "faturas.csv")
gravadas = write_bronze(validos, "faturas", "faturas.csv")
rejeitadas = total_lida - gravadas
rejeitados_coletados.append(rejeitados)
registrar_reconciliacao("faturas", "faturas.csv",
                        linhas_arquivo=contar_linhas_arquivo("faturas.csv"),
                        cabecalhos=1,
                        rejeitadas=rejeitadas,
                        gravadas=gravadas)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. `leituras/` — 5 arquivos por ano, unidos numa tabela só
# MAGIC Cada linha guarda de qual arquivo anual ela veio (em `_arquivo_origem`). Cada arquivo anual é
# MAGIC lido com seu próprio schema (colunas descobertas por arquivo), então uma diferença de colunas
# MAGIC entre anos não quebra a leitura individual.
# MAGIC
# MAGIC **A1 resolvido:** o `unionByName` usa `allowMissingColumns=True` — coluna ausente num ano vira
# MAGIC `null` nas linhas daquele ano em vez de derrubar o pipeline. **Isso não substitui** investigar
# MAGIC se os anos realmente têm esquemas diferentes: se este union passar a introduzir nulos
# MAGIC inesperados, é sinal de variante de schema real entre anos.
# MAGIC
# MAGIC `total_lida_leituras` soma `bruto.count()` de cada um dos 5 arquivos (cada um sem filtro —
# MAGIC seguro); `rejeitadas` sai por aritmética sobre a soma, nunca de `.count()` nos rejeitados.
# MAGIC
# MAGIC `_lote_id`/`_id_registro`/`_data_carga` são adicionados **depois** do laço, para não sobrescrever
# MAGIC o `_arquivo_origem` por ano (a Silver usa `_data_carga` no `orderBy` da deduplicação).

# COMMAND ----------

arquivos_leituras = [f"leituras/leituras_{ano}.csv" for ano in range(2022, 2027)]

leituras_validas = None
leituras_rejeitadas = None
total_lida_leituras = 0
for arquivo in arquivos_leituras:
    bruto = read_csv(arquivo)
    total_lida_leituras += bruto.count()
    validos, rejeitados = separar_validos_rejeitados(bruto, "leituras", arquivo)
    validos = validos.withColumn("_arquivo_origem", F.lit(arquivo))
    leituras_validas = (validos if leituras_validas is None
                        else leituras_validas.unionByName(validos, allowMissingColumns=True))
    leituras_rejeitadas = (rejeitados if leituras_rejeitadas is None
                           else leituras_rejeitadas.unionByName(rejeitados))

# Auditoria do lote: `_lote_id` + `_id_registro` + `_data_carga` (o `_arquivo_origem` já veio por ano).
leituras_validas = (leituras_validas
                    .withColumn("_lote_id", F.lit(LOTE_ID))
                    .withColumn("_id_registro", F.monotonically_increasing_id())
                    .withColumn("_data_carga", F.lit(DATA_CARGA).cast("timestamp")))

(leituras_validas.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{ALVO}.leituras"))
gravadas = spark.table(f"{ALVO}.leituras").count()   # conta a tabela (não reparseia os CSVs)
print(f"OK  {ALVO}.leituras  {gravadas:>10,} linhas")

rejeitadas = total_lida_leituras - gravadas
rejeitados_coletados.append(leituras_rejeitadas)
registrar_reconciliacao("leituras", "leituras/*.csv",
                        linhas_arquivo=contar_linhas_arquivo(*arquivos_leituras),
                        cabecalhos=len(arquivos_leituras),
                        rejeitadas=rejeitadas,
                        gravadas=gravadas)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. `atendimentos.json` — array JSON identado
# MAGIC `multiLine=true` por ser um único array formatado. Mantemos a estrutura **aninhada**:
# MAGIC desaninhar é trabalho da Silver. Reconciliação: JSON identado **não tem** "linhas físicas"
# MAGIC comparáveis ao nº de registros, então o delta fica sem base (`SEM_BASE`) — valem as contagens
# MAGIC de rejeitadas e gravadas.
# MAGIC
# MAGIC > Se este arquivo passar a ter um elemento malformado, a inferência de schema degrada para
# MAGIC > "só a coluna de corrupção" e `read_json_com_corrupt` **falha com erro claro** (em vez de
# MAGIC > gravar a tabela vazia). O erro aponta o arquivo para investigação.

# COMMAND ----------

bruto = read_json_com_corrupt("atendimentos.json")
total_lida = bruto.count()
validos, rejeitados = separar_validos_rejeitados(bruto, "atendimentos", "atendimentos.json")
gravadas = write_bronze(validos, "atendimentos", "atendimentos.json")
rejeitadas = total_lida - gravadas
rejeitados_coletados.append(rejeitados)
registrar_reconciliacao("atendimentos", "atendimentos.json",
                        linhas_arquivo=None,
                        cabecalhos=0,
                        rejeitadas=rejeitadas,
                        gravadas=gravadas)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. `inspecoes.xlsx` — 3 abas consolidadas
# MAGIC Spark não lê Excel nativamente, então usamos pandas + openpyxl e convertemos para Spark com
# MAGIC **schema explícito 100% string** (garante "Bronze = tudo string" e evita que uma coluna vazia
# MAGIC vire `NullType`, que o Delta recusaria gravar). Guardamos `_aba_origem` para não perder de qual
# MAGIC aba cada linha veio.
# MAGIC
# MAGIC **A4:** as 3 abas esperadas são `ago-set`, `out-nov` e `dez` (recortes de período do arquivo);
# MAGIC o **grão é 1 linha por inspeção**. Se o conjunto de abas diferir, o notebook avisa (não falha),
# MAGIC porque o arquivo pode ter sido atualizado.
# MAGIC
# MAGIC `rejeitadas = 0` aqui é **por construção**: o leitor de Excel (pandas/openpyxl) não tem
# MAGIC `badRecordsPath`/`columnNameOfCorruptRecord` — linha ruim dá exceção visível, não é descartada
# MAGIC em silêncio. A reconciliação usa `linhas_dados = nº de registros lidos` (o conceito de "linha
# MAGIC física do arquivo" não se aplica a um XLSX), por isso `linhas_arquivo` fica `None`.

# COMMAND ----------

import pandas as pd

caminho_xlsx = f"{RAW}/inspecoes.xlsx"
abas = pd.read_excel(caminho_xlsx, sheet_name=None, dtype=str, engine="openpyxl")

ABAS_ESPERADAS = {"ago-set", "dez", "out-nov"}
abas_encontradas = set(abas.keys())
if abas_encontradas != ABAS_ESPERADAS:
    print(f"AVISO (A4): abas encontradas {sorted(abas_encontradas)} != esperadas {sorted(ABAS_ESPERADAS)} "
          "— confira se o arquivo mudou.")

partes = []
for nome_aba, dfp in abas.items():
    dfp = dfp.where(pd.notnull(dfp), None)
    dfp["_aba_origem"] = nome_aba
    partes.append(dfp)
    print(f"aba '{nome_aba}': {len(dfp):,} linhas | colunas: {list(dfp.columns)}")

inspecoes_pd = pd.concat(partes, ignore_index=True)
# `pd.concat` de abas com colunas diferentes REINTRODUZ NaN onde a coluna não existia na aba.
# Converter de novo para None aqui (não só por aba) — um NaN num campo string quebraria o
# `createDataFrame` com schema StringType abaixo.
inspecoes_pd = inspecoes_pd.where(pd.notnull(inspecoes_pd), None)

# Schema explícito (tudo string) — evita inferência de tipo e coluna 100% vazia virando NullType.
# Convertemos via lista de tuplas (1,4 mil linhas — barato) em vez de pandas+schema, para não
# depender da compatibilidade Arrow/schema do Connect.
schema_inspecoes = StructType([StructField(c, StringType(), True) for c in inspecoes_pd.columns])
linhas_inspecoes = list(inspecoes_pd.itertuples(index=False, name=None))
inspecoes = spark.createDataFrame(linhas_inspecoes, schema=schema_inspecoes)

gravadas = write_bronze(inspecoes, "inspecoes", "inspecoes.xlsx")
registrar_reconciliacao("inspecoes", "inspecoes.xlsx",
                        linhas_arquivo=None,          # XLSX não tem "linha física" comparável
                        cabecalhos=0,
                        rejeitadas=0,
                        gravadas=gravadas,
                        linhas_dados=len(inspecoes_pd))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6.1. Rejeitados e reconciliação (auditoria do lote)
# MAGIC - **`bronze.rejeitados`**: todo registro malformado capturado via `columnNameOfCorruptRecord`,
# MAGIC   com a linha original (serializada em JSON) e identificado por lote/tabela/arquivo de origem.
# MAGIC - **`bronze.reconciliacao`**: uma linha por tabela com `linhas_arquivo`, `cabecalhos`,
# MAGIC   `linhas_dados`, `rejeitadas`, `gravadas`, `delta` e `status`. O `delta` deve fechar em **0**
# MAGIC   (`status = OK`); `SEM_BASE` (JSON identado) é esperado. A linha `_autoteste_badrecords` é o
# MAGIC   resultado do autoteste da seção 1.1.
# MAGIC
# MAGIC A contagem final de `bronze.rejeitados` é feita **na tabela já gravada**, nunca em
# MAGIC `rejeitados_df.count()` direto — pelo mesmo motivo explicado na seção 1: a união de todos os
# MAGIC `rejeitados` ainda carrega o filtro em `_corrupt_record`, então `.count()` nela cairia na mesma
# MAGIC restrição. A escrita (`.write`) é segura porque precisa dos valores reais; a leitura da tabela
# MAGIC Delta depois é uma operação comum, sem relação com arquivo raw.

# COMMAND ----------

if rejeitados_coletados:
    rejeitados_df = rejeitados_coletados[0]
    for parte in rejeitados_coletados[1:]:
        rejeitados_df = rejeitados_df.unionByName(parte)

    (rejeitados_df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{ALVO}.rejeitados"))
    n_rejeitados_total = spark.table(f"{ALVO}.rejeitados").count()   # conta a tabela gravada, não o DataFrame
    print(f"OK  {ALVO}.rejeitados  {n_rejeitados_total:>10,} registros rejeitados")
else:
    print("Sem fontes com rejeitados a consolidar.")

# COMMAND ----------

recon_schema = StructType([
    StructField("_tabela", StringType(), False),
    StructField("_arquivo_origem", StringType(), False),
    StructField("linhas_arquivo", LongType(), True),
    StructField("cabecalhos", LongType(), False),
    StructField("linhas_dados", LongType(), True),
    StructField("rejeitadas", LongType(), False),
    StructField("gravadas", LongType(), False),
    StructField("delta", LongType(), True),
    StructField("status", StringType(), False),
    StructField("_data_carga", TimestampType(), False),
])

recon_df = spark.createDataFrame(
    [tuple(r[campo.name] for campo in recon_schema.fields) for r in reconciliacao],
    recon_schema)

(recon_df.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{ALVO}.reconciliacao"))
display(recon_df)

# COMMAND ----------

pendentes = [r for r in reconciliacao
             if not r["_tabela"].startswith("_") and r["status"] not in ("OK", "SEM_BASE")]
total_rejeitadas = sum(r["rejeitadas"] for r in reconciliacao if not r["_tabela"].startswith("_"))
_status_autoteste = globals().get("_status_teste", "NAO_RODADO")
if pendentes:
    print(f"ATENÇÃO: {len(pendentes)} tabela(s) com reconciliação fora do esperado:")
    for r in pendentes:
        print(f"  - {r['_tabela']}: delta={r['delta']} ({r['status']})")
if total_rejeitadas:
    print(f"ATENÇÃO: {total_rejeitadas:,} registro(s) malformado(s) capturado(s) "
          f"→ ver {ALVO}.rejeitados (bruto, com arquivo e lote).")
if _status_autoteste != "OK":
    print(f"ATENÇÃO: autoteste de registros malformados = {_status_autoteste} — "
          "com o mecanismo de captura do runtime, `rejeitadas = 0` nas tabelas acima "
          "NÃO é garantia de que não passou registro malformado batido.")
if not pendentes and not total_rejeitadas and _status_autoteste == "OK":
    print("Reconciliação OK: nenhum registro rejeitado e todas as tabelas fecharam (lidas = gravadas).")
elif not pendentes and _status_autoteste == "OK":
    print("Deltas fechados em todas as tabelas; registros rejeitados foram capturados e preservados "
          f"em {ALVO}.rejeitados.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Conferência final
# MAGIC Lista as tabelas criadas e as contagens. Use isso no print do README.
# MAGIC
# MAGIC O schema de destino pode ser compartilhado com outros trabalhos; a contagem abaixo considera
# MAGIC **apenas** as tabelas desta ingestão (as demais não entram nem quebram a conferência).

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {ALVO}"))

# COMMAND ----------

TABELAS_BRONZE = [
    "unidades_consumidoras", "medidores", "ocorrencias_rede", "geracao_distribuida",
    "faturas", "leituras", "atendimentos", "inspecoes", "reconciliacao", "rejeitados",
]

for nome in TABELAS_BRONZE:
    try:
        print(f"{nome:<26} {spark.table(f'{ALVO}.{nome}').count():>12,} linhas")
    except Exception as e:
        print(f"{nome:<26} AUSENTE/erro: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Próximos passos
# MAGIC 1. Conferir os números acima contra o esperado (unidades ~46 mil, leituras ~2,18 mi, faturas ~2,18 mi, atendimentos ~319 mil, ocorrências ~180 mil).
# MAGIC 2. Conferir `bronze.reconciliacao`: `delta = 0` em todas as tabelas (a linha de `atendimentos` sai como `SEM_BASE`, esperado; a de `inspecoes` também fecha, com `linhas_arquivo = null`) e `AUTOTESTE_OK` na linha `_autoteste_badrecords` — se não vier `OK`, os `rejeitadas = 0` do dataset real não têm garantia nenhuma, não assuma que o dataset está limpo.
# MAGIC 3. Conferir `bronze.rejeitados`: se vier com linhas, são registros malformados reais do dataset — decidir com a Silver o que fazer com eles (hoje eles só ficam de fora das tabelas da fonte, não têm tratamento).
# MAGIC 4. **Feito nesta versão:** união anual tolerante, colunas de auditoria (`_lote_id`/`_id_registro`/`_data_carga`), validação das abas do Excel, tabela de encoding/separador e a captura de corrupção por `_corrupt_record`.
# MAGIC 5. **Ainda em aberto:** decidir com a Silver a quarentena dos rejeitados, registrar as regras de negócio como hipóteses no dicionário e concluir as melhorias do `02_perfilamento.py`. As colunas `_lote_id`/`_id_registro` já entraram na lista `AUDITORIA` do perfilamento.
# MAGIC 6. Rodar o **perfilamento** (nulos, duplicatas, órfãos, datas inválidas) direto nestas tabelas bronze e a **Silver** em seguida.
