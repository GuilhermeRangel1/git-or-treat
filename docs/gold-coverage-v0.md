# Cobertura do lote candidato da Gold — v0

**Cartão:** GENAI-02 — Conferir o lote Gold e a cobertura dos dados obrigatórios
**Data da conferência:** 27/10/2026
**IDs do PRD relacionados:** IA-01, IA-02, IA-03, IA-06; dependências DE-04, DE-05, DE-06, DE-08
**Natureza:** relatório de **lote candidato**. Este documento não conclui requisito, não homologa métrica e não declara a Gold pronta para a GenAI. Os estados do PRD não mudam.

> **Nota sobre o conteúdo.** Este documento contém apenas agregados e contagens do lote: nenhuma linha de dado, nenhum id de UC ou de alimentador e nenhum dado pessoal. Os CSVs não estão no repositório. Como o repositório de entrega é público e o material do case tem a marcação "Confidencial", **a publicação dos totais em R$ e kWh (seções c e g) precisa ser confirmada por Dados** antes de o documento sair da branch.

## O que foi conferido e o que não foi

**Lote conferido:** arquivo `rocket_dados-20261027T110204Z-1-001.zip`, com sete CSVs (separador `;`, UTF-8, todos os campos entre aspas), datados de 26/10/2026 no zip. Os CSVs ficam fora do repositório. Sem manifesto, a identificação possível é o hash dos arquivos:

| Arquivo | SHA-256 |
| --- | --- |
| zip | `017dc1ce8cf6843f4867c912f138bc5b0335ec10dc963bd90e21d2630e802ebf` |
| `consumo_mensal_uc.csv` | `29098a94d27198a9256958602a17f44fb7acdb4cd5e7ab0d0a8fadc44c08ccd2` |
| `consumo_receita_bairro.csv` | `7ef3a399882c5cd56afc97c15948fb86ced1f01a073d7335892cf8949d9004b7` |
| `diagnostico_receita.csv` | `25629d076643ccb699a8314c98fcb83bf21cd3826e2dcb6073dc021ddfad709a` |
| `fila_inspecao.csv` | `80b09dc97592f1bbe70f20b9951979ac5e0a1f6e72771b84f96fc95f04ab696c` |
| `indicadores_dec_fec.csv` | `c9f1412051901ef280565c1bfdb62c59bc471e87142b5ff98d4ee5bbd1e46c76` |
| `variacao_consumo_uc.csv` | `253b6fc0a88af7efee636f9531991add8543cae620cc7dc465cea04a19c17fb3` |
| `visao_360_uc.csv` | `64206bede85b6b2a977d0c3c96739ad5aa1460ac7a8e8d8e84d1b40d74409571` |

**Não há manifesto nem `controle_gold` neste lote.** O diretório contém apenas os sete CSVs. Portanto o `batch_ref` proposto no [contrato de consulta](contracts/genai-query-execution.md#lote-da-gold-batch_ref) e na [ADR-0002](decisions/0002-genai-gold-query-owner.md) **ainda não existe**: não é possível saber de qual `run_id_silver`/`lote_bronze_silver` o lote veio, se a execução foi `CONCLUIDO`, nem se usou os valores de reserva `SINTETICO_DEV`/`LOTE_DEV`. O notebook de exportação da branch `feat/gold` (`Exportacao_Gold_SQLite.ipynb`, commit `9664823`) também não grava manifesto.

**Não verificado nesta conferência:**

- recarga dos CSVs no banco local sem duplicar resultados (DE-06). O carregador `backend/scripts/load_gold.py` ainda é esqueleto e não insere registros;
- comparativo entre os CSVs e o banco do Backend: o esquema atual do Backend tem só `gold_indicadores`, não as sete tabelas;
- comparativo entre os CSVs e as tabelas no Databricks;
- controles aprovados de catálogo, papel somente leitura, identidade e auditoria (pendências da ADR-0002).

**Como reproduzir:** a partir de `ai-agent/`, `python scripts/gold_coverage.py <diretório do lote>` (ou `GOLD_DATA_DIR=<diretório> python scripts/gold_coverage.py --json <saída fora do repo>`). O script só lê, usa biblioteca padrão e imprime agregados; não imprime linhas, ids de UC nem ids de alimentador. Salvaguardas da saída:

- valores de coluna só aparecem para as dimensões autorizadas (município, classe, subgrupo, bandeira, GD, status, UF, prioridade e flag de queda), e nunca quando o nome ou os valores parecem dado pessoal (CPF, CEP, e-mail); mínimo e máximo de texto só em colunas de data e competência;
- reconciliações e controles com medida nula ou inválida saem como `nao_verificavel`, com as contagens, e não como "0 divergências";
- as janelas de 12 meses exigem competências contínuas; com lacuna, o percentual não é calculado (`janela incompleta`);
- `--json` recusa destino dentro da pasta do lote, inclusive via link ou `..`, e sobre um arquivo de entrada.

Testes com dados inventados: `python -m pytest tests/test_gold_coverage.py`. Execução sobre este lote: cerca de 2 min.

**Fontes lidas:** [PRD](PRD.md) (§1, §1.2, §2.1, §4, §6.3, §7.6, §8), [contrato](contracts/genai-query-execution.md), [ADR-0002](decisions/0002-genai-gold-query-owner.md), `ai-agent/app/sql/dictionary_gold.toml` (**existe só na branch `feat/ia-gold-dicionario-sql`, commit `fd6db48`; não está na `develop`**), `docs/dicionario_gold.md` e `data-engineering/notebook/Silver_to_gold.ipynb` da branch `feat/gold` (commit `9664823`). O [dicionário Gold](data-dictionary.md) da `develop` ainda é modelo vazio.

## (a) As sete tabelas

Contagens de linhas sem o cabeçalho. "Nulos" lista só as colunas com nulos; as demais têm zero.

| Tabela | Grão (chave candidata) | Chave única? | Período | Linhas | Colunas | Nulos |
| --- | --- | --- | --- | ---: | ---: | --- |
| `visao_360_uc` | UC (`id_uc`) | sim | sem competência | 45.000 | 15 | `media_consumo_historico` 1.046 (2,32%); `media_satisfacao_atendimento` 66 (0,15%) |
| `fila_inspecao` | UC (`id_uc`) | sim | sem competência | 45.000 | 14 | `media_consumo_historico` 1.046 (2,32%) |
| `variacao_consumo_uc` | UC (`id_uc`) | sim | P1 = 2022-07 a 2023-06; P2 = 2025-07 a 2026-06 (fixos no notebook) | 45.000 | 11 | `consumo_medio_inicial`, `variacao_kwh`, `variacao_pct` 1.461 (3,25%); `consumo_medio_final` 1.046 (2,32%) |
| `consumo_mensal_uc` | UC × competência | sim | 2022-07 a 2026-06, 48 meses, sem lacuna | 1.928.920 | 4 | nenhum |
| `consumo_receita_bairro` | competência × município × bairro × classe | sim | 2022-07 a 2026-06, 48 meses, sem lacuna | 55.694 | 7 | nenhum |
| `diagnostico_receita` | competência × município × classe × subgrupo × bandeira × GD | sim | 2022-07 a 2026-06, 48 meses, sem lacuna | 4.694 | 13 | nenhum |
| `indicadores_dec_fec` | alimentador × competência | sim | 2022-07 a 2026-06, 48 meses, sem lacuna | 5.856 | 9 | nenhum |

Dimensões observadas (todas as tabelas que as têm usam os mesmos valores):

- 14 municípios, todos em `uf = PE`; 331 bairros; 122 alimentadores, cada um em um único município.
- Classe: `COMERCIAL`, `INDUSTRIAL`, `PODER PUBLICO`, `RESIDENCIAL`, `RURAL`. Subgrupo: `A4`, `B1`, `B2`, `B3`.
- Bandeira (`diagnostico_receita`): `VERDE`, `AMARELA`, `VERMELHA P1`, `VERMELHA P2`.
- `status` da UC: só `ATIVA` (45.000).
- Prioridade da fila: `MEDIA - NUNCA INSPECIONADO` 42.652; `REVISAR - SEM HISTORICO DE CONSUMO` 1.023; `ALTA - HISTORICO IRREGULAR` 808; `BAIXA` 517.

Formatos: competência como texto `YYYY-MM`; `data_ligacao` como `YYYY-MM-DD`; decimal com ponto; números também entre aspas (`quoteAll`), então a carga precisa converter tipos. GD aparece como texto `Sim`/`Não` (com acento) em `possui_gd` e `possui_geracao_solar`; `queda_consumo_superior_30_pct` é `true`/`false` em minúsculas. As colunas `DEC` e `FEC` vêm em maiúsculas.

Colunas pessoais ou sensíveis: **nenhuma** no cabeçalho de qualquer tabela (`cpf`, `cnpj`, nome, logradouro, número, CEP, latitude, longitude, e-mail e telefone foram procurados por nome) e nenhum valor de texto com padrão de CPF, CEP ou e-mail. As colunas `_*` de pipeline também não vieram. O notebook de exportação avisa que `visao_360_uc` pode conter dados pessoais; neste lote, não contém. Cada nova exportação precisa ser conferida de novo.

## (b) Perguntas de negócio × tabela que as sustenta

**De onde vêm as perguntas.** Não há no repositório uma lista única e numerada de perguntas obrigatórias. As perguntas abaixo foram extraídas do PRD: a pergunta central (§1), as falas das lideranças (§1.2), os exemplos da IA (§7.6), os domínios do IA-01 (consumo, faturamento, interrupções e atendimento) e os termos do IA-02. A lista não acrescenta perguntas por conta própria.

Estados: **coberta** = a Gold tem grão e colunas para responder, sujeita às ressalvas; **parcial** = responde só parte, ou com uma granularidade que limita a resposta; **não coberta** = falta a informação. **Pendência de Dados/Backend** marca o que depende de granularidade ou coluna ausente.

| # | Pergunta (origem) | Tabela / colunas | Estado | Observação |
| --- | --- | --- | --- | --- |
| P1 | Receita e energia faturada por competência, município e classe (§1, IA-01) | `diagnostico_receita`, `consumo_receita_bairro`: `receita_total_reais`, `consumo_total_kwh` | coberta | Os totais das três tabelas fecham exatamente (ver c). A receita é **faturada** (`valor_total` da fatura), não paga. |
| P2 | Explicar a variação da receita diante do reajuste tarifário e da queda de volume, separando preço/tarifa e volume (§1, ENT-01) | `diagnostico_receita`: receita, consumo, `tarifa_media_efetiva`, bandeira, subgrupo, GD | parcial | Dá para calcular o preço médio efetivo e o volume. Faltam a tarifa homologada e o método de decomposição aprovado (PRD §8). Os percentuais do lote diferem em poucos pontos dos citados no case (ver c); a diferença precisa ser explicada com Dados. **Pendência de Dados.** |
| P3 | Abrir a variação por bairro (§1, §1.2) | `consumo_receita_bairro` | parcial | Bairro só aparece com competência × classe; sem subgrupo, bandeira ou GD. A decomposição preço × volume por bairro fica limitada a receita/consumo. **Pendência de Dados** se for preciso bandeira ou GD por bairro. |
| P4 | Qual recorte mais perdeu volume? (§1.2) | `consumo_receita_bairro`, `diagnostico_receita` | coberta | Calculável para município, bairro e classe. "Último ano" é ambíguo (últimos 12 meses contra os 12 anteriores ou contra o primeiro ano?): a IA deve pedir esclarecimento ou declarar a janela. |
| P5 | Quanto cresceu a receita comercial em Jaboatão? (§1.2, §7.6) | `diagnostico_receita` ou `consumo_receita_bairro`, `municipio = JABOATÃO DOS GUARARAPES`, `classe_consumo = COMERCIAL` | coberta | Mesma ambiguidade de janela. No cálculo exploratório, a receita comercial de Jaboatão nos últimos 12 meses ficou abaixo da do primeiro ano (ver c). A IA deve responder com o que a evidência mostra e declarar a janela usada. |
| P6 | Quantas UCs com solar em Olinda tiveram queda de consumo acima de 30%? (§7.6) | `variacao_consumo_uc`: `possui_gd`, `municipio`, `queda_consumo_superior_30_pct` | coberta, com ressalva | P1 e P2 são fixos na Gold; outra janela exige recálculo pela `consumo_mensal_uc`. Basta 1 mês com leitura em cada período. O GD é uma marcação do cadastro atual, sem data de instalação. |
| P7 | A conta da UC subiu? Consumo e valor históricos da UC (§1.2 atendimento, WEB-03) | `consumo_mensal_uc` | coberta para 43.954 UCs | 1.046 UCs da Visão 360 não têm nenhum mês. "Por quê" só tem as hipóteses de consumo, bandeira e interrupções (estas sem mês por UC; ver P10). |
| P8 | Faturas em aberto, pagamento, valor pago (§1.2, ENT-01) | — | não coberta | Nenhuma tabela traz status de fatura, vencimento ou pagamento. **Pendência de Dados.** |
| P9 | Medidor instalado e histórico da UC (§1.2) | — | não coberta | **Pendência de Dados.** |
| P10 | Interrupções sofridas pela UC (§1.2, IA-01 "falta de luz") | `visao_360_uc`: `total_interrupcoes_sofridas`, `duracao_total_interrupcoes_horas` | parcial | Só o total acumulado por UC, **sem mês**; não dá para dizer "em março a UC teve N interrupções". **Pendência de Dados.** |
| P11 | Chamados e satisfação (§1.2, IA-01 "atendimento") | `visao_360_uc`: `total_chamados_callcenter`, `media_satisfacao_atendimento` | parcial | Totais por UC **sem mês** e sem motivo. Não há atendimento por competência nem por recorte temporal. **Pendência de Dados.** |
| P12 | Geração solar da UC (§1.2, ENT-01) | `possui_gd` (visão, variação, diagnóstico), `possui_geracao_solar` (fila) | parcial | Só a marcação Sim/Não; sem potência, energia gerada ou compensada. Não sustenta afirmar o efeito do GD na receita (PRD §8). |
| P13 | Cliente/titular da UC (§1.2) | — | não coberta, por desenho | Os campos pessoais foram removidos (LGPD). A IA deve dizer que não expõe titular. |
| P14 | Fila de UCs suspeitas, motivo e prioridade (§1.2 perdas) | `fila_inspecao`: `prioridade_inspecao`, inspeções, `media_consumo_historico` | parcial | O motivo é o próprio rótulo da prioridade; não há escore para ordenar dentro da faixa, e 94,78% das UCs caem em uma única faixa (ver c). |
| P15 | Energia potencialmente recuperável (§1.2 perdas) | — | não coberta | **Pendência de Dados.** |
| P16 | DEC e FEC por alimentador ao longo do tempo; piores resultados (§1.2 operação) | `indicadores_dec_fec` | coberta, com ressalva | As fórmulas fecham em todas as linhas. O denominador é fixo nos 48 meses (UCs ativas de hoje), não a base de cada mês. Indicador simplificado, sem conformidade ANEEL. |
| P17 | DEC/FEC por município | `indicadores_dec_fec` | coberta | Cada alimentador pertence a um único município. Agregar somando numeradores e denominadores; nunca tirar média de DEC. |
| P18 | Investigar as ocorrências de rede (§1.2 operação) | — | não coberta | Não há tabela por ocorrência, causa ou horário. **Pendência de Dados.** |
| P19 | Efeito da bandeira na receita (glossário, ENT-01) | `diagnostico_receita`: `bandeira_tarifaria` | parcial | A bandeira é dimensão de cada linha (município × classe × mês); não separa o acréscimo de bandeira do preço base. |
| P20 | "Conta de luz" (IA-02) | `receita_total_reais`, `ticket_medio_reais_por_uc`; `consumo_mensal_uc.receita_reais` | coberta como valor faturado | Se a pergunta for "quanto paguei", a resposta é falta de evidência (P8). |
| P21 | "Falta de luz" (IA-02) | `indicadores_dec_fec`; totais da Visão 360 | coberta por alimentador × mês; parcial por UC | Ver P10 e P16. |

## (c) Achados e riscos

**Reconciliações que fecharam exatamente.** `consumo_receita_bairro`, `diagnostico_receita` e `consumo_mensal_uc` (com o município e a classe da Visão 360) somam o mesmo total por competência, por competência × município e por competência × classe: 790.691.150,0 kWh, [valor financeiro omitido] e 1.928.920 UC-meses, com diferença zero nos 48, 672 e 240 grupos. O total de receita foi conciliado com a execução Gold; seu montante deve permanecer nas evidências do ambiente autorizado. As UCs de `fila_inspecao` e `variacao_consumo_uc` são as mesmas 45.000 da Visão 360. Os 122 alimentadores do DEC/FEC são os mesmos da Visão 360. O GD e a `media_consumo_historico` coincidem entre visão, fila e variação em todas as UCs.

**Prioridade da fila concentrada.** 42.652 UCs (94,78%) estão em `MEDIA - NUNCA INSPECIONADO`; `ALTA - HISTORICO IRREGULAR` tem 808 (1,80%), `REVISAR - SEM HISTORICO DE CONSUMO` 1.023 (2,27%) e `BAIXA` 517 (1,15%). Só 1.344 UCs têm inspeção (no máximo uma), e 808 tiveram irregularidade. A faixa `ALTA - CONSUMO ZERO`, listada no `dictionary_gold.toml`, não tem nenhuma UC neste lote. Para a IA: "quais UCs inspecionar primeiro" quase não discrimina, e a fila não deve ser apresentada como ranking de suspeita. Das 808 `ALTA`, 23 não têm consumo histórico.

**Nulos em `media_consumo_historico` e `variacao_pct`.** As 1.046 UCs com `media_consumo_historico` nula são as mesmas que não aparecem em `consumo_mensal_uc` (conferido UC a UC). Na fila, elas estão em `REVISAR` (1.004 nunca inspecionadas e 19 inspecionadas sem irregularidade) e em `ALTA - HISTORICO IRREGULAR` (23). A `variacao_pct` é nula em 1.461 UCs: 1.046 sem leitura em P1 e em P2 (mesma contagem, mas o cruzamento UC a UC com o grupo anterior não foi feito) e 415 sem leitura só em P1. **O texto do notebook diz que a variação só fica nula sem leitura em nenhum dos períodos; o código e o lote mostram que ela fica nula quando falta qualquer um dos dois.** A documentação precisa ser corrigida.

**UCs de `consumo_mensal_uc` menos que as da Visão 360.** São 43.954 contra 45.000; as 1.046 ausentes são todas `ATIVA`. A tabela mensal nasce de um `INNER JOIN` entre faturas e leituras por UC/mês, então um mês só aparece quando tem as duas. Por UC, há de 2 a 48 meses (mediana 44). Uma UC sem linhas não significa consumo zero.

**Duas médias de consumo diferentes para a mesma UC.** Em 17.123 UCs, a `media_consumo_historico` difere em mais de 1 kWh da média dos meses de `consumo_mensal_uc`; as duas vêm de bases diferentes (leituras contra meses com fatura e leitura). A IA não pode usar uma como prova da outra; o dicionário precisa nomear qual é qual.

**Premissa do case: sentido confere, valores diferem (cálculo exploratório, não homologado).** Na fala do diretor comercial, o volume de energia faturada "caiu quase 4%" e a receita "subiu só 8%", comparando os últimos 12 meses com o primeiro ano da base, sem restringir à classe residencial. Neste lote, comparando os últimos 12 meses (2025-07 a 2026-06) com os primeiros 12 (2022-07 a 2023-06) em `consumo_receita_bairro`:

| Recorte | Consumo (kWh) | Receita (R$) |
| --- | ---: | ---: |
| Todas as classes | −5,11% | +6,75% |
| Residencial | −6,54% | +5,63% |
| Citado no case | cerca de −4% | cerca de +8% |

O sentido bate: o volume cai e a receita sobe menos do que a tarifa. Os valores diferem em poucos pontos, e o case não diz se o recorte é o total ou o residencial. Outros cálculos exploratórios, nas mesmas janelas: a receita comercial de Jaboatão ficou −1,99% abaixo da do primeiro ano (−5,41% contra os 12 meses anteriores); o bairro residencial com maior perda de kWh foi Iputinga (Recife), −22,95% contra o primeiro ano; e há 3.120 UCs com GD e queda acima de 30%, das quais 289 em Olinda (janelas P1/P2 da própria Gold). As janelas de 12 meses foram escolha deste relatório. O diagnóstico (ENT-01) deve declarar a diferença em relação ao case, e a IA não deve repetir os números do case como fato da Gold.

**Classe e município são do cadastro atual.** A série mensal reagrupada pela classe da Visão 360 fecha exatamente com o diagnóstico; logo, a classe de cada fatura é a classe atual da UC, sem histórico de mudança. Todas as UCs são `ATIVA` e são 45.000 (o PRD cita cerca de 46 mil no cadastro de origem): UCs desligadas parecem ter ficado fora da Gold, o que afeta denominadores.

**Contagem de UCs no diagnóstico.** `soma_faturamentos_mensais` é igual a `qtd_ucs_distintas_faturadas_no_mes` em todas as 4.694 linhas (uma fatura por UC-mês depois da Silver). A soma de `qtd_ucs_distintas_faturadas_no_mes` entre meses dá UC-meses, não UCs distintas; o dicionário marca a coluna como `sum`, o que só vale dentro de uma competência.

**DEC/FEC.** `DEC = duracao_total_interrupcoes_horas / total_ucs_alimentador` e `FEC = frequencia_total_interrupcoes / total_ucs_alimentador` em todas as 5.856 linhas. `total_ucs_alimentador` é igual ao número de UCs da Visão 360 no alimentador e não varia entre meses. A soma de `frequencia_total_interrupcoes` é 180.000, igual à soma de interrupções por UC da Visão 360.

**Consumo e receita: sem negativos, zeros ou sentinelas.** Nas três tabelas de receita, consumo e receita são sempre positivos (mínimo mensal por UC: 8 kWh e [valor financeiro omitido]). Não há estorno visível. Não dá para saber, só pelo lote, se a origem não tinha estornos ou se a Silver os removeu.

**Sentinela de data.** `data_ligacao` tem 90 UCs com ano anterior a 1950 (mínimo `1900-01-01`), na visão e na fila. Esse valor não é data real de ligação.

**Divergências com o `dictionary_gold.toml`.** O snapshot `gold-v1-31a80e6` está desatualizado em relação ao lote:

| Tabela | No `dictionary_gold.toml` | No lote |
| --- | --- | --- |
| `diagnostico_receita` | `possuo_gd` | `possui_gd` |
| `visao_360_uc`, `fila_inspecao` | `subgrupo_tarifario` | `subgrupo` |
| `fila_inspecao` | `total_chamados_callcenter`, `media_satisfacao_atendimento` | ausentes |
| `indicadores_dec_fec` | `dec`, `fec` | `DEC`, `FEC` |
| `consumo_mensal_uc`, `consumo_receita_bairro`, `variacao_consumo_uc` | ausentes | presentes |

**Precisão numérica.** Há valores com cauda de ponto flutuante (por exemplo, DEC `15.169999999999998`) e 8 UCs em que a `variacao_pct` arredondada difere em mais de 0,02 ponto do recálculo a partir das médias arredondadas. O grounding compara valores após arredondamento declarado: a regra de arredondamento por métrica precisa estar no dicionário. Para "queda acima de 30%", usar a flag, que foi calculada antes do arredondamento.

## (d) Estados do lote que impedem resposta confiável

| Estado | Como aparece | O que a GenAI deve fazer | Situação neste lote |
| --- | --- | --- | --- |
| **Sem identificação** | Sem manifesto/`batch_ref` | O Backend não deve servir evidência como Gold real; sem `batch_ref` não se reproduz a amostra (IA-03) | **É o estado atual.** Bloqueia o aceite. |
| **Parcial** | Tabela ausente; competência faltante; mês com base menor que o normal | Recusar ou pedir esclarecimento nas perguntas da tabela ausente; não calcular percentual com janela incompleta | Sete tabelas presentes, 48 meses sem lacuna, nenhum mês abaixo de 80% da mediana de linhas. Sem data de corte, não dá para provar que 2026-06 está fechado. |
| **Misto** | Tabelas de execuções diferentes | Não cruzar números de tabelas sem o mesmo `batch_ref` | Não verificável sem manifesto. As reconciliações exatas sugerem uma única execução, mas não provam. |
| **Desatualizado** | Lote anterior ao último `CONCLUIDO` | Declarar a data do lote em cada resposta | Não verificável: falta `processado_em`. Só há as datas dos arquivos no zip (26/10/2026). |
| **Vazio** | Tabela com zero linhas | `no_evidence`, nunca zero | Nenhuma tabela vazia. |
| **Indisponível** | Banco local sem carga ou fora do ar | Erro recuperável, sem cair na fonte demonstrativa | **Atual:** não há carga das sete tabelas no banco do Backend. |
| **Valor de reserva** | `SINTETICO_DEV`/`LOTE_DEV` no controle | A carga deve recusar o lote | Não verificável sem `controle_gold`. |

## (e) Perguntas abertas para Dados e Backend

1. **Manifesto.** Quem gera o manifesto (`run_id_silver`, `lote_bronze_silver`, `status_gold`, `processado_em`, contagens e hashes por tabela) e quando ele entra na exportação? O notebook de exportação atual não grava manifesto.
2. **Universo de UCs.** A Gold tem só UCs `ATIVA` (45.000). As UCs desligadas foram excluídas de propósito? Como ficam as faturas antigas dessas UCs nos totais de receita?
3. **Classe e município no tempo.** A classe das faturas é a do cadastro atual. Há mudança de classe no histórico? Isso altera a receita residencial por período?
4. **Granularidade por UC sem mês.** Interrupções, chamados e satisfação por UC só existem como totais acumulados. Haverá tabela por UC × competência (ou por evento) para atendimento e interrupções?
5. **Lacunas para atendimento e perdas.** Faturas em aberto/pagamento, medidor, ocorrências por evento e energia recuperável estão fora da Gold. Ficam fora do escopo (e a IA declara isso) ou entram em uma nova tabela?
6. **Bairro.** `consumo_receita_bairro` precisará de subgrupo, bandeira ou GD para abrir a decomposição preço × volume por bairro?
7. **Duas médias de consumo.** Qual é a definição de `media_consumo_historico` (fonte e meses)? Ela deve continuar diferente da média de `consumo_mensal_uc`?
8. **`variacao_pct`.** Corrigir a documentação do notebook sobre quando a variação é nula. As janelas P1/P2 fixas são as janelas oficiais da pergunta de GD?
9. **Fila.** Há um escore para ordenar dentro de `MEDIA - NUNCA INSPECIONADO`? A faixa `ALTA - CONSUMO ZERO` continua prevista?
10. **Denominador do DEC/FEC.** O denominador fixo (UCs ativas de hoje) é a definição aprovada para DE-05, ou deve ser a base de cada mês?
11. **Estornos.** A origem tinha faturas negativas, zeradas ou canceladas? Se a Silver removeu, onde está a contagem?
12. **Nomes de colunas.** Congelar `possui_gd`, `subgrupo` e `DEC`/`FEC` (caixa alta), e atualizar o `dictionary_gold.toml` e o `docs/data-dictionary.md`. No PostgreSQL, uma coluna criada como `"DEC"` não casa com `dec`.
13. **Data sentinela.** `data_ligacao = 1900-01-01` deve virar nulo com flag na Gold, como na Silver?
14. **Carga no banco local.** Quem implementa a carga idempotente das sete tabelas e a conferência de esquema, contagens, chaves e agregados (DE-06)? Este relatório pode servir de lista de checagens.

## (f) Situação dos itens do cartão GENAI-02

Texto dos itens copiado do checklist do cartão GENAI-02 no quadro "GenAI — Gold real", lido em 27/10/2026. Nenhum item está concluído. "Preparado neste relatório" significa que este documento entrega a base do item; a conclusão ainda depende de revisão e aprovação.

| Checklist | Item | Situação | Evidência neste documento | Quem precisa agir |
| --- | --- | --- | --- | --- |
| Implementação e validação | Conferir schema, tipos, chaves, grão, contagens, nulos, períodos disponíveis e regras de qualidade no ambiente autorizado. | parcial | (a); (c) | Dados: confirmar o ambiente autorizado e as regras de qualidade. A conferência foi feita sobre os CSVs em máquina local, não no Databricks nem no banco do Backend. |
| Implementação e validação | Validar as tabelas candidatas do dicionário v1 contra a versão final, incluindo fontes de receita, consumo, continuidade, GD e atendimento. | parcial | (b); (c), tabela de divergências com o `dictionary_gold.toml` | Dados: congelar nomes e publicar o dicionário Gold (DE-08). GenAI: atualizar o catálogo (GENAI-03). Atendimento só tem totais por UC, sem mês. |
| Implementação e validação | Conferir identificação do lote e agregados entre origem Gold, processo de carga, banco autorizado do Backend e fonte do portal; testar recarga sem duplicar resultados, sem fixar fornecedor da fonte no contrato. | pendente | "O que foi conferido e o que não foi" | Dados: manifesto do lote. Backend: carga idempotente e banco com as sete tabelas. Só foram conferidos agregados entre os próprios CSVs. |
| Implementação e validação | Registrar cobertura por domínio obrigatório e solicitar complemento de Gold quando faltar fonte ou granularidade; não preencher com demonstração. | preparado neste relatório | (b); (e) | Dados: responder às perguntas abertas. GenAI: enviar a solicitação formal de complemento. |
| Implementação e validação | Distinguir lote parcial, misto, desatualizado, vazio e indisponível; definir o que bloqueia uma resposta confiável. | preparado neste relatório | (d) | Backend e GenAI: acordar o comportamento do executor e os estados do contrato. Sem manifesto, "misto" e "desatualizado" não são verificáveis. |
| Implementação e validação | Preparar consultas de controle independentes e exemplos sanitizados para a primeira fatia de integração. | parcial | (g) | Dados (Júlia): conferência independente de cada controle. Os controles de (g) foram calculados pelo mesmo script deste relatório, então ainda não são independentes. |
| Robustez e evidência de integração | Versionar manifesto com fonte, esquema, lote, horário, contagens, janelas e estado de qualidade/reconciliação; testar carga parcial, repetida e troca de lote sem duplicar fatos ou misturar versões. | pendente | "O que foi conferido e o que não foi"; (d) | Dados: manifesto. Backend: testes de carga parcial, repetida e troca de lote. |
| Robustez e evidência de integração | Conferir chaves, unicidade, cardinalidades, dimensão historizada e regras de sentinelas, estornos/estimativas que afetem as métricas; registrar regra aprovada e seu impacto no dicionário. | parcial | (a), chaves; (c), sentinela de data, estornos e classe sem histórico | Dados: aprovar as regras e registrá-las no dicionário. |
| Robustez e evidência de integração | Aprovar ao menos um controle independente por domínio e recorte relevante, incluindo zero, nulo, ausência e período parcial; guardar somente controles e evidências autorizados, com tolerância justificada. | pendente | (g): rascunho com zero (C07), nulo (C10) e período parcial (C09) | Dados (Júlia): aprovar os controles e as tolerâncias. GenAI: transformar em fixture só depois da aprovação. Falta um controle de ausência por domínio (ex.: atendimento por mês). |
| Robustez e evidência de integração | Definir prontidão por capacidade: tabela ou período ausente impede liberar a métrica afetada. Entregar versões e compatibilidade a GENAI-03/06/13; uma migração incompatível precisa de diagnóstico e plano de retorno. | parcial | (b), matriz por pergunta; (d) | GenAI: transformar a matriz em prontidão versionada por capacidade. Backend: depende do `batch_ref`. Ainda não há versão de catálogo nem de lote para entregar. |

## (g) Controles candidatos (rascunho, não aprovados)

Controles agregados calculados a partir dos CSVs por `scripts/gold_coverage.py` (seção "Controles candidatos" da saída). Nenhum identifica UC, alimentador ou pessoa. **Cada controle precisa de aprovação independente da Júlia (Dados), calculado por outro caminho e com tolerância definida, antes de virar fixture.** Os valores de kWh não têm arredondamento além do que vem no lote. Os montantes financeiros foram omitidos deste relatório público; os controles de receita devem ser conferidos no ambiente autorizado.

| ID | Definição | Tabela e colunas | Janela | Valor calculado |
| --- | --- | --- | --- | --- |
| C01 | Total de energia faturada e de receita faturada no lote | `diagnostico_receita`: `consumo_total_kwh`, `receita_total_reais` | 2022-07 a 2026-06 | 790.691.150 kWh; [valor financeiro omitido] |
| C02 | Energia e receita faturadas por classe | `diagnostico_receita`: `classe_consumo`, `consumo_total_kwh`, `receita_total_reais` | 2022-07 a 2026-06 | Comercial 177.546.534 kWh, [valor financeiro omitido]; Industrial 305.167.405 kWh, [valor financeiro omitido]; Poder público 14.818.877 kWh, [valor financeiro omitido]; Residencial 285.113.458 kWh, [valor financeiro omitido]; Rural 8.044.876 kWh, [valor financeiro omitido] |
| C03 | UC-meses com fatura e leitura (linhas da série mensal) | `consumo_mensal_uc`: contagem de (`id_uc`, `competencia`) | 2022-07 a 2026-06 | 1.928.920 |
| C04 | Energia e receita no último mês do lote, no município de maior receita (escolha deste relatório) | `diagnostico_receita`: `competencia`, `municipio`, `consumo_total_kwh`, `receita_total_reais` | 2026-06, Recife | 5.253.939 kWh; [valor financeiro omitido] |
| C05 | UCs por classe | `visao_360_uc`: contagem de `id_uc` por `classe` | cadastro atual, sem competência | Comercial 4.909; Industrial 877; Poder público 222; Residencial 38.336; Rural 656 (total 45.000) |
| C06 | UCs por faixa de prioridade da fila | `fila_inspecao`: contagem de `id_uc` por `prioridade_inspecao` | cadastro atual, sem competência | `MEDIA - NUNCA INSPECIONADO` 42.652; `REVISAR - SEM HISTORICO DE CONSUMO` 1.023; `ALTA - HISTORICO IRREGULAR` 808; `BAIXA` 517 |
| C07 | Caso de zero: UCs na faixa `ALTA - CONSUMO ZERO` | `fila_inspecao`: `prioridade_inspecao` | cadastro atual, sem competência | 0 UC. A resposta esperada é "nenhuma UC nesta faixa", não ausência de evidência. |
| C08 | UCs com GD e queda de consumo acima de 30%, em Olinda e no total | `variacao_consumo_uc`: `municipio`, `possui_gd = Sim`, `queda_consumo_superior_30_pct = true` | P1 = 2022-07 a 2023-06; P2 = 2025-07 a 2026-06 | Olinda 289; total 3.120 |
| C09 | Caso de período parcial: UCs sem leitura em P1, em P2 ou nos dois | `variacao_consumo_uc`: `meses_com_leitura_p1`, `meses_com_leitura_p2`, `variacao_pct` | P1 e P2 | sem leitura só em P1: 415; só em P2: 0; nos dois: 1.046; `variacao_pct` nula: 1.461 |
| C10 | Caso de nulo: UCs sem média de consumo histórico e quantas delas faltam na série mensal | `visao_360_uc`: `media_consumo_historico`; `consumo_mensal_uc`: `id_uc` | cadastro atual | 1.046 com média nula; nenhuma delas tem mês em `consumo_mensal_uc` |
| C11 | O alimentador de maior DEC em 2026-06: DEC e FEC do mês e média simples dos 48 meses (identificador omitido) | `indicadores_dec_fec`: `id_alimentador`, `competencia`, `DEC`, `FEC` | 2026-06; média de 2022-07 a 2026-06 | No mês: DEC 1,8020 h, FEC 1,1471. Médias mensais: DEC 1,5109 h, FEC 0,8511. A média simples entre meses serve só como controle, não é métrica aprovada. |
| C12 | Competências em que bairro e diagnóstico divergem em kWh, R$ ou UC-meses | `consumo_receita_bairro`, `diagnostico_receita`: `competencia`, consumo, receita, `qtd_ucs_distintas_faturadas_no_mes` | 2022-07 a 2026-06 | 0 de 48 |
