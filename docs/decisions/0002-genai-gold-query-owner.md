# ADR-0002 — Backend como proprietário da consulta analítica Gold

**Data:** 2026-10-18 (proposta inicial); revisada em 2026-10-25
**Estado:** proposta — houve alinhamento no grupo em 24/10/2026, com concordância do Backend e do Guilherme. Passa a aprovada quando Backend e Engenharia de Dados aprovarem o PR que traz esta revisão (#XX). Até lá, nenhuma parte desta decisão autoriza adaptador Gold, credencial ou consulta real.
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

Proposta para aprovação de Backend e Engenharia de Dados:

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

1. **Catálogo semântico.** Onde fica a fonte única dos identificadores de métrica, dimensão e campo de evidência (perfil da GenAI, catálogo do Backend ou arquivo gerado do dicionário Gold)? Como a `catalog_version` é publicada e conferida pelos dois serviços?
2. **Lote e versão.** Qual identificador de lote ou carga a exportação Gold → banco local disponibiliza, e como o Backend o lê em cada consulta? Esse valor alimenta o campo proposto `batch_ref` da evidência.
3. **Identidade e escopo.** Qual mecanismo de autenticação de pessoa usuária o Backend vai adotar, e como ele traduz a identidade em métricas e dimensões permitidas? Até existir, o fluxo Gold não deve ser habilitado fora do ambiente local.
4. **Prazos.** O Backend aceita um prazo total maior que os 35 s atuais (`AI_AGENT_TIMEOUT_SECONDS`) ou cada etapa recebe uma fatia fixa? Ver a seção de orçamento do contrato.
5. **Ausência e esclarecimento vindos da consulta.** O Backend sempre envia o resultado da consulta para a operação sintetizar, mesmo em `no_evidence`, ou responde diretamente ao portal nesses casos? A proposta é sempre enviar, para que mensagens e auditoria fiquem em um só lugar.
6. **Auditoria durável.** Onde o Backend grava a trilha de execução e quem a consulta? A referência pública `audit_reference` continua nula até essa trilha existir.
7. **Papel no banco.** Quem cria e mantém o papel somente leitura no banco local e como isso é testado no motor escolhido no P-04.
8. **Rotas internas.** Os nomes e o caminho das duas rotas internas da GenAI, e se elas convivem com `POST /api/v1/questions` durante a transição.
