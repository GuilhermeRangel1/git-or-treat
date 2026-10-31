# ADR-0002 — Backend como proprietário da consulta analítica Gold

**Data:** 2026-10-18 (proposta inicial); revisada em 2026-10-25
**Estado:** aprovada em 25/10/2026. A aprovação se baseia nos comentários de concordância no PR #54 do Backend (Felipe) e da Engenharia de Dados (Júlia), com o Guilherme da GenAI; não houve Approve formal no GitHub. Ela cobre a decisão: Backend como executor único das consultas Gold, fluxo planejar → executar → sintetizar e banco local alimentado pelos CSV da Gold. Não autoriza adaptador Gold, credencial ou consulta real; essas dependem das pendências de implementação listadas no fim deste documento.
**IDs do PRD afetados:** IA-01, IA-03, IA-06, DE-06, DE-08, P-04
**Contrato detalhado:** [Contrato interno de planejamento e síntese entre Backend e GenAI](../contracts/genai-query-execution.md)

## Contexto

A GenAI precisa consultar evidências Gold para responder perguntas e fundamentar os números. O banco local, o esquema Gold e as métricas ainda não foram aprovados. Na data da proposta inicial, `POST /api/v1/ai/query` do Backend era um scaffold que validava uma lista de nomes de tabela e devolvia `records: []`, sem executar consulta ou demonstrar credencial somente leitura. Desde 23/10/2026, essa rota valida a entrada e devolve 503, sem sugerir falsamente uma consulta Gold bem sucedida. O modelo analítico implementado também não representa ainda o catálogo Gold do case.

O enunciado do case pede que a Gold seja exportada para um banco local e que o agente consulte esse banco local. Hoje existem duas bases técnicas que tornam a decisão urgente:

- o núcleo da GenAI já separa interpretação, plano lógico (`LogicalReadPlan`), política de acesso (`ReadAccessPolicy`), porta de evidências (`EvidenceSource.retrieve(plan, access_context)`), validação da evidência (`EvidenceGuard`) e conferência das afirmações numéricas (`has_unsupported_claims`, em `app/agent/grounding.py`);
- a GenAI também tem um leitor SQL demonstrativo (`app/sql/`), usado só com banco sintético. Ele não aprova acesso direto da GenAI ao banco real.

É necessário definir quem controla execução, autorização, limites e auditoria antes de conectar o agente a dados reais. Portal e agente também precisam compartilhar definições e números consistentes.

## Opções consideradas

1. **Backend como dono da consulta (escolhida nesta proposta):** a GenAI produz um plano lógico; o Backend revalida o plano contra o catálogo aprovado e o escopo da pessoa usuária, executa a consulta parametrizada com papel somente leitura e devolve evidência agregada com proveniência. A GenAI sintetiza a resposta só a partir dessa evidência.
   - Benefícios: um único consumidor do esquema físico e das credenciais; autorização, limites e auditoria no mesmo serviço que já atende o portal; portal e agente leem a mesma fonte com as mesmas regras.
   - Custos: o fluxo de perguntas passa a ter duas chamadas internas à GenAI; o Backend precisa de catálogo semântico, executor e auditoria próprios.
2. **GenAI acessa diretamente o banco local:** a GenAI recebe credencial somente leitura e executa as consultas com o leitor de `app/sql/`.
   - Benefícios: menos chamadas entre serviços; reaproveita o leitor demonstrativo.
   - Custos e riscos: segundo consumidor direto do esquema e das permissões; controles e catálogo duplicados entre Backend e GenAI; credencial de banco no serviço que também conversa com o provedor do modelo.
3. **GenAI chama de volta a API pública do Backend durante a resposta:** a GenAI implementaria `EvidenceSource` como cliente HTTP do Backend.
   - Rejeitada: cria dependência circular entre serviços, mistura a identidade do serviço com a da pessoa usuária e dificulta orçamento e correlação.

## Decisão

Aprovada por Backend e Engenharia de Dados em 25/10/2026 (ver Estado):

1. **O Backend é o único executor das consultas SQL da Gold.** A GenAI não recebe credenciais do banco, não executa SQL contra a Gold e o modelo não produz SQL executável. O plano trocado entre os serviços é lógico: identificadores de catálogo, sem nomes físicos de tabela ou coluna.
2. **Fluxo.** O Backend coordena as etapas; a GenAI não chama de volta a API pública do Backend.

   ```text
   Portal → API pública do Backend (POST /api/v1/ai/questions)
          → GenAI: planejar (interpretação, guardrails, plano lógico)
          → Backend: revalidar o plano e consultar a Gold no banco local
          → GenAI: sintetizar a resposta a partir das evidências
          → Backend → Portal (envelope público v1)
   ```

3. **Fonte dos dados.** A consulta em tempo de execução usa o banco local alimentado pelos CSV da Gold exportados do Databricks (DE-06). O Databricks não é consultado em tempo de execução; serve à reconciliação entre Gold e banco local prevista em DE-06. A escolha do motor (SQLite ou PostgreSQL) segue em aberto no P-04 e não altera o contrato lógico. Definições, unidades e granularidades vêm do dicionário Gold (DE-08).
4. **Contrato.** As duas operações internas, os estados, a identidade, os prazos e os exemplos ficam em [genai-query-execution.md](../contracts/genai-query-execution.md). Campos que ainda não existem no código estão marcados ali como propostos.

## Consequências

### O que muda na GenAI

- O orquestrador de perguntas (`QuestionOrchestrator`) passa a expor duas operações internas, **planejar** e **sintetizar**, em vez de executar a fonte dentro de uma única chamada. A divisão segue as fronteiras que já existem:
  - planejar reutiliza `QuestionSafetyGate`, `QuestionInterpreter`, `ReadPlanBuilder` e `ReadPlanValidator.approve` e para antes de `EvidenceSource.retrieve`;
  - sintetizar revalida o plano, aplica `EvidenceGuard.validate(plan, result)` à evidência recebida do Backend, chama o modelo pelo `ExecutionController` e confere as afirmações com `has_unsupported_claims` antes de montar o `QuestionResponse`.
- Interpretação, guardrails, `EvidenceGuard`, grounding, roteamento de modelos, orçamento e os contratos públicos permanecem. O modo demonstrativo com fixture ou SQLite sintético continua disponível para desenvolvimento e CI.
- O leitor SQL de `app/sql/` não é ligado à Gold. Pode servir de referência para os controles que o Backend implementar.

### O que muda no Backend

- Novo executor da consulta Gold atrás da rota pública de perguntas: revalida o plano contra o catálogo aprovado e o escopo da pessoa usuária, traduz o plano lógico em consulta parametrizada, aplica limite de linhas, timeout e papel somente leitura no banco local.
- Coordena as chamadas à GenAI (planejar e sintetizar) e propaga a mesma correlação.
- Registra auditoria da execução: correlação, quem pediu, fingerprint do plano, versão do catálogo, lote, quantidade de linhas e resultado, sem SQL com valores nem dados pessoais.
- A rota legada `POST /api/v1/ai/query` continua indisponível (503) e não é reaproveitada como executor.

### O que continua igual

- Os contratos públicos `POST /api/v1/ai/questions` e `POST /api/v1/ai/insights` não mudam; o portal continua chamando só o Backend.
- O insight do Panorama continua com o contexto calculado pelo Backend ([panorama-insight-api.md](../contracts/panorama-insight-api.md)); a ligação com a Gold fica para o cartão de insight.
- `GenAI` continua sem estado de sessão e sem identidade própria da pessoa usuária.
- Nenhum requisito IA-01 a IA-06 muda de estado por causa desta decisão.

### Verificação

- Antes do primeiro adaptador real, Backend e GenAI revisam juntos os exemplos do contrato e criam testes de: plano aceito e rejeitado, escopo indevido, evidência adulterada, ausência de evidência, timeout, papel somente leitura e rastreabilidade.
- A implementação real depende do P-04, do dicionário Gold (DE-08) e da carga no banco local (DE-06).
- Se o time escolher acesso direto da GenAI ao banco, esta ADR deve ser revista com a explicação de como evitar catálogos e controles duplicados.

## Pontos a confirmar com Backend e Dados

Estes pontos são pendências de implementação, não da decisão: precisam ser resolvidos antes do primeiro adaptador Gold, mas não reabrem a escolha do executor, do fluxo ou da fonte. Os pontos marcados com "resposta recebida no PR #54" tiveram resposta nos comentários de revisão; o que segue em aberto em cada um está descrito no próprio ponto.

1. **Catálogo semântico.** _Resposta recebida no PR #54._ A fonte dos identificadores de métrica, dimensão e campo de evidência é o dicionário Gold (DE-08). A `catalog_version` não deve ser congelada antes da decisão sobre as colunas expostas da Visão 360 e da fila (A5 da revisão da Gold), ainda em andamento. Segue em aberto como a `catalog_version` é publicada e conferida pelos dois serviços.
2. **Lote e versão.** _Resposta recebida no PR #54._ Proposta: o `batch_ref` identifica o lote efetivamente carregado e validado no banco local, não apenas a última execução no Databricks. Ele é derivado dos registros de `gold.controle_gold` (`run_id_silver`, `lote_bronze_silver`, `status_gold`, `tabelas_geradas`, `processado_em`), considerando só execuções com `status_gold = CONCLUIDO`. A exportação dos CSV leva um pequeno manifesto com esses valores, e a carga no banco local registra qual manifesto foi carregado e validado. O formato exato do identificador fica para combinar com quem é dona da exportação da Gold. Também a combinar: quando faltam metadados de execução, o notebook grava os valores de reserva `SINTETICO_DEV` e `LOTE_DEV` em `controle_gold`, e `status_gold` é sempre `CONCLUIDO`; filtrar só por `CONCLUIDO` não descarta esses registros. O manifesto deve excluí-los ou sinalizá-los, e a carga no banco local deve recusar um lote com esses valores. Detalhes na seção "Lote da Gold" do contrato.
3. **Identidade e escopo.** _Resposta recebida no PR #54._ Decisão proposta: autenticação individual da pessoa usuária é dependência para habilitar o fluxo Gold fora do ambiente local. Estado do Backend na branch `develop` em 25/10/2026: `ORDERS_AUTH_MODE` tem valor padrão `service`; o modo `oidc` é exigido quando `APP_ENV=production`; a demo local das ordens usa `demo` e não identifica a pessoa; o OIDC existe como preparação para a jornada com identificação da pessoa. No chat com a GenAI, o token Bearer autentica só a comunicação Backend → GenAI e não identifica quem usa o portal nem define o escopo de acesso à Gold. O token de serviço não substitui a identidade. Perguntas abertas: a autenticação individual será dependência para consultas Gold fora do ambiente local, considerando que perfis por cargo são diferencial (WEB-10) no PRD? Como a identidade se traduz em métricas e dimensões permitidas?
4. **Prazos.** Definido pela pessoa usuária em 30/10/2026: 35 s totais, SQL com teto de 5 s e propagação do saldo pelo campo interno `remaining_timeout_ms`, sem reiniciar o orçamento. O contrato detalha validação, consumidor, migração e limites da preparação; ativação do coordenador continua pendente.
5. **Ausência e esclarecimento vindos da consulta.** Confirmado pela pessoa usuária em 31/10/2026: todo lookup concluído válido segue para síntese, inclusive ausência e esclarecimento, com mensagens determinísticas no núcleo. Falhas de execução encerram o fluxo. A implementação no coordenador pertence a GENAI-07.
6. **Auditoria durável.** Onde o Backend grava a trilha de execução e quem a consulta? A referência pública `audit_reference` continua nula até essa trilha existir.
7. **Papel no banco.** _Resposta recebida no PR #54._ O service principal do Databricks não participa da execução. A permissão somente leitura continua necessária no banco local usado pelo Backend. Segue a confirmar quem cria e mantém esse papel e como isso é testado no motor escolhido no P-04.
8. **Rotas internas.** Confirmadas pela pessoa usuária em 31/10/2026: `POST /api/v1/internal/question-plans` e `POST /api/v1/internal/question-syntheses`, no serviço GenAI e chamadas exclusivamente pelo Backend. Convivem com `POST /api/v1/questions` durante a transição; o fluxo Gold não usa a rota demonstrativa como fallback. GENAI-07 implementará transporte e coordenação, reutilizando `QuestionOrchestrator.plan()` e `synthesize()`.


### 30/10/2026 — finalização contratual para a Gold CSV v2

A versão final do pacote é `gold-csv-v2`; o envelope interno permanece v1 em preparação. Os parsers dos dois serviços preservam v1/v2 explicitamente e rejeitam versões desconhecidas; uma publicação de versão diferente da esperada é incompatível, sem fallback. O Backend permanece o único executor SQL. O prazo total de 35 s e teto SQL de 5 s foram aprovados pela pessoa usuária nesta revisão; a aplicação ao transporte e ao executor exige a integração prevista nos cartões seguintes. Política `completed_lookup` e exemplos finais serão submetidos à revisão do PR #79; não há alegação de aprovação conjunta adicional ou aceite Gold.
