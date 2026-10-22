# ADR-0007 — Consulta da UC em resumo e históricos independentes

**Data:** 2026-10-22

**Estado:** aprovada para a demonstração DEV-04 pela autorização de execução; definições Gold pendentes.

**ID do PRD afetado:** WEB-03.

## Contexto

A DEV-01 publica busca de UC e um detalhe com todos os registros sintéticos em listas. WEB-03 exige comparação por período e históricos potencialmente longos, incluindo ausência de fonte e mês sem leitura. O frontend da UC ainda está vazio. O dicionário Gold não contém esquema, cobertura nem chaves homologados.

## Opções consideradas

1. Acrescentar parâmetros e paginação diretamente ao detalhe 1.0.0. Isso mudaria arrays consumidos e confundiria totais da UC com a página exibida.
2. Buscar o detalhe inteiro e paginar/calcular no navegador. Isso manteria a resposta atual, mas transferiria regras de comparação para o frontend e escalaria mal com o histórico do case.
3. Preservar busca/detalhe 1.0.0 e criar overview de comparação e históricos paginados por seção. As respostas têm grãos e responsabilidades distintos, sem quebrar clientes existentes.

## Decisão

Adotar a opção 3 e o [contrato UC 1.1.0](../contracts/uc360-dev04.md), conforme [desenho](../design/2026-10-22-dev04-design.md) e [plano](../plans/2026-10-22-dev04-plan.md). O serviço calcula comparação e contagens a partir do universo filtrado, nunca da página histórica. O repositório declara cobertura por UC, fonte, medida e período ou snapshot antes de classificar uma lista vazia. Cada medida publica valor, estado e limitações próprios; um valor zero observado permanece distinto de lacuna ou indisponibilidade.

A URL guarda busca, UC, janela e página aplicadas; o formulário em edição fica local e consultas remotas usam TanStack Query. A tela mostra cadastro e fontes na mesma jornada. Competência de fatura, data de pagamento e vigência do medidor conservam seus relógios; GD em kW não se converte em energia compensada ou causa presumida de aumento.

## Consequências e verificação

- Dois endpoints novos da UC usam contrato 1.1.0; busca/detalhe DEV-01 seguem em 1.0.0. Frontend e backend revisam o mesmo contrato, com testes HTTP e de interação.
- A fonte sintética continua explícita e serve à demonstração. A Gold futura precisa provar chaves, cardinalidades, vigência, cobertura, autorização e reconciliação antes de WEB-03 ser concluído.
- Uma fonte individual indisponível não apaga cadastro e outras seções; a indisponibilidade global mantém resposta 503. Resumo e comparação não podem usar apenas a página retornada.
- O custo é maior número de requisições HTTP e validação de estado por seção. Esse custo permite paginação e recuperação localizada; verificar mudanças rápidas de UC/período e cancelamento de consultas na integração.
