# Cobertura do lote candidato da Gold — v0

**Cartão:** GENAI-02 — Conferir o lote Gold e a cobertura dos dados obrigatórios
**Data da conferência:** 27/10/2026; reanálise com o lote gerado em 28/10/2026
**IDs do PRD relacionados:** IA-01, IA-02, IA-03, IA-06; dependências DE-04, DE-05, DE-06, DE-08
**Natureza:** relatório de **lote candidato**. Este documento não conclui requisito, não homologa métrica e não declara a Gold pronta para a GenAI. Os estados do PRD não mudam.

> **Nota sobre o conteúdo.** Por regra de Dados e pela confidencialidade do case, este repositório não publica agregados além dos do diagnóstico da receita; os valores ficam com Dados. Para reproduzir localmente, ver [Como reproduzir](#como-reproduzir). O documento registra estrutura, método e conclusões em palavras: nenhuma linha de dado, nenhum total, contagem ou percentual do lote, nenhum id de UC ou de alimentador, nenhum nome de município ou bairro tirado do lote e nenhum dado pessoal. Os CSVs e o manifesto não estão no repositório.

## O que foi conferido e o que não foi

**Lote conferido:** sete CSVs exportados da Gold (separador `;`, UTF-8, todos os campos entre aspas), um por tabela. Os CSVs ficam fora do repositório; nome do arquivo, hashes e identificadores do lote também não são publicados aqui.

**Manifesto.** O primeiro lote não tinha manifesto nem `controle_gold`, então não havia como saber de qual `run_id_silver`/`lote_bronze_silver` ele veio, se a execução foi `CONCLUIDO`, nem se usou os valores de reserva `SINTETICO_DEV`/`LOTE_DEV`. O lote reanalisado traz manifesto (ver [Lote reanalisado](#lote-reanalisado)). No exportador da `develop` (commit `ca73db5`, PR #36), a exportação exige ambiente `prod` e falha se não for, o fallback para lote de reserva foi removido e o notebook lê a última execução com `status_gold = CONCLUIDO` em `controle_gold`. Falta só gravar o `status_gold` no manifesto (sugestão para Dados; ver e). O `batch_ref` proposto no [contrato de consulta](contracts/genai-query-execution.md#lote-da-gold-batch_ref) e na [ADR-0002](decisions/0002-genai-gold-query-owner.md) ainda não está definido a partir dele. O notebook de exportação da branch `feat/gold` (`Exportacao_Gold_SQLite.ipynb`, commit `9664823`) não gravava manifesto.

**Não verificado nesta conferência:**

- recarga dos CSVs no banco local sem duplicar resultados (DE-06). Na primeira conferência, o carregador `backend/scripts/load_gold.py` ainda era esqueleto e não inseria registros;
- comparativo entre os CSVs e o banco do Backend;
- comparativo entre os CSVs e as tabelas no Databricks;
- controles aprovados de catálogo, papel somente leitura, identidade e auditoria (pendências da ADR-0002).

### Como reproduzir

A partir de `ai-agent/`, `python scripts/gold_coverage.py <diretório do lote>` (ou `GOLD_DATA_DIR=<diretório> python scripts/gold_coverage.py --json <saída fora do repo>`). O script só lê, usa biblioteca padrão e imprime agregados; não imprime linhas, ids de UC nem ids de alimentador. Os agregados ficam no terminal ou no JSON local e não devem ser copiados para o repositório.

O diretório do lote pode estar em um de dois layouts:

- CSVs soltos na pasta: `<diretório>/<tabela>.csv`;
- uma subpasta por tabela: `<diretório>/<tabela>/<tabela>.csv`, o layout que o carregador do Backend espera (uma subpasta com partes `*.csv` do Spark também é aceita).

O manifesto é procurado em `<diretório>/manifest.json` (onde o exportador da Gold o grava) ou em `<diretório>/manifesto/manifest.json`; se existirem os dois, o script usa o da raiz e avisa. Ele mostra só qual arquivo leu e os campos técnicos de identificação (`ambiente`, `lote`, `run_id_silver`, `lote_bronze_silver`, `tabelas_exportadas`), sem nenhum valor de negócio, e avisa quando o `ambiente` não é de produção ou quando `tabelas_exportadas` não bate com as sete tabelas encontradas. Sem manifesto, a saída diz "nenhum".

Salvaguardas da saída:

- valores de coluna só aparecem para as dimensões autorizadas (município, classe, subgrupo, bandeira, GD, status, UF, prioridade e flag de queda), e nunca quando o nome ou os valores parecem dado pessoal (CPF, CEP, e-mail); mínimo e máximo de texto só em colunas de data e competência;
- reconciliações e controles com medida nula ou inválida saem como `nao_verificavel`, com as contagens, e não como "0 divergências";
- as janelas de 12 meses exigem competências contínuas; com lacuna, o percentual não é calculado (`janela incompleta`);
- `--json` recusa destino dentro da pasta do lote, inclusive nas subpastas de tabela e de manifesto, via link ou `..`, e sobre um arquivo de entrada.

Testes com dados inventados: `python -m pytest tests/test_gold_coverage.py`.

**Fontes lidas:** [PRD](PRD.md) (§1, §1.2, §2.1, §4, §6.3, §7.6, §8), [contrato](contracts/genai-query-execution.md), [ADR-0002](decisions/0002-genai-gold-query-owner.md), `ai-agent/app/sql/dictionary_gold.toml` (**existe só na branch `feat/ia-gold-dicionario-sql`, commit `fd6db48`; não está na `develop`**), `docs/dicionario_gold.md` e `data-engineering/notebook/Silver_to_gold.ipynb` da branch `feat/gold` (commit `9664823`), e o comentário de Dados no PR #60. O [dicionário Gold](data-dictionary.md) da `develop` ainda é modelo vazio.

## Lote reanalisado

A primeira conferência usou um lote gerado a partir de uma Silver sem o reparo de encoding do bairro, o que duplicava bairros em `consumo_receita_bairro`. O lote gerado em 28/10 corrigiu essa duplicação. Nele, as reconciliações entre as tabelas fecham sem divergência, não há nulo nem valor inválido nas medidas de consumo, receita e UCs usadas nas reconciliações e o manifesto traz ambiente de produção e a linhagem Silver/Bronze. O exportador atual só exporta a partir de uma execução `CONCLUIDO` em ambiente de produção, mas o manifesto ainda não grava o `status_gold`. Como o C12 compara totais por competência, ele não detecta bairro duplicado; o controle C13 (ver g) cobre esse caso. Resultados que dependem de bairro devem ser lidos no lote reanalisado, não no primeiro.

## (a) As sete tabelas

"Nulos" lista só as colunas com nulos; as demais não têm nenhum.

| Tabela | Grão (chave candidata) | Chave única? | Período | Colunas | Colunas com nulos |
| --- | --- | --- | --- | ---: | --- |
| `visao_360_uc` | UC (`id_uc`) | sim | sem competência | 15 | `media_consumo_historico`; `media_satisfacao_atendimento` |
| `fila_inspecao` | UC (`id_uc`) | sim | sem competência | 14 | `media_consumo_historico` |
| `variacao_consumo_uc` | UC (`id_uc`) | sim | P1 = 2022-07 a 2023-06; P2 = 2025-07 a 2026-06 (fixos no notebook) | 11 | `consumo_medio_inicial`, `variacao_kwh`, `variacao_pct`, `consumo_medio_final` |
| `consumo_mensal_uc` | UC × competência | sim | 2022-07 a 2026-06, 48 meses, sem lacuna | 4 | nenhuma |
| `consumo_receita_bairro` | competência × município × bairro × classe | sim | 2022-07 a 2026-06, 48 meses, sem lacuna | 7 | nenhuma |
| `diagnostico_receita` | competência × município × classe × subgrupo × bandeira × GD | sim | 2022-07 a 2026-06, 48 meses, sem lacuna | 13 | nenhuma |
| `indicadores_dec_fec` | alimentador × competência | sim | 2022-07 a 2026-06, 48 meses, sem lacuna | 9 | nenhuma |

Dimensões observadas (todas as tabelas que as têm usam os mesmos valores):

- Uma única UF; cada alimentador pertence a um único município.
- Classe: `COMERCIAL`, `INDUSTRIAL`, `PODER PUBLICO`, `RESIDENCIAL`, `RURAL`. Subgrupo: `A4`, `B1`, `B2`, `B3`.
- Bandeira (`diagnostico_receita`): `VERDE`, `AMARELA`, `VERMELHA P1`, `VERMELHA P2`.
- `status` da UC: só `ATIVA`.
- Prioridade da fila: `MEDIA - NUNCA INSPECIONADO`, `REVISAR - SEM HISTORICO DE CONSUMO`, `ALTA - HISTORICO IRREGULAR`, `BAIXA`.

Formatos: competência como texto `YYYY-MM`; `data_ligacao` como `YYYY-MM-DD`; decimal com ponto; números também entre aspas (`quoteAll`), então a carga precisa converter tipos. GD aparece como texto `Sim`/`Não` (com acento) em `possui_gd` e `possui_geracao_solar`; `queda_consumo_superior_30_pct` é `true`/`false` em minúsculas. As colunas `DEC` e `FEC` vêm em maiúsculas.

Colunas pessoais ou sensíveis: **nenhuma** no cabeçalho de qualquer tabela (`cpf`, `cnpj`, nome, logradouro, número, CEP, latitude, longitude, e-mail e telefone foram procurados por nome) e nenhum valor de texto com padrão de CPF, CEP ou e-mail. As colunas `_*` de pipeline também não vieram. O notebook de exportação avisa que `visao_360_uc` pode conter dados pessoais; neste lote, não contém. Cada nova exportação precisa ser conferida de novo.

## (b) Perguntas de negócio × tabela que as sustenta

**De onde vêm as perguntas.** Não há no repositório uma lista única e numerada de perguntas obrigatórias. As perguntas abaixo foram extraídas do PRD: a pergunta central (§1), as falas das lideranças (§1.2), os exemplos da IA (§7.6), os domínios do IA-01 (consumo, faturamento, interrupções e atendimento) e os termos do IA-02. A lista não acrescenta perguntas por conta própria.

Estados: **coberta** = a Gold tem grão e colunas para responder, sujeita às ressalvas; **parcial** = responde só parte, ou com uma granularidade que limita a resposta; **não coberta** = falta a informação. **Pendência de Dados/Backend** marca o que depende de granularidade ou coluna ausente.

| # | Pergunta (origem) | Tabela / colunas | Estado | Observação |
| --- | --- | --- | --- | --- |
| P1 | Receita e energia faturada por competência, município e classe (§1, IA-01) | `diagnostico_receita`, `consumo_receita_bairro`: `receita_total_reais`, `consumo_total_kwh` | coberta | Os totais das três tabelas conferem entre si, sem divergência (ver c). A receita é **faturada** (`valor_total` da fatura), não paga. |
| P2 | Explicar a variação da receita diante do reajuste tarifário e da queda de volume, separando preço/tarifa e volume (§1, ENT-01) | `diagnostico_receita`: receita, consumo, `tarifa_media_efetiva`, bandeira, subgrupo, GD | parcial | Dá para calcular o preço médio efetivo e o volume. Faltam a tarifa homologada e o método de decomposição aprovado (PRD §8). As variações do lote têm o mesmo sentido das citadas no case, mas não os mesmos valores (ver c); a diferença precisa ser explicada com Dados. **Pendência de Dados.** |
| P3 | Abrir a variação por bairro (§1, §1.2) | `consumo_receita_bairro` | parcial | Bairro só aparece com competência × classe; sem subgrupo, bandeira ou GD. A decomposição preço × volume por bairro fica limitada a receita/consumo. Usar o lote reanalisado, sem a duplicação de bairros. |
| P4 | Qual recorte mais perdeu volume? (§1.2) | `consumo_receita_bairro`, `diagnostico_receita` | coberta | Calculável para município, bairro e classe. "Último ano" é ambíguo (últimos 12 meses contra os 12 anteriores ou contra o primeiro ano?): a IA deve pedir esclarecimento ou declarar a janela. |
| P5 | Quanto cresceu a receita comercial em Jaboatão? (§1.2, §7.6) | `diagnostico_receita` ou `consumo_receita_bairro`, filtro por município e `classe_consumo = COMERCIAL` | coberta | Mesma ambiguidade de janela. No cálculo exploratório, a receita comercial desse município nos últimos 12 meses não cresceu em relação ao primeiro ano (ver c). A IA deve responder com o que a evidência mostra e declarar a janela usada. |
| P6 | Quantas UCs com solar em Olinda tiveram queda de consumo acima de 30%? (§7.6) | `variacao_consumo_uc`: `possui_gd`, `municipio`, `queda_consumo_superior_30_pct` | coberta, com ressalva | P1 e P2 são fixos na Gold e o case não define a janela da pergunta (premissa a documentar); outra janela exige recálculo pela `consumo_mensal_uc`. Basta um mês com leitura em cada período. O GD é uma marcação do cadastro atual, sem data de instalação. |
| P7 | A conta da UC subiu? Consumo e valor históricos da UC (§1.2 atendimento, WEB-03) | `consumo_mensal_uc` | coberta para a maior parte das UCs | Algumas UCs da Visão 360 não têm nenhum mês na série. "Por quê" só tem as hipóteses de consumo, bandeira e interrupções (estas sem mês por UC; ver P10). |
| P8 | Faturas em aberto, pagamento, valor pago (§1.2, ENT-01) | — | não coberta | Nenhuma tabela traz status de fatura, vencimento ou pagamento. **Pendência de Dados** (`faturas_uc`). |
| P9 | Medidor instalado e histórico da UC (§1.2) | — | não coberta | **Pendência de Dados** (`medidor_uc`). |
| P10 | Interrupções sofridas pela UC (§1.2, IA-01 "falta de luz") | `visao_360_uc`: `total_interrupcoes_sofridas`, `duracao_total_interrupcoes_horas` | parcial | Só o total acumulado por UC, **sem mês**; não dá para dizer "em março a UC teve N interrupções". **Pendência de Dados.** |
| P11 | Chamados e satisfação (§1.2, IA-01 "atendimento") | `visao_360_uc`: `total_chamados_callcenter`, `media_satisfacao_atendimento` | parcial | Totais por UC **sem mês** e sem motivo. Não há atendimento por competência nem por recorte temporal. **Pendência de Dados.** |
| P12 | Geração solar da UC (§1.2, ENT-01) | `possui_gd` (visão, variação, diagnóstico), `possui_geracao_solar` (fila) | parcial | Só a marcação Sim/Não; sem potência, energia gerada ou compensada. Não sustenta afirmar o efeito do GD na receita (PRD §8). |
| P13 | Cliente/titular da UC (§1.2) | — | não coberta, por desenho | Os campos pessoais foram removidos (LGPD). A IA deve dizer que não expõe titular. |
| P14 | Fila de UCs suspeitas, motivo e prioridade (§1.2 perdas) | `fila_inspecao`: `prioridade_inspecao`, inspeções, `media_consumo_historico` | parcial | O motivo é o próprio rótulo da prioridade; não há escore para ordenar dentro da faixa, e a maior parte das UCs cai em uma única faixa (ver c). |
| P15 | Energia potencialmente recuperável (§1.2 perdas) | — | não coberta | **Pendência de Dados** (energia estimada). |
| P16 | DEC e FEC por alimentador ao longo do tempo; piores resultados (§1.2 operação) | `indicadores_dec_fec` | coberta, com ressalva | As fórmulas fecham em todas as linhas. O denominador é o cadastro atual por alimentador, constante nos 48 meses, não a base de cada mês. Indicador simplificado, sem conformidade ANEEL. |
| P17 | DEC/FEC por município | `indicadores_dec_fec` | coberta | Cada alimentador pertence a um único município. Agregar somando numeradores e denominadores; nunca tirar média de DEC. |
| P18 | Investigar as ocorrências de rede (§1.2 operação) | — | não coberta | Não há tabela por ocorrência, causa ou horário. **Pendência de Dados.** |
| P19 | Efeito da bandeira na receita (glossário, ENT-01) | `diagnostico_receita`: `bandeira_tarifaria` | parcial | A bandeira é dimensão de cada linha (município × classe × mês); não separa o acréscimo de bandeira do preço base. |
| P20 | "Conta de luz" (IA-02) | `receita_total_reais`, `ticket_medio_reais_por_uc`; `consumo_mensal_uc.receita_reais` | coberta como valor faturado | Se a pergunta for "quanto paguei", a resposta é falta de evidência (P8). |
| P21 | "Falta de luz" (IA-02) | `indicadores_dec_fec`; totais da Visão 360 | coberta por alimentador × mês; parcial por UC | Ver P10 e P16. |

## (c) Achados e riscos

**Reconciliações que conferem sem divergência.** `consumo_receita_bairro`, `diagnostico_receita` e `consumo_mensal_uc` (com o município e a classe da Visão 360) somam os mesmos totais de energia, receita e UC-meses por competência, por competência × município e por competência × classe, sem divergência em nenhum grupo. O total de receita coincide com o registrado no notebook. As UCs de `fila_inspecao` e `variacao_consumo_uc` são as mesmas da Visão 360, e os alimentadores do DEC/FEC são os mesmos da Visão 360. O GD coincide entre visão, fila e variação em todas as UCs, e a `media_consumo_historico` coincide entre visão e fila (é a mesma coluna nas duas). A variação usa outras médias (`consumo_medio_inicial` e `consumo_medio_final`, por período).

**Prioridade da fila concentrada.** A maior parte das UCs cai em uma única faixa da fila, a de UCs nunca inspecionadas; as demais faixas somam uma parcela pequena. Poucas UCs têm inspeção registrada (no máximo uma por UC). A faixa `ALTA - CONSUMO ZERO`, listada no `dictionary_gold.toml`, não aparece neste lote. Para a IA: "quais UCs inspecionar primeiro" quase não discrimina, e a fila não deve ser apresentada como ranking de suspeita. Há UCs em `ALTA` sem consumo histórico.

**Nulos em `media_consumo_historico` e `variacao_pct`.** As UCs com `media_consumo_historico` nula são as mesmas que não aparecem em `consumo_mensal_uc` (conferido UC a UC): são UCs sem leitura na Silver. Isso não torna as duas médias equivalentes (ver as premissas abaixo). Na fila, essas UCs estão em `REVISAR` e em `ALTA - HISTORICO IRREGULAR`. A `variacao_pct` é nula nas UCs sem leitura em P1 e em P2 e nas UCs sem leitura só em P1. **O texto do notebook diz que a variação só fica nula sem leitura em nenhum dos períodos; o código, o lote e a resposta de Dados mostram que ela fica nula quando falta qualquer um dos dois (ou quando a média inicial é menor ou igual a zero).** A documentação do notebook precisa ser corrigida.

**UCs de `consumo_mensal_uc` menos que as da Visão 360.** Parte das UCs da Visão 360, todas `ATIVA`, não tem nenhum mês na série mensal. A tabela mensal nasce de um `INNER JOIN` entre faturas e leituras por UC/mês, então um mês só aparece quando tem as duas, e o número de meses por UC varia. Uma UC sem linhas não significa consumo zero.

**Duas médias de consumo diferentes para a mesma UC.** A `media_consumo_historico` é a média das leituras da Silver por UC; a média dos meses de `consumo_mensal_uc` usa só os meses com fatura e leitura. Para boa parte das UCs, as duas diferem em mais de 1 kWh. A IA não pode usar uma como prova da outra; o dicionário precisa nomear qual é qual.

**Premissa do case: sentido confere, valores diferem (cálculo exploratório, não homologado).** Na fala do diretor comercial, o volume de energia faturada "caiu quase 4%" e a receita "subiu só 8%", comparando os últimos 12 meses com o primeiro ano da base, sem restringir à classe residencial. Neste lote, comparando os últimos 12 meses (P2) com os primeiros 12 (P1) em `consumo_receita_bairro`, no total e na classe residencial, o sentido bate: o volume cai e a receita sobe menos do que a tarifa. Os valores diferem dos do case em poucos pontos, e o case não diz se o recorte é o total ou o residencial. Nas mesmas janelas, também foram calculados, de forma exploratória, a receita comercial em Jaboatão (que não cresceu em relação ao primeiro ano nem aos 12 meses anteriores), o bairro residencial com maior perda de kWh e as UCs com GD e queda acima de 30% (no total e em Olinda, com as janelas P1/P2 da própria Gold). As janelas de 12 meses foram escolha deste relatório. O diagnóstico (ENT-01) deve declarar a diferença em relação ao case, e a IA não deve repetir os números do case como fato da Gold.

**Classe e município são do cadastro atual.** A série mensal reagrupada pela classe da Visão 360 fecha exatamente com o diagnóstico; logo, a classe de cada fatura é a classe atual da UC, sem histórico de mudança (confirmado por Dados). Todas as UCs são `ATIVA`, em número menor que o do cadastro de origem citado no PRD; a questão do universo está fechada com Dados (ver e).

**Contagem de UCs no diagnóstico.** `soma_faturamentos_mensais` é igual a `qtd_ucs_distintas_faturadas_no_mes` em todas as linhas (uma fatura por UC-mês depois da Silver). A soma de `qtd_ucs_distintas_faturadas_no_mes` entre meses dá UC-meses, não UCs distintas; o dicionário marca a coluna como `sum`, o que só vale dentro de uma competência.

**DEC/FEC.** `DEC = duracao_total_interrupcoes_horas / total_ucs_alimentador` e `FEC = frequencia_total_interrupcoes / total_ucs_alimentador` em todas as linhas. `total_ucs_alimentador` é igual ao número de UCs da Visão 360 no alimentador e não varia entre meses. A soma de `frequencia_total_interrupcoes` é igual à soma de interrupções por UC da Visão 360.

**Consumo e receita: sem negativos, zeros ou sentinelas.** Nas três tabelas de receita, consumo e receita são sempre positivos. Não há estorno visível, e Dados confirmou que a Silver publicada não tem faturas estornadas, negativas ou canceladas.

**Data de ligação inválida na origem.** Algumas UCs têm `data_ligacao` com ano anterior a 1950, na visão e na fila, sempre no dia 01-01. Não é um valor-marcador único: segundo Dados, são UCs reais com data de cadastro inválida na origem. O lote atual ainda traz o valor original; a sugestão de Dados para a próxima execução da Gold está nas premissas abaixo.

**Divergências com o `dictionary_gold.toml`.** O snapshot `gold-v1-31a80e6` está desatualizado em relação ao lote:

| Tabela | No `dictionary_gold.toml` | No lote |
| --- | --- | --- |
| `diagnostico_receita` | `possuo_gd` | `possui_gd` |
| `visao_360_uc`, `fila_inspecao` | `subgrupo_tarifario` | `subgrupo` |
| `fila_inspecao` | `total_chamados_callcenter`, `media_satisfacao_atendimento` | ausentes |
| `indicadores_dec_fec` | `dec`, `fec` | `DEC`, `FEC` |
| `consumo_mensal_uc`, `consumo_receita_bairro`, `variacao_consumo_uc` | ausentes | presentes |

**Precisão numérica.** Há valores com cauda de ponto flutuante (por exemplo, em `DEC`) e algumas UCs em que a `variacao_pct` arredondada difere em mais de 0,02 ponto do recálculo a partir das médias arredondadas. O grounding compara valores após arredondamento declarado: a regra de arredondamento por métrica precisa estar no dicionário. Para "queda acima de 30%", usar a flag, que foi calculada antes do arredondamento.

## Premissas e definições registradas por Dados

Registradas a partir do comentário de Dados no PR #60. Valem para a GenAI até o dicionário Gold (DE-08) publicá-las.

- **Classe da UC.** Vem do cadastro atual; o dado não tem histórico de classe.
- **`media_consumo_historico`.** É a média das leituras da Silver por UC, não a média da série mensal faturada (`consumo_mensal_uc`). As duas diferem para boa parte das UCs; a média da Visão 360 e a média da série mensal não são equivalentes e não devem ser usadas uma pela outra.
- **`variacao_pct`.** Fica nula quando falta histórico em P1 ou em P2, ou quando a média inicial é menor ou igual a zero. O case não define a janela da pergunta de GD em Olinda; usar P1/P2 da Gold é premissa a documentar na resposta.
- **Denominador do DEC/FEC.** É o cadastro atual por alimentador, constante nos 48 meses.
- **`data_ligacao` anterior a 1950.** São UCs reais com data de cadastro inválida na origem, todas com dia 01-01. Dados sugere tratar essas datas como nulas na Gold, na próxima execução, sem coluna nova; o lote atual ainda traz o valor original (contrato [Gold CSV v1](contracts/gold-csv-v1.md)); a Silver continua preservando o valor original.
- **Estornos.** Não há faturas estornadas, negativas ou canceladas na Silver publicada.

## (d) Estados do lote que impedem resposta confiável

| Estado | Como aparece | O que a GenAI deve fazer | Situação neste lote |
| --- | --- | --- | --- |
| **Sem identificação** | Sem manifesto/`batch_ref` | O Backend não deve servir evidência como Gold real; sem `batch_ref` não se reproduz a amostra (IA-03) | Era o estado do primeiro lote. O lote reanalisado traz manifesto com ambiente e linhagem, mas o manifesto ainda é parcial e o `batch_ref` do contrato não está definido (ver e). |
| **Parcial** | Tabela ausente; competência faltante; mês com base menor que o normal | Recusar ou pedir esclarecimento nas perguntas da tabela ausente; não calcular percentual com janela incompleta | Sete tabelas presentes, 48 meses sem lacuna, nenhum mês abaixo de 80% da mediana de linhas. Sem data de corte, não dá para provar que o último mês está fechado. |
| **Misto** | Tabelas de execuções diferentes | Não cruzar números de tabelas sem o mesmo `batch_ref` | As reconciliações exatas sugerem uma única execução, mas não provam; depende do manifesto completo. |
| **Desatualizado** | Lote anterior ao último `CONCLUIDO` | Declarar a data do lote em cada resposta | O manifesto já grava `data_processamento`, derivada do `processado_em` da última execução `CONCLUIDO` em `controle_gold`, e `data_exportacao_csv`. A carga e a GenAI ainda precisam usar essas datas para comparar com o último `CONCLUIDO` e declarar a data do lote. |
| **Vazio** | Tabela com zero linhas | `no_evidence`, nunca zero | Nenhuma tabela vazia. |
| **Indisponível** | Banco local sem carga ou fora do ar | Erro recuperável, sem cair na fonte demonstrativa | Carga e reconciliação com o banco do Backend ainda em aberto (ver e). |
| **Valor de reserva** | `SINTETICO_DEV`/`LOTE_DEV` no controle | A carga deve recusar o lote | Coberto na origem: o exportador da `develop` exige ambiente `prod` e não tem mais fallback para lote de reserva. Pelo manifesto, falta ainda o `status_gold` para a carga conferir a execução. |

## (e) Perguntas abertas para Dados e Backend

Estado depois da resposta de Dados no PR #60.

**Fechadas:**

- universo de UCs;
- classe da UC no tempo (cadastro atual, sem histórico);
- bairro (duplicação corrigida no lote reanalisado);
- estornos (nenhum na Silver publicada);
- controles C01 a C12 (recalculados e aprovados por Dados; ver g).

**Respondidas** (registradas em [Premissas e definições registradas por Dados](#premissas-e-definições-registradas-por-dados)):

- as duas médias de consumo;
- quando `variacao_pct` fica nula;
- denominador do DEC/FEC.

**Abertas:**

- manifesto ainda parcial: falta gravar o `status_gold` (sugestão para Dados, com a Bia). Exigência de `prod`, remoção do lote de reserva e leitura da última execução `CONCLUIDO` já estão no exportador da `develop` (commit `ca73db5`);
- conferência do C13 por Dados;
- eventos recentes por UC: interrupções, chamados e satisfação só existem como totais acumulados, sem mês;
- `faturas_uc`, `medidor_uc`, energia estimada e escore da fila, exigidos pelo case;
- congelar os nomes de colunas `possui_gd`, `subgrupo`, `DEC` e `FEC` e atualizar o `dictionary_gold.toml` e o `docs/data-dictionary.md`. No PostgreSQL, uma coluna criada como `"DEC"` não casa com `dec`;
- identificador do lote: se faltar `run_id_gold` no controle, o notebook de exportação gera um identificador manual (`batch_<usuário>_<data e hora>`) em vez de falhar. Sugestão para Dados: falhar nesse caso ou registrar no manifesto que a origem do identificador é manual;
- carga e reconciliação Databricks → CSV → banco (DE-06): esquema, contagens, chaves e agregados em cada passo;
- aplicar, na próxima execução da Gold, o tratamento como nulo de `data_ligacao` anterior a 1950 (sugestão de Dados, sem coluna nova); até lá, o lote traz o valor original. Responsável: Dados.

## (f) Situação dos itens do cartão GENAI-02

Texto dos itens copiado do checklist do cartão GENAI-02 no quadro "GenAI — Gold real", lido em 27/10/2026. Nenhum item está concluído. "Preparado neste relatório" significa que este documento entrega a base do item; a conclusão ainda depende de revisão e aprovação.

| Checklist | Item | Situação | Evidência neste documento | Quem precisa agir |
| --- | --- | --- | --- | --- |
| Implementação e validação | Conferir schema, tipos, chaves, grão, contagens, nulos, períodos disponíveis e regras de qualidade no ambiente autorizado. | parcial | (a); (c) | Dados: confirmar o ambiente autorizado e as regras de qualidade. A conferência foi feita sobre os CSVs em máquina local, não no Databricks nem no banco do Backend. |
| Implementação e validação | Validar as tabelas candidatas do dicionário v1 contra a versão final, incluindo fontes de receita, consumo, continuidade, GD e atendimento. | parcial | (b); (c), tabela de divergências com o `dictionary_gold.toml` | Dados: congelar nomes e publicar o dicionário Gold (DE-08). GenAI: atualizar o catálogo (GENAI-03). Atendimento só tem totais por UC, sem mês. |
| Implementação e validação | Conferir identificação do lote e agregados entre origem Gold, processo de carga, banco autorizado do Backend e fonte do portal; testar recarga sem duplicar resultados, sem fixar fornecedor da fonte no contrato. | pendente | "O que foi conferido e o que não foi"; "Lote reanalisado" | Dados: completar o manifesto do lote. Backend: carga idempotente e banco com as sete tabelas. Só foram conferidos agregados entre os próprios CSVs. |
| Implementação e validação | Registrar cobertura por domínio obrigatório e solicitar complemento de Gold quando faltar fonte ou granularidade; não preencher com demonstração. | preparado neste relatório | (b); (e) | Dados: responder às perguntas abertas. GenAI: enviar a solicitação formal de complemento. |
| Implementação e validação | Distinguir lote parcial, misto, desatualizado, vazio e indisponível; definir o que bloqueia uma resposta confiável. | preparado neste relatório | (d) | Backend e GenAI: acordar o comportamento do executor e os estados do contrato. Sem manifesto completo, "misto" e "desatualizado" não são verificáveis. |
| Implementação e validação | Preparar consultas de controle independentes e exemplos sanitizados para a primeira fatia de integração. | parcial | (g) | Dados (Júlia) recalculou C01 a C12 de forma independente no Databricks e os aprovou como referência. Falta a conferência do C13 e os exemplos sanitizados. |
| Robustez e evidência de integração | Versionar manifesto com fonte, esquema, lote, horário, contagens, janelas e estado de qualidade/reconciliação; testar carga parcial, repetida e troca de lote sem duplicar fatos ou misturar versões. | pendente | "O que foi conferido e o que não foi"; (d) | Dados: completar o manifesto. Backend: testes de carga parcial, repetida e troca de lote. |
| Robustez e evidência de integração | Conferir chaves, unicidade, cardinalidades, dimensão historizada e regras de sentinelas, estornos/estimativas que afetem as métricas; registrar regra aprovada e seu impacto no dicionário. | parcial | (a), chaves; (c); premissas de Dados (classe sem histórico, data de ligação inválida, estornos) | Dados: registrar as regras no dicionário. |
| Robustez e evidência de integração | Aprovar ao menos um controle independente por domínio e recorte relevante, incluindo zero, nulo, ausência e período parcial; guardar somente controles e evidências autorizados, com tolerância justificada. | parcial | (g): C01 a C12 aprovados por Dados, com zero (C07), nulo (C10) e período parcial (C09) | Dados (Júlia) aprovou C01 a C12 com tolerâncias definidas por Dados. GenAI: transformar em fixture a partir da referência de Dados, sem gravar valores no repositório. Faltam a conferência do C13 e um controle de ausência por domínio (ex.: atendimento por mês). |
| Robustez e evidência de integração | Definir prontidão por capacidade: tabela ou período ausente impede liberar a métrica afetada. Entregar versões e compatibilidade a GENAI-03/06/13; uma migração incompatível precisa de diagnóstico e plano de retorno. | parcial | (b), matriz por pergunta; (d) | GenAI: transformar a matriz em prontidão versionada por capacidade. Backend: depende do `batch_ref`. Ainda não há versão de catálogo nem de lote para entregar. |

## (g) Controles do lote

Controles agregados que `scripts/gold_coverage.py` calcula a partir dos CSVs (seção "Controles candidatos" da saída). Nenhum identifica UC, alimentador, bairro ou pessoa. **Os valores não são publicados aqui; ficam com Dados.**

- **C01 a C12: aprovados.** Dados (Júlia) recalculou C01 a C12 de forma independente no Databricks e os aprovou como referência para a Gold oficial, com tolerâncias definidas por Dados. O script serve apenas de conferência cruzada.
- **C13: candidato.** O C12 compara totais por competência, e um bairro duplicado por grafia não altera esses totais; por isso o C12 não detecta duplicidade de bairro. O C13 foi acrescentado para esse caso e ainda precisa da conferência de Dados.

| ID | O que verifica | Tabela e colunas | Janela | Como se calcula |
| --- | --- | --- | --- | --- |
| C01 | Total de energia faturada e de receita faturada no lote | `diagnostico_receita`: `consumo_total_kwh`, `receita_total_reais` | todas as competências | Soma das duas colunas em todas as linhas. |
| C02 | Energia e receita faturadas por classe | `diagnostico_receita`: `classe_consumo`, `consumo_total_kwh`, `receita_total_reais` | todas as competências | Soma das duas colunas agrupada por `classe_consumo`. |
| C03 | UC-meses com fatura e leitura (linhas da série mensal) | `consumo_mensal_uc`: contagem de (`id_uc`, `competencia`) | todas as competências | Contagem de pares distintos (`id_uc`, `competencia`). |
| C04 | Energia e receita no último mês do lote, no município de maior receita (escolha deste relatório) | `diagnostico_receita`: `competencia`, `municipio`, `consumo_total_kwh`, `receita_total_reais` | última competência | Na última competência, soma por `municipio`; reporta o município de maior receita e seus totais. |
| C05 | UCs por classe | `visao_360_uc`: contagem de `id_uc` por `classe` | cadastro atual, sem competência | Contagem de `id_uc` agrupada por `classe`. |
| C06 | UCs por faixa de prioridade da fila | `fila_inspecao`: contagem de `id_uc` por `prioridade_inspecao` | cadastro atual, sem competência | Contagem de `id_uc` agrupada por `prioridade_inspecao`. |
| C07 | Caso de zero: UCs na faixa `ALTA - CONSUMO ZERO` | `fila_inspecao`: `prioridade_inspecao` | cadastro atual, sem competência | Contagem de `id_uc` com essa faixa. Se a faixa estiver vazia, a resposta esperada é "nenhuma UC nesta faixa", não ausência de evidência. |
| C08 | UCs com GD e queda de consumo acima de 30%, em Olinda e no total | `variacao_consumo_uc`: `municipio`, `possui_gd = Sim`, `queda_consumo_superior_30_pct = true` | P1 e P2 da Gold | Contagem de `id_uc` com as duas condições, no total e no município. |
| C09 | Caso de período parcial: UCs sem leitura em P1, em P2 ou nos dois | `variacao_consumo_uc`: `meses_com_leitura_p1`, `meses_com_leitura_p2`, `variacao_pct` | P1 e P2 | Contagem de `id_uc` sem leitura só em P1, só em P2 e nos dois, e de `variacao_pct` nula. |
| C10 | Caso de nulo: UCs sem média de consumo histórico e quantas delas faltam na série mensal | `visao_360_uc`: `media_consumo_historico`; `consumo_mensal_uc`: `id_uc` | cadastro atual | Contagem de `id_uc` com média nula e, dessas, quantas não têm mês em `consumo_mensal_uc`. Não compara os valores das duas médias. |
| C11 | O alimentador de maior DEC na última competência: DEC e FEC do mês e média simples dos 48 meses (identificador omitido) | `indicadores_dec_fec`: `id_alimentador`, `competencia`, `DEC`, `FEC` | última competência; média de todas as competências | Escolhe o alimentador de maior `DEC` no mês e calcula a média simples mensal de `DEC` e `FEC` dele, só com meses contínuos. A média simples entre meses serve só como controle, não é métrica aprovada. |
| C12 | Competências em que bairro e diagnóstico divergem em kWh, R$ ou UC-meses | `consumo_receita_bairro`, `diagnostico_receita`: `competencia`, consumo, receita, `qtd_ucs_distintas_faturadas_no_mes` | todas as competências | Soma por competência nas duas tabelas e contagem das competências com diferença. Não detecta bairro duplicado (ver C13). |
| C13 | Linhas e bairros distintos de `consumo_receita_bairro`; detecta duplicidade de bairro | `consumo_receita_bairro`: `competencia`, `municipio`, `bairro`, `classe_consumo` | todas as competências | Conta as linhas e os pares distintos município × bairro, antes e depois de normalizar a grafia (acentos, caixa, espaços e texto UTF-8 lido como latin-1). Menos pares depois da normalização indica bairro duplicado por grafia; a saída marca `possivel_duplicidade_de_bairro`. Não detecta grafias que perderam caracteres (por exemplo, trocados por `?`). |
