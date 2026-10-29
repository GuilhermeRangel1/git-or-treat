# Contrato físico provisório dos CSVs Gold v1

Referência: arquivos locais recebidos em 27/10/2026 e notebooks da `feat/gold` em `9664823`. Entrega de preparação DE-06; DE-08 e os aceites WEB/IA continuam pendentes. Os arquivos reais permanecem ignorados pelo Git.

## Organização e formato

O lote fica em `backend/data/gold/v1/`, com uma pasta por tabela: `consumo_mensal_uc`, `consumo_receita_bairro`, `diagnostico_receita`, `fila_inspecao`, `indicadores_dec_fec`, `variacao_consumo_uc` e `visao_360_uc`. Cada pasta aceita um ou vários arquivos `.csv`, todos com o mesmo cabeçalho. Arquivos Spark como `_SUCCESS` não são lidos.

Formato observado: UTF-8, separador `;`, cabeçalho, decimal com ponto, datas ISO, booleanos `true`/`false`, campo vazio como nulo. Aspas e quebras de linha internas são tratadas pelo leitor CSV. Cabeçalho com coluna ausente, extra ou repetida é recusado. Valores nulos nas chaves, números não finitos, tipos inválidos e chaves duplicadas impedem a carga inteira.

O contrato físico histórico é `backend/app/models/gold_v1.py`; os metadados atuais são registrados por `backend/app/models/gold_load.py`, com versão `gold-csv-v1`. No PostgreSQL, cada CSV corresponde a `gold.gold_<nome_da_tabela>`; no SQLite de testes o schema é traduzido para o padrão. Os campos mantêm os nomes observados. Receita usa `Numeric(38,2)`/Decimal; campos double da exportação usam Float, contagens usam BigInteger, datas usam Date. Ticket médio é uma medida derivada com casas adicionais, não um valor monetário total. Essa escolha física não valida sua fórmula.

Campos financeiros anuláveis permanecem distintos entre ausência e zero: CSV vazio gera `NULL`; o manifesto registra `totals[field]=null` e `present_counts[field]=0` quando todos os valores estão ausentes. Um zero explícito soma `0.00` e incrementa a contagem de presentes. A validação compara `SUM` nulo somente com expectativa ausente e reconcilia as três tabelas financeiras exigindo ausência nas três ou totais numéricos iguais. A conversão e a soma Decimal não dependem do contexto decimal global; SQLite não serve como prova de exatidão `Numeric(38,2)` por armazenar valores numéricos via ponto flutuante.

Chaves: UC/competência em `consumo_mensal_uc`; competência/município/bairro/classe em `consumo_receita_bairro`; competência/município/classe/subgrupo/bandeira/GD em `diagnostico_receita`; alimentador/competência em `indicadores_dec_fec`; UC nas outras três tabelas.

## Carga e publicação no banco local

Execute em `backend/`, com `DATABASE_URL` apontando explicitamente para o banco de integração:

```powershell
venv/Scripts/python.exe -m alembic upgrade head
venv/Scripts/python.exe scripts/load_gold.py --directory data/gold/v1 --schema-version gold-csv-v1
```

A carga não cria tabelas implicitamente: aplica-se a migração antes. Não altera `gold_indicadores` legado nem ordens/histórico operacionais. Substitui somente as sete tabelas e seu registro de carga, em uma única transação. Falha em qualquer tabela reverte o conjunto. No PostgreSQL, os importadores são serializados por advisory lock transacional; leitores existentes continuam vendo os dados previamente confirmados.

`gold_carga_atual` registra o lote, versão do esquema, instante da importação local, hashes SHA-256 dos arquivos, contagens e somas conferidas no banco. O instante de importação não é data de processamento da Gold. A segunda carga dos mesmos arquivos sob o mesmo identificador/versão retorna `unchanged`; um lote alterado é revalidado integralmente. Cada execução conserva UUID, status, controles e eventual falha em `gold_carga_tentativas`, separadamente da publicação. Não usar o mesmo banco com cargas simultâneas SQLite nem modificar manualmente essas tabelas. [Reprodução sintética, estados, falhas e recuperação DEV-12](gold-load-dev12.md).

São verificadas contagens CSV/banco e somas de receita/consumo por tabela (tolerância SQL de 0,0001 para acumulação em ponto flutuante), além da igualdade Decimal dos totais exportados nas três tabelas financeiras. Os arquivos são relidos para conferir hashes antes do commit. A origem do manifesto é validada e vinculada à carga, mas a reconciliação com Delta depende de controles da origem para o mesmo lote exportado; hashes calculados no destino não comprovam esse vínculo sozinhos.

## Limites para consumo

- `consumo_mensal_uc` é agregado mensal, não detalhe de faturas. Não criar faturas fictícias a partir dessas linhas.
- Os CSVs não fornecem receita paga, energia faturada separada, detalhes de medidores, faturas, chamados ou ocorrências. Ausência não equivale a zero.
- O diagnóstico atual restringe faturamento a UC/competência com leitura. Reconciliação entre CSVs não comprova faturamento integral da Silver.
- DEC/FEC usam cadastro atual e só publicam grupos com ocorrência; cobertura temporal, zeros conhecidos e interpretação simplificada dependem de homologação.
- O dicionário ainda deve confirmar fórmulas, unidades, vigência, cobertura, limitações e significado das categorias. `subgrupo`, `possui_gd` e `possui_geracao_solar` seguem os nomes efetivamente observados.
- O carregador não ativa `ANALYTICS_SOURCE`, altera o `.env`, adapta rotas nem substitui mocks do portal. Os consumidores continuam pendentes de adaptação explícita e prova CSV → banco → API → tela. IA não recebe acesso novo por esta carga.

## Origem e publicação

O lote exige exatamente um `manifest.json`, na raiz ou em `manifesto/manifest.json`. A presença nos dois locais, campos repetidos no JSON, arquivo maior que 64 KiB e links simbólicos na localização do manifesto são recusados. O inventário deve listar exatamente as sete tabelas, sem repetições. O manifesto não determina caminhos de leitura dos CSVs.

Campos: `ambiente` igual a `prod` (caixa/espaços normalizados), `run_id` e `lote` iguais no formato `GOLD_<YYYYMMDDTHHMMSSZ>_<8 hex minúsculos>`, `run_id_silver` e `lote_bronze_silver` no formato `<YYYYMMDDTHHMMSSZ>_<8 hex minúsculos>`, `data_processamento`, `tabelas_exportadas` e `schema_version=gold-csv-v1`. Valores de reserva ou IDs manuais não satisfazem esses formatos. São aceitos também `data_exportacao_csv`, `responsavel` e `status_gold` (quando presente, somente `CONCLUIDO`). Campos desconhecidos são recusados. A validação não autentica o produtor do arquivo: use apenas o Volume e a transferência autorizados.

Compatibilidade: o exportador atual não grava `schema_version`; nesses manifestos, o operador precisa declarar `--schema-version gold-csv-v1` explicitamente. Não há versão presumida pelo carregador. A opção deve coincidir com a versão do JSON quando ambos a informam. O timestamp legado `YYYY-MM-DD HH:MM:SS` é interpretado como America/Recife (UTC−03), conforme o exportador; instantes com offset são normalizados para UTC. Recomenda-se que novas exportações declarem versão e offset.

`--batch` é somente uma conferência opcional: deve ser igual ao `run_id` e nunca substitui a origem. Ambiente ausente/não produtivo, versão incompatível, linhagem inválida ou inventário incompleto impedem a carga e geram erro sanitizado. Para testar o contrato, o gerador existente produz CSVs e manifesto inteiramente artificiais com ambiente declarado `prod`; isso não representa um lote real homologado.

`gold_carga_atual` mantém `origem` (ambiente, run Gold, run Silver, lote Bronze, processamento e versão) e `publication_id`, UUID4 gerado ao publicar `loaded`. `unchanged` exige origem, conteúdo e versão iguais e preserva essa identidade e o instante da carga; toda tentativa continua tendo outro `attempt_id`. Uma origem diferente produz nova publicação mesmo com CSVs iguais. Falha conserva a publicação anterior. A origem também é registrada na tentativa quando foi validada; tentativas `loaded`/`unchanged` guardam o `publication_id` correspondente para rastreabilidade histórica.

A referência canônica é `gold-csv-v1:<run_id>:<publication_id>`. O modelo e parser estão em `backend/app/schemas/gold_publication.py`; exemplos artificiais para revisão com GenAI estão em `backend/tests/fixtures/gold_publication_contract.json`. Os exemplos não são envelopes completos de planejamento/síntese e não implementam o fluxo GenAI.

A migração `goldv1000003` preserva fatos e registros legados e deixa origem/publication_id nulos nesses registros. Eles não podem sustentar uma referência real até uma nova carga com manifesto validado; nenhuma origem é reconstruída por suposição. A vista mínima `gold.publicacao_atual` expõe só versão, run e publicação. Ordens, histórico e auditoria continuam fora do schema analítico e fora dos grants do leitor.

O helper `current_publication` valida uma referência esperada contra a publicação consultada. É preparação: não garante sozinho snapshot consistente durante uma consulta de negócio. O futuro executor precisa ler fatos e publicação sob a mesma visão transacional e aplicar a política de troca de lote do contrato interno.

Resultados por lote e contagens históricas não são constantes deste contrato. Consulte o Registro de progresso do PRD para a evidência histórica delimitada à execução correspondente.
