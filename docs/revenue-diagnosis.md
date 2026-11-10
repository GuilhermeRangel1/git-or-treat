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
| A queda de volume vem de geração distribuída | Data de conexão e consumo pareado; energia gerada/compensada para atribuição física | Investigação complementar de 05/11: forte associação temporal com conexão de GD; 92,68% das contribuições negativas do efeito-volume estão nos grupos com GD entre janelas/durante P1 (seção 11). Potência instalada isolada continua insuficiente | Associação sustentada; causalidade e energia compensada indeterminadas |
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

## 11. Investigação complementar — GD e redução de volume (05/11/2026)

**Pergunta:** qual mecanismo observável ajuda a explicar a redução de volume, além de localizar a sua contribuição?

**Fonte:** consulta somente leitura à mesma Gold v2 `GOLD_20261103T173853Z_76c37784`, usada pela API local, com `default_transaction_read_only=on` conferido e prazo de 15 s por consulta. Não foram alteradas tabelas, papéis ou dados. Script analítico local em `work/receita-investigacao/analyze.py`; sem exportação de linhas individuais. A análise abaixo não altera a fórmula V3 nem constitui aceite ENT-01.

### Método

1. Parear a mesma UC e a mesma posição mensal de P0 (jul/2022–jun/2023) e P1 (jul/2025–jun/2026), usando somente `receita_base_comparavel_reais` e `consumo_base_comparavel_kwh` não nulos nos dois extremos.
2. Exigir pelo menos seis pares e consumo somado positivo nas duas janelas. Somar R0, R1, Q0 e Q1 por UC e reconstruir o efeito-volume por `R0/Q0 × (Q1−Q0)` antes de agregar.
3. Associar cadastro atual (`visao_360_uc`) e registro de GD (`gd_uc`, chave única por UC). Separar conexão anterior a P0, entre o fim de P0 e o início de P1, durante P1 e vigência indeterminada. O grupo de comparação exige ausência de registro em `gd_uc` **e** cadastro negativo para GD; ausência de linha isolada não comprova ausência de geração.
4. Conferir a soma dos efeitos reconstruídos contra `decomposicao_receita.efeito_volume_reais`: **reconciliou com tolerância de R$ 0,01**, sem divulgar os valores monetários.
5. Comparar os grupos dentro de município/classe, exigindo ao menos cinco UCs em cada lado. Repetir a leitura residencial com pisos de três e nove pares para verificar sensibilidade.

### Resultados

Os percentuais de consumo abaixo são `(ΣQ1−ΣQ0)/ΣQ0` nos pares elegíveis de cada grupo. Diferem dos componentes monetários expressos em pontos percentuais de faturamento P0.

| Situação de GD | Variação de consumo medido residencial | Variação comercial |
| --- | --- | --- |
| Conectada entre as duas janelas | −68,83% | −69,03% |
| Conectada durante P1 | −41,19% | −38,46% |
| Sem registro de GD e com cadastro negativo | +2,18% | −1,93% |

- **92,68% das contribuições negativas do efeito-volume** da base pareada estão nos dois grupos de conexão de GD. O denominador é a soma das parcelas negativas, antes de compensar aumentos dos demais grupos; não é 92,68% de toda a receita nem uma medida de energia compensada.
- Nas comparações elegíveis dentro do mesmo município e classe, o grupo com conexão de GD teve variação inferior ao grupo sem registro/cadastro negativo em **100%** dos recortes comparados. A queda física dos grupos com GD nesses recortes variou de **51,99% a 69,09%**.
- A leitura residencial foi estável aos pisos de três/seis/nove pares: conexão entre janelas, de −68,83% a −68,89%; conexão durante P1, de −41,16% a −41,22%; grupo sem registro/cadastro negativo, crescimento de +2,14% a +2,18%.
- A parcela sem leitura tem contribuição positiva no faturamento: no lote local, +1,75 p.p. do faturamento P0 no total e +1,79 p.p. no residencial. Ela precisa de auditoria e não explica a redução do consumo pareado, porque meses sem base comparável não entraram nessa reconstrução.

### Interpretação comercial e limite causal

A explicação sustentada é mais específica que “o volume caiu”: **o ganho de preço foi parcialmente anulado pela redução de consumo medido concentrada em UCs que receberam conexão de GD entre as janelas ou durante a janela final**. No residencial, o grupo sem registro de GD e com cadastro negativo aumentou o consumo, enquanto os grupos conectados reduziram fortemente. Isso torna a adoção de GD a principal hipótese observável para aprofundar a explicação comercial, em vez de tratar a queda como retração uniforme de todos os clientes.

O mecanismo plausível é menor energia medida da rede após a conexão. Não foi medida a energia gerada/compensada e não foi construído contrafactual causal: seleção dos clientes que adotam GD, alteração de ocupação/atividade e outros fatores simultâneos ainda podem contribuir. Portanto, não afirmar que toda a redução foi causada por GD, que ela representa irregularidade ou que o volume seria recuperável por inspeção.

**Consequência prática:** separar a carteira com conexão de GD da carteira sem esse registro antes de planejar recuperação comercial/perdas. Investigar especialmente o residual comercial sem GD (−1,93% de consumo pareado) e, em paralelo, auditar faturamento sem leitura. Para quantificar o mecanismo de GD, obter energia gerada/injetada/compensada e validar a evolução antes/depois da conexão com controles adicionais.

## 12. Aprofundamento usando exclusivamente Gold — antes/depois da conexão (05/11/2026)

**Restrição confirmada pela pessoa usuária:** somente a Gold está acessível. O campo `energia_injetada_kwh_media_mensal` existe no contrato de origem/Silver, mas não está na Gold nem no banco local; não foi consultado, estimado ou preenchido. Esta etapa usa apenas `gd_uc`, `visao_360_uc`, `consumo_mensal_uc` e metadados de publicação da mesma Gold v2 da seção 11.

### Comparação temporal

- Selecionar datas de conexão válidas, sem flags de futuro/sentinela, com seis meses de horizonte observável de cada lado dentro da base. Excluir o mês da conexão, pois não há rateio diário que permita separar antes/depois nele.
- Para cada UC com GD, calcular consumo médio nos seis meses anteriores e nos seis posteriores; exigir pelo menos quatro competências válidas de cada lado, consumo anterior positivo e todas as leituras observadas válidas nos meses utilizados. Receita/fatura não é requisito deste teste físico; ele não substitui a população da decomposição financeira V3.
- Formar grupos por município, classe e mês da conexão, com pelo menos cinco UCs elegíveis com GD. Construir referência com UCs sem registro de GD e com cadastro negativo, na mesma localidade/classe e nos mesmos meses, também com quatro competências válidas por lado e pelo menos cinco UCs por grupo. Cada UC de referência precisa aparecer dos dois lados; não comparar populações diferentes de antes e depois.
- Ponderar a mudança da referência pelo consumo anterior do respectivo grupo com GD. Essa padronização compara os mesmos períodos e composição territorial/classe, mas não é pareamento individual por renda, tamanho, perfil de carga ou motivo de adesão.

| Classe | Consumo após conexão, ante os seis meses anteriores | Referência sem registro de GD, padronizada | Diferença descritiva |
| --- | --- | --- | --- |
| Residencial | −70,75% | −2,89% | −67,87 p.p. |
| Comercial | −71,39% | −6,31% | −65,08 p.p. |

**Antes da conexão:** entre os três primeiros e os três últimos meses da janela anterior, os futuros conectados cresceram +2,74% no residencial e +2,97% no comercial. As referências correspondentes cresceram +2,45% e +3,21%. Portanto, não se observou queda anterior de magnitude próxima à redução dos meses posteriores. Essa é uma conferência descritiva de tendência, sem teste estatístico de tendências paralelas.

### Cobertura e sensibilidade

A comparação com piso de quatro meses abrangeu **85,56% das conexões residenciais temporalmente elegíveis** e **37,98% das comerciais**. O denominador contém somente conexões com data válida e horizonte de seis meses disponível de cada lado; não são percentuais de todas as UCs com GD. As exclusões adicionais incluem poucos meses válidos e grupos pequenos sem referência suficiente. A leitura comercial tem representatividade mais limitada.

Exigindo pelo menos cinco competências válidas de cada lado, a queda observada ficou em **−70,63% no residencial** e **−71,59% no comercial**, contra **−2,60%** e **−6,79%** nas referências. A cobertura passou a 78,59% e 31,45% das conexões temporalmente elegíveis. A conclusão descritiva permaneceu estável, embora a amostra tenha diminuído.

### O que isso acrescenta ao diagnóstico

A Gold sustenta duas evidências complementares: a queda de volume entre as janelas se concentra nas UCs com conexão de GD (seção 11), e o consumo medido dessas UCs reduz fortemente **depois da conexão**, com evolução anterior semelhante à referência territorial/classe. O mecanismo de redução da energia medida da rede após adoção de GD é compatível com ambas.

Essa evidência é mais forte que comparar apenas “com GD” e “sem GD” em um mês. Ainda não mede geração/injeção/compensação e não isola todos os fatores simultâneos à adesão. Não chamar a diferença de efeito causal identificado, energia gerada ou volume recuperável por fiscalização. Cadastro/classe são atuais; observações mensais ausentes e seleção de clientes que adotam GD continuam possíveis fontes de viés.

**Reprodução e verificação:** script local `work/receita-investigacao/event_study.py`, com `MIN_EVENT_MONTHS=4` e `5`; execução somente leitura, sem exportar UCs ou valores absolutos, conferindo a propriedade de transação. A consulta monolítica inicial excedeu o prazo de 20 s e não produziu resultado aceito; o cálculo foi dividido em agregação dos conectados e leitura sequencial dos controles, processada em memória, sem alterar o banco ou ampliar o prazo por consulta. Os resultados acima são das duas execuções concluídas dessa versão. Não houve mudança de API, interface ou fórmula Gold nesta etapa.

## 13. Impacto na receita das UCs com GD (conferência de 04/11/2026)

**Pergunta:** o que a concentração da queda de volume em UCs com GD (seções 11 e 12) significa para a **receita**?

**Fonte e método:** consulta somente leitura à Gold `GOLD_20261103T173853Z_76c37784`, sem tabelas alteradas e sem divulgar R$ nem contagens. Usa a mesma base pareada da seção 11 (seis ou mais pares UC/mês nas duas janelas, consumo positivo nas duas pontas, somente `receita_base_comparavel_reais` e `consumo_base_comparavel_kwh` não nulos) e o **cadastro atual** (`possui_gd` de `visao_360_uc`), e não a data de conexão. Os percentuais são razões agregadas e por isso **não substituem** a decomposição da seção 5: a receita da base pareada sobe +7,37%, o volume cai −4,54% e o preço efetivo agregado sobe +12,47%.

| Grupo | Peso na receita de P0 | Volume | Receita | Preço efetivo | Contribuição à variação da receita |
| --- | --- | --- | --- | --- | --- |
| Sem GD no cadastro | 91,5% | +0,46% | +13,21% | +12,69% | +12,09 p.p. |
| Com GD no cadastro | 8,5% | −61,65% | −55,58% | +15,81% | −4,72 p.p. |

- **A receita das UCs com GD cai quase na mesma proporção do volume** (−55,58% contra −61,65%): a fatura é quase toda proporcional ao consumo medido, então a energia abatida vira receita não faturada. As UCs com GD reduziram a variação da receita em cerca de 4,7 p.p.; sem elas, a base pareada teria crescido cerca de 12%.
- **A receita total continua subindo** (+7,97% na decomposição): as UCs sem GD, ≈ 92% da receita, crescem tanto que compensam a perda.
- **Concentração (base pareada):** só 23,8% das UCs caíram; 9,4% caíram 30% ou mais e respondem por 89,3% da perda bruta de volume; a mediana por UC foi +3,2%. Quem subiu devolveu cerca de 35% da perda bruta.
- **Por classe e GD:** comercial sem GD −1,93% e com GD −61,51%; residencial sem GD +2,18% e com GD −61,74%, em linha com a seção 11. Industrial, poder público e rural não têm UCs com GD nesta base.
- **Tempo:** comparando o mesmo trimestre, o volume vem caindo gradualmente desde 2024, e não em degrau, o que combina com adesão crescente.

**Limites:** associação, não causa (não há energia gerada na Gold); "tem GD" é o cadastro atual e a seção 11 separa por data de conexão; o preço efetivo agregado inclui efeito de composição.

**Consequência prática:** a perda de receita por GD (≈ 4,7 p.p.) é da mesma ordem de grandeza do teto teórico de recuperação de volume da seção 8 (≈ 4%), e parte dela é geração legítima, que não se recupera. Medir o impacto por município e rever como a energia abatida é cobrada antes de planejar recuperação comercial.
