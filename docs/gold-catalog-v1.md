# Catálogo Gold: métricas lógicas e mapeamento físico

**Cartão:** GENAI-03 (parte 2). **Versões:** mapeamento `gold-catalog-v1`, dicionário `gold-v1-develop-c9580cd`, prontidão `gold-readiness-v1`. **Código:** `ai-agent/app/profiles/grid360_gold.py` (perfil lógico) e `ai-agent/app/profiles/grid360_gold_mapping.py` (mapeamento físico). **Testes:** `ai-agent/tests/test_gold_catalog.py` e `ai-agent/tests/test_gold_catalog_mapping.py`.

**Natureza:** preparação. Nada aqui prova a Gold real, e este documento não traz valores, contagens nem nomes de lugar do lote. A liberação para consulta real depende de GENAI-06, GENAI-07 e GENAI-10.

## Fronteira

- **Perfil lógico** (`GRID360_GOLD_PROFILE`, `v-energy-grid-360-gold`): o núcleo o usa para interpretar e planejar. Contém ids lógicos, aliases do negócio, unidades, dimensões e limitações, sem nenhum nome de tabela ou coluna física (verificado por teste).
- **Mapeamento físico** (`GRID360_GOLD_MAPPING`): o executor do Backend o usará no futuro. Liga cada id lógico a tabela, coluna, fórmula, grão, nulidade e capacidade da prontidão. `validate_mapping` confere o mapeamento com o perfil, a prontidão e o dicionário, e falha com erro explícito em qualquer divergência.

## Métricas do catálogo

Nesta tabela, "Fontes" lista as tabelas em ordem de preferência. Dimensões: município, bairro, classe, subgrupo, bandeira, GD, alimentador e UC.

| Id lógico | Rótulo | Unidade | Grão de leitura | Dimensões | Fontes (capacidade) | Agregação | Limitações principais |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `billing.revenue` | Receita faturada | R$ | competência | município, classe, subgrupo, bandeira, GD, bairro, UC | `diagnostico_receita` (`faturamento.receita`); `consumo_receita_bairro` (`faturamento.receita_bairro`); `consumo_mensal_uc` (`consumo.mensal_uc`) | soma | Valor faturado, não pago. Só entram UC/mês com fatura e leitura. Usa o cadastro atual. |
| `energy.consumption` | Consumo medido | kWh | competência | mesmas da receita | mesmas da receita | soma | Leituras, não energia faturada. Mesma interseção fatura × leitura. |
| `billing.average_ticket` | Ticket médio | R$ por UC faturada no mês | competência | município, classe, subgrupo, bandeira, GD, bairro | `diagnostico_receita`; `consumo_receita_bairro` | razão de somas: receita ÷ UCs faturadas | Média por UC e mês. Nunca soma nem tira média de tickets já calculados. |
| `billing.effective_tariff` | Tarifa média efetiva | R$/kWh | competência | mesmas da receita | as três da receita | razão de somas: receita ÷ consumo | Preço observado, não tarifa homologada. Consumo zero ou ausente dá resultado ausente. |
| `energy.average_consumption_per_uc` | Consumo médio por UC | kWh por UC faturada no mês | competência | município, classe, subgrupo, bandeira, GD, bairro | `diagnostico_receita`; `consumo_receita_bairro` | razão de somas: consumo ÷ UCs faturadas | Média por UC e mês. |
| `network.equivalent_interruption_duration` | DEC | horas por UC | alimentador × competência | alimentador (obrigatório), município | `indicadores_dec_fec` (`interrupcoes.dec_fec`) | leitura no grão da chave | Indicador interno simplificado. Nunca é somado nem tirado em média entre alimentadores ou meses. |
| `network.equivalent_interruption_frequency` | FEC | interrupções por UC | alimentador × competência | alimentador (obrigatório), município | `indicadores_dec_fec` (`interrupcoes.dec_fec`) | leitura no grão da chave | Conta pares UC–ocorrência. Mês sem linha não prova ausência. |

**Escolha da fonte:** a consulta usa uma única fonte, a primeira da lista cujas dimensões cobrem a consulta e cuja capacidade está disponível. Se nenhuma cobre, a capacidade fica indisponível para aquela consulta. Duas tabelas nunca são somadas, e fatos de tabelas diferentes nunca são juntados. Exemplos: receita por bairro e bandeira não tem fonte; receita por UC usa `consumo_mensal_uc`.

**Nulidade:** nulo é ausência, nunca zero. A soma ignora nulos, e um recorte só com nulos fica sem evidência. Na razão, numerador ou denominador ausente, ou denominador zero, dá resultado ausente. Em DEC/FEC, linha ausente não vira zero.

**Arredondamento:** só na apresentação, depois do cálculo, com meio-par. R$, kWh e DEC/FEC com 2 casas; R$/kWh com 4. É proposta a confirmar com Dados.

**Nomes físicos:** são os do dicionário. DEC e FEC são declarados como `dec`/`fec`, e as tabelas não têm o prefixo `gold_`.

## Capacidades fora do catálogo

Nenhuma destas capacidades vira métrica do perfil. O motivo vem da prontidão.

| Capacidade | Motivo | Observação |
| --- | --- | --- |
| `faturamento.preco_volume` | `definition_pending` | Falta tarifa homologada e método de decomposição preço × volume. |
| `faturamento.faturas_em_aberto` | `definition_pending`, `source_not_in_gold` | Nenhuma tabela traz status, vencimento ou pagamento. |
| `consumo.variacao_uc` | `definition_pending` | Janela e mínimo de meses abertos; P1/P2 fixos na Gold. |
| `interrupcoes.uc_acumulado` | `definition_pending` | Só total acumulado por UC, sem mês nem controle. |
| `atendimento.uc_acumulado` | `definition_pending` | Só totais por UC, sem mês nem motivo; sem controle. |
| `apoio.fila_inspecao` | `definition_pending` | Rótulos de resultado de inspeção pendentes (issue #39). |
| `apoio.medidor_uc` | `definition_pending`, `source_not_in_gold` | Sem tabela de medidor. |
| `apoio.energia_recuperavel` | `definition_pending`, `source_not_in_gold` | Sem estimativa de energia recuperável. |

`out_of_scope_terms` não foi usado para essas capacidades. O campo alimenta o filtro de segurança, que recusa a pergunta como **fora do escopo do assistente**, quando o certo seria dizer que o dado ainda não está disponível. O campo também aceita no máximo 30 termos, e o perfil já usa 20. Hoje, perguntas sobre esses temas recebem pedido de esclarecimento por falta de métrica. A resposta específica "dado indisponível na Gold" fica pendente para o GENAI-04.

## Checklist de revisão com Dados

- [ ] **Receita faturada:** soma de `valor_total` das faturas de UC/mês com leitura; confirmar que é a definição de faturamento do case, sem inadimplência nem pagamentos.
- [ ] **Consumo:** soma das leituras de UC/mês com fatura; confirmar que perguntas sobre "energia faturada" não devem usar esta métrica. O comentário da prontidão chama `faturamento.receita` de "receita e energia faturadas".
- [ ] **Ticket médio e consumo médio por UC:** confirmar a razão de somas por UC e mês, diferente de "média por UC distinta no período".
- [ ] **Tarifa média efetiva:** confirmar o uso como preço observado e o nome "tarifa", para que não seja lida como tarifa homologada.
- [ ] **DEC/FEC:** confirmar unidades (horas por UC; interrupções por UC como pares UC–ocorrência), denominador do cadastro atual e a proibição de consolidar alimentadores e meses.
- [ ] **Janela temporal:** como frases relativas ("últimos 12 meses", "mês passado") se resolvem contra as competências do lote; competências sem lacuna, como exige a prontidão.
- [ ] **Nulos:** ausência como "sem evidência" nas somas e razões; `Não informado` em `consumo_receita_bairro` como categoria de ausência, não lugar real.
- [ ] **Arredondamento** de apresentação e precisão (`decimal(38,2)` para R$).
- [ ] **Classes declaradas no perfil:** as cinco classes citadas como exemplo no dicionário; confirmar se o domínio tem outras.
- [ ] **Soma de UCs faturadas entre segmentos:** a razão de somas do ticket médio e do consumo médio por UC soma `qtd_ucs_distintas_faturadas_no_mes` entre linhas do mesmo mês. Isso só é correto porque o dicionário garante uma única bandeira, classe, subgrupo, GD e município por UC/mês (o notebook falha se a UC tiver duas bandeiras no mês). Confirmar que cada UC aparece em uma só linha por mês em `diagnostico_receita` e em `consumo_receita_bairro`.
- [ ] **Controles do consumo:** o consumo pelo diagnóstico usa a capacidade `faturamento.receita` (controles C01, C02 e C04). Confirmar que esses controles cobrem também a coluna de consumo, e que o consumo por `consumo_mensal_uc` é coberto por C03 e C10.

## Pontos abertos com o Backend

- **DEC/FEC entre aspas:** no PostgreSQL as colunas são `"DEC"`/`"FEC"`, sensíveis a caixa, e o dicionário usa `dec`/`fec`. Uma consulta sem aspas pode não encontrar a coluna.
- **Prefixo `gold_`:** o Backend grava as tabelas como `gold_<nome>`; o mapeamento usa o nome da Gold.
- **Nomes físicos definitivos:** podem ser alinhados por visão de leitura ou por nova revisão. Qualquer mudança exige nova versão do dicionário e do mapeamento.

## Pendências para o GENAI-04

- "ticket médio" cai na regra de detalhe "média", e "consumo médio por UC" cai na quebra por UC; as duas métricas ainda não são alcançáveis por pergunta livre.
- Perguntas por município ou bairro não têm valores no perfil: filtro geográfico pede esclarecimento.
- Resposta específica para capacidades indisponíveis, em vez de falta de métrica.
- Matriz completa de perguntas e ligação do mapeamento ao executor.

## Limites

- Preparação: testes só com dados sintéticos e cópias do dicionário em memória; não provam a Gold real.
- O perfil e o mapeamento não estão em `app/main.py` nem em nenhuma composição da aplicação.
- Liberação para consulta real depende de GENAI-06, GENAI-07 e GENAI-10, além de credencial, permissões e reconciliação.
