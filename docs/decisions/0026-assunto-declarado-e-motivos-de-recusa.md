# ADR-0026 — Assunto declarado e motivos tipados de recusa e esclarecimento

**Data:** 08/11/2026. **Estado:** implementada na branch `feat/genai-recusas-esclarecimentos`; aceite generativo (TSQL-12) permanece pendente.
**Requisitos:** IA-01, IA-02, IA-03, IA-06 e a avaliação IA-08. Plano: [recusas e esclarecimentos](../superpowers/plans/2026-11-08-recusas-esclarecimentos-genai.md).

## Contexto

Dois relatos reais do Assistente mostraram assuntos externos virando perguntas de energia: “receita do UFC em janeiro de 2025” pediu município/classe, e a variação com “luta de UFC” foi recusada só por uma lista curta de termos. O portal também apresentava toda recusa como “Solicitação recusada”, inclusive uma análise legítima ainda indisponível, e usava apenas a prosa do modelo para o esclarecimento.

## Decisão

1. A chamada Gemini já existente passa a declarar `scope_assessment` (`in_domain`, `out_of_domain` ou `uncertain`, com até três `unresolved_terms` de até 80 caracteres e sem raciocínio livre). Não há segunda chamada de modelo. A declaração é um dado não confiável: o Backend só a confere contra o estado do candidato (`genai_question_feedback.enforce_scope_decision`); ela não prova entendimento semântico, e uma classificação errada continua sendo falha do modelo medida na avaliação.
2. Somente `sql_candidate` com `in_domain` chega à revisão semântica, à admissão e ao executor. Assunto incerto exige esclarecimento de assunto; assunto externo exige recusa. Candidato sem a avaliação, ou contraditório, é resposta inválida do provedor (falha técnica), nunca esclarecimento nem recusa de negócio.
3. Recusas e esclarecimentos carregam `reason_code` tipado: `out_of_domain`, `ambiguous_subject`, `missing_context`, `unsupported_capability`, `insufficient_coverage`, `security_restriction`. Acesso negado e falhas técnicas continuam nos erros tipados existentes. O portal escolhe título e apresentação pelo código, nunca pela prosa; histórico sem código usa apresentação neutra com a mensagem original.
4. O esclarecimento pode trazer até cinco opções `{label, question}`. A pergunta da opção é enviada como nova mensagem e reaprovada normalmente (identidade, escopo, publicação, cobertura); nunca é permissão nem SQL. O Backend descarta opções duplicadas ou com forma de comando SQL.
5. Sigla ou termo desconhecido não é município nem classe: com assunto incerto o Backend substitui qualquer pergunta por município/classe por uma pergunta neutra sobre o assunto.
6. Ano fechado (decisão da pessoa responsável, 08/11/2026): “em 2026” continua resolvido pelas competências disponíveis, com o intervalo parcial declarado na resposta. “2026 fechado”, “ano inteiro” e “janeiro a dezembro” exigem o ano completo: sem as doze competências o Backend responde `insufficient_coverage` sem chamar o modelo, informa os meses ausentes e oferece somente o recorte já publicado, que só segue após confirmação. Intervalo parcial escrito pela própria pessoa não é reapresentado como dúvida anual.

## Desvio do plano: sem `text-to-sql-f1-v14`

O plano reservava `v14` para esta extensão. A versão `generation_contract_version` identifica a métrica/operação que o candidato pode executar (`v1`…`v13`, escolhida por `build_sql_generation_context`); uma nova versão passaria a significar uma métrica. Por isso a extensão é **aditiva e independente dessa versão**: `scope_assessment`, `reason_code` e `options` são opcionais no schema espelhado (leitura de histórico e de contratos antigos) e exigidos pelo runtime novo. A versão do prompt (`text-to-sql-f1-34`) identifica a geração que os produz. `v14` permanece livre.

## Compatibilidade, implantação e reversão

- Leitores primeiro: Backend e portal aceitam os campos novos como opcionais antes de o gerador passar a emitir. Valor desconhecido de `reason_code` invalida a resposta; campo ausente continua legível.
- O Backend novo exige `scope_assessment`; um gerador antigo (sem o campo) produz resposta inválida do provedor. Implante GenAI e Backend juntos, na ordem: Backend e portal compatíveis, depois a GenAI com o prompt novo.
- Reversão: restaurar as imagens da base `7561a10`. O histórico novo continua legível pelos leitores antigos? **Não**: o `SqlAnalysisResponse` antigo é fechado e rejeitaria `reason_code`/`options`; conversas salvas durante a janela do prompt novo ficam indisponíveis, sem serem reinterpretadas como autorização, até a reimplantação. Registrar essa janela antes da ativação.

## Limites

Validadores de contrato e SQL permanecem independentes e não são prova de entendimento semântico. Esta decisão não amplia fonte, métrica ou operação, não altera segurança, e não substitui a revisão humana dos rótulos nem uma reserva inédita para o aceite TSQL-12.
