# DEV-12 — Infraestrutura de carga local

Separação solicitada em 27/10/2026. Requisito DE-06; dependência DEV-01. Base: `origin/develop` em `2581385`. Os commits originais `a93a272` e `4118cd5` foram reaplicados preservando os helpers de migração da nova develop. O histórico completo anterior permanece em `backup/dev12-antes-separacao-20261027`.

## Checklist e pendências

- Parcial: identificação do lote e sete tabelas esperadas implementados; esquema físico v1 definido no código. Falta registrar uma versão explícita de esquema nos metadados do lote.
- Implementado para o contrato físico observado: tipos, cabeçalhos, campos obrigatórios das chaves e unicidade. Regras de negócio dependem do dicionário.
- Parcial: contagens, hashes e totais de controle persistidos para a carga válida. Falhas são devolvidas pelo CLI; falta histórico persistente das tentativas malsucedidas.
- Verificado com CSVs artificiais: repetir o lote não duplica linhas e mantém os totais.
- Verificado com CSVs artificiais: falha na última tabela reverte a transação e preserva o lote válido anterior.
- Parcial: importador só altera as tabelas Gold e os metadados da carga. Falta teste específico com ordens e históricos operacionais previamente preenchidos durante uma recarga.
- Parcial: execução e rollback estão no contrato e README; detalhar recuperação por tipo de falha e tratamento do histórico de tentativas quando este existir.

Esta entrega permanece em andamento; não fecha todo o checklist nem a reconciliação Databricks → banco exigida por DE-06. O teste sintético comprova o mecanismo de carga para o esquema observado v1, sem homologar a semântica da Gold.

## Fronteira com DEV-13

A `dev12` não contém notebooks importados, dicionário em elaboração, adaptadores analíticos Gold, endpoint de opções ou alterações no frontend. Essas mudanças foram destinadas à `dev13`, que depende desta infraestrutura. Os CSVs e bancos locais permanecem ignorados pelo Git.

O registro anterior do PRD descreve a execução histórica antes da separação. Os notebooks e o rascunho mencionados naquele registro estão na DEV-13, não no diff deste PR.

## Verificações após a separação

Em `backend/`, com `TEST_POSTGRES_URL` e `TEST_GOLD_POSTGRES_URL` apontando para bancos descartáveis distintos, usuário sem superusuário:

- `venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gold_import.py tests/test_database.py tests/test_migrations.py`: 24 aprovados, nenhum ignorado; aviso preexistente Starlette/httpx.
- Na raiz, `backend/venv/Scripts/python.exe -m compileall -q backend/app backend/tests backend/scripts`: passou.
- `git diff --check`: passou.

Python 3.14.3 / PostgreSQL 18.4 locais. Docker/CI Python 3.12 / PostgreSQL 16 não reexecutados nesta separação. As verificações históricas do contrato não substituem estes resultados sobre a nova base. Trello não está conectado; sincronização do cartão DE-06 permanece pendente.
