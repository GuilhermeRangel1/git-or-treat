# ADR-0011 — Uma ordem de inspeção ativa por UC

**Data:** 2026-10-23

**Estado:** adotada para o alinhamento DEV-06/DEV-07 solicitado pela pessoa usuária

**IDs do PRD afetados:** WEB-05

## Contexto

A DEV-06 impedia ordens simultâneas para a mesma referência de suspeita (UC, fonte e versão da regra). A DEV-07 impede trabalho simultâneo para a mesma UC. Na regra anterior, atualizar a fonte permitiria criar outra ordem para uma UC que ainda tem trabalho em campo. Em 23/10/2026, a pessoa usuária solicitou resolver a divergência entre as duas entregas.

## Opções consideradas

1. Uma ordem ativa por referência: permite investigações simultâneas da UC em versões distintas, com risco de trabalho de campo duplicado.
2. Uma ordem ativa por UC: mantém uma frente operacional por unidade, preservando as evidências que motivaram cada ordem no histórico.

## Decisão

Adotar a segunda opção, alinhada à regra operacional da DEV-07. Ordens PENDENTE/EM_ANDAMENTO bloqueiam outra criação para a mesma UC, tanto manual quanto pela fila, independentemente da versão da fonte ou regra. O servidor continua preservando a referência e o snapshot originais; não atualiza evidências históricas silenciosamente. Após cancelamento/conclusão, uma nova intenção pode abrir outra ordem. Repetir a chave antiga retorna a ordem original.

A garantia está no índice parcial único `uq_orders_active_uc`, além da validação no serviço. Chaves globais continuam únicas. Reenvio idêntico é resolvido no banco antes de consultar a fonte analítica; fonte indisponível impede novas criações pela fila, mas não a recuperação de um envio confirmado. O controle de acesso continua obrigatório em ambos os casos.

## Consequências e verificação

Migração `a6d060000002` substitui o índice por referência pelo índice por UC. Se já houver duplicidades ativas, ela falha com orientação para reconciliação manual e não altera o estado de nenhuma ordem. Não se escolhe automaticamente uma ordem vencedora. A configuração da aplicação deve aplicar Alembic antes de servir escritas sobre banco existente.

Conflitos retornam mensagem compatível em `detail` e campos estruturados em `error`: código, mensagem e ID quando existe uma ordem relacionada. A criação manual não recebe idempotência nova nesta decisão; repetição indevida continua impedida por UC, com 409 e referência à ordem existente.

Testes HTTP, migração SQLite/PostgreSQL e concorrência PostgreSQL cobrem versões diferentes, criação manual concorrente com criação pela fila, reenvio sem fonte, rollback anterior ao commit e falha de confirmação posterior ao commit. Contratos e evidências em [DEV-06](../contracts/inspection-orders-dev06.md). A integração futura da DEV-07 deve preservar este índice, fingerprint e limite de 128 caracteres da chave DEV-06; esta decisão alinha a regra, sem incorporar agora seus modelos de histórico ou rotas de resultado/cancelamento.
