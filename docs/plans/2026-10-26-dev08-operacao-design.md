# DEV-08 — Operação integrada ao protótipo

Estado: aprovado pela pessoa usuária em 26/10/2026. Requisitos WEB-06 e WEB-07; DE-05/Gold futura. A pessoa usuária escolheu ampliar o backend para fornecer indicadores consolidados e solicitou execução por subagentes GPT-6 Luna/high, com revisão do agente principal.

## Backend: consolidado demonstrativo

Adicionar `GET /api/v1/operations/summary`, com os mesmos filtros de período e alimentador, validação estrita e limite de 120 competências das consultas DEV-08. A resposta nova terá versão 1.2.0; os contratos atuais permanecem disponíveis.

O consolidado usa apenas alimentadores com estado `available` em toda a janela solicitada. DEC é a soma das durações originais em horas dividida pela soma dos denominadores desses alimentadores; FEC é a quantidade original de registros UC-interrupção dividida pela mesma base. Arredondar apenas o resultado final em três casas, preservando a regra demonstrativa existente. Não calcular média simples nem somar indicadores previamente arredondados.

Expor indicadores, numeradores, denominador incluído, população cadastral do recorte, população incluída, IDs incluídos/excluídos, janela solicitada/observada, definição, origem e limitações. Se há exclusões, os cards mostram explicitamente consolidado **parcial**, com sua base incluída. Sem alimentadores elegíveis, indicadores e denominador consolidado ficam nulos; sem alimentadores na fonte, apresentar estado vazio. Não inferir zero fora de cobertura. Zero é válido somente com base e cobertura conhecidas.

Amostra independente janeiro–fevereiro/2025: AL-01 contribui 3 h, 2 registros e denominador 2; AL-02 contribui 3 h, 1 registro e denominador 2. Consolidado: **DEC 1,5 h/UC**, **FEC 0,75 interrupções/UC**, **base incluída 4 UCs**. AL-03 permanece explicitamente excluído por denominador ausente. Filtrar AL-01 produz DEC 1,5 e FEC 1; filtrar AL-03 produz indisponibilidade.

Esta definição é provisória da aplicação e será registrada em ADR e no PRD após aprovação. Não valida a Gold nem conformidade regulatória.

## Frontend: layer 06

Referência: seção `249:12481`, visão geral clara `16:735`, escura `16:1989`, detalhe `16:850`, conteúdo do detalhe `16:909`, dados `212:5016`; referências mobile na mesma seção. Preservar o layout persistente, os tokens e componentes compartilhados existentes.

- Visão geral com aviso de demonstração, barra/modal de filtros, quatro cards (DEC, FEC, base incluída e cobertura), ranking selecionável por DEC/FEC, alimentadores excluídos identificados e acesso aos fundamentos.
- Filtros funcionais de competência inicial/final e alimentador. Usar apenas filtros suportados pelo contrato; os valores ilustrativos, comparação anual, classe e município do desenho não viram controles sem suporte.
- Abrir alimentador mantém período, ordenação e retorno na URL. Detalhe apresenta resumo, dois gráficos de barras mensais, dados textuais acessíveis, ocorrências paginadas e fórmula/base. Todos os alimentadores podem ser investigados, inclusive os sem denominador.
- Período, alimentador, métrica do ranking, detalhe e paginação na URL; rascunhos/modais locais; respostas validadas em execução e TanStack Query com chave completa e cancelamento.
- Estados distintos de carregamento, atualização, erro/repetição manual, vazio, parcial, indisponível e zero conhecido. Sem exibir respostas de outro recorte como atuais.
- Claro/escuro, teclado, Escape, retorno de foco, larguras estreitas/intermediárias/desktop e zoom. Séries mensais da API substituem os bimestres e números estáticos do Figma.

## Evidência de entrega

Executores Luna/high trabalham em arquivos separados após o contrato ficar definido; agente principal revisa a implementação e os critérios. Testes HTTP verificam consolidação independente, pesos distintos, exclusões, ausência e filtros; testes frontend verificam contrato e jornada. Executar gates backend/frontend e jornada real API → portal, comparar a amostra, conferir os dois temas e responsividade. Atualizar PRD e guias com resultados observados, mantendo aceite Gold pendente; sincronizar Trello se houver acesso.
