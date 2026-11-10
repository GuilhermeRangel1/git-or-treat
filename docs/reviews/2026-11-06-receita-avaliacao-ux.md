# Receita — avaliação da composição e argumentos para apresentação

**Data:** 06/11/2026. **Escopo:** avaliação da página atual, sem alteração de implementação. Referências: WEB-02, WEB-07, jornada comercial do PRD (§7.2) e apoio a ENT-01.

## Parecer

A organização atual é adequada ao propósito comercial: **entender a variação → localizar a contribuição negativa → examinar evidências → consultar o histórico se necessário**. A separação entre Resumo, Investigação e histórico sob demanda reduziu a concorrência de informações. A decisão de não repetir preço/volume em cartões e gráfico é correta.

Eu apresentaria essa estrutura à equipe como uma proposta bem encaminhada. Antes de apresentá-la como experiência finalizada, corrigiria o filtro de Alimentador, a coerência do formulário com o recorte explorado e o contraste da aba ativa no tema escuro. A ligação entre a investigação e a explicação do recorte também merece um ajuste simples de navegação.

Essa avaliação não substitui teste com a equipe comercial, reconciliação integral dos dados ou aceite de ENT-01. A tabela oficial de requisitos não foi alterada.

## Como a composição atende à história

| Necessidade do diretor comercial | Componente atual | Avaliação |
| --- | --- | --- |
| Entender o que aconteceu com a receita | Frase de variação e gráfico do Resumo | Adequado: resultado primeiro, composição depois; sem repetir três KPIs |
| Separar preço e quantidade | Gráfico preço × volume e composição completa sob demanda | Adequado para a decomposição disponível; o efeito-volume é impacto monetário do consumo medido, não uma medida direta de energia faturada |
| Comparar períodos | Contexto com janelas publicadas | Atende ao cenário primeiro ano × últimos 12 meses quando essas janelas coincidem com o catálogo. Não oferece decomposição arbitrária para qualquer par de períodos |
| Investigar por município, bairro e classe | Filtros, agrupamento, barras selecionáveis e breadcrumb | Estrutura adequada; formulário precisa preservar o recorte alcançado pelo drill-down |
| Encontrar onde a redução pesa mais | Ordenação por efeito-volume negativo em R$ e acesso a todos os grupos | Adequado para priorizar impacto comercial; esclarecer que o ranking é de impacto em receita, não de maior queda percentual de kWh |
| Entender por que o volume mudou | Achados do recorte, população faturada e comparação por conexão de GD | Acrescenta evidência real, em vez de repetir o case. Associação com GD não identifica integralmente a causa nem mede energia compensada |
| Saber quando o faturamento mudou | Histórico do recorte em diálogo | Adequado como apoio, sem outra aba principal e sem perder bairro/classe |

## Barra de contexto e filtros

Os períodos e os recortes têm responsabilidades diferentes. As datas delimitam a comparação analítica; município, bairro e classe delimitam a população investigada. Mostrar todos com aparência semelhante pode sugerir que as datas também serão editadas no mesmo modal. O texto de apoio atual ajuda, mas eu separaria visualmente **“Comparação”** de **“Recorte”**, sem criar outro painel grande.

| Elemento | Manter? | Justificativa |
| --- | --- | --- |
| Datas das duas janelas | Sim, como contexto de leitura | Toda variação depende de uma referência temporal; evita misturar a comparação anual com o histórico mensal |
| Município | Sim | Primeiro nível territorial pedido na história |
| Bairro dependente de município | Sim | Evita ambiguidade entre bairros com o mesmo nome e sustenta o drill-down |
| Classe | Sim, desde o início | O diretor pode começar pelo residencial, comparar classes ou restringir um território |
| Alimentador | Retirar da escolha comum e ocultar no resumo quando vazio | Não é dimensão solicitada nesta jornada e a decomposição publicada não o suporta; oferecer a escolha leva a uma análise indisponível |
| Agrupamento por município/bairro/classe | Sim, na Investigação | Não duplica o filtro: filtro escolhe a população; agrupamento escolhe como compará-la |
| Período do histórico | Sim, dentro do diálogo do histórico | Controla a leitura mensal e não deve aparentar alterar a decomposição das janelas |

O contrato já prevê `alimentador` como compatibilidade de URL e declara que a tela não acrescenta um seletor. A implementação atual oferece esse seletor. Há, portanto, divergência funcional e documental, além da questão de simplicidade. Links antigos podem continuar reconhecidos, com aviso e ação para remover o recorte incompatível; isso não exige oferecer Alimentador como escolha normal.

## Modal de filtros: estrutura correta, comportamento a ajustar

**O que está certo:** reutiliza o `Modal` e o `Button` do portal; segue o padrão de título, fechar, aplicar/cancelar, rascunho e organização em duas colunas no desktop. Os campos do modal têm 44 px de altura, como os filtros de outras jornadas. Bairro fica desabilitado até haver município. Datas deixam de aparecer quando há comparação por janelas. A moldura interna do formulário também aparece no Panorama; não é uma quebra de padrão isolada da Receita.

**Problemas confirmados:**

1. **O formulário pode divergir da barra.** Depois de explorar Olinda, o contexto mostra Olinda, mas Município abre vazio no modal porque `initialFilters` recebe `parsed.base`, sem os refinamentos. Aplicar apenas uma classe remove `recorte_municipio`/`recorte_bairro` e amplia a consulta. O diretor pode achar que mudou a classe dentro do território e receber uma população maior. Recomendo iniciar o modal com o recorte efetivo e conservar município/bairro ao ajustar classe; se a intenção for editar somente filtros gerais, isso precisa estar explicitamente identificado.
2. **“Limpar filtros” pode alterar um período oculto.** O reset usa `defaultFilters` inteiro, incluindo competências, mesmo com `showPeriod=false`. Na reprodução, um histórico configurado em jan–jun/2024 passou para jan–fev/2025 ao limpar/aplicar apenas o recorte. Recomendo limpar somente os campos visíveis de recorte e preservar o período do histórico. Se houver uma ação para restaurar tudo, ela precisa ter esse nome e escopo explícitos.
3. **Alimentador permite sair da análise principal.** O formulário oferece uma dimensão que torna as janelas/efeitos indisponíveis. Isso não deve ser uma surpresa depois de aplicar o filtro.

Evidências no código: `ReceitaPage.tsx:432`, `RevenueFiltersForm.tsx:161`, `RevenueFiltersForm.tsx:286` e `updateRevenueBaseParams` em `revenue-filters.ts`.

## Resumo

Eu manteria a composição principal: **variação em uma frase → gráfico único → achados que acrescentam informação**. O gráfico responde “quanto foi preço e quanto foi volume”; concentração, população faturada e GD acrescentam perguntas diferentes. Método e valores completos sob demanda preservam auditabilidade sem ocupar o primeiro plano.

O aviso de base parcial deve permanecer próximo do gráfico. Não é uma redundância descartável: informa que parcelas conhecidas não representam fechamento integral. Também é correto preservar a diferença entre preço observado e tarifa homologada e entre consumo medido e energia faturada.

Para apresentação, traduziria termos residuais como `P0/P1` nas tabelas para “período inicial/final”. Não retiraria o dado numérico exato. Usaria linguagem comercial para os achados, mantendo critérios e denominadores nos detalhes.

O ponto sobre GD deve ser defendido como **evidência contextual que ajuda a explicar a variação**, e não como uma causa integralmente comprovada. Os achados são calculados para o recorte atual, não copiados de um diagnóstico geral.

## Investigação

O desenho é adequado: efeito-volume como ponto de partida, ordenação pelas menores contribuições, barras com sinal e valor, exploração município → bairro → classe e breadcrumb para retorno. A limitação a dez grupos é declarada e a tabela preserva todos os recortes. Isso evita sobrecarga sem esconder os demais dados.

Recomendaria três ajustes de clareza:

- Trocar “Ordenar pela menor contribuição” por algo como **“Comparar impacto de”**, com opção **“Volume na receita (R$)”**. A pessoa escolhe a métrica e recebe a ordem mais negativa; não escolhe uma direção de ordenação. Isso reduz o esforço de entender o controle.
- Ao chegar ao território/classe de interesse, oferecer **“Ver explicação deste recorte”**, retornando ao Resumo sem perder filtros. Hoje a área “O que explica esse recorte?” ainda é um texto genérico de cautela, enquanto os achados reais ficam em outra aba. A funcionalidade existe, mas o próximo passo não está suficientemente explícito.
- Adaptar o estado quando não houver contribuição negativa e sinalizar o fim do drill-down. Atualmente a pergunta “Onde está a queda?” e a seta de exploração podem continuar aparecendo mesmo com crescimento ou em uma classe já selecionada. Não é necessário inventar outro nível de detalhe.

Na demonstração atual, é possível selecionar a classe e voltar manualmente ao Resumo para ver os achados daquele contexto. Essa é a sequência honesta para mostrar antes de acrescentar o atalho.

## Histórico do recorte

Eu manteria sob demanda. Ele tem uma função diferente da comparação estrutural: ajudar a localizar quando o faturamento mudou, num município/bairro/classe já investigado. Isso evita voltar ao Panorama e reconstruir ou perder o contexto, especialmente o bairro.

A decisão de removê-lo das abas principais é coerente: a história prioriza variação, decomposição e localização da queda; uma série longa não deve disputar o primeiro plano. O diálogo com período próprio e tabela inline evita um modal dentro de outro modal.

Limites que devem ficar claros na apresentação:

- O gráfico mostra **faturamento mensal**. Não demonstra sozinho quando o consumo caiu, porque o preço pode compensar a redução de volume. Consumo mensal está disponível na tabela; uma seleção de métrica no gráfico seria uma melhoria possível, não uma justificativa para voltar a encher o Resumo.
- Alterar os meses do histórico não recalcula as janelas da decomposição.
- Em celular, o conteúdo exige rolagem dentro do diálogo e o gráfico tem largura mínima interna. Na inspeção não houve overflow horizontal da página, mas isso não significa que todo o gráfico caiba de uma vez na tela. É um ponto de conforto para evolução.
- “BRL” pode ser apresentado como “R$”; o código de moeda não acrescenta valor para esse público.

## Padronização e acessibilidade

| Área | Evidência | Parecer |
| --- | --- | --- |
| Modal e ações | `shared/ui/Modal`, `shared/ui/Button`, mesmos padrões usados em Panorama/Inspeções/Operação | Manter |
| Campos de mês/ano do histórico | `MonthYearField` compartilhado | Manter |
| Temas, superfícies e tipografia | Tokens do portal; estados e valores com alternativas textuais | Base consistente |
| Campos geográficos do modal | Altura 44 px, mas seletor nativo sem o mesmo tratamento de seta/aparência dos filtros do Panorama/Operação | Alinhar acabamento dos controles, sem criar um novo estilo específico de Receita |
| Seletores da Investigação | Altura computada de 39 px, contra 44 px no modal | Padronizar altura, borda, espaçamento e seta |
| Aba ativa no escuro | Texto branco forçado por `text-white`, em vez do token de texto sobre a cor de destaque | Corrigir antes da aprovação visual |

**Contraste medido da aba ativa:** no tema claro, branco sobre `rgb(168,63,77)` resulta em aproximadamente **6,03:1**. No escuro, branco sobre `rgb(238,135,148)` resulta em **2,46:1**. O token já existente `--accent-goiaba-text: #211a1c` produziria cerca de **6,94:1** nesse fundo. A referência WCAG AA para texto normal é **4,5:1** ([W3C — Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)). Isso é uma falha localizada do uso de cor na aba, não motivo para redesenhar o tema inteiro.

Referências: `ReceitaPage.tsx:518`, `RevenueInvestigation.tsx:68`, `shared/ui/Button.tsx`, `shared/filters/FilterSelect.tsx`, `features/operacao/OperationFilters.tsx` e `styles/tokens.css`.

## Prioridade antes da apresentação

**Corrigir antes de tratar como experiência finalizada:**

1. Retirar Alimentador da seleção comum da Receita e tratar somente a compatibilidade explícita de links antigos.
2. Fazer o modal refletir/preservar o recorte explorado e impedir que limpar campos de recorte altere o histórico oculto.
3. Usar o token correto de texto na aba ativa do tema escuro.

**Ajustes pequenos recomendados:** atalho da Investigação para o diagnóstico do recorte; seletores com o mesmo acabamento/altura; rótulos comerciais e indicação de fim da exploração. Não recomendo outro redesenho nem acrescentar nova fileira de indicadores.

## O que foi mantido ou alterado — argumento para a equipe

| Decisão na revisão já realizada | Motivo ligado à dor comercial |
| --- | --- |
| Mantidas as janelas visíveis | A variação só faz sentido com períodos e população identificados |
| Mantidos município, bairro e classe | São as dimensões explicitamente pedidas na história |
| Retirados os cartões que repetiam o gráfico | A mesma informação não precisa ocupar duas áreas de destaque |
| Mantido um gráfico preço × volume | É a resposta direta para “quanto foi preço e quanto foi quantidade” em impacto monetário |
| Agrupadas visualmente parcelas secundárias, com detalhes disponíveis | A leitura inicial fica simples sem esconder interação, entradas, saídas e demais componentes |
| Substituído o texto genérico de Henrique por achados do recorte | O diretor precisa de evidências, não de uma repetição da pergunta |
| Separados Resumo e Investigação | Primeiro entender o resultado; depois localizar a contribuição negativa |
| Mantidos valores completos e todos os grupos sob demanda | Simplicidade visual não pode eliminar a possibilidade de conferir os números |
| Histórico retirado das abas e mantido como apoio | Ajuda a localizar o momento da mudança sem competir com o diagnóstico |
| Preservados filtros/recortes na URL e navegação de retorno | A investigação precisa continuar ao trocar de leitura, recarregar ou compartilhar o link |

**Fala sugerida:**

> “Organizamos a Receita em duas perguntas: o que mudou e onde isso aconteceu. O Resumo mostra a variação uma única vez, separa preço e volume e acrescenta evidências do recorte. A Investigação permite abrir município, bairro e classe até localizar a contribuição negativa. O histórico ficou como apoio para investigar o momento da mudança, sem ocupar a tela principal. Preservamos os valores completos e as limitações da base para que a resposta seja verificável.”

**Roteiro de demonstração:**

1. Mostrar as datas e o recorte ativo. Para discutir especificamente a tarifa residencial do case, selecionar Residencial; não apresentar o resultado de todas as classes como residencial.
2. Ler a variação e apontar preço, volume e demais componentes no gráfico. Mostrar os valores completos somente se houver pergunta.
3. Apresentar os achados: concentração, população faturada e comparação por conexão de GD. Diferenciar observação e hipótese causal.
4. Abrir Investigação e percorrer município → bairro → classe, explicando que a ordem é de impacto monetário do volume. Voltar ao Resumo para ver a explicação do recorte selecionado.
5. Abrir o histórico apenas para uma pergunta temporal; mostrar que o bairro/classe se mantém e que os meses desse diálogo têm outra responsabilidade.

**O que não afirmar:** que toda comparação arbitrária está disponível; que consumo medido equivale a energia faturada; que preço observado é tarifa homologada; que GD prova toda a causa; ou que UCs com fatura observada representam o histórico completo de clientes cadastrados.

## Implementação após a avaliação

As correções de apresentação e navegação foram aplicadas: formulário parte do recorte efetivo, limpar não redefine competências ocultas, Alimentador é somente legado com remoção explícita, aba ativa usa o token de contraste, investigação retorna ao diagnóstico contextual e distingue valores negativos, não negativos e indisponíveis. Rótulos de moeda e períodos foram simplificados; comparação e recorte têm subtítulos curtos na barra.

A configuração de janelas de preço-volume consultada contém um par P0/P1, que a tela apresenta como contexto da comparação. O período do histórico mensal é independente.

Validações observadas após as alterações: 564 testes frontend completos; 50 testes dirigidos de Receita; build, lint (com dois avisos legados em AuthProvider/AssistentePage), formatação, fronteiras e quatro jornadas Playwright artificiais em desktop/mobile e claro/escuro. A validação visual não representa reconciliação Gold; não foi feita nova consulta autenticada nesta etapa. A aplicação das alterações não altera o aceite de ENT-01.

## Base e limites da avaliação

Foram lidos os componentes atuais de Receita, regras de URL, padrões compartilhados, implementações de filtros de outras jornadas, contrato de Receita, guias e PRD. A composição foi exercitada em Chromium com fixture **artificial**, incluindo modal claro/escuro, drill-down, alteração de classe, reset com datas ocultas e histórico mobile. Capturas locais em `work/receita-audit/`; script de reprodução em `work/receita-audit/audit.mjs`.

Foram reproduzidos: formulário com município vazio após drill-down; perda do recorte ao aplicar classe; redefinição de meses ocultos; quatro controles de 44 px no modal; dois seletores de 39 px na Investigação; cores computadas da aba; ausência de overflow horizontal da página no cenário mobile. A primeira tentativa de automação falhou por um localizador textual; foi corrigido no script de auditoria e a reprodução terminou com sucesso.

Não foi feita nova consulta ao dataset, execução de testes unitários, alteração de produto ou aprovação no Figma. As referências Figma registradas continuam úteis para fundação visual, mas o fluxo atual revisado não foi declarado idêntico ao protótipo histórico. A análise de contraste cobre o elemento medido, não uma auditoria completa de acessibilidade. As conclusões sobre facilidade para a equipe precisam ser confirmadas na apresentação e, idealmente, com uma pessoa do comercial executando o percurso sem orientação.
