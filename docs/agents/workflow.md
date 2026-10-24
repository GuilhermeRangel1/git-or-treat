# Fluxo de desenvolvimento e qualidade

Este procedimento vale para humanos e agentes. O [PRD](../PRD.md) é a fonte de verdade dos IDs, estados e critérios. A preparação documental deste repositório não conclui histórias funcionais.

## 1. Selecionar trabalho

1. Escolha um ou poucos IDs do PRD e leia o guia do serviço afetado.
2. Confirme dados, contratos e decisões necessárias. Se faltar o dataset ou uma definição material, registre `Bloqueado` ou formule hipótese explícita; não fabrique campo/métrica.
3. Faça fatias demonstráveis. Uma fatia de receita, por exemplo, percorre Gold → API → tela → reconciliação antes de ser dada como pronta.
4. Se usar `to-tickets`, mantenha IDs do PRD em cada ticket e registre arestas de bloqueio reais. O Trello acompanha os requisitos obrigatórios; use tickets locais em `.scratch/` para decomposição técnica, conforme `issue-tracker.md`.

## 2. Planejar verificação antes de implementar

Para cada ID, identifique: resultado visível, dado necessário, caso normal, ausência/erro, cálculo manual de controle, teste automatizado apropriado, comando de qualidade e documentação que mudará. Quando o critério mencionar número, determine tolerância de arredondamento e granularidade. Não aceite teste que apenas confirma um mock ou reproduz a mesma fórmula sem fonte independente.

## 3. Executar e testar

- Engenharia: teste de perfil, transformação, integridade e reconciliação de contagens/somas; comprovação de Job e reexecução.
- Backend: teste de contrato, filtros, erro, paginação e transições das ordens; amostra consultada diretamente no banco.
- Frontend: teste de interação, estados vazio/erro/carregamento, acessibilidade e jornada manual com API real.
- IA: conjunto de perguntas em português, resposta numérica contra Gold, recusa para perguntas impossíveis e bloqueio de escrita/escopo indevido.
- Diagnóstico: contas que fecham com Gold, revisão das hipóteses e rastreio da recomendação à evidência.

O hook `quality-gate` pode verificar automaticamente comandos existentes, mas não comprova sozinho a regra de negócio. Registre resultado dos testes manuais e quantitativos também.

## 4. Atualizar o PRD na mesma entrega

Atualize a célula `Estado` na tabela do ID e adicione uma entrada no `Registro de progresso` do PRD com: mudança observável, arquivos/commit/PR, dados e versão, comandos/resultados, reconciliação/amostra, pendências e revisor. Use `Em validação` quando há implementação sem prova suficiente. Use `Bloqueado` com causa e desbloqueio necessário. `Concluído` exige todos os critérios do ID.

Quando a decisão altera arquitetura ou métrica, registre contexto, opções, escolha, consequências, data e estado de
validação. Para Engenharia de Dados, mantenha o registro consolidado em
`data-engineering/decisoes-tecnicas.md` e aponte para ele no índice `docs/decisions/README.md`; para os demais
módulos, crie ADR em `docs/decisions/`. Atualize PRD, dicionário e guias afetados. A decisão não deve ficar apenas
em chat.

Sincronize o cartão Trello de cada ID alterado, conforme `issue-tracker.md`. Atualize estado e evidência depois do PRD; marque como concluído apenas quando o estado canônico for `Concluído`.

## 5. Revisão de entrega

Antes de publicar ou apresentar: executar verificações de todos os módulos alterados, conferir ausência de segredos/dados brutos, validar links/README, reconciliar números da demo e diagnóstico, e confirmar a política de publicação do enunciado confidencial. Uma falha mantém o item aberto.
