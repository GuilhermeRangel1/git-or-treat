# ADR-0025 — Transição quantitativa para SQL proposto pelo modelo

**Data:** 05/11/2026. **Estado:** direção autorizada pela pessoa usuária no chat; implementação e aceite integrado em andamento.
**Requisitos:** IA-01/02/03/05/06/07/08; ENT-01 conforme as capacidades efetivamente entregues.

## Contexto

O caminho Gold existente interpreta deterministicamente, produz `LogicalReadPlan`, compila SQL no Backend e sintetiza evidência. A pessoa usuária solicitou a migração descrita no documento Text-to-SQL e autorizou iniciar alterações na branch `feat/genai-text-to-sql`. A hipótese é ampliar combinações analíticas sem representar cada operação no planner antigo. Ganho de qualidade/cobertura ainda depende de benchmark numérico e uso real.

## Decisão

1. O Gemini poderá propor SQL PostgreSQL parametrizado e uma interpretação estruturada. O candidato é entrada não confiável, não autorização.
2. O Backend mantém identidade, escopo, publicação, prontidão, validação final, credencial, execução SQL e auditoria. A GenAI permanece sem conexão Gold.
3. Adaptar controles do validador SQL demonstrativo para módulo local do Backend. SQLGlot já existe na GenAI; sua inclusão no Backend e o subconjunto permitido serão entregas testadas. Não importar o pacote `app` de um serviço no outro.
4. Contratos Python independentes nos serviços usam fixtures comuns e teste de compatibilidade. Novo contrato interno do candidato: `text-to-sql-f1-v1`. Ele ainda não é aceito pelas rotas existentes de plano/síntese.
5. Primeiro escopo: `billing.revenue` sobre `gold_v2.diagnostico_receita`, município/classe/competência, soma, agrupamento, ranking simples e comparação de duas janelas com diferença em reais. JOIN e reparo ficam posteriores.
6. PostgreSQL/psycopg é o primeiro alvo Gold, coerente com ADR-0017, Compose e fábrica de conexão. SQLite permanece compatibilidade demonstrativa/teste sem aceite generativo implícito.
7. Preservar orçamento total de 60 s, teto SQL de 5 s e espera do navegador de 70 s como referência operacional existente. Novos componentes consomem o saldo; configuração não reinicia por tentativa.
8. O caminho determinístico permanece o caminho implantado até integração, benchmark e ativação explícita da estratégia. Retirada será uma entrega posterior com rollback, não uma consequência deste ADR.
9. Planejar transporte separado autenticado em `POST /api/v1/internal/sql-candidates` e, após contrato de resultado, `POST /api/v1/internal/sql-syntheses`. São rotas internas a implementar: não alteram os envelopes atuais de `question-plans`/`question-syntheses` ou o contrato público. Token técnico, correlação e saldo de prazo seguem a fronteira interna existente; identidade/autorização de pessoa continuam resolvidas no Backend.

## Relação com a ADR-0002

Esta decisão substitui **na arquitetura-alvo autorizada** a proibição de o modelo produzir SQL e a exigência de transportar exclusivamente um plano lógico. Preserva integralmente a propriedade de execução no Backend. A ADR-0002 continua descrevendo o caminho implantado enquanto a estratégia nova não estiver habilitada. Não há liberação antecipada de SQL por uma interpretação deste texto.

## Contrato e migração

O [contrato F1 e matriz de consumidores](../contracts/text-to-sql-f1.md) define estados, limites, evidências e componentes que precisam de adaptação. O catálogo continua `gold-catalog-v2`, Gold física `gold-csv-v2`; versões desses artefatos não são a versão HTTP pública.

Catálogo e metadados instalados não certificam a publicação real. Contexto permitido não autoriza SQL candidato. Envelope validado não substitui AST, regras empresariais, grants, snapshot ou referência numérica independente.

## Alternativas e consequências

- Ampliar apenas intenção/planner preservaria compilação determinística, mas manteria o contrato de operações como limite da exploração. O trabalho experimental pode ajudar a comparação, sem tornar-se dependência obrigatória do gerador SQL.
- Executar SQL diretamente pela GenAI duplicaria propriedade de acesso/credenciais; a decisão mantém um único executor no Backend.
- Um pacote compartilhado de código exigiria empacotamento e implantação adicionais. Neste início, contratos independentes e fixtures cruzadas seguem o padrão existente; divergência é detectada por teste.

São necessárias mudanças em evidência, síntese, contexto/histórico, cache, replay e visualização. Nenhuma dessas compatibilidades é presumida por existir SQL válido.

## Estado de validação

Nesta entrega existem contratos testados, construtor de contexto e adaptador de geração em preparação. Não há endpoint generativo habilitado nem novo executor Gold. Aceite exige composição real, SQL validado no Backend, prova numérica independente, Gold autorizado e jornada portal no escopo da F1. Os estados oficiais IA/ENT do PRD permanecem preservados.
