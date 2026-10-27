# DEV-12 — Carga sintética, auditoria e recuperação

Requisito DE-06; dependência DEV-01. Esta entrega valida a infraestrutura com dados artificiais. O aceite completo de DE-06 continua dependendo da reconciliação Databricks → CSV → banco e da homologação do esquema/métricas. A integração dos consumidores fica na DEV-13.

## Identidade e contrato

O identificador `--batch` tem de 1 a 100 caracteres ASCII entre letras, números, ponto, hífen e sublinhado. A versão suportada é `gold-csv-v1`, informada por `--schema-version` e persistida no lote atual e nas tentativas. Versão desconhecida é recusada antes de alterar a publicação. O SHA-256 identifica o conteúdo e o inventário dos arquivos, separadamente do nome do lote. Cada execução recebe um UUID `attempt_id`, inclusive as repetições sem alteração.

São esperadas sete pastas, com um ou mais arquivos `*.csv` por pasta: `consumo_mensal_uc`, `consumo_receita_bairro`, `diagnostico_receita`, `fila_inspecao`, `indicadores_dec_fec`, `variacao_consumo_uc` e `visao_360_uc`. Os cabeçalhos e chaves estão no [contrato físico v1](gold-csv-v1.md). Partes adicionais da mesma tabela são aceitas e entram nos hashes; as chaves são únicas no conjunto, não apenas dentro de cada arquivo. Arquivos auxiliares e pastas fora desse inventário não são importados.

O [snapshot v1](../../backend/app/models/gold_v1.py) usa metadados próprios para preservar a revisão histórica `goldv1000001`. Os [modelos atuais](../../backend/app/models/gold_load.py) copiam esse esquema e acrescentam versão/auditoria. A revisão `goldv1000002` atualiza bancos existentes; atribui `gold-csv-v1` aos lotes da revisão anterior sem reimportar nem alterar seus fatos. Para um esquema Gold futuro, criar nova revisão e mapeamento explícito; não editar o snapshot ou aceitar uma nova versão apenas trocando a string.

## Publicação e auditoria

`gold_carga_atual` representa somente a versão publicada: lote, versão de esquema, fingerprint, data da importação local e manifesto com arquivos/hashes, contagens e totais validados. É atualizado na mesma transação das sete tabelas. Esse instante não é data de processamento da origem.

`gold_carga_tentativas` conserva uma linha por execução, com UUID, lote/versão solicitados quando sintaticamente válidos, início/fim, fingerprint quando disponível, manifesto de progresso e erro público. Identificadores inválidos não são copiados para a auditoria. Os estados são:

- `running`: tentativa registrada, sem conclusão confirmada. Não significa lote válido.
- `loaded`: sete tabelas e metadados publicados e auditoria confirmada na mesma transação.
- `unchanged`: arquivos, lote e versão já correspondem à publicação atual. Os fatos, totais e instante original de publicação são preservados; só uma nova tentativa é registrada.
- `failed`: carga rejeitada e rollback concluído antes do registro do erro, em uma transação separada. A publicação válida anterior permanece íntegra; sem versão anterior, nenhuma é criada.

O manifesto da tentativa usa `rows` para linhas convertidas do CSV e `totals` para controles dessas linhas. `validated=true` indica que aquela tabela passou nos controles CSV/banco dentro da tentativa; não afirma que uma tentativa `failed` foi publicada. O manifesto pode ser parcial se a falha ocorrer antes de ler todas as tabelas. Os totais são strings decimais; nomes de arquivos e hashes são metadados, sem conteúdo de linhas.

A finalização só transita a partir de `running`; não sobrescreve sucesso já confirmado. Falha ao registrar o início impede a carga. Falha ao registrar o sucesso reverte a publicação. Se o banco estiver inacessível também ao registrar uma falha, o CLI informa `audit_unavailable` e o UUID; a tentativa pode continuar `running`. Encerramento abrupto do processo também pode deixá-la assim. Consulte a publicação antes de concluir o resultado ou repetir: uma perda de confirmação no commit exige reconciliação, não suposição de falha.

No PostgreSQL, importadores são serializados pelo lock transacional existente. SQLite admite somente um importador por vez. A carga nunca remove ou atualiza `gold_indicadores`, ordens, histórico operacional ou tentativas anteriores.

## Reprodução com CSVs sintéticos

Na pasta `backend/`, use um banco local isolado. O gerador só aceita um diretório novo e não sobrescreve arquivos existentes:

```powershell
$env:APP_ENV = "development"
$env:ANALYTICS_SOURCE = "unavailable"
$env:ORDERS_AUTH_MODE = "service"
$env:DATABASE_URL = "sqlite:///../work/dev12-sintetico.db"
venv/Scripts/python.exe scripts/generate_gold_sample.py --directory ../work/dev12-lote-01
venv/Scripts/python.exe -m alembic upgrade head
venv/Scripts/python.exe scripts/load_gold.py --directory ../work/dev12-lote-01 --batch sintetico-001 --schema-version gold-csv-v1
venv/Scripts/python.exe scripts/load_gold.py --directory ../work/dev12-lote-01 --batch sintetico-001 --schema-version gold-csv-v1
```

A primeira carga retorna JSON com `status=loaded`; a segunda, `status=unchanged`, com UUIDs distintos. O controle independente da amostra é: duas linhas mensais/UCs, 30 kWh e R$ 25,50; demais seis tabelas têm uma linha cada. Esse controle não representa métricas do dataset real.

Para inspecionar com seu cliente SQL, sem consultar linhas de negócio:

```sql
SELECT lote, schema_version, fingerprint, importado_em FROM gold_carga_atual;
SELECT id, lote, schema_version, status, iniciado_em, finalizado_em,
       erro_codigo, erro_mensagem, manifesto
FROM gold_carga_tentativas ORDER BY iniciado_em DESC, id;
```

O CLI retorna 0 em `loaded`/`unchanged`; 1 em falhas da carga, com código e UUID no stderr; argumentos inválidos do argparse retornam 2 antes de iniciar tentativa. Não imprime valores de registros, SQL ou parâmetros do banco.

## Falhas e recuperação

1. **Cabeçalho, tipo, chave vazia/duplicada, tabela ausente/vazia ou totais divergentes:** a execução termina com `failed`. Consulte código, mensagem e manifesto da tentativa; corrija/reexporte o lote inteiro, preserve-o estável e execute novamente. Rejeições de tipos mostram tabela e número do registro, sem seu conteúdo. Duplicidades/restrições usam `constraint_error`; demais validações físicas, `validation_error`.
2. **Versão ou identificador inválidos:** `unsupported_schema`/`invalid_batch`, sem tocar a publicação. Use o identificador válido e o mapeamento suportado. Não renomeie uma versão futura para fazê-la passar.
3. **Arquivo ilegível, encoding/CSV malformado ou arquivo alterado durante a carga:** estabilize os arquivos e a leitura antes de repetir. Erros de leitura usam `file_error`; mudança detectada pelos hashes rejeita a carga. Não desabilite os controles.
4. **Banco indisponível, migração ausente ou auditoria indisponível:** restabeleça conexão, aplique `alembic upgrade head` e consulte a tentativa e `gold_carga_atual`. O código `database_error` não expõe SQL. Em `audit_unavailable`, confirme o estado final no banco antes de repetir; uma tentativa sem início gravado pode não existir.
5. **Interrupção:** Ctrl+C tratado registra `interrupted` quando o banco permite. Para processo morto ou conexão perdida, aguarde a liberação da sessão/lock e verifique o lote publicado. `running` não deve ser convertido em sucesso manualmente. Reexecutar o mesmo lote estável reconcilia com a publicação: pode retornar `unchanged` ou carregar novamente atomicamente. Preserve a tentativa antiga como evidência; não a apague para tentar de novo.
6. **Carga válida de conteúdo incorreto:** mantenha cópia autorizada do último lote aceito e execute-o novamente com identificação rastreável; não restaure tabelas isoladamente. Não existe rollback automático de versões históricas de dados: a infraestrutura mantém a publicação anterior em caso de falha, mas uma publicação válida substitui o conteúdo anterior.

Para demonstrar rejeição e recuperação, em uma cópia sintética troque o cabeçalho de `visao_360_uc/part-000.csv`, execute a carga e confira que o lote publicado e seus totais não mudaram. Restaure o arquivo original e repita; deve retornar `unchanged` se o lote já era o publicado. O teste do CLI automatiza esta sequência sem tocar dados reais.

## Verificação reproduzível

Na pasta `backend/`, definir `TEST_POSTGRES_URL` e `TEST_GOLD_POSTGRES_URL` para dois bancos vazios distintos, descartáveis, terminados em `_test`, com papel sem superusuário:

```powershell
venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gold_import.py tests/test_database.py tests/test_migrations.py
venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
venv/Scripts/python.exe -m compileall -q app tests scripts
```

Sem as variáveis, as variantes PostgreSQL são ignoradas; isso não equivale a aprovação delas. A CI prepara `v_energy_test` e `gold_import_test` separados e propaga as duas URLs também para os testes do contêiner. Os testes verificam publicação inteira, repetição, falha tardia, tipos/chaves, controles, auditoria, mudanças nos arquivos, preservação integral de ordem/históricos e migração de lote existente. O teste por subprocesso também executa o gerador e o CLI reais.

Resultados da entrega: 62 testes dirigidos aprovados e suíte completa com 484 aprovados, sem ignorados, em ambiente local Python 3.14.3/PostgreSQL 18.4; suíte completa também com 484 aprovados em Python 3.12.15/PostgreSQL 16.15, fontes atuais montados para leitura na imagem local existente. O build novo no registry DHI retornou 401; reconstrução da imagem continua sem prova nesta rodada. [Detalhes da evidência](../plans/2026-10-27-dev12-separacao.md#evidência-da-conclusão-técnica).

Documentação consultada via Context7 em 27/10/2026: [transações SQLAlchemy Core 2](https://docs.sqlalchemy.org/en/20/core/connections.html) e [cópia de metadados](https://docs.sqlalchemy.org/en/20/core/metadata.html). Versão local SQLAlchemy 2.1.5. Evidência e resultados desta entrega ficam também no Registro de progresso do PRD.
