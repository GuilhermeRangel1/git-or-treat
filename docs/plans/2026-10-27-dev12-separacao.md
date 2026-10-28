# DEV-12 — Infraestrutura de carga local

Separação solicitada em 27/10/2026. Requisito DE-06; dependência DEV-01. Base: `origin/develop` em `2581385`. Os commits originais `a93a272` e `4118cd5` foram reaplicados preservando os helpers de migração da nova develop. O histórico completo anterior permanece em `backup/dev12-antes-separacao-20261027`.

## Checklist DEV-12 — atualizado após completar a infraestrutura

- [x] Definir identificação de lote, versão do esquema e arquivos esperados: nome validado, fingerprint, versão explícita `gold-csv-v1` e inventário das sete pastas/partes CSV. Migração de lote existente preserva fatos e manifesto.
- [x] Validar tipos, campos obrigatórios e chaves: cabeçalhos, estrutura, nulidade/vazio das chaves, competências/datas ISO, booleanos, limites de inteiros/decimais, finitude e unicidade entre partes. Regras de negócio futuras dependem do dicionário.
- [x] Registrar contagens, falhas e totais de controle: `gold_carga_atual` e histórico persistente `gold_carga_tentativas`, com UUID, versão, início/fim, estados, hashes, progresso e erros sem valores das linhas.
- [x] Garantir que repetir o mesmo lote não duplique resultados: fatos, totais e instante de publicação preservados; nova tentativa `unchanged` auditada.
- [x] Impedir publicação parcial: falha na última tabela, controles, mudança de arquivos e falha ao registrar sucesso revertem toda a publicação.
- [x] Preservar ordens e históricos operacionais: teste com ordem preenchida e duas entradas de histórico compara integralmente todos os campos após carga, repetição, substituição válida e carga inválida.
- [x] Documentar execução, falhas e recuperação: [runbook DEV-12](../contracts/gold-load-dev12.md), gerador sintético sem sobrescrita, consulta da auditoria e tratamento de interrupção/perda de conexão.

O checklist técnico DEV-12 está implementado e verificado com CSVs artificiais. O requisito de produto DE-06 continua `Em andamento`: falta reconciliação Databricks → CSV → banco e homologação da Gold. A adaptação futura muda explicitamente o mapeamento e a versão, sem editar snapshots históricos ou inventar métricas.

## Evidência da conclusão técnica

- Foco carga/metadados/migrações em SQLite e PostgreSQL 18.4 descartável: 62 aprovados, nenhum ignorado.
- Suíte completa local Python 3.14.3 / PostgreSQL 18.4: 484 aprovados, nenhum ignorado.
- Suíte completa Python 3.12.15 / PostgreSQL 16.15: 484 aprovados, nenhum ignorado. A imagem local `git-or-treat-backend:latest` recebeu somente os fontes atuais montados para leitura (app/tests/scripts/alembic/alembic.ini). Rede e servidor de teste exclusivos; papel sem superusuário, dois bancos separados preparados pelo script da CI.
- O build novo foi tentado com `docker build -f backend/Dockerfile -t git-or-treat-backend:dev12-check .`, mas o registry DHI retornou 401. A prova em contêiner usa a imagem local existente com os fontes atuais; não comprova reconstrução da imagem a partir do registry.
- `compileall`, YAML da CI e `git diff --check`: passaram. Aviso preexistente Starlette/httpx nas suítes.

Comandos completos do fluxo e testes: [runbook](../contracts/gold-load-dev12.md). A CI agora fornece `TEST_GOLD_POSTGRES_URL` separada da URL de migrações, também ao contêiner; o script de preparação foi executado com sucesso no PostgreSQL 16.15 isolado. A confirmação de uma nova execução remota da CI é independente desta evidência local.

## Fronteira com DEV-13

A `dev12` não contém notebooks importados, dicionário em elaboração, adaptadores analíticos Gold, endpoint de opções ou alterações no frontend. Essas mudanças foram destinadas à `dev13`, que depende desta infraestrutura. Os CSVs e bancos locais permanecem ignorados pelo Git.

O registro anterior do PRD descreve a execução histórica antes da separação. Os notebooks e o rascunho mencionados naquele registro estão na DEV-13, não no diff deste PR.

## Verificações históricas da separação inicial

Em `backend/`, com `TEST_POSTGRES_URL` e `TEST_GOLD_POSTGRES_URL` apontando para bancos descartáveis distintos, usuário sem superusuário:

- `venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gold_import.py tests/test_database.py tests/test_migrations.py`: 24 aprovados, nenhum ignorado; aviso preexistente Starlette/httpx.
- Na raiz, `backend/venv/Scripts/python.exe -m compileall -q backend/app backend/tests backend/scripts`: passou.
- `git diff --check`: passou.

Python 3.14.3 / PostgreSQL 18.4 locais. Docker/CI Python 3.12 / PostgreSQL 16 não reexecutados nesta separação. As verificações históricas do contrato não substituem estes resultados sobre a nova base. Trello não está conectado; sincronização do cartão DE-06 permanece pendente.
