# Perguntas do chatbot legado que receberam resposta

## Escopo

Esta lista reúne os **22 casos** cujo status público aparece como `answered` na execução real da matriz Gold de 02/11/2026. As perguntas vêm dos templates da fixture legada; por isso, campos entre chaves, como `{municipio}` e `{ano}`, foram mantidos. A fixture não preserva os valores exatos usados em cada requisição histórica.

O status `answered` comprova que a rota antiga devolveu uma resposta naquele caso e naquela publicação. Não afirma que todas as perguntas tenham resposta numérica, que os dados atuais sejam iguais, nem que o fluxo Text-to-SQL atual já suporte essas perguntas. As perguntas de acompanhamento dependem do contexto indicado.

Fontes: [`gold_domain_scenarios.json`](../../ai-agent/tests/fixtures/gold_domain_scenarios.json) e [relatório da matriz Gold real de 02/11/2026](2026-11-02-genai-assistente-matriz-real.md), seção “Estados por caso”.

## Perguntas respondidas na execução histórica

| Caso | Domínio | Pergunta usada como referência |
| --- | --- | --- |
| FAT-01 | Faturamento | Qual foi a receita faturada em `{municipio}` em `{mes_extenso}` de `{ano}`? |
| FAT-02 | Faturamento | Qual foi a receita comercial em Jaboatão dos Guararapes no último trimestre? |
| FAT-03 | Faturamento | Qual foi o faturamento residencial em Olinda em `{mes_extenso}` de `{ano}`? |
| FAT-04 | Faturamento | Qual foi a receita residencial no bairro `{bairro}`, em Recife, em `{mes_extenso}` de `{ano}`? |
| FAT-05 | Faturamento | Qual foi o ticket médio no município de Recife em `{mes_extenso}` de `{ano}`? |
| FAT-06 | Faturamento | Qual foi o preço médio observado da energia residencial no município de Recife em `{mes_extenso}` de `{ano}`? |
| FAT-09 | Faturamento | Quanto cresceu a receita comercial em Jaboatão dos Guararapes entre `{mes_p0}` de `{ano_p0}` e `{mes_p1}` de `{ano_p1}`? |
| FAT-10 | Faturamento | Qual classe mais contribuiu para a receita no município de Recife em `{mes_extenso}` de `{ano}`? |
| FAT-11 | Faturamento | Quanto da variação da receita residencial foi efeito preço e quanto foi efeito volume? |
| FAT-16 | Faturamento | Qual foi a receita no município de Recife neste ano? |
| CON-01 | Consumo | Qual foi o consumo de energia em `{municipio}` em `{mes_extenso}` de `{ano}`? |
| CON-02 | Consumo | Qual foi o consumo residencial em Olinda em `{mes_extenso}` de `{ano}`? |
| CON-04 | Consumo | Qual foi o consumo das unidades com geração distribuída no município de Recife em `{mes_extenso}` de `{ano}`? |
| CON-05 | Consumo | Qual foi o consumo médio por unidade com leitura no município de Recife em `{mes_extenso}` de `{ano}`? |
| CON-06 | Consumo | O consumo residencial em Olinda caiu entre `{mes_p0}` de `{ano_p0}` e `{mes_p1}` de `{ano_p1}`? |
| CON-07 | Consumo | Qual bairro de Recife mais perdeu volume residencial entre `{mes_p0}` de `{ano_p0}` e `{mes_p1}` de `{ano_p1}`? |
| CON-08 | Consumo | Quantas UCs com geração distribuída em Olinda tiveram queda de consumo acima de 30%? |
| ATE-03 | Atendimento | Quantos chamados de atendimento existem no histórico acumulado? |
| ATE-04 | Atendimento | Qual é a satisfação média do atendimento no histórico acumulado? |
| ATE-05 | Atendimento | Quantos chamados de atendimento existem no histórico acumulado? |
| AMB-04 | Correção de local | Qual foi a receita em Olinda, não, em Jaboatão dos Guararapes, em `{mes_extenso}` de `{ano}`? |
| AMB-05 | Continuação | “E em Olinda?”, após “Qual foi a receita residencial no município de Recife em `{mes_extenso}` de `{ano}`?”. |

## Limites desta lista

- A execução é histórica e se refere à publicação Gold v2 usada em 02/11/2026.
- “Respondida” não significa necessariamente que toda medida ou domínio tenha sido homologado para uso atual; confira os bloqueios e as limitações no relatório da matriz.
- Os exemplos com `{...}` são padrões de pergunta da fixture, não transcrições exatas das mensagens enviadas naquela execução.
- A lista não inclui casos que retornaram esclarecimento, recusa, erro de acesso ou bloqueio de cobertura.
