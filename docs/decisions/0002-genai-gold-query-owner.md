# ADR-0002 — Backend como proprietário da consulta analítica Gold

**Data:** 2026-10-18
**Estado:** proposta — aguarda revisão de Backend e Engenharia de Dados
**IDs do PRD afetados:** IA-01, IA-03, IA-06, DE-06, DE-08, P-04

## Contexto

A GenAI precisa consultar evidências Gold para responder perguntas e fundamentar os números. O banco local, o esquema Gold e as métricas ainda não foram aprovados. O endpoint atual `POST /api/v1/ai/query` do Backend é um scaffold: valida uma lista de nomes de tabela e sempre devolve `records: []`; não executa consulta nem demonstra credencial somente leitura. O modelo analítico implementado também não representa ainda o catálogo Gold do case.

É necessário definir quem controla a execução, autorização, limites e auditoria antes de conectar o agente a dados reais. Portal e agente também precisam compartilhar definições e números consistentes.

## Opções consideradas

1. **Backend como dono da consulta (proposta):** o agente envia uma intenção analítica estruturada a uma API versionada do Backend; o Backend valida o catálogo, aplica filtros e executa a consulta com controles próprios. O agente recebe resultados agregados e proveniência.
2. **GenAI acessa diretamente o banco local:** o serviço GenAI recebe credencial somente leitura, mantém sua própria validação e executa consultas ao banco. Isso duplica parte dos controles e cria um segundo consumidor direto do esquema e das permissões.

## Decisão proposta

Propor que o **Backend seja dono da consulta Gold**, incluindo autorização, allowlist semântica, execução parametrizada, limites, timeout e auditoria. A GenAI deve enviar uma intenção tipada — métrica, dimensões, período e filtros — e não SQL livre nem nomes de tabelas físicas. O Backend deve retornar somente linhas agregadas necessárias à resposta, com unidade, período, filtros efetivamente aplicados, referência/versão da Gold, limitações de qualidade e estado de ausência de evidência.

Contrato conceitual para revisão, sem fixar rota, nomes de métricas, tabelas ou fórmulas:

- **Solicitação:** identificador estável da métrica, dimensões solicitadas, intervalo temporal e filtros tipados.
- **Resposta:** estado (`available`, `no_evidence` ou `needs_clarification`), registros agregados, unidade, período e filtros aplicados, referência e versão do lote, limitações e identificador de correlação.
- **Responsabilidades:** GenAI identifica intenção, resolve ambiguidade e redige apenas a partir da evidência recebida; Backend autoriza o chamador, valida identificadores contra o catálogo aprovado, parametriza valores, aplica limite/timeout e não expõe SQL ao consumidor.

Esta é uma recomendação para decisão conjunta, não uma decisão aprovada. Backend e Engenharia de Dados devem confirmar a propriedade, o contrato e a divisão de responsabilidades antes de qualquer adaptador Gold real.

## Consequências e verificação

- A API `POST /api/v1/ai/query` existente permanece um placeholder e não deve ser tratada como fonte analítica funcional.
- A porta interna da GenAI pode ser validada com a fixture sintética, sem definir o contrato HTTP entre serviços.
- A implementação real depende da decisão P-04, do esquema/dicionário Gold e da carga exportada ao banco local.
- Após aprovação, Backend e GenAI devem revisar juntos exemplos de solicitação/resposta e testes de autorização, consulta somente leitura, ausência de evidência, limites e rastreabilidade.
- Se o time escolher acesso direto da GenAI ao banco, revisar esta ADR e documentar como serão evitados controles e catálogos duplicados.
