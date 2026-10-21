# Decisões arquiteturais (ADR)

Registre aqui escolhas que alterem contratos, métricas, banco, frameworks, privacidade ou limites da solução. Cada ADR deve conter **data, estado, contexto, opções consideradas, decisão, consequências e IDs do PRD afetados**. Atualize o PRD e os guias relacionados na mesma mudança.

- [ADR-0001 — Arquitetura do frontend](0001-arquitetura-frontend.md): aprovada em 18/10/2026 para a fundação modular, antes da implementação visual e funcional das páginas.
- [ADR-0002 — Backend como proprietário da consulta analítica Gold](0002-genai-gold-query-owner.md): proposta em 18/10/2026, pendente de revisão de Backend e Engenharia de Dados.
- [ADR-0003 — Reconciliação da ingestão e captura de registros malformados na Bronze](0003-reconciliacao-e-captura-de-registros-malformados.md): proposta para reconciliar registros da Bronze e preservar registros malformados para auditoria.
- [ADR-0004 — Ciclo operacional, auditoria e concorrência das ordens de inspeção](0004-ciclo-operacional-e-concorrencia-das-ordens-de-inspecao.md): aprovada em 20/10/2026 para governar estados, transições, resultado obrigatório, cancelamento, idempotência e auditoria de WEB-05.
