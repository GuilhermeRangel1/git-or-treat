# Contrato físico provisório dos CSVs Gold v1

Referência: arquivos locais recebidos em 27/10/2026 e notebooks da `feat/gold` em `9664823`. Entrega de preparação DE-06; DE-08 e os aceites WEB/IA continuam pendentes. Os arquivos reais permanecem ignorados pelo Git.

## Organização e formato

O lote fica em `backend/data/gold/v1/`, com uma pasta por tabela: `consumo_mensal_uc`, `consumo_receita_bairro`, `diagnostico_receita`, `fila_inspecao`, `indicadores_dec_fec`, `variacao_consumo_uc` e `visao_360_uc`. Cada pasta aceita um ou vários arquivos `.csv`, todos com o mesmo cabeçalho. Arquivos Spark como `_SUCCESS` não são lidos.

Formato observado: UTF-8, separador `;`, cabeçalho, decimal com ponto, datas ISO, booleanos `true`/`false`, campo vazio como nulo. Aspas e quebras de linha internas são tratadas pelo leitor CSV. Cabeçalho com coluna ausente, extra ou repetida é recusado. Valores nulos nas chaves, números não finitos, tipos inválidos e chaves duplicadas impedem a carga inteira.

O contrato físico histórico é `backend/app/models/gold_v1.py`; os metadados atuais são registrados por `backend/app/models/gold_load.py`, com versão `gold-csv-v1`. Cada CSV corresponde a `gold_<nome_da_tabela>` no banco; campos mantêm os nomes observados. Receita usa `Numeric(38,2)`/Decimal; campos double da exportação usam Float, contagens usam BigInteger, datas usam Date. Ticket médio é uma medida derivada com casas adicionais, não um valor monetário total. Essa escolha física não valida sua fórmula.

Chaves: UC/competência em `consumo_mensal_uc`; competência/município/bairro/classe em `consumo_receita_bairro`; competência/município/classe/subgrupo/bandeira/GD em `diagnostico_receita`; alimentador/competência em `indicadores_dec_fec`; UC nas outras três tabelas.

## Carga e publicação no banco local

Execute em `backend/`, com `DATABASE_URL` apontando explicitamente para o banco de integração:

```powershell
venv/Scripts/python.exe -m alembic upgrade head
venv/Scripts/python.exe scripts/load_gold.py --directory data/gold/v1 --batch v1 --schema-version gold-csv-v1
```

A carga não cria tabelas implicitamente: aplica-se a migração antes. Não altera `gold_indicadores` legado nem ordens/histórico operacionais. Substitui somente as sete tabelas e seu registro de carga, em uma única transação. Falha em qualquer tabela reverte o conjunto. No PostgreSQL, os importadores são serializados por advisory lock transacional; leitores existentes continuam vendo os dados previamente confirmados.

`gold_carga_atual` registra o lote, versão do esquema, instante da importação local, hashes SHA-256 dos arquivos, contagens e somas conferidas no banco. O instante de importação não é data de processamento da Gold. A segunda carga dos mesmos arquivos sob o mesmo identificador/versão retorna `unchanged`; um lote alterado é revalidado integralmente. Cada execução conserva UUID, status, controles e eventual falha em `gold_carga_tentativas`, separadamente da publicação. Não usar o mesmo banco com cargas simultâneas SQLite nem modificar manualmente essas tabelas. [Reprodução sintética, estados, falhas e recuperação DEV-12](gold-load-dev12.md).

São verificadas contagens CSV/banco e somas de receita/consumo por tabela (tolerância SQL de 0,0001 para acumulação em ponto flutuante), além da igualdade Decimal dos totais exportados nas três tabelas financeiras. Os arquivos são relidos para conferir hashes antes do commit. Não há prova de reconciliação com Delta: o exportador atual não fornece manifesto de execução/versões nem controle de publicação aprovado.

## Limites para consumo

- `consumo_mensal_uc` é agregado mensal, não detalhe de faturas. Não criar faturas fictícias a partir dessas linhas.
- Os CSVs não fornecem receita paga, energia faturada separada, detalhes de medidores, faturas, chamados ou ocorrências. Ausência não equivale a zero.
- O diagnóstico atual restringe faturamento a UC/competência com leitura. Reconciliação entre CSVs não comprova faturamento integral da Silver.
- DEC/FEC usam cadastro atual e só publicam grupos com ocorrência; cobertura temporal, zeros conhecidos e interpretação simplificada dependem de homologação.
- O dicionário ainda deve confirmar fórmulas, unidades, vigência, cobertura, limitações e significado das categorias. `subgrupo`, `possui_gd` e `possui_geracao_solar` seguem os nomes efetivamente observados.
- O carregador não ativa `ANALYTICS_SOURCE`, altera o `.env`, adapta rotas nem substitui mocks do portal. Os consumidores continuam pendentes de adaptação explícita e prova CSV → banco → API → tela. IA não recebe acesso novo por esta carga.

## Evidência local histórica anterior à auditoria DEV-12

O lote tem 48 competências, de julho/2022 a junho/2026. Contagens observadas: mensal 1.928.920; bairro 55.694; diagnóstico 4.694; fila 45.000; continuidade 5.856; variação 45.000; visão 360 45.000. Carga completa e repetição verificadas em SQLite isolado em `work/gold-v1-integration.db`, com migrações Alembic. Esses números são evidência do lote recebido, não assertions permanentes do pipeline. A mesma carga e repetição foram verificadas em PostgreSQL 18.4 descartável (`gold_csv_v1_test`, porta local 55439), com contagens e somas reconciliadas. A suíte backend executou 420 testes sem skips, incluindo carga em SQLite/PostgreSQL e migrações com usuário sem superusuário. O servidor descartável é encerrado após a validação; o arquivo SQLite local permanece disponível. Ambiente Python 3.14.3; o alvo Docker/CI Python 3.12/PostgreSQL 16 ainda requer prova separada. A validação de métricas de negócio permanece pendente.

Documentação consultada: SQLAlchemy local 2.1.5, [transações Core](https://docs.sqlalchemy.org/en/20/core/connections.html), via Context7 em 27/10/2026. A implementação usa o contrato Core 2.x de `Engine.begin()` e inserção em lotes com parâmetros vinculados.
