# Diagnóstico da variação de receita

**Estado:** versão completa para a entrega de Dados. A decomposição foi reproduzida na Gold `GOLD_20261103T173853Z_76c37784` (Silver `20261103T171539Z_12682bfc`) e aberta por classe, município e bairro (seção 6). **Requisito:** ENT-01. **Método e aceite:** [guia do diagnóstico](services/revenue-diagnosis.md).

Todos os valores deste documento são percentuais do faturamento da primeira janela. Não há valores em R$ nem contagens de registros.

## 1. Resumo executivo

- Nos 12 meses finais (jul/2025 a jun/2026) o faturamento ficou **7,97% acima** do primeiro ano da base (jul/2022 a jun/2023). O "subiu só 8%" do case se reproduz.
- O **preço efetivo observado** contribuiu com **+10,81%**, próximo do reajuste homologado de 10,5%. Isso é preço efetivo calculado a partir das faturas, não tarifa homologada.
- O **volume** contribuiu com **−4,02%**, o que bate com a queda de "quase 4%" do case. É consumo medido, não energia faturada (ver seção 9).
- Os termos restantes (interação, faturas sem leitura, entradas e outros) fecham a conta sem resíduo.
- Leitura para a diretoria: o ganho de preço, de cerca de 11%, foi reduzido pela queda de volume (cerca de 4%) e pela interação (cerca de 0,7%), e por isso a receita subiu apenas cerca de 8%.
- Cerca de **1/5 (21,8%)** da alta total vem de faturas sem leitura na mesma UC/mês, e esse é o ponto que mais merece auditoria.
- **Confiança:** alta na aritmética (resíduo de reconciliação nulo); média na leitura de preço (não é tarifa); baixa para causas, porque a decomposição descreve o que mudou e não prova por quê.
- **Onde caiu o volume:** quase toda a queda está nas classes **comercial** (−8,87% do próprio faturamento base) e **residencial** (−5,11%). A industrial ficou estável (+0,14%). A queda aparece em todos os municípios, e **Recife** e **Jaboatão dos Guararapes** respondem juntos por cerca de 69% dela. Os 10 bairros de maior queda concentram 46,2%.
- **Só residencial:** a receita sobe +7,04%, o preço efetivo +10,95% e o volume cai −5,11%. Os 8% e os ~4% do case reproduzem no total de todas as classes.
- **Recomendação prioritária:** atacar a queda de volume em comercial e residencial, começando por Recife e Jaboatão dos Guararapes, e auditar as faturas sem leitura (seção 8).

## 2. Recorte e definições

- **Janelas:** P0 = 2022-07 a 2023-06; P1 = 2025-07 a 2026-06. Os meses são pareados pela posição na janela (1º mês de P0 com 1º mês de P1, e assim por diante).
- **Receita:** valor das faturas elegíveis, sem afirmar pagamento. Não é receita recebida.
- **Volume:** consumo medido nos mesmos pares UC/mês. A origem não traz energia faturada separada.
- **Preço efetivo observado:** receita dividida pelo consumo nos pares UC/mês. Não é tarifa homologada.
- **Base comum:** UCs com pelo menos 6 pares UC/mês válidos nas duas janelas. Ela cobre **96,3%** das UCs observadas.
- **Fora da base comum:** faturas sem leitura, UCs que entram ou saem, e outros casos.
- **Método:** `PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3`, na tabela `decomposicao_receita` ([dicionário](dicionario_gold.md)).
- **Recorte geográfico e de classe:** vem do cadastro atual, sem histórico.

## 3. Qualidade e cobertura

- Os números vêm de um run limpo do Job de seis tarefas (run `1070940765616595`), documentado em `data-engineering/evidencias/workflow/`.
- Consumo e faturamento têm cobertura **FECHADO** na janela, declarada na tarefa `Cobertura_Declaracao`. A tarefa confere que origem = aceitos + excluídos + quarentena e falha se não fechar.
- Atendimentos e ocorrências reconciliam entre Bronze e Silver (delta zero, gravadas + rejeitadas = origem, identidade origem = aceitos + quarentena), e têm **declaração de cobertura de extração** no total do domínio (`FECHADO`, natureza `EXTRACAO`). Por alimentador, a cobertura continua `NAO_CERTIFICADA`, pois exigiria evidência externa de fechamento. Esses domínios não entram na decomposição de receita.
- Em alguns recortes (município/bairro/classe) não há base comum. Eles ficam marcados como `SEM_BASE_COMUM` e fora da soma dos efeitos de preço e volume.

## 4. Reconciliação com os números do case

| Número do case | O que reproduzimos | Leitura |
| --- | --- | --- |
| Receita subiu cerca de 8% | +7,97% (diferença entre P1 e P0 igual à soma dos componentes) | Reproduz. |
| Volume caiu quase 4% | −4,02% (consumo medido na base comum) | Reproduz como consumo medido. A equivalência com energia faturada não é comprovada. |
| Reajuste de 10,5% | +10,81% de preço efetivo observado | Compatível, mas não prova que o reajuste causou a variação (mix, bandeiras e ajustes também entram). |
| Mesmos números só na classe residencial | Receita +7,04%, preço +10,95%, volume −5,11% | Os 8% e os ~4% do case reproduzem no total de todas as classes. Na residencial isolada o volume cai mais e a receita sobe menos. O preço residencial fica próximo dos 10,5%. |

## 5. Decomposição preço × volume

| Componente | % do faturamento de P0 |
| --- | --- |
| Preço efetivo observado | +10,81 |
| Volume | −4,02 |
| Interação (preço × volume) | −0,66 |
| Faturas sem leitura (fora da base) | +1,74 |
| Entradas de UCs | +0,42 |
| Saídas de UCs | 0,00 |
| Outros fora da base | −0,33 |
| **Variação total** | **+7,97** |
| Resíduo de reconciliação | 0,00 |

**Sensibilidade ao piso de pares.** Percentual de UCs que entram na base comum conforme o mínimo de pares: 3 pares, 97%; 6 pares, 96%; 9 pares, 86%; 12 pares, 12%. O piso de 6 foi escolhido porque mantém a cobertura estável sem aceitar poucos meses por UC.

## 6. Contribuição por segmento

Todos os valores são percentuais. Peso, preço, volume e sem leitura são % do faturamento de P0 do próprio recorte. A contribuição é em pontos percentuais do total (7,97). As contribuições somam o total nas duas aberturas.

### 6.1 Por classe de consumo

| Classe | Peso em P0 | Variação própria | Contribuição (p.p.) | Preço | Volume | Sem leitura |
| --- | --- | --- | --- | --- | --- | --- |
| Industrial | 34,94 | +8,36 | 2,92 | +6,52 | +0,14 | +1,78 |
| Residencial | 37,17 | +7,04 | 2,62 | +10,95 | −5,11 | +1,79 |
| Comercial | 24,89 | +6,81 | 1,70 | +15,77 | −8,87 | +1,40 |
| Poder público | 1,98 | +21,91 | 0,43 | +15,94 | +1,67 | +3,13 |
| Rural | 1,02 | +29,11 | 0,30 | +21,72 | +1,10 | +3,85 |

- A queda de volume está em **comercial** (≈ −2,2 p.p. do total) e **residencial** (≈ −1,9 p.p.). As outras três classes somam cerca de +0,1 p.p. (valores obtidos multiplicando peso por volume).
- O preço efetivo residencial (+10,95%) fica perto dos 10,5% do reajuste citado no case. O comercial (+15,77%) e o industrial (+6,52%) diferem, e o dataset não permite explicar isso (mix, outras tarifas, ajustes).
- Rural e poder público têm peso pequeno e variação alta. Com base pequena, não tire conclusões deles.

### 6.2 Por município

| Município | Peso em P0 | Variação própria | Contribuição (p.p.) | Preço | Volume | Sem leitura |
| --- | --- | --- | --- | --- | --- | --- |
| Recife | 39,77 | +7,78 | 3,09 | +10,89 | −4,29 | +1,30 |
| Olinda | 9,61 | +10,01 | 0,96 | +10,40 | −2,25 | +3,55 |
| Paulista | 8,62 | +9,69 | 0,84 | +10,96 | −3,17 | +1,51 |
| Jaboatão dos Guararapes | 16,89 | +4,84 | 0,82 | +10,88 | −6,45 | +0,93 |
| Cabo de Santo Agostinho | 6,02 | +8,74 | 0,53 | +10,78 | −3,01 | +1,08 |
| Camaragibe | 4,22 | +9,91 | 0,42 | +10,60 | −2,24 | +3,91 |
| São Lourenço da Mata | 3,22 | +9,61 | 0,31 | +10,80 | −2,43 | +0,73 |
| Ipojuca | 2,55 | +10,08 | 0,26 | +10,91 | −2,99 | +3,57 |
| Igarassu | 2,81 | +8,48 | 0,24 | +11,14 | −3,90 | +3,03 |
| Abreu e Lima | 2,11 | +10,47 | 0,22 | +11,57 | −3,10 | +2,63 |
| Moreno | 1,79 | +6,20 | 0,11 | +9,83 | −2,93 | +3,81 |
| Araçoiaba | 0,50 | +13,20 | 0,07 | +11,02 | −1,75 | +3,50 |
| Ilha de Itamaracá | 0,78 | +7,28 | 0,06 | +9,17 | −3,74 | +0,14 |
| Itapissuma | 1,12 | +4,82 | 0,05 | +10,45 | −3,53 | +1,65 |

- O preço efetivo é quase uniforme entre municípios (de +9,2% a +11,6%), o que sugere que a diferença de variação vem do **volume**.
- O volume cai em **todos** os municípios (de −1,75% a −6,45%). Não é um problema localizado.
- **Jaboatão dos Guararapes** tem a queda mais intensa (−6,45%) e a menor variação entre os grandes (+4,84%). **Recife** pesa mais em valor absoluto. Os dois juntos respondem por cerca de 69% da queda de volume (Recife ≈ 42%, Jaboatão ≈ 27%, calculado multiplicando peso por volume).
- O efeito de faturas sem leitura é mais alto em Camaragibe, Moreno, Ipojuca, Olinda e Araçoiaba (entre 3,5% e 3,9%) e menor em Jaboatão, São Lourenço da Mata e Ilha de Itamaracá.

### 6.3 Concentração por bairro

Os 10 bairros com maior queda de volume respondem por **46,2%** da queda total, e os 20 maiores por **56,2%** (somando só os bairros com efeito de volume negativo). A queda é espalhada, com concentração moderada. Nomes de bairro ficam fora do documento.

## 7. Hipóteses

| Hipótese | Dado necessário | Resultado | Veredito |
| --- | --- | --- | --- |
| A alta de preço vem do reajuste homologado | Tarifa homologada por classe e mês | O preço efetivo (+10,81%) é compatível com 10,5%, mas a tarifa não está no dataset | Indeterminada |
| A queda de volume está concentrada em classes ou regiões específicas | Decomposição por classe, município e bairro | Concentrada em comercial e residencial; industrial estável; presente em todos os municípios, com maior intensidade em Jaboatão dos Guararapes | Sustentada (descreve onde, não por quê) |
| A queda de volume vem de geração distribuída | Energia gerada ou compensada | Só há potência instalada, que não basta | Indeterminada |
| Faturas sem leitura inflam a receita | Faturas sem leitura por UC/mês | Componente de +1,74% e 21,8% da alta total | Sustentada como componente aritmético; causa indeterminada |
| Entrada de novas UCs explica a alta | Variação de entradas | +0,42%, pequena | Sustentada, com peso pequeno |
| Inadimplência explica a variação | Valor efetivamente recebido | A origem não traz valor pago | Não testável |
| Bandeiras tarifárias | Bandeira por mês e classe | Não testada | Indeterminada |
| Perdas não técnicas | Energia irregular estimada | A fila de inspeção prioriza e agora traz estimativa de kWh por UC, condicional à confirmação da irregularidade (validada em teste temporal), mas não mede a perda real | Indeterminada |
| Sazonalidade | Janelas de 12 meses completos | Ambas as janelas têm 12 meses, o que reduz o efeito sazonal | Atenuada |

## 8. Recomendações

Ordem de grandeza em % do faturamento de P0. Os ganhos se sobrepõem e **não** devem ser somados.

1. **Atacar a queda de volume em comercial e residencial.** Elas respondem por praticamente toda a queda (≈ −2,2 p.p. e ≈ −1,9 p.p. do total, contra cerca de +0,1 p.p. das demais classes). Priorizar Recife e Jaboatão dos Guararapes (cerca de 69% da queda) e os 10 bairros de maior queda (46%). Teto teórico: voltar ao volume do primeiro ano valeria cerca de 4% do faturamento de P0 (mais cerca de 0,7% de interação). É limite máximo, não previsão. Área: Comercial e Perdas. Indicador: consumo medido na base comparável, por classe e município. Pré-condição: investigar a causa (geração distribuída, desligamentos, migração de consumo), que os dados atuais não identificam.
2. **Auditar as faturas sem leitura.** Elas respondem por +1,74% da base e pesam mais em rural (3,85%), poder público (3,13%) e em Camaragibe, Moreno, Ipojuca e Olinda (entre 3,5% e 3,9%). Se forem estimativas depois regularizadas, esse valor pode ser revertido. Área: Medição. Indicador: percentual de UC/mês faturadas sem leitura.
3. **Usar a fila de inspeção para perdas não técnicas.** A ordem de prioridade e o motivo já existem. Para as UCs com pelo menos 6 meses de consumo, a Gold publica uma **estimativa de energia a recuperar por UC, condicional à confirmação da irregularidade**: cerca de 3,9 vezes o consumo médio mensal dos 12 meses anteriores, com faixa de 90% (aproximadamente 1,8 a 7,0 vezes). Ela passou na validação temporal (ganho de erro sobre a média das confirmadas acima de 50%, cobertura da faixa acima de 90% e viés abaixo de 15% da média) e **não é probabilidade de fraude nem garantia de recuperação**. As demais UCs mostram só a referência histórica. Ainda não há base para quantificar o benefício total: falta a taxa de confirmação por perfil de UC.
4. **Fechar lacunas de dados:** valor efetivamente recebido, energia faturada separada do consumo medido e tarifa homologada por mês. Sem elas, as hipóteses de preço e inadimplência continuam indeterminadas.

## 9. Limitações

- Preço efetivo observado não é tarifa homologada, e a decomposição não prova causalidade.
- O consumo medido não é energia faturada. O case fala em energia faturada, e essa equivalência não foi comprovada.
- Receita aqui é faturada, não recebida.
- O recorte de município, bairro e classe usa o cadastro atual, sem histórico.
- Os percentuais do resumo somam todas as classes da tabela. O recorte residencial está na seção 6.1 e difere do total (receita +7,04%, volume −5,11%).
- A decomposição é um método candidato, sem homologação tarifária.
- Atendimentos e ocorrências têm cobertura de extração `FECHADO` no total do domínio, mas **não** por alimentador (`NAO_CERTIFICADA`), e não entram nesta análise.
- A estimativa de energia a recuperar é condicional à confirmação da irregularidade e foi validada em um único corte temporal.
- Classes de baixo peso (rural e poder público) e municípios pequenos têm base reduzida.

## 10. Reprodução

O [roteiro de demonstração](demo-roteiro.md) indica como apresentar o diagnóstico e conferir o recorte no portal. Para carregar a Gold v2 usada pela aplicação, siga o [guia de execução](../README.md#executar-localmente-com-docker).

- **Tabela:** `decomposicao_receita`, na Gold `GOLD_20261103T173853Z_76c37784`.
- **Método:** `Silver_to_gold.ipynb`, com `MIN_PARES_PRECO_VOLUME=6`.
- **Controles:** roteiros `validacao_gold_v4` e `validacao_silver_v1`, executados depois do run limpo, sem falhas.
- Os valores em R$ e as contagens ficam no ambiente de Dados.
