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
- O carregador não ativa a fonte automaticamente nem modifica o `.env`. O modo explícito `ANALYTICS_SOURCE=gold` integra Receita, UC 360 e fila conforme a seção abaixo. IA não recebe acesso novo por essa seleção.

## Origem e publicação

O lote exige exatamente um `manifest.json`, na raiz ou em `manifesto/manifest.json`. A presença nos dois locais, campos repetidos no JSON, arquivo maior que 64 KiB e links simbólicos na localização do manifesto são recusados. O inventário deve listar exatamente as sete tabelas, sem repetições. O manifesto não determina caminhos de leitura dos CSVs.

Campos: `ambiente` igual a `prod` (caixa/espaços normalizados), `run_id` e `lote` iguais no formato `GOLD_<YYYYMMDDTHHMMSSZ>_<8 hex minúsculos>`, `run_id_silver` e `lote_bronze_silver` no formato `<YYYYMMDDTHHMMSSZ>_<8 hex minúsculos>`, `data_processamento_gold`, `tabelas_exportadas` e `schema_version=gold-csv-v1`. Valores de reserva ou IDs manuais não satisfazem esses formatos. São aceitos também `data_exportacao_csv`, `responsavel` e `status_gold` (quando presente, somente `CONCLUIDO`). Campos desconhecidos são recusados. A validação não autentica o produtor do arquivo: use apenas o Volume e a transferência autorizados.

Compatibilidade: o exportador atual não grava `schema_version`; nesses manifestos, o operador precisa declarar `--schema-version gold-csv-v1` explicitamente. Não há versão presumida pelo carregador. A opção deve coincidir com a versão do JSON quando ambos a informam. O timestamp legado `YYYY-MM-DD HH:MM:SS` é interpretado como America/Recife (UTC−03), conforme o exportador; instantes com offset são normalizados para UTC. Recomenda-se que novas exportações declarem versão e offset.

`--batch` é somente uma conferência opcional: deve ser igual ao `run_id` e nunca substitui a origem. Ambiente ausente/não produtivo, versão incompatível, linhagem inválida ou inventário incompleto impedem a carga e geram erro sanitizado. Para testar o contrato, o gerador existente produz CSVs e manifesto inteiramente artificiais com ambiente declarado `prod`; isso não representa um lote real homologado.

`gold_carga_atual` mantém `origem` (ambiente, run Gold, run Silver, lote Bronze, processamento e versão) e `publication_id`, UUID4 gerado ao publicar `loaded`. `unchanged` exige origem, conteúdo e versão iguais e preserva essa identidade e o instante da carga; toda tentativa continua tendo outro `attempt_id`. Uma origem diferente produz nova publicação mesmo com CSVs iguais. Falha conserva a publicação anterior. A origem também é registrada na tentativa quando foi validada; tentativas `loaded`/`unchanged` guardam o `publication_id` correspondente para rastreabilidade histórica.

A referência canônica é `gold-csv-v1:<run_id>:<publication_id>`. O modelo e parser estão em `backend/app/schemas/gold_publication.py`; exemplos artificiais para revisão com GenAI estão em `backend/tests/fixtures/gold_publication_contract.json`. Os exemplos não são envelopes completos de planejamento/síntese e não implementam o fluxo GenAI.

A migração `goldv1000003` preserva fatos e registros legados e deixa origem/publication_id nulos nesses registros. Eles não podem sustentar uma referência real até uma nova carga com manifesto validado; nenhuma origem é reconstruída por suposição. A vista mínima `gold.publicacao_atual` expõe só versão, run e publicação. Ordens, histórico e auditoria continuam fora do schema analítico e fora dos grants do leitor.

O helper `current_publication` valida uma referência esperada contra a publicação consultada. É preparação: não garante sozinho snapshot consistente durante uma consulta de negócio. O futuro executor precisa ler fatos e publicação sob a mesma visão transacional e aplicar a política de troca de lote do contrato interno.

Resultados por lote e contagens históricas não são constantes deste contrato. Consulte o Registro de progresso do PRD para a evidência histórica delimitada à execução correspondente.

Documentação consultada: SQLAlchemy local 2.1.5, [transações Core](https://docs.sqlalchemy.org/en/20/core/connections.html), via Context7 em 27/10/2026. A implementação usa o contrato Core 2.x de `Engine.begin()` e inserção em lotes com parâmetros vinculados.


## Consumo provisório pela API e pelo portal

Entrega de **integração executável**, sem aceite das métricas. O runtime existente resolve `GoldAnalyticsRepository` apenas com `ANALYTICS_SOURCE=gold`. A demonstração sintética continua explícita e não abre sessão SQL. A fonte Gold informa `kind=gold_csv`, `is_demo=false` e versão composta por lote/hash; não há fallback para fixtures.

As rotas existentes `/revenue`, `/ucs`, `/ucs/{id}/overview`, `/ucs/{id}/history/{section}`, `/inspections/queue` e `/inspections/queue/{id}` têm projeção Gold. `/analytics/options` publica competências e dimensões do banco. Receita consulta o agregado `gold_consumo_receita_bairro` por SQL para município/bairro/classe; filtros por alimentador usam `gold_consumo_mensal_uc` com join cadastral um-para-um. Ambos usam filtros parametrizados. UC e fila contam, ordenam e paginam no banco, até 100 registros por página. Não carregam os milhões de fatos em memória. PostgreSQL usa lock compartilhado da carga até fechar a sessão; SQLite usa snapshot transacional, evitando mistura de tabelas/lotes na mesma requisição.

Receita apresenta os valores publicados e seus limites de população. Receita paga, energia faturada separada, tarifa e preço-volume continuam indisponíveis. Diferença financeira entre extremos é observação, sem percentual homologado. Meses sem observação não recebem zero. Padrão: últimas 12 competências observadas, preservando período explícito da URL. As opções de município/bairro/classe/alimentador vêm do banco.

UC 360 mostra cadastro e histórico mensal com consumo e receita agregada. A coluna de receita no histórico de consumo não representa fatura individual. Medidores, pagamentos, faturas detalhadas, interrupções e chamados detalhados ficam indisponíveis. GD cadastral aparece como apoio, sem potência ou geração presumidas. Período, unidades, lote, importação local e limitações acompanham a consulta.

A fila Gold usa envelope 1.1.0; a demonstração preserva 1.0.0. A fila preserva `prioridade_inspecao` como texto em `priority_label`, com `priority=null`. Ordenação provisória de apresentação: Alta → Média → Revisar → Baixa; desempate por UC crescente. Não é score, probabilidade ou regra homologada. Indicadores mostram apenas contagens históricas e GD disponíveis. Não há pesos inventados, e a estimativa é nula. Criação de ordem por essa fila não foi habilitada: a regra existente exige fonte demonstrativa, e o portal informa essa dependência. Ordens existentes mantêm autenticação e persistência.

Panorama/DEC-FEC e GenAI não receberam interpretação Gold nesta entrega. Panorama e Operação falham fechado no modo Gold, em vez de devolver números sintéticos como reais. As opções do Panorama vêm do catálogo, mas isso não conclui seus indicadores. Chat e insight não receberam acesso novo ao banco.

Para executar localmente em `backend/`, usando o banco isolado já carregado neste workspace:

```powershell
$env:ANALYTICS_SOURCE = "gold"
$env:ORDERS_AUTH_MODE = "service"
$env:DATABASE_URL = "sqlite:///../work/gold-v1-integration.db"
venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8029
```

Em `frontend/`:

```powershell
$env:API_PROXY_TARGET = "http://127.0.0.1:8029"
npm.cmd run dev -- --host 127.0.0.1 --port 5199 --strictPort
```

As variáveis valem para esses processos. `.env` e seleção do Docker não foram trocados. Não expor dados reais antes de concluir a autorização individual/territorial das leituras. Dicionário, cobertura e revisão humana continuam pendentes.

### Qualidade da fonte observada na integração

O catálogo do lote contém grafias territoriais distintas com sinais de mojibake. A projeção conserva os valores recebidos; não corrige encoding por heurística nem funde categorias. A engenharia deve confirmar o tratamento na origem/Silver/Gold e republicar o lote antes de interpretar recortes territoriais como diagnóstico homologado.


### Verificações da integração executável

- Backend: suíte completa com PostgreSQL descartável — 426 aprovados, nenhum ignorado; recorte HTTP Gold anterior à otimização — 6 aprovados; recorte Gold/regressão de Receita após a otimização territorial e controle de alimentador — 20 aprovados.
- Frontend: suíte sequencial — 265 aprovados; build, lint, formatação e fronteiras (142 arquivos) aprovados.
- CSV → banco → API: controles independentes de receita/consumo para três agrupamentos e um recorte, histórico mensal paginado de UC e fila paginada passaram em SQLite e PostgreSQL. O script local de verificação permanece ignorado em `work/verify_gold_runtime.py`, sem registros individuais no resultado. Isto não homologa a origem Delta ou a interpretação de negócio.
- API → proxy → navegador: Receita, filtros reais, fila/detalhe e UC 360 conferidos. UC testada em 390/1440 px, temas claro/escuro, sem transbordamento global após corrigir a quebra do lote. Captura local ignorada, sem publicar dados reais.
- Ambiente: Python 3.14.3, SQLAlchemy 2.1.5, PostgreSQL 18.4; React 19/TanStack Query 5/Vite 8 do lockfile local. Docker/CI alvo não reexecutado. Documentação SQLAlchemy Core 2 e TanStack Query consultada via Context7 em 27/10/2026 para agregação/paginação parametrizada e cancelamento por AbortSignal.

A reconciliação real SQLite/PostgreSQL foi repetida após a otimização para o agregado territorial e passou nos dois bancos. O PostgreSQL descartável foi encerrado; o portal local de revisão usa SQLite e as portas 8029/5199.
