# Decisões arquiteturais (ADR)

Registre aqui escolhas que alterem contratos, métricas, banco, frameworks, privacidade ou limites da solução. Cada ADR deve conter **data, estado, contexto, opções consideradas, decisão, consequências e IDs do PRD afetados**. Atualize o PRD e os guias relacionados na mesma mudança.

- [ADR-0001 — Arquitetura do frontend](0001-arquitetura-frontend.md): aprovada em 18/10/2026 para a fundação modular, antes da implementação visual e funcional das páginas.
- [ADR-0002 — Backend como proprietário da consulta analítica Gold](0002-genai-gold-query-owner.md): proposta em 18/10/2026, pendente de revisão de Backend e Engenharia de Dados.
- [ADR-0003 — Reconciliação da ingestão e captura de registros malformados na Bronze](0003-reconciliacao-e-captura-de-registros-malformados.md): proposta para reconciliar registros da Bronze e preservar registros malformados para auditoria.
- [ADR-0004 — Contratos analíticos e fonte sintética](0004-contratos-analiticos-e-fonte-sintetica.md): aprovada em 20/10/2026 para preparar a DEV-01 sem antecipar o esquema físico da Gold.
- [ADR-0005 — Python 3.12 com Docker Hardened Alpine](0005-backend-python312-alpine.md): aprovada em 20/10/2026 para usar uma base oficial já corrigida, com testes dentro do contêiner e PostgreSQL descartável.
- [ADR-0006 — Exploração demonstrativa da receita por extremos](0006-exploracao-demonstrativa-receita.md): aprovada para DEV-03 em 21/10/2026; cobertura explícita, base pequena, preço observado e reconciliação, sem substituir a definição Gold ou as janelas anuais finais.
