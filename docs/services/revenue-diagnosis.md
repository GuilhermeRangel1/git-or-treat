# Entregável: diagnóstico da variação de receita

**Escopo:** ENT-01 e ENT-02 do [PRD](../PRD.md). **Estado:** perguntas e método definidos; análise bloqueada até receber o dataset e Gold validada.

## Pergunta executiva

Explicar por que a receita residencial ficou cerca de 8% abaixo do primeiro ano da base nos 12 meses finais, apesar de reajuste tarifário homologado acumulado de 10,5% desde meados de 2022 e queda de quase 4% no volume de energia faturada. Os três percentuais são do enunciado; devem ser reconciliados antes de entrarem como achado final.

Separar quatro perguntas: (1) o valor da queda se reproduz no dataset? (2) quanto da mudança aritmética se associa a volume e preço efetivo? (3) em quais recortes a contribuição é maior? (4) quais mecanismos têm evidência suficiente para justificar ação? Uma conta que fecha não prova a causa do comportamento do cliente.

## Método a executar

Para a exploração sintética DEV-03, o [contrato Receita 1.1.0](../contracts/revenue-dev03.md) e a [ADR-0006](../decisions/0006-exploracao-demonstrativa-receita.md) fixam comparação por competências extremas, cobertura explícita, base pequena e reconciliação. A exploração foi [verificada com API e tela reais](../plans/2026-10-21-dev03-evidence.md), usando exclusivamente fatos artificiais. Essa demonstração não executa o diagnóstico anual abaixo: suas janelas e definições continuam dependentes da inspeção Gold. Contribuições absolutas dos grupos são aditivas; efeitos recalculados com preços médios de cada grupo podem mudar por mix e não devem ser somados como se fossem os efeitos recalculados do agregado.

1. Definir exatamente as competências dos dois intervalos e a receita comparada (faturada, paga, líquida etc.). Verificar cobertura mensal e mudanças de população de UCs.
2. Reproduzir receita e energia residencial totais em Gold e conferir contra faturas tratadas, com contagem de registros excluídos e ajustes.
3. Decompor a variação em componente de volume, componente de preço efetivo/tarifa e termo de interação, por método documentado cuja soma feche com a diferença total.
4. Abrir por município, bairro, subgrupo/classe residencial, alimentador quando fizer sentido e tempo; distinguir contribuição absoluta da queda percentual.
5. Investigar hipóteses com dados disponíveis: bandeiras, geração distribuída, inadimplência/pagamento, composição de clientes, perda não técnica, anomalia de leitura, qualidade de serviço e sazonalidade. Não inferir causalidade de simples associação.
6. Formular recomendações ligadas a achados, com mecanismo, público alvo, esforço, ordem de grandeza do impacto e incerteza. Não apresentar recuperação como garantida.

### Decomposição candidata, a validar com o dado

Se o conceito de receita escolhido puder ser representado por `R = P × Q`, onde `Q` é energia faturada comparável e `P = R/Q` é preço médio efetivo, uma identidade possível é `ΔR = P₀ΔQ + Q₀ΔP + ΔPΔQ`. O termo de interação deve permanecer explícito ou ser distribuído por método documentado. Essa identidade **não** demonstra que o reajuste homologado causou `ΔP`; tributos, bandeiras, composição de clientes, ajustes e recebimento podem alterar o preço efetivo. Se `Q` não for comparável ou tiver base zero, escolher outro método e registrar o motivo.

Conferir tanto a diferença absoluta quanto a percentual, com mesma população/competências nos dois períodos. Ao decompor por bairro/município, registrar mudança de cadastro e classes, grupos que entram/saem da base, localização faltante e pequenos denominadores. A soma das contribuições por recorte deve fechar com o total elegível ou apresentar residual identificado.

### Registro de hipóteses

Para cada hipótese, manter uma linha com mecanismo proposto, dado que a tornaria observável, consulta/teste, valor encontrado, comparação/controle, limite e decisão `sustentada`, `não sustentada` ou `indeterminada`. GD requer série de energia gerada/compensada para atribuir abatimento quantitativo; potência instalada isolada não basta. Inadimplência pode explicar valor pago, não necessariamente valor faturado. Perdas não técnicas exigem evidência além de consumo anômalo. Continuidade e sazonalidade precisam de recorte temporal/geográfico coerente. Hipóteses não testáveis permanecem assim no documento final.

### Recomendações e impacto

Cada recomendação deve referir uma causa sustentada ou uma incerteza importante, indicar o mecanismo de melhoria, área responsável, população alcançável, esforço, pré-condição, indicador de acompanhamento e cálculo transparente da ordem de grandeza. Diferenciar impacto potencial de receita recuperada, custo evitado e melhoria de serviço; não somar ganhos que se sobrepõem. Apresentar intervalo ou cenário quando a evidência não sustentar ponto único.

## Estrutura do documento final

Resumo executivo; recorte e definições; qualidade/cobertura; reconciliação dos três números do case; decomposição; contribuições por segmento/geografia; hipóteses testadas e descartadas; principais causas sustentadas; recomendações priorizadas; estimativa de impacto; limitações e próximos dados necessários. Gráficos/tabelas podem ser inseridos posteriormente, mas a narrativa e as contas devem ser reproduzíveis em texto.

## Critério de aceite

Uma pessoa da diretoria consegue responder “quanto caiu, onde caiu, por quê, com que confiança e o que fazer primeiro?” A banca técnica consegue reproduzir totais, filtros e fórmula a partir do dicionário/Gold. Não declarar o diagnóstico concluído com apenas dashboard ou opinião.
