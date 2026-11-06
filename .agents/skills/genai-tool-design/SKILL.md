---
name: genai-tool-design
description: Projete ou amplie capacidades analíticas e contratos de ferramentas do GenAI entre planejador, catálogo, executor Backend e evidências Gold.
---

# Ferramentas analíticas do GenAI

Use a [genai-gold](../genai-gold/SKILL.md) para rastrear o consumidor e a composição. Leia o [contrato de execução](../../../docs/contracts/genai-query-execution.md), o [catálogo Gold](../../../docs/gold-catalog.md) e o dicionário vigente da métrica antes de definir uma operação.

## Definir a capacidade

Parta de uma pergunta que a operação deve responder. Especifique entradas tipadas, IDs lógicos aceitos, unidade e grão, semântica temporal, filtros, agrupamentos, ordenação e limite. Descreva ambiguidades que exigem esclarecimento e como ausência de linha, zero, nulo e cobertura parcial são representados.

O modelo propõe intenção e parâmetros lógicos. O Backend resolve tabelas físicas, reautoriza o plano e compila SQL parametrizado no [executor](../../../backend/app/services/genai_executor.py). A descrição da ferramenta deve permitir escolher a operação sem expor credenciais ou permitir SQL arbitrário.

## Ligar o fluxo completo

- Confira o [plano GenAI](../../../ai-agent/app/schemas/read_plan.py), o [plano Backend](../../../backend/app/schemas/genai_plan.py) e seus validadores. Cada operação exposta ao modelo precisa de implementação executável e de evidência correspondente.
- Inclua a capacidade no perfil e catálogo existentes, na interpretação, no planejamento e na composição efetivamente chamada pela API. Identifique restrições demonstrativas antes de reutilizar adaptadores.
- Preserve compatibilidade dos envelopes e fingerprints. Uma extensão deve definir como clientes e planos anteriores continuam tratados durante a implantação.
- Para subconsultas, valide cada plano e a composição inteira, com publicação e escopo comuns, orçamento total, limite de linhas e comportamento em falha parcial. Preserve a proveniência dos resultados derivados.
- Faça cálculos entre evidências em código confiável, com semântica definida para bases incompatíveis, unidade, períodos, denominador zero e dados ausentes.

## Verificar a fronteira

Exercite a capacidade pela entrada pública e compare os resultados com uma referência independente. Inclua uma pergunta equivalente e os limites que a operação introduziu. Use [genai-evaluation](../genai-evaluation/SKILL.md) para medir o ganho e a regressão. A entrega identifica quem chama a ferramenta, quem valida e executa, e qual evidência chega ao usuário.
