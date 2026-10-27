# ADR-0016 — Priorização de melhorias pré-Gold

**Data:** 2026-10-27
**Estado:** aprovada para o escopo da Fase 1, por solicitação da pessoa usuária
**IDs do PRD afetados:** WEB-03, IA-01, IA-03, IA-04, IA-05, IA-06; preparação técnica relacionada a FE-010, FE-015, FE-017, FE-018, BE-009, BE-012, BE-013 e TR-001.

## Contexto

A auditoria arquitetural de Backend e Frontend registrou 49 observações (20 BE, 22 FE e 7 TR), além de 34 itens de rastreabilidade L-01–L-34. A integração Gold ainda depende de definições e acessos reais. A pessoa usuária delimitou esta execução a oito IDs: FE-010, FE-015, FE-017, FE-018, BE-012, BE-013, BE-009 e TR-001.

As melhorias selecionadas reduzem risco imediato e têm baixo retrabalho: validação de contratos, acessibilidade, isolamento dos testes e consistência do transporte. A modularização de fronteiras que dependem de contratos e semântica Gold reais pode se beneficiar da redução dessa incerteza. O adiamento dos demais itens é uma escolha de prioridade e escopo; não significa que cada observação dependa tecnicamente da Gold. A auditoria completa permanece preservada para revisão posterior.

## Opções consideradas

1. **Executar as 49 observações agora.** Ampliaria a cobertura de refatoração, mas aumentaria o escopo antes de estarem definidos contratos e limites reais, com risco de retrabalho nas modularizações amplas.
2. **Executar somente as oito melhorias delimitadas e manter o restante para reavaliação.** Entrega benefícios de validação, acessibilidade, isolamento e transporte com mudança pequena; mantém visível o backlog e permite reordená-lo quando houver prioridade e evidência.

## Decisão

Adotar a opção 2. Na Fase 1 pré-Gold, implementar somente FE-010, FE-015, FE-017, FE-018, BE-012, BE-013, BE-009 e TR-001. Preservar a arquitetura feature-based, os contratos públicos, os cálculos e os controles existentes. A decisão não cancela nem aprova automaticamente cada observação futura; o plano de execução lista os 41 itens adiados e identifica hipóteses e oportunidades condicionais como itens a validar ou avaliar.

TR-001 corrige a documentação do estado da ADR-0002: aprovada em 25/10/2026 com base nos comentários de concordância de Backend e Engenharia de Dados no PR #54, sem aprovação formal no GitHub. Conforme a ADR-0002, o Backend é o único executor SQL da Gold local e coordena planejar → executar → sintetizar. Essa decisão arquitetural não implementa nem autoriza adaptador, credencial ou consulta Gold real. P-04, DE-06, DE-08, catálogo, autorização e prazos continuam dependências para a implementação.

WEB-03 e IA-01/03/04/05/06 são relacionados como preparação e contexto de integração, sem alteração de estado funcional ou de critério de aceite no PRD. FE-010 atende uma inconsistência de paginação e se sobrepõe parcialmente à observação TR-003; essa correção isolada não conclui TR-003 nem comprova o smoke automatizado integrado TR-004.

## Consequências e verificação

- A auditoria integral original permanece disponível, incluindo achados, evidências, recomendações e rastreabilidade. O plano desta execução separa claramente a auditoria da Fase 1 reduzida.
- A reavaliação do backlog ocorre após a integração Backend + Gold ou quando prioridade/dados disponíveis justificarem antecipá-la. Cada item será revalidado contra os contratos e evidências então vigentes.
- A ADR-0002 continua sem autorizar acesso real: P-04, DE-06, DE-08, catálogo, autorização individual, execução e auditoria durável permanecem necessários.
- T1/T2/T3 foram revisadas pelo agente principal sem achado impeditivo; a revisão documental T4 foi aprovada pelo agente principal em 27/10/2026. A evidência permanente, com diretórios, comandos, resultados e limites, está na seção [Verificações reproduzíveis do plano](../plans/2026-10-27-melhorias-pre-gold-fase1.md#verificações-reproduzíveis). A suíte frontend sequencial passou: 281 testes em 34 arquivos. Uma tentativa anterior com dois workers teve 1 timeout de 5 s; a execução isolada passou e a suíte sequencial passou sem mudança de código, teste ou timeout, mas a causa da diferença permanece indeterminada. `work/refactor-pre-gold/review.md` e os relatórios T1/T2/T3 são artefatos auxiliares locais. A documentação de TR-001 e a revisão documental ficam registradas no PRD e no plano permanente.
- As verificações desta entrega documental incluem validação de links locais alterados e `git diff --check`. Testes de código não fazem parte de T4. As verificações reportadas pelos executores usaram Python 3.11 local, enquanto CI tem alvo Python 3.12; quatro testes de backend foram ignorados por não haver PostgreSQL descartável configurado, portanto essa fronteira não foi validada.
- A sincronização do Trello está pendente: a leitura do quadro obrigatório retornou recurso não encontrado ou sem acesso; nenhuma escrita foi realizada.
