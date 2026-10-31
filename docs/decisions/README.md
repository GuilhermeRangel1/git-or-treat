# Decisões arquiteturais

Este diretório mantém registros de decisões arquiteturais por módulo. As decisões técnicas da Engenharia de Dados,
incluindo a decisão consolidada da Bronze para DE-01, estão em
[`data-engineering/decisoes-tecnicas.md`](../../data-engineering/decisoes-tecnicas.md),
junto do contexto, das alternativas, das consequências e das pendências de validação. Atualize o PRD e os guias
relacionados na mesma mudança.

- [ADR-0001 — Arquitetura do frontend](0001-arquitetura-frontend.md): aprovada em 18/10/2026 para a fundação modular, antes da implementação visual e funcional das páginas.
- [ADR-0002 — Backend como proprietário da consulta analítica Gold](0002-genai-gold-query-owner.md): proposta em 18/10/2026 e aprovada em 25/10/2026.
  - Revisão de 25/10/2026 (GENAI-01, PR #54): Backend como único executor SQL da Gold no banco local, com fluxo planejar → executar → sintetizar coordenado pelo Backend. Aprovada com base nos comentários de concordância de Backend e Engenharia de Dados no PR #54, sem Approve formal no GitHub; não autoriza adaptador Gold, credencial ou consulta real. Contrato em [genai-query-execution.md](../contracts/genai-query-execution.md).
- [ADR-0004 — Contratos analíticos e fonte sintética](0004-contratos-analiticos-e-fonte-sintetica.md): aprovada em 20/10/2026 para preparar a DEV-01 sem antecipar o esquema físico da Gold.
- [ADR-0005 — Python 3.12 com Docker Hardened Alpine](0005-backend-python312-alpine.md): aprovada em 20/10/2026 para usar uma base oficial já corrigida, com testes dentro do contêiner e PostgreSQL descartável.
- [ADR-0006 — Contrato de produto do Panorama em rota própria](0006-panorama-fonte-produto-e-contrato-dev01.md): aprovada em 21/10/2026 para publicar a WEB-01 em `GET /api/v1/panorama`, preservando o contrato analítico da DEV-01 em `GET /api/v1/kpis`.

- [ADR-0007 — Contenção de segurança das ordens e entradas](0007-contencao-seguranca-ordens-e-entradas.md): política conservadora implementada na correção de 21/10/2026; revisão do time pendente.
- [ADR-0008 — Exploração demonstrativa da receita por extremos](0008-exploracao-demonstrativa-receita.md): aprovada para DEV-03 em 21/10/2026; cobertura explícita, base pequena, preço observado e reconciliação, sem substituir a definição Gold ou as janelas anuais finais.
- [ADR-0009 — Consulta da UC em resumo e históricos independentes](0009-uc360-contratos-de-consulta.md): aprovada para a demonstração DEV-04 em 22/10/2026; comparação e paginação sem quebrar contratos DEV-01, com cobertura por UC/fonte/medida.
- [ADR-0010 — Prioridade e estimativa auditáveis na fila sintética](0010-fila-de-inspecao-sintetica.md): adotada para DEV-05 em 22/10/2026; regra demonstrativa, evidências explícitas e revisão futura com a Gold. Renumerada na integração DEV-06 com develop para preservar as ADRs 0008 de Receita e 0009 de UC.
- [ADR-0011 — Uma ordem de inspeção ativa por UC](0011-ordem-ativa-por-uc.md): adotada em 23/10/2026 no alinhamento DEV-06/DEV-07 solicitado pela pessoa usuária; unicidade operacional por UC, reenvio independente da fonte e migração sem cancelamento automático.
- [ADR-0012 — Identidade individual nas ordens e proxy sem credenciais](0012-autenticacao-individual-das-ordens.md): princípios de identidade no servidor, proxy sem credenciais e demo sintética; arquitetura vigente em ADR-0020.
- [ADR-0013 — Composição da interface e carregamento das páginas](0013-composicao-ui-e-carregamento-frontend.md): aprovada em 23/10/2026 para compartilhar botões/modais, dividir a UC 360 e carregar as demais rotas sob demanda, preservando o Panorama para revisão futura.
- [ADR-0014 — Integração DEV-07/DEV-06](0014-integracao-do-ciclo-operacional-dev07.md): estados compatíveis com DEV-06, histórico transacional, concorrência por versão e convergência das migrações.
- [ADR-0015 — Consolidado demonstrativo de continuidade](0015-consolidado-demonstrativo-de-continuidade.md): aprovada em 26/10/2026 para DEV-08; consolidação por numeradores e denominadores originais dos alimentadores elegíveis, com base parcial e exclusões explícitas, sem homologação Gold/regulatória.
- [ADR-0016 — Priorização de melhorias pré-Gold](0016-priorizacao-melhorias-pre-gold.md): aprovada em 27/10/2026 para a Fase 1 reduzida de oito IDs; preserva as 41 observações restantes para reavaliação sem as classificar todas como defeitos ou dependências técnicas da Gold.
- [ADR-0017 — PostgreSQL como banco local da Gold](0017-banco-local-postgresql.md): aprovada em 27/10/2026 para o P-04, com base nos comentários de Backend e Engenharia de Dados no PR #63; PostgreSQL 16 como banco local, Backend como executor único e papel somente leitura `venergy_gold_reader` (`SELECT` no schema `gold`) mantido pelo Backend. Pendência do Backend: alinhar o `docker-compose.yml` (hoje `postgres:18`) à versão 16.
- [ADR-0018 — API analítica sobre a publicação Gold](0018-api-gold-dev13-1.md): implementação técnica da DEV-13.1 em 28/10/2026; contratos Gold v2, identidade por lote/fingerprint, leitura consistente, categorias/evidências reais e ordens preservadas. Homologação de negócio e aceite do portal permanecem pendentes.
- [ADR-0020 — Autenticação individual por sessão do backend](0020-autenticacao-backend-por-sessao.md): sessão opaca persistida, cookie HttpOnly e provisão local; autenticação/jornada principal validadas, com WEB-10/WEB-11 ainda pendentes no escopo completo.

- [D20 — projeção cadastral restrita](../../data-engineering/decisoes-tecnicas.md#93-exclusão-de-dados-pessoais-na-projeção-gold-d20-decidido): revisão pontual solicitada em 30/10/2026 para nome de exibição do titular, fora dos agregados e da GenAI; contratos e ACLs do consumidor continuam pendentes.
