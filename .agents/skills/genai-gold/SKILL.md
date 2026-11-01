---
name: genai-gold
description: Use ao desenvolver ou revisar o núcleo GenAI, sua integração com a Gold, catálogo e consulta de evidências, ou os fluxos de chat e insights deste repositório.
---

# GenAI e Gold no fluxo existente

Evolua o núcleo e os consumidores já existentes. Esta skill é orientação do projeto; os requisitos e decisões continuam nas fontes indicadas no `AGENTS.md` da raiz.

## Antes de alterar

1. Leia o [guia de integração](../../../docs/agents/genai-gold.md), o requisito do [PRD](../../../docs/PRD.md) e o guia do serviço afetado. Para um cartão GENAI, confirme dependências e aceite no quadro; o cartão não substitui o PRD.
2. Rastreie a execução atual: entrada pública → composição → caso de uso → porta/adaptador → retorno ao consumidor. Identifique símbolos reais no código, inclusive restrições demonstrativas. Termine esta leitura com uma descrição curta do caminho afetado e do ponto de extensão escolhido.
3. Defina a entrega como **preparação**, **integração executável** ou **aceite Gold**, conforme o guia. Declare o que a verificação conseguirá comprovar e a dependência que permanecerá aberta.

## Durante a mudança

Aplique a [referência obrigatória Gold v2](../../../docs/agents/genai-gold.md#referência-obrigatória-gold-v2): identifique o contrato físico, catálogo e publicação v2 usados pelo consumidor. Distingua a versão de dados das versões dos envelopes HTTP. Evidência v1 ou sintética não encerra aceite Gold v2.

- Estenda os pontos de composição, contratos, perfil, plano, portas e controles existentes descritos no guia. Uma substituição arquitetural exige justificativa e decisão registrada, não apenas um novo caminho paralelo.
- Confira o dicionário e o lote disponíveis na branch de trabalho. Uma proposta de schema ou uma fixture de teste não aprova o esquema real.
- Preserve a distinção entre evidência demonstrativa e real, os limites de acesso e a separação entre número observado e hipótese.
- Execute a fronteira apropriada da [matriz de validação](../../../docs/agents/genai-gold.md#validação-por-fronteira). Modelo falso é adequado para determinismo; a composição e a consulta que o teste pretende provar devem ser reais.

## Antes de entregar

Use a [evidência de revisão](../../../docs/agents/genai-gold.md#evidência-para-revisão) para mostrar chamador, composição, fonte, controles, resultado observável, verificações e limites. Um arquivo configurado apenas em testes continua sendo preparação.

Atualize os documentos e cartões conforme o workflow existente, sem concluir requisitos pelo número de testes. A skill não concede autorização para commit, push, merge, alteração de permissões ou publicação de dados.
