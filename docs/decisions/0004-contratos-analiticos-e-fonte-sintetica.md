# ADR-0004 — Contratos analíticos independentes da fonte física

**Data:** 2026-10-20
**Estado:** aprovada pelo desenho DEV-01 em conversa; implementação e verificação nesta branch.
**IDs do PRD afetados:** preparação para WEB-01 a WEB-07 e IA-01 a IA-06.

## Contexto

O desenvolvimento das jornadas precisa avançar antes da definição física da Gold. Existem rotas FastAPI, envelopes conceituais, cliente HTTP e cache, mas as leituras analíticas devolvem zeros/listas vazias sem demonstrar uma consulta integrada. Há contratos separados já implementados para ordens operacionais e perguntas/insights de IA.

## Opções consideradas

1. Simular respostas somente no navegador: simples, mas não exercita API, validação e acesso aos dados.
2. Semear tabelas analíticas agora: exercita o banco, mas antecipa colunas e grãos ainda não validados na Gold.
3. Fonte sintética em memória atrás de uma interface de leitura, com contratos HTTP tipados: exercita o caminho completo e deixa a adaptação física para uma implementação futura.

## Decisão

Adotar a opção 3 conforme [desenho](../design/2026-10-20-dev01-design.md) e [plano](../plans/2026-10-20-dev01-plan.md). As rotas analíticas dependem de serviços e de uma interface de leitura injetável. A fonte inicial contém somente registros artificiais determinísticos e relacionados; o modo sintético exige configuração explícita e nunca funciona como fallback de uma Gold ausente.

Versionar o contrato público de leitura e incluir período, filtros efetivos, origem/versão, atualização e limitações. Definir unidade e disponibilidade por métrica e seção para distinguir zero, ausência, cobertura parcial e indisponibilidade. A fonte física não aparece como nome de tabela escolhido pelo navegador.

Uma rota somente de desenvolvimento exercita o contrato através do transporte e cache existentes. As páginas do produto, a persistência operacional e os contratos de IA são preservados. Não são criadas migrações nesta etapa.

## Consequências e verificação

- A futura integração Gold implementa a interface de leitura e reconcilia conceitos; substituição de adaptador não dispensa revisão de semântica.
- Os schemas de consumo e fórmulas demonstrativas não definem o esquema real do dataset nem concluem DE-08.
- Serviços/fixtures devem reconciliar detalhe e agregado e declarar lacunas, sem usar constantes independentes para cada tela.
- Testes HTTP e de interface mais uma execução real frontend/API verificam o contrato; dados artificiais não comprovam números de negócio reais.
- O catálogo de contratos, guias e Registro de progresso do PRD acompanham a implementação. Os requisitos WEB/IA continuam pendentes do aceite com Gold.

## Referências

[PRD](../PRD.md), [arquitetura frontend](../architecture/frontend.md), [backend](../services/backend.md), [IA](../services/ai-agent.md) e [dicionário](../dicionario_gold.md).
