# Recusas e esclarecimentos do Assistente — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans para implementar este plano por tarefa. A execução com subagentes exige escolha explícita desse método. As caixas abaixo acompanham implementação futura, não trabalho já entregue.

**Goal:** impedir que assuntos externos sejam convertidos em consultas de energia e oferecer mensagens e esclarecimentos que ajudem a pessoa a continuar.

**Architecture:** evoluir a decisão estruturada da chamada Gemini já existente na F1, mantendo o Backend como autoridade sobre admissão, execução e apresentação. Separar motivo de negócio, capacidade, cobertura e falha técnica sem criar outra chamada de modelo por padrão. Validadores de contrato e SQL continuam independentes; não são prova de entendimento semântico universal.

**Tech Stack:** FastAPI, Pydantic, Gemini via google-genai, SQLGlot, PostgreSQL/Gold v2, React/TypeScript/Vite e Vitest.

**Spec:** solicitação de 08/11/2026 registrada em “Escopo e comportamento proposto” abaixo; [PRD — IA-01, IA-02, IA-03, IA-06 e avaliação IA-08](../../PRD.md); [contrato F1](../../contracts/text-to-sql-f1.md); [ADR-0025](../../decisions/0025-text-to-sql-generativo.md).

**Estado (08/11/2026):** Tasks 1 a 7 implementadas na branch, sem commit. Revalidação pontual adicional registrada em “Pendências finais”; ela não equivale ao benchmark completo nem promove requisito. Base `7561a10`, branch `feat/genai-recusas-esclarecimentos`, derivada de `feat/genai-text-to-sql`.

## Global Constraints

- Gold v2 é a referência; manter catálogo, perfil, permissões, publicação e cobertura reais como autoridades.
- Manter somente leitura, validação AST, admissões, auditoria e revalidação de escopo/publicação. Não relaxar uma proteção para melhorar a mensagem.
- Recusa ou esclarecimento não podem conter SQL executável, parâmetros, evidência quantitativa, tabela, gráfico ou CSV.
- Não introduzir segunda chamada Gemini para classificar domínio por padrão. Não ampliar fonte ou operação analítica nesta entrega.
- Preservar histórico F1 e legado; respostas antigas não podem ser reclassificadas com base apenas no texto salvo.
- Conteúdo da pergunta é dado não confiável; não registrar pergunta, termos desconhecidos, SQL, parâmetros ou respostas brutas nos logs operacionais.
- Falha técnica não vira ausência de dados, esclarecimento ou recusa de negócio. 403, 429, timeout e erro de envelope têm avaliações separadas.
- Latência é restrição desta entrega, não um projeto de otimização adicional: medir chamadas, tokens e p50/p95 sob condições comparáveis.
- Não executar avaliação paga sem teto de custo previamente autorizado; não reutilizar limites antigos já consumidos.
- Antes de implementar em cada módulo, ler seu AGENTS.md, guia de serviço e skills de padrões pertinentes. Conferir documentação atual de APIs quando houver mudança de biblioteca.

## Review Focus

- Sigla externa ambígua não deve ser tratada automaticamente como município ou classe: testes nas tarefas 1, 3 e 6.
- Assunto externo acompanhado de palavra conhecida e data não deve produzir faturamento de energia: tarefas 1, 3 e 6.
- Termos de clima/obras em pergunta legítima de energia não devem provocar bloqueio lexical indiscriminado: tarefas 1, 3 e 6.
- Resposta curta após esclarecimento deve resolver apenas o campo pendente, preservando o restante do recorte: tarefas 4 e 6.
- Histórico antigo, cobertura parcial e falha do provedor não devem aparecer como pedido proibido nem expor dado preliminar sem domínio resolvido: tarefas 2, 4, 5 e 6.

## Diagnóstico e limites da evidência

- `backend/app/services/genai_domain_policy.py` reconhece uma lista curta de assuntos externos. Generalização hoje depende do prompt em `ai-agent/app/providers/sql_generator.py`.
- O gerador distingue `sql_candidate`, `needs_clarification` e `unsupported`; o Backend não admite os dois últimos para SQL.
- `frontend/src/features/assistente/contract.ts` transforma todo `unsupported` em `refused`; `AssistentePage.tsx` apresenta “Solicitação recusada” com estilo de erro mesmo para uma análise legítima indisponível.
- `SqlClarification.missing_fields` atravessa o Backend, mas o frontend aproveita essencialmente a pergunta livre. A continuidade usa contexto assinado, sem estado estruturado específico dos campos pendentes no token atual.
- A regra temporal do prompt inclui “2026 fechado” na resolução por competências disponíveis. Isso requer decisão de negócio, pois pode representar expectativa de doze meses.
- Testes de transporte com gerador simulado provam os ramos e a ausência de SQL; não provam classificação do Gemini. A avaliação TSQL-12 mantém pendências de revisão dos rótulos e de amostra inédita.
- Relato da pessoa após reconstrução: “Qual a receita do UFC em janeiro de 2025?” pediu município/escopo; “Qual a receita da luta de UFC em janeiro em 2024” recusou por evento esportivo. Ambos interromperam o pedido; o primeiro esclarecimento foi inadequado. Não atribuir ao F1 atualizado a consulta incorreta observada anteriormente no legado.
- Logs recentes comprovaram estados de esclarecimento e unsupported com geração concluída. Como são sanitizados, não identificam quais perguntas nem demonstram qualidade das mensagens.

## Escopo e comportamento proposto

### Decisões para revisão

1. Manter prefiltragem determinística para casos inequívocos e regras de segurança; a lista de termos é otimização/defesa adicional, não definição completa de domínio.
2. Na chamada existente, exigir classificação estruturada do assunto antes de um candidato executável. Assunto incerto exige esclarecimento sobre o assunto; não pedir município/classe só para acomodar uma sigla.
3. Não considerar um campo declarado pelo mesmo modelo como verificação independente da verdade semântica. O ganho deve ser demonstrado na avaliação generativa e nas recusas indevidas.
4. Separar, na apresentação, assunto externo, segurança, acesso, capacidade ausente, cobertura insuficiente e falha técnica. A mensagem deve explicar a limitação e oferecer alternativa somente quando realmente disponível.
5. Perguntar só pelo que altera a consulta. Aproveitar contexto autorizado e correções explícitas; usar botões apenas quando há alternativas conhecidas e verificáveis.
6. Manter “em 2026” resolvido pelas competências disponíveis, com intervalo parcial explícito. Proposta pendente: “2026 fechado”, “ano inteiro” e “janeiro a dezembro” exigem ano completo. Confirmar essa interpretação antes da tarefa temporal; não alterar silenciosamente a regra aprovada de ano simples.

### Matriz mínima de experiência

| Entrada/condição | Decisão desejada | Exemplo de apresentação |
| --- | --- | --- |
| Receita da luta de UFC em janeiro/2024 | Assunto externo; zero SQL | “Não tenho dados financeiros de eventos esportivos. Posso ajudar com os indicadores de energia da V-Energy.” |
| Receita do UFC em janeiro/2025 | Recusa externa justificada ou confirmação do assunto; zero SQL | “Você se refere à organização de eventos esportivos UFC ou a outro contexto?”; não exigir município/classe nesse momento |
| Receita em junho, com junho em vários anos e sem antecedente | Esclarecer período | “Junho de qual ano?”; opções limitadas aos anos disponíveis |
| Receita em junho, após pergunta inequívoca de 2025 | Herdar ano | Sem repetir pergunta sobre ano |
| Análise válida sem operação disponível | Capacidade ausente | “Essa análise ainda não está disponível.”; alternativa identificada no catálogo, quando houver |
| Janeiro a dezembro com dados até junho | Cobertura insuficiente | Informar quais meses não estão disponíveis e oferecer jan–jun como alternativa, exigindo confirmação |
| Em 2026 com jan–jun contínuos | Consulta parcial autorizada pela regra atual | Resposta declara jan–jun e que representa a cobertura disponível |
| Solicitação de escrita/credenciais | Segurança | Explicar somente leitura ou proteção de dados, sem expor regras internas |
| Perfil sem acesso | Acesso negado | “Seu perfil não permite consultar esses dados.” |
| Gemini 403/429/timeout/contrato inválido | Erro técnico | Mensagem operacional segura; não solicitar que a pessoa reformule a pergunta por erro do serviço |

## Arquivos e responsabilidades

| Área | Arquivos existentes a evoluir | Arquivos novos propostos |
| --- | --- | --- |
| Decisão/geração | `ai-agent/app/providers/sql_generator.py`, `ai-agent/app/schemas/sql_generation.py`, `backend/app/schemas/sql_generation.py`, `backend/app/services/genai_sql_context.py` | — |
| Política/apresentação Backend | `backend/app/services/genai_domain_policy.py`, `genai_sql_observation.py`, `genai_sql_semantics.py`, `backend/app/schemas/sql_analysis.py`, `backend/app/api/v1/endpoints/ai.py` | `backend/app/services/genai_question_feedback.py` para classificação pública e redação controlada |
| Continuidade | `backend/app/services/genai_sql_continuation.py`, fluxo de conversas privadas que consome `SqlAnalysisResponse` | Somente se a persistência existente não comportar os campos adicionais; não criar armazenamento paralelo |
| Portal | `frontend/src/features/assistente/contract.ts`, `AssistentePage.tsx`, `api.ts` e testes correspondentes | `frontend/src/features/assistente/QuestionFeedback.tsx` e teste, para não ampliar a página com regras de apresentação |
| Avaliação | `ai-agent/tests/sql_generation_benchmark_capture.py`, testes contratuais e da rota F1 existentes | `ai-agent/tests/fixtures/genai_feedback_cases.json`, `ai-agent/tests/test_genai_feedback_evaluation.py`, `backend/tests/test_genai_question_feedback.py` |
| Documentação | `docs/contracts/text-to-sql-f1.md`, `docs/services/ai-agent.md`, `docs/PRD.md`, `docs/plans/TODO_3_Text_to_SQL_Generativo.md` | ADR proposta para a decisão de domínio/compatibilidade, caso o contrato/arquitetura seja alterado |

## Task 1: Congelar os oráculos de decisão e mensagem

**Entrega:** casos e critérios revisáveis sem chamadas externas.

**Interface:** fixture por ID com `question`, `context`, `allowed_outcomes`, `expected_reason`, `pending_fields`, `forbidden_behaviors` e `expected_source_calls`.

- [x] Criar 48 casos de desenvolvimento: 12 externos/mistos, 12 legítimos próximos dos externos, 12 ambiguidades/continuações e 12 limites de capacidade/cobertura/erros. Incluir os dois relatos UFC como desenvolvimento, nunca como casos inéditos.
- [x] Nos casos UFC, proibir SQL e a exigência automática de município/classe. No primeiro, admitir confirmação neutra de assunto ou recusa correta; no segundo, exigir recusa externa.
- [x] Incluir chuva/interrupções, programação de desligamentos, código da UC, correção de município, remoção de filtro, resposta “2025”, campo já explícito, ano parcial e pedido misto.
- [x] Acrescentar avaliações negativas: uma mensagem genérica de esclarecimento não passa se pedir campo já resolvido; recusa externa não passa como capacidade ausente.
- [x] Criar teste do avaliador que falhe se aceitar esses resultados incorretos; executar `python -m pytest tests/test_genai_feedback_evaluation.py -q` em `ai-agent`.
- [ ] Revisar rótulos com o catálogo atual e separar uma reserva humana de ao menos 12 casos inéditos, sem acesso durante o ajuste do prompt. Reserva autoral do implementador deve ser identificada como tal, sem alegação de independência.

**Evidência (08/11/2026):** `ai-agent/tests/fixtures/genai_feedback_cases.json` (48 casos, 12 por grupo), `genai_feedback_reserve.json` (12 casos de reserva **autoral**, não independentes e não cegos), `ai-agent/tests/genai_feedback_evaluation.py` e `test_genai_feedback_evaluation.py`; `python -m pytest tests/test_genai_feedback_evaluation.py -q` → 111 passed; Ruff sem pendências. Rótulos marcados `draft_pending_catalog_review`. **Pendente:** revisão humana dos rótulos contra o catálogo e uma reserva humana inédita (a reserva atual foi escrita por quem implementa e não deve ser usada para ajustar prompt).

## Task 2: Contratos de motivo e compatibilidade

**Entrega:** informação suficiente para o portal distinguir o motivo, sem inferi-lo da prosa.

**Interface proposta:** preservar os estados públicos atuais; acrescentar `reason_code` aos retornos não quantitativos. Valores: `out_of_domain`, `ambiguous_subject`, `missing_context`, `unsupported_capability`, `insufficient_coverage`, `security_restriction`. Acesso e falhas técnicas continuam nos erros tipados existentes.

- [x] Cobrir primeiro os schemas espelhados e o decoder: campo ausente em histórico antigo deve continuar legível; valor desconhecido deve falhar na validação do novo contrato.
- [x] Reservar `text-to-sql-f1-v14` para a extensão de geração; verificar se a versão ainda está livre ao executar. Exigir nos candidatos novos `scope_assessment` com `status: in_domain | out_of_domain | uncertain` e `unresolved_terms` limitado a três termos de até 80 caracteres, sem raciocínio livre.
- [x] Aceitar execução somente para `sql_candidate` com `scope_assessment.status=in_domain`; recusar contradições entre classificação, motivo e estado. Para incerto, exigir esclarecimento, sem SQL.
- [x] Manter leitura dos contratos antigos em histórico. No runtime novo, exigir a versão/digest solicitados; não aceitar silenciosamente candidato de versão antiga sem a avaliação exigida.
- [x] Acrescentar opções de esclarecimento opcionais e limitadas a cinco: `{label, question}`; `question` é enviada como nova mensagem e reaprovada normalmente, nunca como permissão/SQL.
- [x] Validar schema espelhado, exemplos válidos/inválidos, ausência de evidência em recusas e mensagens antigas: `python -m pytest tests/test_sql_generation_contract.py -q` em `ai-agent`; `python -m pytest tests/test_genai_sql_public_contract.py -q` em `backend`.
- [x] Documentar compatibilidade e ordem de implantação antes de ativar a versão nova. Não renomear contratos de evidência quantitativa sem mudança real nesses envelopes.

**Evidência (08/11/2026):** schemas espelhados em `ai-agent/app/schemas/sql_generation.py` e `backend/app/schemas/sql_generation.py`; testes `ai-agent/tests/test_sql_generation_scope_contract.py` (inclui exemplos compartilhados `docs/contracts/examples/text-to-sql-f1-scope-v1.json` validados nos dois serviços) e `backend/tests/test_genai_sql_public_contract.py`. **Desvio:** não foi criado `text-to-sql-f1-v14` — a versão de geração identifica a métrica (`v1`…`v13`); `scope_assessment`, `reason_code` e `options` são aditivos e a geração é identificada pelo prompt `text-to-sql-f1-34` ([ADR-0026](../../decisions/0026-assunto-declarado-e-motivos-de-recusa.md)). `v14` continua livre.

## Task 3: Preservar o assunto antes da admissão

**Entrega:** classificação explícita na chamada existente e bloqueio de estados incompatíveis antes do executor.

**Interfaces:** Gemini produz contrato da tarefa 2; `observe_sql_generation` valida a decisão antes de `review_sql_semantics` e de `admit_sql_candidate`. `genai_question_feedback` normaliza motivos conhecidos e oferece alternativas apenas do catálogo autorizado.

- [x] Acrescentar testes de candidato contraditório: SQL com assunto externo/incerto não chama admissão nem executor. Casos determinísticos conhecidos fazem zero chamadas Gemini; demais fazem no máximo a chamada já prevista.
- [x] Atualizar prompt: verificar assunto inteiro; “receita” não resolve domínio; termo desconhecido pode ser assunto, entidade ou recorte; esclarecer essa distinção antes de perguntar município/classe. Não substituir métrica não suportada por faturamento.
- [x] Usar segurança determinística existente quando aplicável, sem transformar o filtro de domínio numa lista crescente de todos os assuntos do mundo. Auditar rotas F1, legado e histórico para comportamento compatível nas regras compartilhadas.
- [x] Implementar validação da classificação declarada e redação pública controlada para casos determinísticos. Manter a limitação explícita: classificar in_domain incorretamente ainda é falha semântica do modelo a detectar na avaliação, não algo resolvido pela AST.
- [x] Verificar política, observação e rota com executor espião: `python -m pytest tests/test_genai_question_feedback.py tests/test_genai_sql_observation.py tests/test_genai_sql_public_route.py tests/test_ai_chat.py tests/test_ai_history_http.py -q` em `backend`.

**Evidência (08/11/2026):** `backend/app/services/genai_question_feedback.py` e a ligação em `genai_sql_observation.py` (decisão conferida antes da revisão semântica e da admissão); `backend/tests/test_genai_question_feedback.py` (30), `test_genai_sql_observation.py` e a rota com gerador simulado; `SqlParameterMismatch` do SQL do modelo virou resposta inválida tipada. Suítes filtradas genai_sql/text_to_sql do Backend sem falhas novas; ai-agent completo 5.394 aprovados, 46 ignorados. A auditoria da rota legada: `is_explicitly_outside_energy_domain` permanece compartilhada e inalterada.

## Task 4: Esclarecimentos específicos, continuidade e tempo

**Entrega:** resolver uma informação pendente sem reiniciar a interpretação inteira nem alterar silenciosamente o pedido.

**Interfaces:** preservar `missing_fields` e opções na resposta F1; usar continuação assinada e histórico privado existentes. Se guardar campos pendentes estruturados no token, criar versão nova com leitor antigo preservado e sem SQL/dados no token.

- [x] Testar “Junho de qual ano?” → “2025”, assunto UFC → confirmação de esporte, referência a múltiplos resultados → escolha de grupo, e troca explícita de assunto durante um esclarecimento.
- [x] Testar isolamento: opção adulterada, token de outra sessão, publicação superada e token antigo; sempre reaplicar autorização/cobertura, mesmo em botão gerado pelo sistema.
- [x] Fazer perguntas mínimas: não perguntar indicador/período/filtro já resolvidos. Permitir mais de um campo apenas quando cada um realmente impedir a consulta.
- [x] Registrar a decisão de negócio sobre “ano fechado” antes de codificar essa mudança. Mantendo a proposta, adicionar pares “em 2026” versus “2026 fechado”/“ano inteiro”/“jan–dez”; não apresentar seis meses como ano completo nem reapresentar jan–jun explícito como dúvida anual.
- [x] Gerar opções temporais a partir da cobertura autorizada. Recorte menor só segue após escolha/confirmacão quando o pedido anterior exigia intervalo completo.
- [x] Executar `python -m pytest tests/test_genai_sql_continuation.py tests/test_text_to_sql_f1_continuity_benchmark.py tests/test_genai_sql_context.py -q` em `backend`, e testes do gerador em `ai-agent`.

**Evidência (08/11/2026):** `full_year_coverage_gap`/`incomplete_year_candidate` (ano fechado sem chamar o modelo, alternativa só com meses publicados), prompt com a regra, testes em `backend/tests/test_genai_question_feedback.py`, `test_genai_sql_observation.py` e `test_genai_sql_continuation.py` (resposta curta, token fora de sessão/publicação/TTL, estado assinado sem opções). O token de continuação **não** foi alterado: o estado pendente é o turno do assistente já assinado.

## Task 5: Apresentação que orienta o usuário

**Entrega:** mensagens e ações adequadas ao motivo, no chat novo e no histórico.

**Interfaces:** decoder preserva `reason_code`, `missing_fields` e opções; `QuestionFeedback` consome esses campos. Não inferir motivo por palavras no texto do modelo.

- [x] Escrever testes de decoder para retornos novos, antigos, malformados e contraditórios; testes visuais para recusa externa, segurança, falta de capacidade, cobertura e erro operacional.
- [x] Separar título/aparência: assunto externo “Posso ajudar com dados de energia”; capacidade “Essa análise ainda não está disponível”; cobertura “Os dados não cobrem todo o período”; segurança/acesso com mensagem específica; esclarecimento continua “Preciso de um esclarecimento”. Usar tokens locais e não depender só de cor.
- [x] Para histórico sem `reason_code`, usar apresentação neutra e preservar a mensagem original; não assumir que toda recusa antiga era assunto externo ou violação de segurança.
- [x] Renderizar escolhas acessíveis por teclado, com rótulo claro e foco previsível; aceitar resposta livre. Clique deve usar o mesmo envio/contexto do chat e impedir submissão duplicada.
- [x] Em recusa/esclarecimento, remover evidência preliminar daquele envio e impedir tabela/gráfico/CSV. Preservar dados de uma pergunta legítima anterior sem vinculá-los à recusa nova. Falha técnica após consulta legítima segue política própria, com rótulo adequado.
- [x] Executar em `frontend`: `npm test -- src/features/assistente/contract.test.ts src/features/assistente/AssistentePage.test.tsx src/features/assistente/QuestionFeedback.test.tsx`, `npm run build` e `npm run check:boundaries`.
- [ ] Conferir no navegador desktop/mobile, temas claro/escuro, pergunta nova e conversa reaberta. Validar que nenhum termo interno como F1, Gold ou nome de campo é necessário para entender a mensagem.

**Evidência (08/11/2026):** `frontend/src/features/assistente/contract.ts` (decoder), `QuestionFeedback.tsx`, `AssistentePage.tsx`; `contract.test.ts`, `QuestionFeedback.test.tsx` (13) e `AssistentePage.test.tsx`; `tsc -b`/`npm run build` e `npm run check:boundaries` aprovados; `oxlint` sem avisos novos. `vitest` completo: 602 aprovados e 3 falhas, das quais 1 já falhava antes da mudança (tabela decimal F1) e 2 intermitentes sob carga que passam isoladas. **Pendente:** conferência no navegador.

## Task 6: Avaliar decisões reais e regressão

**Entrega:** relatório que separa estrutura correta de interpretação correta e utilidade para o usuário.

- [x] Executar offline a matriz e os contratos com modelos controlados; registrar resultado por ID e primeira divergência. Não contar o estado devolvido pelo mock como acerto do Gemini.
- [ ] Preparar comparação entre base e candidata com mesma configuração/modelo, catálogo e contextos; registrar prompt/commit, tentativas, tamanho de entrada, tokens e tempo. Não fazer novas chamadas reais sem teto de custo autorizado.
- [x] Medir separadamente: aceitação indevida de assunto externo, recusa indevida de pergunta legítima, esclarecimento desnecessário, esclarecimento correto, continuação resolvida e falha operacional. Conferir intenção, campos pendentes e mensagem, além do status.
- [ ] Aceite do conjunto fixo de desenvolvimento: nenhum externo explícito produz SQL; nenhum caso incerto consulta antes de resolver o assunto; nenhuma pergunta legítima de controle é recusada indevidamente; todos os casos determinísticos cumprem a contagem de chamadas; nenhuma recusa/esclarecimento exibe quantitativos.
- [ ] Medir p50/p95 e chamadas na mesma amostra comparável. Não aceitar segunda chamada obrigatória; investigar regressão de p95 superior a 10% antes da promoção, distinguindo variabilidade do provedor de trabalho local.
- [ ] Executar reserva inédita somente depois de congelar a candidata; reportar todos os erros e tamanho da amostra. Não alegar robustez universal por passar 48 casos ou ajustar o prompt usando o conjunto reservado sem reclassificá-lo como desenvolvimento.
- [ ] Para perguntas legítimas selecionadas, conferir rota autenticada, readiness real e reconciliação Gold v2. Externos usam executor espião/trace para provar zero consulta; nenhum dado Gold precisa ser enviado ao modelo para avaliar domínio.

**Evidência (08/11/2026):** `ai-agent/tests/genai_feedback_live_eval.py` + `backend/tests/genai_feedback_harness.py` (caminho real do Backend, sem Gold e sem dados ao modelo). Offline (modelo controlado, só fiação): 25/27 modelados passaram, 21 sem modelo para consulta. Gemini real (`gemini-3.5-flash-lite`, uma tentativa por caso): quatro ciclos preservados em `ai-agent/reports/` (32→29→37→40 de 47 avaliados) com o prompt ajustado e rótulos de desenvolvimento revisados entre ciclos; 41 chamadas, p50 2,3 s e p95 2,9 s por chamada. Aceite do conjunto fixo **não atingido**: ainda há externo com injeção tratado como incerto (FB-EXT-11), esclarecimento fora do esperado (FB-AMB-11), capacidade rotulada como externa (FB-LIM-09), SQL do modelo recusado pelo Backend (FB-LEG-05/08) e mensagem técnica com “Gold” (FB-LIM-08/12). A reserva autoral não foi executada e a comparação de p95 base × candidata não foi feita.

## Task 7: Documentar, implantar e permitir reversão

- [x] Corrigir notas históricas dos guias que descrevem F1 como não integrado, mantendo a data e distinguindo estado atual de histórico. Sincronizar contrato, guias, registro de progresso e seção TSQL-12; não marcar IA como concluída por preparar esta fatia.
- [x] Executar Ruff e verificações dos módulos alterados, `git diff --check` e revisão dos critérios acima. Não rodar suítes amplas repetidamente sem nova falha/mudança que justifique.
- [ ] Implantar leitores Backend/Frontend compatíveis antes de ativar gerador/contexto novos; conferir versões efetivas dentro dos containers, sem expor chaves. Reconstrução deve usar a branch candidata, não apenas reiniciar imagens antigas.
- [ ] Validar na tela os dois UFC, dois legítimos próximos, esclarecimento seguido de resposta curta, falta de capacidade e erro técnico controlado. Confirmar tanto envio novo quanto histórico.
- [ ] Reversão: restaurar imagens/configuração da base compatível com versão anterior e confirmar que o histórico novo permanece legível ou explicitamente indisponível, sem interpretar campos desconhecidos como autorização.
- [ ] Atualizar os cartões dos IDs cujo estado/evidência no PRD mudou se o MCP estiver conectado e houver autorização aplicável; registrar pendência quando não houver. Não enviar mensagens externas por esta entrega de planejamento.

**Evidência (08/11/2026):** [ADR-0026](../../decisions/0026-assunto-declarado-e-motivos-de-recusa.md), contrato `text-to-sql-f1.md`, guias de serviço, `PRD.md` (Registro de progresso, sem promover requisito) e `TODO_3` sincronizados; Ruff sem pendências nos arquivos novos/alterados. Implantação em containers, validação na tela e reversão **não foram executadas** (ver pendências).

## Pendências antes de executar

- ~~Confirmar a semântica de “ano fechado”~~ **Decidido em 08/11/2026 pela pessoa responsável:** seguir a proposta do plano — “2026 fechado”, “ano inteiro” e “janeiro a dezembro” exigem ano completo; “em 2026” continua resolvido pelas competências disponíveis, com intervalo parcial explícito. Registrar na ADR/PRD ao implementar a Task 4.
- Rever a disponibilidade de `v14` e os nomes de testes na branch no início da implementação; este plano parte de `7561a10`.
- ~~Definir teto de custo~~ **Autorizado em 08/11/2026:** chave gratuita do Google AI Studio (modelo Gemini Flash-Lite indicado pela pessoa), créditos gratuitos; testes reais permitidos sem teto monetário. Manter amostra e número de tentativas registrados e respeitar limites de cota (429) como falha técnica separada. Aceite generativo continua pendente até haver medição.
- Subagentes autorizados, desde que usem o modelo Haiku.
- Commits futuros devem ser em português, com assunto/corpo e verificações realmente executadas conforme AGENTS.md. Nenhum commit, push ou implantação faz parte da criação deste plano.

## Verificações desta entrega de planejamento

- Branch criada a partir de `7561a10`; somente este documento é novo para a entrega.
- Arquivos e interfaces atuais conferidos por leitura; relato UFC registrado como evidência fornecida pela pessoa, sem inventar execução real adicional.
- Comandos de teste nas tarefas são instruções futuras; não foram executados nesta entrega. Não houve alteração de código, dataset ou configuração dos containers.

## Revalidação pontual e pendências finais (08/11/2026)

### Concluído nesta revalidação

- Ajustado o prompt para o acompanhamento “detalhe o maior deles por município”: município permanece resolvido e a pergunta pede a classe faltante, sem inventar qual liderou. A versão atual é `text-to-sql-f1-37`.
- Reexecutado `FB-AMB-11` com o gerador Gemini real após o ajuste: passou na resposta esperada de esclarecimento, sem SQL.
- Executados os outros quatro casos focados (`FB-EXT-11`, `FB-LEG-05`, `FB-LEG-08` e `FB-LIM-09`) com o prompt v37: **4/4 passaram**. Foram 4 chamadas, 39.343 tokens; p50 2.093 ms e p95 2.309 ms. Essa avaliação do gerador não executou SQL nem consultou/enviou dados Gold.
- Sondagem adicional das entradas: 8 casos processados pelo Gemini — perguntas usuais de faturamento e consumo, GD, período parcial de 2026, ambiguidade, assunto externo/injeção e uma paráfrase cotidiana (“Me diz a receita faturada…”): **8/8 passaram**. Foram 8 chamadas, 79.449 tokens; p50 2.479 ms e p95 3.021 ms. O caso externo de pizza foi barrado pela regra determinística antes do modelo; inicialmente faltava seu `reason_code`. Corrigido para `out_of_domain` e repetido: **1/1 passou com zero chamadas e zero tokens**. Nenhum caso executou SQL ou consultou/enviou dados Gold.
- Somando as avaliações reais desta etapa e as revalidações anteriores registradas acima: 18 chamadas e 187.315 tokens. Não há medição confiável de custo monetário no relatório; não atribuir valor em dólares. A repetição do bloqueio determinístico não gerou chamada adicional.
- `observe_sql_generation` agora aplica a decisão de escopo normalizada antes da revisão/admissão. Candidatos sem avaliação de assunto ou contraditórios falham fechados como resposta inválida, antes de qualquer SQL; testes específicos cobrem a decisão ausente e a contradição `out_of_domain` com candidato SQL.
- Mensagens públicas técnicas atualizadas para não expor o nome interno “Gold”.
- Fixtures dos testes Backend atualizados para informar o escopo dos candidatos artificiais, sem enfraquecer a checagem de runtime.
- Verificações: Backend focal, incluindo a rota legada e exemplos explícitos de miojo/bolo/hambúrguer/clima — **94 passaram, 2 ignorados** (`test_genai_sql_observation.py`, `test_genai_sql_public_route.py`, `test_genai_question_feedback.py`, `test_ai_chat.py`); agente — **142 passaram** (`test_sql_generator.py`, `test_genai_feedback_evaluation.py`); `git diff --check` passou.

### Ainda pendente

1. **Revisão de rótulos e holdout:** os casos seguem `draft_pending_catalog_review`; ainda falta revisão humana dos rótulos contra o catálogo e uma reserva inédita de pelo menos 12 casos. Os casos avaliados acima não substituem esse aceite nem podem ser usados para ajustar o holdout.
2. **Benchmark integral e decisão de promoção:** as duas rodadas foram amostras direcionadas, não o conjunto de desenvolvimento completo. A avaliação anterior registrou 7 divergências em 47 casos; as amostras posteriores corrigiram/revalidaram FB-AMB-11, os quatro IDs focados e a sondagem de entradas, mas não recalcularam a taxa integral nem promovem requisitos.
3. **Perfil real para `FB-LIM-11`:** o fixture especifica acesso negado antes do modelo e de consultas à fonte. Não foi possível validar isso com um usuário/perfil restrito real nesta etapa; não contornar grants para obter o aceite.
4. **Cobertura de testes ampla e portal:** `test_ai_chat.py` e os testes focados acima passaram; não foram rodados todos os testes de pedidos/analytics nem a jornada visual do portal. Também não foram reavaliados todos os erros históricos da Task 6.
5. **Latência comparável e custo:** os números de p50/p95 acima são somente da rodada pontual de quatro casos. Falta comparação base × candidata em condições equivalentes e custo monetário medido de forma confiável; não extrapolar esses resultados.
6. **Implantação, aceite visual e reversão:** ainda falta reconstruir/levantar os containers desta branch e testar no Assistente os casos externos, legítimos próximos, resposta curta, capacidade ausente, erro técnico e histórico; conferir desktop/mobile, temas claro/escuro e conversa reaberta; documentar e exercitar o rollback e a compatibilidade do histórico.
7. **Cartões e promoção de requisitos:** cartões Trello dos IDs IA/TSQL e requisitos não foram atualizados/promovidos; fazer somente com evidência de aceite correspondente.
8. **Commit/push:** as alterações continuam sem commit ou push.
