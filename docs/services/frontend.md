# Serviço: portal web

**Escopo:** WEB-01 a WEB-10, IA-04 e IA-05 do [PRD](../PRD.md). **Estado:** WEB-01 em validação no Panorama com filtros na URL, 4 KPIs principais e 4 complementares, séries e API sintética em `GET /api/v1/panorama`. Receita mantém a exploração DEV-03; Inspeções mantém fila e detalhe auditável DEV-05. As demais jornadas seguem seus estados no PRD. A DEV-01 acrescenta uma rota de desenvolvimento para verificar contratos, sem substituir o contrato do Panorama. **Stack adotada:** React + TypeScript com Vite, Tailwind CSS e Lucide.

O ambiente Docker de desenvolvimento seleciona a fonte sintética explicitamente. O navegador consulta a API pela origem do portal, via proxy Vite, inclusive ao acessar pelo celular. Cabeçalho e área de dados têm largura fluida centralizada; filtros e cartões se reorganizam por breakpoint.

## Arquitetura adotada

A DEV-06 acrescenta criação no detalhe da suspeita e consulta básica em `/ordens`, com UC/estado/página na URL. Sucesso exige confirmação do servidor e reenvio reutiliza a chave da intenção. O proxy Vite pode receber `ORDERS_DEV_PROXY_TOKEN` somente no processo servidor; nenhum token deve entrar em `VITE_*`. Interface simples por decisão da pessoa usuária, para a pessoa responsável pelo frontend continuar o acabamento e as ações. Veja [contrato e evidências DEV-06](../contracts/inspection-orders-dev06.md).

Consulte o [guia arquitetural](../architecture/frontend.md) e a [ADR-0001](../decisions/0001-arquitetura-frontend.md) para estrutura, limites de importação, layout persistente, tema, transporte HTTP e política de estado. A primeira fatia visual cobre apenas navegação, apresentação visual do Panorama e textos superiores das demais páginas, até antes dos filtros ou conteúdo operacional.

A DEV-01 usa TanStack Query e o transporte existente na rota `/dev/contratos`, somente em desenvolvimento e sem item no menu. Ela valida o contrato de indicadores em execução, consulta a API real e mostra demonstração, disponibilidade e proveniência. O build de produção exclui essa página. Veja [contratos](../contracts/analytics-api.md), [desenho](../design/2026-10-20-dev01-design.md) e [ADR-0004](../decisions/0004-contratos-analiticos-e-fonte-sintetica.md). A rota não implementa os dashboards ou conclui suas jornadas.

## Público e jornadas

A DEV-03 torna Receita explorável com API sintética real, segundo [contrato 1.1.0](../contracts/revenue-dev03.md), [desenho](../design/2026-10-21-dev03-design.md) e [ADR-0006](../decisions/0006-exploracao-demonstrativa-receita.md). Filtros base e refinamentos ficam na URL; voltar ao total preserva os filtros base. A barra compacta abre um diálogo de filtros; cartões, decomposição e tabela seguem os frames claro/escuro, com série e fundamento após os recortes. JSON é validado em execução; chave da consulta e cancelamento acompanham os filtros. A demonstração compara competências extremas explicitamente e não substitui as janelas anuais ou o aceite com Gold. Veja as [evidências de revisão integrada](../plans/2026-10-21-dev03-evidence.md).

O portal é interno e apoia cinco rotinas: panorama para diretoria, receita para comercial, visão UC para atendimento, fila/ordens para perdas e continuidade por alimentador para operação. O agente de IA deve estar acessível no próprio portal e gerar insight contextual em ao menos uma tela. A divisão exata em rotas/telas é decisão de produto; cada jornada precisa ser testada por perfil de usuário relevante.

## Inventário funcional mínimo

| Área | Conteúdo e ações | Requisitos |
| --- | --- | --- |
| Panorama | KPIs, séries, comparação entre períodos, filtros e atualização dos dados | WEB-01, WEB-07 |
| Receita | Separar preço e volume; navegar município, bairro e classe; visualizar fundamento da variação | WEB-02, WEB-07 |
| UC 360 | Buscar UC e reunir cliente/cadastro, consumo, faturas, medidor, GD, interrupções, chamados | WEB-03 |
| Inspeções | Fila com motivo/energia estimada, geração e ciclo de vida de ordens; exportar/importar se diferenciais forem feitos | WEB-04, WEB-05, WEB-08, WEB-09 |
| Operação | DEC/FEC por alimentador, tendência e pior desempenho | WEB-06 |
| IA | Conversa em português e insight contextual verificável | IA-04, IA-05 |
| Acesso | Perfis e telas/ações por cargo, se diferencial for escolhido | WEB-10 |

### Jornadas para revisão de produto

1. **Diretoria:** escolher janela e comparar indicadores com período anterior; abrir recorte mantendo período e unidade claros. A soma dos recortes precisa ser explicável em relação ao total.
2. **Comercial:** partir da receita residencial total, separar preço efetivo/volume, navegar município e bairro e reconhecer onde há queda absoluta relevante. A tela deve deixar visível a diferença entre reajuste homologado e preço observado.
3. **Atendimento:** localizar UC pelo número dito na ligação, comparar consumo/faturas recentes e ler contexto de medidor, GD, rede e chamados sem mudar de sistema. Campo ausente não deve parecer consumo zero.
4. **Perdas:** abrir fila ordenada, entender o motivo e a estimativa, iniciar ordem e acompanhar estado/resultado. A interface descreve suspeita, nunca fraude comprovada antes da inspeção.
5. **Operação:** comparar DEC/FEC simplificados entre alimentadores e competências, investigar piores casos e ler fórmula/denominador antes de propor ação.
6. **IA:** perguntar em português dentro do portal e conferir período, filtros, fonte e limites da resposta. O insight embutido deve usar o mesmo recorte da tela.

Esses percursos são critérios de revisão, não uma imposição de seis rotas. Propor mapa de navegação e componentes depois que o contrato da API e as métricas Gold estiverem definidos.

## Regras de apresentação

- Toda métrica mostra nome, unidade, período/competência, filtros aplicados e data da atualização.
- A distinção entre `valor faturado`, `valor pago`, `energia consumida` e `energia faturada` deve ser visível.
- Gráficos terão rótulos e alternativa textual; tabelas suportarão navegação por teclado, ordenação/recorte claros e estados de carregamento/erro/vazio.
- Filtros globais e locais devem ser distinguíveis, persistir de forma previsível ao navegar e aparecer também em exportações.
- O insight de IA é sinalizado como interpretação automatizada e oferece caminho para auditar números.
- Em suspeita de perdas, usar linguagem de priorização de inspeção, sem imputar fraude como fato.

## Estados e dados que cada visualização deve tratar

| Estado | Comportamento esperado |
| --- | --- |
| Carregando | Identificar área em atualização sem exibir número antigo como se fosse atual. |
| Vazio legítimo | Distinguir ausência de registro para filtros escolhidos de falha na carga ou valor zero. |
| Parcial/incompleto | Indicar quais fontes/competências faltam e quais conclusões ficam indisponíveis. |
| Erro de API/IA | Permitir nova tentativa quando apropriado e manter os dados já válidos; mensagem sem detalhes internos. |
| Base pequena/denominador zero | Evitar percentuais e ordenações enganosas; mostrar contagem de base e razão da indisponibilidade. |
| Filtro alterado | Atualizar gráfico, tabela, exportação e insight contextual em conjunto ou sinalizar que um deles ainda não foi recalculado. |

Para tabelas grandes, definir paginação/ordenação de modo consistente com a API; para visualizações, explicitar unidade, legenda, escala e descrição textual. Validar uso por teclado, foco, rótulos e contraste nas jornadas principais.

## Integração e aceitação

A DEV-05 implementa a jornada demonstrativa de perdas em `/inspecoes`, com consulta real ao backend sintético, filtros/página/ordenação na URL e detalhe de evidências com retorno ao mesmo recorte. A [regra de prioridade, estimativa e desempate](../contracts/inspection-dev05.md) expõe insumos, ausência e limitações; não confirma irregularidade. A regra real, a Gold e as ordens de WEB-05 continuam pendentes. Dados cacheados podem permanecer durante atualização ou falha somente com aviso explícito.

A revisão visual DEV-05 usa as capturas fornecidas pela pessoa usuária e acrescenta filtros recolhíveis, resumo do recorte completo, sinais na fila e barras de pontuação, com detalhe próprio em cartões. O backend fornece o resumo e os rótulos/pesos dos sinais antes de paginar; a interface não recalcula prioridade nem confunde os totais com a página atual. O cabeçalho da rota distingue fila e detalhe; os temas usam os mesmos tokens e a tabela mobile oferece rolagem focável.

O frontend consome API FastAPI; não lê o banco ou arquivos Gold diretamente. Definir contratos com backend antes de codificar componentes. Verificar ao menos uma jornada real de cada área com Gold carregada e demonstrar que os números batem com a consulta fonte. A skill `vercel-react-best-practices` é referência para performance React, não substitui os critérios do PRD. O [protótipo próprio em Figma](../design/grid360-prototype.md) orienta a interface nos dois temas; contém dados sintéticos e não valida integração, persistência ou acessibilidade de execução.

Antes de declarar WEB-01 a WEB-07 concluídos, guardar evidência de uma execução com API real, filtros exercitados, caso vazio/erro e amostra reconciliada com Gold. Os diferenciais WEB-08 a WEB-10 são independentes e continuam pendentes até seus próprios critérios serem testados.

### Revisão DEV-02 — 22/10/2026

Filtros da URL são validados antes do envio: comparação, município e classe devem pertencer aos conjuntos demonstrativos; competência deve ser real em YYYY-MM; parâmetros repetidos são recusados. Valores inválidos permanecem na URL com erro por campo até correção ou restauração. Histórico e recarga conservam o contexto. Datas válidas sem fatos continuam sendo recortes vazios. Fonte sintética e atualização ficam no topo. Quatro KPIs principais precedem a série; os outros quatro aparecem como complementares. Filtros usam duas colunas no mobile. O gráfico mostra escala vertical (R$ mil/MWh), valores nas barras, detalhes fora da rolagem por mouse/teclado e tabela alternativa. Comparação de competência parcial é indisponível, sem exibir percentual zero; 1 GWh equivale a 1.000.000 kWh.

### Faixa compacta de filtros — DEV-02, 22/10/2026

A apresentação inicial dos filtros é um resumo de competência, período de comparação, território e classe, conforme as capturas do protótipo fornecidas na revisão. “Ajustar filtros” expande os controles na mesma superfície; edições são aplicadas automaticamente na URL e nos dados. Fechar ajustes ou Escape recolhe os campos; Escape retorna foco ao botão. URLs inválidas abrem os campos para correção. Desktop usa quatro colunas com ação lateral; mobile organiza o resumo em duas colunas e a ação abaixo. Os períodos e valores seguem a fixture vigente, sem trocar pelos exemplos visuais do Figma.

Por solicitação da pessoa usuária nesta revisão, a linha de fonte/lote e última atualização foi retirada do topo do Panorama. A API preserva os metadados e os detalhes das métricas mantêm o lote; a origem continua sintética.
