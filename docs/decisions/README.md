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
- [ADR-0006 — Contrato de produto do Panorama em rota própria](0006-panorama-fonte-produto-e-contrato-dev01.md): aprovada em 21/10/2026 para publicar a WEB-01 em `GET /api/v1/panorama`, preservando o contrato analítico da DEV-01 em `GET /api/v1/kpis`.

- [ADR-0007 — Contenção de segurança das ordens e entradas](0007-contencao-seguranca-ordens-e-entradas.md): política conservadora implementada na correção de 21/10/2026; revisão do time pendente.
- [ADR-0008 — Exploração demonstrativa da receita por extremos](0008-exploracao-demonstrativa-receita.md): aprovada para DEV-03 em 21/10/2026; cobertura explícita, base pequena, preço observado e reconciliação, sem substituir a definição Gold ou as janelas anuais finais.
- [ADR-0009 — Consulta da UC em resumo e históricos independentes](0009-uc360-contratos-de-consulta.md): aprovada para a demonstração DEV-04 em 22/10/2026; comparação e paginação sem quebrar contratos DEV-01, com cobertura por UC/fonte/medida.
- [ADR-0010 — Prioridade e estimativa auditáveis na fila sintética](0010-fila-de-inspecao-sintetica.md): adotada para DEV-05 em 22/10/2026; regra demonstrativa, evidências explícitas e revisão futura com a Gold. Renumerada na integração DEV-06 com develop para preservar as ADRs 0008 de Receita e 0009 de UC.
- [ADR-0011 — Uma ordem de inspeção ativa por UC](0011-ordem-ativa-por-uc.md): adotada em 23/10/2026 no alinhamento DEV-06/DEV-07 solicitado pela pessoa usuária; unicidade operacional por UC, reenvio independente da fonte e migração sem cancelamento automático.
- [ADR-0012 — Identidade individual nas ordens e proxy sem credenciais](0012-autenticacao-individual-das-ordens.md): adotada no pedido de segurança de 23/10/2026; validação OIDC, permissões por ação, produção sem token compartilhado e portas locais. Revisada na mesma data: login adiado; modo demo sintético local sem Bearer preserva a tela básica.
- [ADR-0013 — Composição da interface e carregamento das páginas](0013-composicao-ui-e-carregamento-frontend.md): aprovada em 23/10/2026 para compartilhar botões/modais, dividir a UC 360 e carregar as demais rotas sob demanda, preservando o Panorama para revisão futura.
