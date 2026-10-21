# Decisões arquiteturais

Este diretório mantém registros de decisões arquiteturais por módulo. As decisões técnicas da Engenharia de Dados,
incluindo a decisão consolidada da Bronze para DE-01, estão em
[`data-engineering/decisoes-tecnicas.md`](../../data-engineering/decisoes-tecnicas.md),
junto do contexto, das alternativas, das consequências e das pendências de validação. Atualize o PRD e os guias
relacionados na mesma mudança.

- [ADR-0001 — Arquitetura do frontend](0001-arquitetura-frontend.md): aprovada em 18/10/2026 para a fundação modular, antes da implementação visual e funcional das páginas.
- [ADR-0002 — Backend como proprietário da consulta analítica Gold](0002-genai-gold-query-owner.md): proposta em 18/10/2026, pendente de revisão de Backend e Engenharia de Dados.
- [ADR-0004 — Contratos analíticos e fonte sintética](0004-contratos-analiticos-e-fonte-sintetica.md): aprovada em 20/10/2026 para preparar a DEV-01 sem antecipar o esquema físico da Gold.
- [ADR-0005 — Python 3.12 com Docker Hardened Alpine](0005-backend-python312-alpine.md): aprovada em 20/10/2026 para usar uma base oficial já corrigida, com testes dentro do contêiner e PostgreSQL descartável.
