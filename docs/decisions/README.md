# Decisões arquiteturais (ADR)

Registre aqui escolhas que alterem contratos, métricas, banco, frameworks, privacidade ou limites da solução. Cada ADR deve conter **data, estado, contexto, opções consideradas, decisão, consequências e IDs do PRD afetados**. Atualize o PRD e os guias relacionados na mesma mudança.

- [ADR-0001 — Arquitetura do frontend](0001-arquitetura-frontend.md): aprovada em 18/10/2026 para a fundação modular, antes da implementação visual e funcional das páginas.
- [ADR-0002 — Backend como proprietário da consulta analítica Gold](0002-genai-gold-query-owner.md): proposta em 18/10/2026, pendente de revisão de Backend e Engenharia de Dados.
- [ADR-0003 — Reconciliação da ingestão e captura de registros malformados na Bronze](0003-reconciliacao-e-captura-de-registros-malformados.md): proposta para reconciliar registros da Bronze e preservar registros malformados para auditoria.
- [ADR-0004 — Contratos analíticos e fonte sintética](0004-contratos-analiticos-e-fonte-sintetica.md): aprovada em 20/10/2026 para preparar a DEV-01 sem antecipar o esquema físico da Gold.
- [ADR-0005 — Python 3.12 com Docker Hardened Alpine](0005-backend-python312-alpine.md): aprovada em 20/10/2026 para usar uma base oficial já corrigida, com testes dentro do contêiner e PostgreSQL descartável.
- [ADR-0006 — Contrato de produto do Panorama em rota própria](0006-panorama-fonte-produto-e-contrato-dev01.md): aprovada em 21/10/2026 para publicar a WEB-01 em `GET /api/v1/panorama`, preservando o contrato analítico da DEV-01 em `GET /api/v1/kpis`.

- [ADR-0007 — Contenção de segurança das ordens e entradas](0007-contencao-seguranca-ordens-e-entradas.md): política conservadora implementada na correção de 21/10/2026; revisão do time pendente.
- [ADR-0008 — Exploração demonstrativa da receita por extremos](0008-exploracao-demonstrativa-receita.md): aprovada para DEV-03 em 21/10/2026; cobertura explícita, base pequena, preço observado e reconciliação, sem substituir a definição Gold ou as janelas anuais finais.
- [ADR-0009 — Consulta da UC em resumo e históricos independentes](0009-uc360-contratos-de-consulta.md): aprovada para a demonstração DEV-04 em 22/10/2026; comparação e paginação sem quebrar contratos DEV-01, com cobertura por UC/fonte/medida.
