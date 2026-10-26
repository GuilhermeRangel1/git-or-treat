# ADR-0014 — integração do ciclo operacional DEV-07 com DEV-06

**Data:** 24/10/2026. **Estado:** adotada na integração solicitada. **IDs:** WEB-05 e WEB-11.

## Contexto e opções

DEV-07 tinha ciclo/histórico iniciais em branch anterior à fila e à criação DEV-06. O [registro inicial do ciclo operacional](registro-historico-ciclo-operacional-dev06.md) permitia concluir PENDENTE e prioridade CRITICA; a base DEV-06 preservava o início obrigatório e BAIXA/MEDIA/ALTA. Sobrescrever a DEV-06 perderia snapshot, fingerprint, paginação e controles de acesso. Reescrever todo o histórico de migrações exigiria recriar bancos existentes.

## Decisão

Integrar o backend DEV-06 (`85a72a0`) e acrescentar auditoria transacional e versionamento ORM sobre seus contratos. Preservar a regra mais restrita da DEV-06: PENDENTE inicia/cancela; EM_ANDAMENTO conclui com resultado/cancela. Prioridades BAIXA/MEDIA/ALTA. Complementa a ADR-0007 e substitui os pontos divergentes do registro inicial do ciclo operacional. O PRD registra a regra vigente e mantém WEB-05 Em validação.

Histórico durável conserva estados, conteúdo do resultado/motivo, identidade confiada pelo servidor e versão. Estados finais são imutáveis, com replay idêntico sem gravação. Cancelamento dedicado exige confirmar o ID. Atualização solicitada em 24/10/2026 antes da integração do frontend: PATCH não permite CANCELADA e version passa a ser obrigatória em todas as mutações; clientes DEV-06 devem se adaptar. A confirmação do ID fica restrita à rota de cancelamento; proteção entre sessões ocorre via version_id_col e StaleDataError no flush, sem bulk update. Idempotência de criação segue DEV-06, exclusivamente pela fila; criação manual mantém bloqueio por UC. A revisão merge Alembic preserva ambas as linhagens, normalizando sua coluna compartilhada em vez de apagar dados/stampar versões.

## Consequências e evidência

Sem frontend novo, dados reais ou alteração de métricas Gold. Controle de acesso e identidade têm os limites do modo configurado (demo/service/OIDC). WEB-10 não é concluído por este trabalho. A revisão de 24/10/2026 foi validada em PostgreSQL 18 efêmero separado do banco de desenvolvimento, com usuário sem SUPERUSER. Contrato, comandos, limites de concorrência, migração e resultados na [DEV-07](../contracts/inspection-lifecycle-dev07.md).

SQLAlchemy instalado 2.1.5; API de versionamento consultada via Context7 na [documentação 2.x](https://docs.sqlalchemy.org/en/20/orm/versioning.html).
