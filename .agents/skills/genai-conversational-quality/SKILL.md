---
name: genai-conversational-quality
description: Melhore clareza, naturalidade, esclarecimentos e continuidade das respostas do Assistente e dos insights GenAI com evidências verificáveis.
---

# Qualidade conversacional do GenAI

Avalie a pergunta, o contexto autorizado, a evidência recebida e a resposta efetivamente exibida. Use a [genai-gold](../genai-gold/SKILL.md) para localizar o fluxo. Falhas anteriores à síntese precisam ser diagnosticadas na etapa responsável.

## Localizar o limite da resposta

Confira o [orquestrador](../../../ai-agent/app/agent/orchestrator.py), os [prompts](../../../ai-agent/app/generation/prompts.py), a [seleção de observações](../../../ai-agent/app/generation/selection.py) e o consumidor do portal. Identifique quais partes vêm do modelo e quais são compostas em código. Alterar um prompt só melhora os trechos que o runtime usa.

## Produzir uma explicação útil

Responda diretamente à pergunta com os valores relevantes, unidade e recorte temporal. Acrescente interpretação proporcional às evidências e referências verificáveis. Adapte o detalhe à pergunta, preservando filtros e limitações necessários para entender os números.

Mantenha valores e cálculos ligados às observações ou resultados derivados identificáveis. A narrativa pode explicar diferenças e padrões sustentados, distinguindo observação, hipótese e causalidade comprovada. A verificação numérica deve aceitar a formatação legítima das unidades e do português sem liberar afirmações sem suporte.

Quando faltar capacidade, explique a operação ausente e ofereça uma alternativa executável, se houver. Quando faltar dado ou cobertura, diga qual evidência falta. Em ambiguidades relevantes, peça a informação que muda a consulta e aproveite o contexto já validado.

## Preservar continuidade

Leia o [contrato de acompanhamento](../../../docs/contracts/genai-follow-up.md) ao alterar herança de período, métrica ou filtros. Confira a troca explícita de assunto, contexto vencido e isolamento de conversas. Trate a mensagem atual como correção quando ela modifica o recorte anterior.

## Avaliar a experiência

Compare respostas para perguntas inéditas e acompanhamentos pela entrada usada pelo portal. Revise correção, aderência à pergunta, clareza de esclarecimentos, utilidade e fidelidade das referências. Use [genai-evaluation](../genai-evaluation/SKILL.md) para registrar os resultados. Ganhos de naturalidade precisam coexistir com números reconciliados e limitações visíveis.
