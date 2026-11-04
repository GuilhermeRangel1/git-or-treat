# ADR-0024 — Recuperação condicional e continuidade observada

**Data:** 03/11/2026. **Estado:** adotada para implementação; aceite integrado ainda em validação. **Requisitos relacionados:** WEB-04, WEB-06, WEB-10, IA-01, IA-03 e IA-06.

## Contexto

A Gold v2 contém uma estimativa por UC candidata, condicionada à confirmação da irregularidade, com intervalo nominal de 90% validado temporalmente. O portal ainda tratava todas as UCs como sem estimativa. Já DEC/FEC por alimentador existem, mas a cobertura do recorte consultado permanece `NAO_CERTIFICADA`; o bloqueio universal do Assistente impedia consultar os valores observados sem que uma nova carga de dados fosse executada.

## Decisão

1. Inspeções pode apresentar a estimativa publicada pela Gold somente quando status, método, validação temporal, faixa e valores atenderem ao contrato conhecido. A mensagem sempre a qualifica como estimativa se a irregularidade se confirmar. Ausência ou metadado inválido continua indisponível; zero permanece zero. A declaração `aceite_web04` do pacote não é reescrita nem promovida pelo consumidor.
2. O Assistente pode consultar DEC/FEC como `observed_uncertified` somente para um alimentador explícito e meses completos presentes na mesma publicação, quando a única falha de prontidão for cobertura não certificada e os controles, denominadores e autorização forem válidos. Resposta, evidência e auditoria preservam a limitação: “Valores observados; cobertura do alimentador não certificada.”
3. Esta política não certifica a cobertura, não afirma fechamento/regulação, não cria meses ou valores ausentes e não amplia o catálogo/permissões. Ausência de linha, denominador inválido, controle reprovado, lote divergente ou outra razão de prontidão continua bloqueando.
4. A estimativa de energia não é somada nem calculada no portal a partir da variação de consumo. Os valores e limites são apresentados por UC, sem prometer recuperação efetiva.

## Alternativas consideradas

- Manter o bloqueio integral até declaração e nova publicação de Dados: descartada para a leitura delimitada escolhida pela pessoa usuária; continua sendo necessária para chamar a cobertura de certificada.
- Remover/alterar `NAO_CERTIFICADA` ou dispensar prontidão global: rejeitada por quebrar a semântica de governança.
- Derivar recuperação da queda de consumo ou da média histórica: rejeitada por não ser a estimativa publicada nem uma previsão validada por UC.

## Consequências e validação

O contrato entre Backend e GenAI distingue prontidão certificada de elegibilidade observacional, e a camada pública fixa o aviso mesmo que o modelo o omita. O portal mostra a estimativa Gold com condição e faixa nominal. Nenhuma migração, escrita na Gold, nova exportação ou job de Dados é necessária. A decisão não conclui WEB-04, WEB-10 ou IA-01/03/06: cada critério integrado ainda depende das evidências registradas no [PRD](../PRD.md#14-registro-de-progresso) e no plano de entrega em `plans/2026-11-03-inspecoes-recuperacao-continuidade-observada.md`.
