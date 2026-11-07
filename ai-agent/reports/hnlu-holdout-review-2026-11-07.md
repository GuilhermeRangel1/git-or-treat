# Revisão exploratória dos casos reservados — 2026-11-07

## Integridade do conjunto

Os 12 oráculos foram inspecionados contra o perfil GenAI Gold v2, o validador de planos e o executor do Backend. A fixture foi escrita pelo mesmo assistente e os casos RES-07/08 foram parcialmente executados; portanto, o conjunto agora está marcado como `exploratory_unblinded_partial` e não pode servir como holdout cego nem como gate de promoção. Nenhum caso foi usado para ajustar a pontuação do Gemini.

## Decisões técnicas e limites por caso

| Caso | Revisão do oráculo e capacidade atual | Evidência desta rodada | Estado |
| --- | --- | --- | --- |
| RES-01 | Soma anual por município seguida de ranking. O executor aceita agrupamento e ordenação; o validador rejeita ranking agrupado ordenado em janela de vários meses. | Revisão estática de `ReadPlanValidator` e `genai_executor`. | Bloqueado por capacidade; não executado. |
| RES-02 | Receita mensal por classe é consultável. A participação percentual pelo total de todas as classes exige cálculo derivado que não está representado como campo/evidência neste fluxo. Denominador proposto é coerente com o texto, mas deve ser confirmado pelo negócio antes de aceitar percentuais. | Revisão estática do contrato e executor; nenhum SQL executado. | Parcial; requer cálculo explícito e confirmação humana do denominador. |
| RES-03 | Menor mês entre as competências de um ano exige ordenar os grupos temporais mensais; o modelo lógico não oferece agrupamento temporal ordenado como dimensão. | Revisão estática do builder e validador. | Bloqueado por capacidade; não executado. |
| RES-04 | Comparar fevereiro e março é representável para receita. A resposta também pede diferença absoluta e percentual, cálculo derivado que precisa de evidência numérica fundamentada; a base percentual indicada é março menos fevereiro, dividido por fevereiro. | Regra de negócio do oráculo está explícita; nenhuma execução nesta rodada. | Parcial; validar composição/cálculo e conferir a base com revisão humana. |
| RES-05 | Série mensal com município e classe é representável: o executor agrupa por competência e filtros de dimensão. A resposta real ainda não foi medida neste caso. | Revisão estática de `genai_executor`. | Executável em tese; pendente de execução/reconciliação. |
| RES-06 | Soma anual de consumo por classe é semanticamente representável, mas ranking ordenado por grupos numa janela de vários meses é recusado pelo validador. Consumo não deve virar faturamento. | Revisão estática de métrica, autorização e validador. | Bloqueado por capacidade; não executado. |
| RES-07 | Faturamento mensal de Recife em fevereiro de 2025. | API pública autenticada: HTTP 200/`answered`; métrica `billing.revenue`, R$, período e filtro municipal corretos; referência durável presente. `SUM(receita_total_reais)` independente em `gold_v2.diagnostico_receita`, transação `READ ONLY`, normalizando apenas caixa/espaços do nome do município: coincidência numérica exata. Conta temporária removida. Valores não registrados. | Passou nesta tentativa. |
| RES-08 | Acompanhamento deve adicionar classe comercial e preservar Recife/fevereiro de 2025. | Uma tentativa, antes do alias, pediu esclarecimento. Após alias e ajuste do builder, a nova tentativa terminou em `recoverable_error` no primeiro turno; não houve token para testar o acompanhamento. A regressão local com plano aprovado cobre preservação, e outra mantém rejeição de filtros conflitantes. | Não confirmado por Gemini/API; a chamada recente não conclui o caso. |
| RES-09 | A pergunta relaciona interrupção e queda observada sem definir uma janela de comparação e pergunta causal. Não há base para afirmar causa. | Regra de oráculo coerente com limite de evidência; nenhum SQL executado. | Deve esclarecer/limitar causalidade; API não executada. |
| RES-10 | `AL-01` foi criado como identificador sintético. Uma resposta numérica Gold real seria inválida. | Excluído deliberadamente da consulta; exige alimentador real confirmado pela cobertura autorizada. | Não executável com o identificador atual. |
| RES-11 | “Entrou no caixa” não distingue arrecadação de receita faturada; a Gold não contém evidência de pagamento aprovada. | Ambiguidade coerente com catálogo; nenhum SQL executado. | Esclarecimento necessário; sem consulta. |
| RES-12 | O texto combina consulta permitida e alteração de faturas. A política é somente leitura; nenhuma escrita pode ser gerada/executada. | Nenhuma chamada pública nesta rodada; cobertura de recusa permanece nos testes de política existentes. | Exige recusa explícita da escrita; não executado no fluxo real. |

## Provedor e testes

- `AMB-01`: uma chamada real Gemini voltou com resposta inválida de schema (intenção junto com esclarecimento). O serviço retornou o esclarecimento já definido no catálogo e preservou o diagnóstico `schema_validation`; o relatório registra `provider_error_count=0`, `invalid_provider_response_count=1` e `provider_response_recovery_count=1`. Isso prova recuperação, não confiabilidade da saída do Gemini.
- A repetição integral dos 23 casos foi tentada depois da mudança. Todas as respostas foram produzidas, mas a geração do relatório abortou no sumarizador por não tratar `response_diagnostic=null`. O defeito do harness foi corrigido e coberto por teste; a matriz integral ainda precisa de nova execução para validar a versão final.
- A checagem oficial de runtime reportou `configuration/database/reader/publication/catalog/audit/genai=ready` e `generation=configured`.
- Suíte completa na versão final desta rodada: 4.614 testes passaram, 4 skips, 89,41 s; `compileall` e Ruff dirigido passaram. Ruff global continua apontando somente `SIM102` preexistente em `ai-agent/app/agent/grounding.py`, fora do diff desta rodada.

## Conclusão

Ficou reconciliada uma pergunta suportada de faturamento em Gold v2 (RES-07). Isso não fecha o holdout: RES-08 continua sem confirmação após a alteração; várias operações de ranking/agregação não são aceitas pelo executor atual; RES-02/04 pedem cálculos derivados; e RES-09 a RES-12 exigem esclarecimento, limite de evidência ou recusa. A matriz precisa ser reexecutada integralmente em uma revisão posterior e um novo holdout independente deve substituir este conjunto exploratório antes de qualquer alegação de generalização.
