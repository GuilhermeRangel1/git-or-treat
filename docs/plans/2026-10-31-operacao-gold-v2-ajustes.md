# Proposta de ajustes de Operação com Gold v2

Data: 31/10/2026. Execução frontend concluída; evidências e verificações em `work/operacao-gold-v2-implementation-report.md`. O root integrou o progresso parcial no PRD e atualizou este guia. WEB-06 permanece `Em validação`; WEB-07 permanece `Pendente`.

## Objetivo e referências

Atender a fatia de Operação da DEV-13.1: WEB-06 (evolução de DEC/FEC por alimentador e identificação dos piores resultados) e WEB-07 (filtros e recorte compreensíveis). Usar o PRD, `docs/contracts/operations-dev08.md`, o contrato Gold DEV-13.1, o dicionário e as decisões de consolidação como fonte de verdade. O PDF de avaliação, item 6.1, reconhece o uso de período e pede consistência entre telas; a observação geral pede hierarquia e menor excesso de informação.

Skills obrigatórias na execução: `backend-coding-standards`, `frontend-coding-standards` e recomendações React aplicáveis. Consultar padrões PostgreSQL se alterar consultas/índices.

## Prioridades solicitadas pela pessoa usuária

1. **Filtros:** barra e modal de Operação no mesmo padrão de Panorama e Ordens. Panorama é a referência visual para as três páginas, incluindo o ícone de “Limpar filtros”, variantes e posições de Cancelar/Aplicar, espaçamentos e controles.
2. **KPIs DEC/FEC:** reduzir o excesso de informações mostrado em `image.png`, consultada localmente nesta revisão. Os cartões devem priorizar nome, valor e unidade; listas completas de IDs, numeradores e detalhes do cálculo ficam nos fundamentos. Remover mensagens repetidas de carregamento e ressalvas técnicas do corpo principal, mantendo estados de erro/dados e limites existentes nos fundamentos. Não copiar a imagem nem seus valores para o Git.
3. **Tabela de alimentadores:** aplicar o padrão da tabela atual de Ordens: superfície, bordas, raio, densidade, tipografia, alinhamento de cabeçalhos/células e ações. Manter colunas próprias do domínio de continuidade.

A ausência do ícone de “Limpar filtros” em Ordens é uma correção da execução de Ordens, encaminhada ao implementador; deve estar corrigida antes de usar esse modal como referência.

## Achados da inspeção inicial

Página consultada com sessão real, fonte Gold v2 e período Jun/2026:

- Os dois cartões DEC/FEC exibem todos os IDs de alimentadores incluídos/excluídos, ocupando grande parte da tela e duplicando listas.
- O ranking Gold renderiza todos os alimentadores sem paginação e várias linhas de ressalvas. A página fica muito longa.
- Fonte técnica, horário UTC, fórmula e limitações detalhadas aparecem na composição principal; priorizar leitura operacional e preservar auditoria nos fundamentos.
- A apresentação Gold usa tabela de série no detalhe. O componente de série existente deve ser avaliado para oferecer tendência visual com tabela acessível.
- Há controles próprios de filtros e um parâmetro de paginação usado na jornada anterior de ocorrências. Não confundir essa paginação com o ranking Gold.
- A Gold disponibiliza agregados; não fingir ocorrências individuais nem apuração regulatória oficial.

## Trabalho proposto

### 1. Resumo e hierarquia

- [x] Manter DEC e FEC como indicadores principais compactos, com unidade e período visíveis. Não adicionar indicadores só para preencher quatro cartões.
- [x] Retirar dos cartões as listas de IDs, fórmulas e numeradores extensos. Mostrar apenas a informação de base que ajude a leitura; universos distintos permanecem identificáveis.
- [x] Levar listas completas de incluídos/excluídos, fórmulas, denominadores, proveniência e razões de cobertura a um modal de fundamentos padronizado com o portal.
- [x] A imagem de referência mostra a mesma lista extensa repetida nos dois cartões. Evitar tanto a repetição quanto substituir a lista por outro bloco longo: usar detalhes consultáveis por indicador para preservar universos diferentes de DEC/FEC.
- [x] Remover fonte/lote/fingerprint/horário UTC da área principal. Preservar esses dados nos fundamentos.
- [x] Remover da composição principal as frases redundantes de período aplicado e de cadastro sem vigência histórica/resultado não regulatório; manter a temporalidade e a ressalva técnica nos fundamentos.
- [x] Tratar zero, ausência, cobertura insuficiente e denominador inválido sem criar valores. Os estados parciais permanecem explícitos; zero segue distinto de `null`.

Arquivos: `GoldOperationView.tsx`, `OperationSource.tsx`, `OperationFoundations.tsx`, `OperacaoPage.tsx` e testes.

### 2. Filtros consistentes

- [x] Igualar superfície, espaçamento, tipografia, controles e ações ao padrão atual de Panorama/Ordens, respeitando campos de Operação: início/fim, município e alimentador.
- [x] Padronizar Cancelar, Aplicar e Limpar com rascunho local e aplicação explícita.
- [x] Incluir o ícone `RotateCcw` em “Limpar filtros”, igual ao Panorama, e igualar variantes/tamanhos/ordem dos botões nas três páginas. Conferir fundo dos campos, bordas, foco, setas dos selects e espaçamento do formulário; manter a semântica própria dos campos de período.
- [x] Nomear janela como “Período”; se início=fim, exibir competência única no resumo em vez de repetir o mesmo mês.
- [x] Validar compatibilidade município/alimentador e competências observadas. Não acrescentar classe de consumo sem suporte na Gold de continuidade.
- [x] Comprovar que período e dimensões afetam resumo, ranking e detalhe conforme contrato, com URL/reload/cache corretos e sem misturar publicações.

Arquivos: `OperationFilters.tsx`, `operations-state.ts`, `useOperations.ts` e testes.

### 3. Ranking legível e paginado

- [x] Mostrar 20 alimentadores por página, totais e Anterior/Próxima, com página persistida na URL e reiniciada ao mudar recorte/ordenação.
- [x] Manter ranking global DEC/FEC ordenado pela API e posições absolutas; não recalcular ranking somente dentro da página.
- [x] O contrato atual entrega a lista Gold completa. Para o volume atual, paginar a apresentação dessa lista é suficiente; não inventar paginação de servidor existente. Separar o parâmetro do ranking da paginação legada de ocorrências e documentar a URL.
- [x] Separar alimentadores sem indicador calculável do ranking válido. Motivos ficam em detalhe expansível; não exibir dezenas de avisos de mesmo peso na tabela.
- [x] Alinhar cabeçalhos/células e nomear coluna de ação “Detalhes”. Mostrar unidades e valores com precisão consistente; adaptar para registros mobile ou tabela com rolagem contida, sem overflow da página.
- [x] Comparar visualmente com `frontend/src/features/ordens/OrdersTable.tsx` depois dos ajustes aprovados: cabeçalho e conteúdo começam no mesmo alinhamento, ação sem recuo extra e padding consistente. Conservar posição, alimentador, município, DEC, FEC, base e ação conforme o contrato.

Arquivos: `GoldOperationView.tsx`, `operations-state.ts`, componentes específicos extraídos se necessário e testes.

### 4. Detalhe e evolução

- [x] Manter identificação do alimentador, município e janela no detalhe, com retorno ao mesmo ranking/página/ordenação.
- [x] Remover do corpo principal do detalhe as mensagens “Janela do agregado…”, contagem de competências observadas/ausentes e disponibilidade de ocorrências individuais; preservar período, observações, população, cobertura e limites somente nos fundamentos quando fornecidos pelo contrato. Não inventar campo de disponibilidade de ocorrências ausente do contrato.
- [x] Remover do corpo principal “Período aplicado” e a ressalva sobre vigência cadastral/homologação regulatória; o filtro já informa o período e os limites cabíveis ficam nos fundamentos.
- [x] Remover o aviso visual “Carregando consolidado Gold…” que aparecia acima dos KPIs enquanto o resumo não chegava; manter a consulta, os erros e a apresentação de dados válidos.
- [x] Apresentar tendência mensal DEC/FEC com unidade, eixo e alternativa tabular. Reutilizar `OperationSeries.tsx` quando compatível, sem converter lacunas em zero ou somar médias mensais.
- [x] Distinguir série histórica do agregado do período, preservando fórmula e população definidos na API.
- [x] Remover a mensagem principal sobre ausência de ocorrências individuais; fundamentos usam somente limites existentes em definição/summary/metadata.

### 5. Validação e fechamento

- [x] Reconciliar resumo, amostra do ranking e série de um alimentador com a API Gold já carregada; incluir janela de um e vários meses, município/alimentador, ausência, zero e base inválida por amostra ou teste. Nenhuma lacuna mensal foi encontrada nos alimentadores verificados na amostra ao vivo.
- [x] Conferir fórmula consolidada: numerador e denominador no mesmo universo; excluir conforme regra contratual e não tirar média simples dos DEC/FEC.
- [x] Reutilizar evidência da carga final compartilhada; nenhuma importação ampla foi executada nesta tarefa de apresentação.
- [x] Testar filtros/paginação/ordenação/volta/URL. Playwright em desktop/mobile, dois temas, teclado e modais; largura 390px sem overflow horizontal do documento. Escape fecha o modal e devolve foco ao acionador.
- [x] Rodar testes afetados, build, lint direcionado, formatação e fronteiras. O root atualizou o PRD e este guia; os contratos de API existentes não precisaram de mudança.
- [x] Revisão final: suíte frontend completa passou (344 testes, 1 ignorado); suíte backend completa passou com `ANALYTICS_SOURCE=synthetic` e `ORDERS_AUTH_MODE=service` (779 testes, 99 ignorados, 1 aviso preexistente). A execução backend usou `--basetemp=../work/pytest-full-dev13-final-synthetic` para contornar a permissão do temporário global.

## Restrições

Manter hooks desativados apenas localmente, sem commit. Não adicionar PDFs/datasets/capturas privadas ou segredos ao Git. Não modificar Ordens ou dados operacionais locais. O plano cobre a implementação frontend de Operação; o registro parcial no PRD não altera o estado do requisito nem substitui a revisão de aceite compartilhada.
