# DEV-07 — ciclo operacional das ordens (WEB-05)

24/10/2026. Base incorporada: backend da DEV-06, commit `85a72a0`, que já inclui DEV-05. Frontend não alterado nesta entrega. Fonte analítica exclusivamente sintética; nenhuma validação Gold é afirmada.

## Estados e validação

- PENDENTE → EM_ANDAMENTO ou CANCELADA.
- EM_ANDAMENTO → CONCLUIDA (resultado não vazio) ou CANCELADA.
- CONCLUIDA/CANCELADA não aceitam alterações; repetição exatamente igual com a versão atual é aceita sem nova versão/histórico. Tentativa de reabertura retorna 409.
- Criação manual exige UC/motivo não vazios (50/255 caracteres). Prioridades BAIXA/MEDIA/ALTA, padrão MEDIA. Resultado e observações limitados a 4.000 caracteres; campos desconhecidos são recusados. Criação pela fila preserva o contrato e a evidência DEV-06.

## Endpoints

Prefixo `/api/v1/inspections`. Todos preservam o controle de acesso DEV-06; histórico exige leitura e alterações exigem escrita.

- `PATCH /orders/{id}`: status, notes, result e version obrigatória. Campos omitidos são preservados. Não aceita corpo vazio nem apenas version. Resultado fornecido em branco é 422. Conclusão sem resultado é 422; transição inválida é 409.
- `POST /orders/{id}/result`: `{ "result": "Sem irregularidade", "version": 2 }`, com notes opcional. Exige estado EM_ANDAMENTO e conclui a ordem. Resultado é aparado antes da gravação.
- `POST /orders/{id}/cancel`: `{ "confirmed_order_id": 42, "reason": "Inspeção desnecessária", "version": 2 }`. O ID confirmado deve ser igual ao ID da rota (divergência: 409, `confirmation_mismatch`); motivo é opcional. Cancelamento via PATCH é recusado com 422; somente esta rota permite cancelar.
- `GET /orders/{id}/history`: lista cronológica de eventos por ID, com ação, estados anterior/novo, observações, detalhes do resultado/motivo, data UTC, identidade do servidor e versão resultante. 404 para ordem inexistente; lista vazia para ordem antiga sem eventos conhecidos. Não se fabrica histórico anterior à implantação.

Respostas de detalhe/criação/alteração e resumos paginados incluem `version` e `cancellation_reason`. O snapshot analítico de criação permanece imutável. Conflitos conservam `detail` e `error: {code, message, order_id}`; novos códigos: `version_conflict`, `invalid_transition`, `terminal_order`, `confirmation_mismatch`. Erros não revelam SQL ou credenciais.

## Repetição, concorrência e auditoria

A criação pela fila mantém `Idempotency-Key` de 16–128 caracteres, fingerprint e retorno 200 no replay/201 na criação; chave com outro conteúdo recebe 409. Reenvio não gera histórico adicional. Criação manual continua sem chave e responde 409 se já houver ordem ativa. O índice parcial único por UC cobre múltiplos workers.

Toda mudança real incrementa version e registra evento na mesma transação; falha do histórico desfaz também a ordem. O cliente deve enviar a versão obtida no GET para detectar tela obsoleta. Após 409, recarregue a ordem e peça revisão da intenção; não substitua automaticamente a versão e repita a escrita. A versão é obrigatória em PATCH, resultado e cancelamento: ausência, null, booleano, texto ou inteiro menor que 1 retorna 422. Clientes DEV-06 devem adaptar seus envios; não há caminho legado sem versão. O mapper SQLAlchemy inclui a versão na condição SQL do UPDATE e converte StaleDataError em 409, inclusive quando o status não mudou.

Não há nova chave de idempotência nas mutações. Repetição sem mudança de conteúdo com a versão atual não grava; reenvio com versão já ultrapassada responde 409, sem repetir efeito. Corrigir um resultado antes do encerramento é uma nova alteração auditada. Ordens encerradas não permitem corrigir conteúdo.

`actor` vem do controle de acesso, nunca do corpo. No modo demo identifica a demonstração; no modo service identifica a credencial compartilhada; identidade individual exige OIDC configurado. Novos eventos têm ator/versão; eventos antigos permanecem com esses campos nulos.

## Migrações e execução

Instalar `backend/requirements.txt` e executar `alembic upgrade head` na pasta backend antes de iniciar a API sobre banco existente. Não usar create_all para atualizar esquema existente.

A revisão `a7d070000001` reúne as heads históricas `c4b1a239d8e7` (DEV-07) e `a6d060000002` (DEV-06), preservando ordens, resultados, chaves, snapshots e histórico. As migrações que compartilhavam idempotency_key passam a detectar a coluna existente para permitir as duas origens; a revisão de convergência padroniza o limite em 128 e mantém apenas o índice único DEV-06. Nenhum stamp manual nem recriação do banco é necessário. Duplicidades ativas antigas interrompem a migração DEV-06 para reconciliação explícita, sem cancelamento automático. Downgrade é destrutivo para os campos/tabelas removidos e foi exercitado somente em bancos descartáveis.

Fonte técnica: SQLAlchemy instalado 2.1.5; contador de versão consultado via Context7 na [documentação 2.x](https://docs.sqlalchemy.org/en/20/orm/versioning.html). O mapper usa flush ORM, sem bulk update, pois o contador de versão não protege bulk updates.

## Evidência reproduzível

Na pasta backend: `venv/Scripts/python.exe -m pytest -q` e `venv/Scripts/python.exe -m compileall -q app tests scripts`.

Na validação inicial de 24/10/2026: 263 testes passaram e quatro testes PostgreSQL foram ignorados por falta de TEST_POSTGRES_URL. Ambiente local Python 3.14.3, FastAPI 0.143.3, SQLAlchemy 2.1.5 e Alembic 1.20.0. Python 3.12/container e PostgreSQL ainda precisam da verificação no ambiente de destino; Docker local sem daemon disponível.

`tests/test_order_lifecycle_dev07.py` percorre HTTP → serviço → banco real SQLite → leitura por nova sessão. Cobre criação, resultado, cancelamento, histórico, ator, versões, terminalidade, repetição, confirmação incorreta, validações, acesso, rollback e duas sessões com alterações no mesmo status. Migra bancos originados de ambas as branches, verifica preservação de ordem/chave e impede reativação da ordem cancelada após migração. A suíte DEV-06 conserva os testes da fila, snapshots, idempotência, paginação e segurança.

WEB-05 segue Em validação: integração completa da interface e confirmação visual pendentes. A execução PostgreSQL foi realizada na revisão abaixo. Trello não conectado nesta sessão.


## Preparação para o frontend — revisão de 24/10/2026

`version` é obrigatória e inteira positiva nos três schemas de alteração; PATCH não admite CANCELADA no OpenAPI. Requisição de uma tela antiga é recusada mesmo que chegue depois de outra alteração já ter sido confirmada. A rota de cancelamento também valida o ID confirmado. Criação pela fila, idempotência e consulta permanecem compatíveis com DEV-06; suas mutações antigas precisam adaptar versão/rota.

Exemplos sintéticos publicados no Swagger:

- Iniciar: `PATCH /orders/42` com `{ "version": 1, "status": "EM_ANDAMENTO" }`.
- Registrar resultado: `POST /orders/42/result` com `{ "version": 2, "result": "Sem irregularidade" }`.
- Cancelar uma ordem ativa selecionada: `POST /orders/42/cancel` com `{ "version": 1, "confirmed_order_id": 42, "reason": "Inspeção desnecessária" }`. É uma alternativa ao fluxo de conclusão; não cancela uma ordem já concluída.

Versão/ID dos exemplos são ilustrativos: use os valores reais retornados na consulta. A resposta 409 tem `detail` e `error` tipados, com exemplo de version_conflict. Sem nova migração SQL nesta revisão; basta reiniciar a API após atualizar o código (as migrações anteriores continuam necessárias para bancos ainda não atualizados).

Validação adicional em PostgreSQL 18.6 efêmero, com volume anônimo descartado por --rm e isolado dos volumes de desenvolvimento, com usuário migrador sem SUPERUSER. A suíte passou com PostgreSQL configurado (293 testes, nenhum ignorado), cobrindo migração com comparação ORM/esquema, round-trip, índices de unicidade, concorrência, ciclo HTTP e histórico. O ambiente local Python 3.14.3 e a imagem Python 3.12.15 passaram com 293 testes cada. Na imagem, a suíte final executou sobre cópia temporária apenas de app/tests/alembic/scripts e alembic.ini, sem .env nem dados; fonte original montada somente leitura. A primeira tentativa sobre montagem direta Windows teve timeout no teste de reinício (292 passaram); repetição sobre disco Linux passou integralmente em 27,15 s. Fontes dos exemplos consultadas via Context7: [FastAPI — exemplos de schema](https://fastapi.tiangolo.com/tutorial/schema-extra-example/).
