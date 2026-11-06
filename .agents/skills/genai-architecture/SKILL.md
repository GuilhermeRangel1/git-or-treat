---
name: genai-architecture
description: Diagnostique limitações arquiteturais do GenAI e planeje evolução da interpretação semântica, dos planos analíticos e da síntese neste repositório.
---

# Evolução arquitetural do GenAI

Use a [genai-gold](../genai-gold/SKILL.md) para localizar requisitos, composição e fronteiras de validação. Relacione a mudança aos IDs IA do [PRD](../../../docs/PRD.md) e às decisões vigentes. Uma proposta de arquitetura precisa distinguir hipótese de diagnóstico observado.

## Localizar a falha

Rastreie uma pergunta representativa pela entrada pública, interpretação, plano, execução, evidência e resposta. Registre a primeira etapa que diverge da intenção esperada, com símbolos e resultado observável. Diferencie intenção mal interpretada, capacidade ausente, cobertura insuficiente, recusa indevida e síntese pouco útil.

Confira especialmente o [interpretador](../../../ai-agent/app/agent/interpreter.py), a [recuperação de linguagem](../../../ai-agent/app/agent/language_recovery.py), o [planejador](../../../ai-agent/app/agent/planner.py) e os pontos em que essas peças são compostas. Verifique quando a recuperação já é chamada antes de propor outro fallback. Uma interpretação determinística aceita também pode estar semanticamente errada.

## Escolher a evolução

- Preserve o caminho determinístico para casos inequívocos e proponha apoio semântico nas falhas demonstradas. A proposta do modelo usa IDs do catálogo e passa por validação independente antes da execução.
- Confira se a pergunta cabe no [plano lógico](../../../ai-agent/app/schemas/read_plan.py) e no [contrato do Backend](../../../backend/app/schemas/genai_plan.py). Amplie uma operação demandada por vez, incluindo catálogo, compilação, cálculo, evidência e consumidor.
- Para análises compostas, defina subplanos, composição permitida, unidades, regra de divisão por zero, mesma publicação e escopo, além de orçamento global. Registre a compatibilidade dos envelopes antes de versioná-los.
- Mantenha o Backend como executor exclusivo Gold, com consultas parametrizadas e leitor restrito. Avalie mudanças nos filtros de linguagem pela taxa de recusas indevidas e pelo comportamento das fronteiras de execução.
- Avalie a [seleção de observações](../../../ai-agent/app/generation/selection.py) e o [orquestrador](../../../ai-agent/app/agent/orchestrator.py) ao melhorar explicações. A liberdade narrativa depende da evidência que chega a essa etapa.

## Entregar

Apresente o caminho atual, a falha reproduzida, o ponto de extensão e a fatia proposta. Use [genai-evaluation](../genai-evaluation/SKILL.md) para comparar antes e depois. Explicite dependências e resultados ainda não medidos. Mudança de decisão segue o fluxo do PRD e das ADRs existente no repositório.
