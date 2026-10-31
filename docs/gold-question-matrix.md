# Matriz de perguntas para o catálogo Gold v2

Matriz versionada para o trabalho de linguagem do núcleo GenAI. As expectativas abaixo vêm do catálogo lógico Gold v2, do contrato de execução e dos critérios do cartão; não usam respostas de fixtures para afirmar resultado sobre a Gold. Os testes de planejamento usam cobertura e valores de dimensão sintéticos explícitos, e não comprovam inventário ou valores do lote real.

| ID | Pergunta | Saída esperada | Verificação independente |
| --- | --- | --- | --- |
| Q04-01 | Qual foi a receita comercial em Jaboatão no último trimestre? | Plano `billing.revenue`; filtro `customer.consumption_class=COMERCIAL` e `geography.municipality=Jaboatão`; últimos 3 meses contíguos na cobertura. | A métrica é receita faturada em R$; classe e município são dimensões permitidas no catálogo. Os valores de município precisam vir da publicação confiável. |
| Q04-02 | Qual foi o faturamento residencial em Olinda nos últimos 12 meses? | Plano de receita faturada; classe `RESIDENCIAL`, município `Olinda` e janela mensal de 12 competências terminando na mais recente recebida. | Aliases e IDs de dimensão são conferidos contra `GRID360_GOLD_PROFILE`; limites vêm da cobertura enviada pelo Backend. |
| Q04-03 | Qual bairro mais perdeu volume residencial no último ano? | `needs_clarification`: não retornar total como ranking; agrupamento por bairro/ordenação não está habilitado no plano Gold atual. | A pergunta exige grupo, ordenação e sentido. `ReadPlanBuilder` não cria esses campos a partir de intenção. |
| Q04-04 | Quanto cresceu a receita comercial em Jaboatão no último trimestre? | `needs_clarification`: falta janela de referência para comparar; nenhum filtro é descartado e não é calculado percentual. | A Gold publica receita faturada; uma janela única não representa comparação. |
| Q04-05 | Quantas UCs com solar em Olinda tiveram queda de consumo no último ano? | `needs_clarification`: Gold v2 registra GD, sem afirmar que a fonte é solar; não retirar filtro solar nem devolver total. | O perfil contém `generation.distributed`; solar não é alias nem atributo físico aprovado. |
| Q04-06 | Qual foi o valor pago em Olinda no último trimestre? | `needs_clarification`: valor pago não é receita faturada e não é publicado por esse indicador. | A definição v2 de `billing.revenue` declara valor faturado; aliás genéricos não podem igualar pagamento. |
| Q04-07 | Qual foi a energia faturada em Olinda no último trimestre? | `needs_clarification`: `energy.consumption` é consumo medido, não energia faturada. | A definição e as limitações de `energy.consumption` distinguem as duas medidas. |
| Q04-08 | Qual foi a receita em Olinda e Jaboatão no último trimestre? | `needs_clarification` sem cláusula de correção explícita; não reduzir a uma cidade. | Dois valores não cabem no filtro escalar atual. |
| Q04-09 | Qual foi a receita em Olinda, não, em Jaboatão no último trimestre? | Plano apenas para Jaboatão, se o valor estiver na cobertura de dimensão dessa publicação. | Regra de correção explícita substitui o local anterior; a autorização do plano é reaplicada. |
| Q04-10 | Qual foi a receita em município ausente do vocabulário recebido? | `needs_clarification`; o nome livre não é transformado em filtro e não é removido. | Correspondência exige valor dinâmico da mesma publicação ou valor estático do perfil. |
| Q04-11 | Qual foi a receita este ano? | Janela de janeiro ao último mês publicado, com período parcial; lacuna interna resulta em esclarecimento. | Data do servidor não participa; limites são primeiro e último dia das competências presentes. |
| Q04-12 | Qual foi a receita no último trimestre? com uma competência faltando | `needs_clarification`; não encurtar para os dois meses presentes nem completar o mês ausente. | Comparar expectativa de três competências consecutivas com a cobertura enviada. |
| Q04-13 | Qual foi o valor pago e faturado? | `needs_clarification` de métrica/definição; não combinar populações ou colunas. | A Gold v2 não oferece uma métrica de pagamento equivalente à receita faturada. |
| Q04-14 | Compare a receita do ano passado com este ano quando a base anterior é zero. | Nesta etapa, esclarecer que comparação não está representada em um plano; não produzir percentual. A regra final para zero/base ausente será exercitada pelo caso público após integração de executor e evidência. | O planejador não calcula variação. Este caso é pendência de integração da resposta e não pode ser marcado como provado por um teste de plano. |

## Evidência e limites desta etapa

- Testes automatizados compõem a pergunta com o catálogo v2 e percorrem `compose_core → question.plan`; checam IDs de métrica/dimensão, filtros, estado e janela. Em 31/10/2026, a execução fora do sandbox resolveu o bloqueio de `asyncio`: os quatro arquivos de catálogo v2, períodos, envelopes e regras do interpretador passaram com 243 testes. A regressão adicional de esclarecimento pelo caso público passou: pergunta anual sem cobertura → esclarecimento → último trimestre mantém receita, classe comercial e município, com limites inclusivos de janeiro a março de 2025 na cobertura controlada.
- Testes síncronos verificam a resolução temporal, preservação de lacunas, validação dos envelopes, dimensões no escopo e regressões de acentos. Não substituem a execução integrada do caso público.
- A composição de produção ainda não fornece `dimension_value_coverage`, não existe rota interna de planejamento ativa e não foi executado lookup contra lote Gold real. O caso público `question.plan` está comprovado com metadados controlados, incluindo Q04-09 (correção de cidade). Q04-14 comprova esclarecimento sem percentual; cálculo numérico com base zero pertence à execução/evidência futura.
- A cobertura mensal identifica competências reportadas no lote. Não prova que a extração da origem trouxe todas as competências existentes. A conclusão de completude exige evidência de reconciliação separada, como registrado no contrato de cobertura.

## Implementação ampliada do GENAI-04 — 31/10/2026

O perfil Gold v2 ativa `structured_dimension_filters`; outros perfis mantêm o comportamento anterior. Cada dimensão é resolvida separadamente, permitindo município + bairro + classe + GD/subgrupo sem perder filtros. Alimentador usa apenas valores publicados pelo Backend. Valor desconhecido, nome ambíguo entre dimensões, múltiplos valores sem correção e exclusão não suportada pedem esclarecimento. `sem GD` é um valor cadastral próprio, não exclusão genérica.

IDs de UC não são enviados como vocabulário. Pedido por UC sem resolução autorizada gera esclarecimento explícito; não se extrai número livre nem se consulta o total silenciosamente. Isso preserva o critério de usar o filtro somente quando a capacidade estiver autorizada, sem criar um cadastro paralelo na GenAI.

Os valores canônicos da publicação prevalecem sobre a grafia de exemplo do perfil. O perfil mantém seus aliases e é enriquecido apenas na requisição. Esclarecimentos de métrica (pago/faturado, energia faturada/medida, interrupção/DEC) e de período preservam os filtros e a janela original; autorização é reaplicada a cada plano, inclusive com permissão revogada.

| Casos adicionais | Resultado comprovado em `test_gold_question_filters.py` |
| --- | --- |
| Município + bairro + classe | Todos os filtros no plano aprovado, sem tratar dimensões diferentes como cidades conflitantes. |
| Classe + GD e classe + GD + subgrupo | Valores e IDs preservados por dimensão. |
| DEC por alimentador e mês | Alimentador publicado reconhecido, janela mensal delimitada. |
| Cidade corrigida explicitamente | Somente o valor corrigido aparece no plano. |
| Subgrupo/alimentador desconhecido; UC sem resolução | Esclarecimento e nenhum plano. |
| Duas classes, dois municípios ou com/sem GD juntos | Esclarecimento, sem reduzir a um valor. |
| Exclusão de classe ou mesmo nome em duas dimensões | Esclarecimento, sem interpretar exclusão como igualdade. |
| Follow-up de cidade e revogação de GD | Recortes herdados preservados; permissão revogada recusa o plano. |
| Escolha de receita, consumo ou DEC após ambiguidade | Métrica selecionada, período e filtros originais preservados. |

Verificações: suíte completa GenAI com 3.620 aprovados, 4 skips e 1 xfail histórico; Backend, contratos internos e produtor, 84 aprovados incluindo HTTP. Execução fora do sandbox confirmou que a limitação anterior era do ambiente restrito, não do `asyncio` no Windows. Após a suíte completa, 21 cenários dirigidos passaram com o ajuste de lint e três casos adicionais de unidade/dimensão sem suporte.

Escopo entregue: interpretação e planejamento pelo núcleo composto, sem fonte/LLM no planejamento. Escopo dos próximos cartões: executor (GENAI-06), transporte/coordenador (GENAI-07), evidência e prova quantitativa real (GENAI-08/09/10). Validação semântica da ADR-0018 continua registrada como pendente; estes testes não a substituem. IA-01/IA-02 não são concluídos por uma matriz de planos.
