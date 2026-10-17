# Protótipo visual — V-Energy Grid 360

**Data:** 16/10/2026 · **Branch:** `feat/git-or-treat-figma` · **Estado:** referência visual criada; aplicação ainda não implementada.

O protótipo foi criado pelo Figma MCP com camadas editáveis, componentes reutilizáveis e temas claro/escuro. É uma preparação solicitada pela pessoa usuária, adicional ao case; não conclui os requisitos funcionais do [PRD](../PRD.md#93-experiência-e-acessibilidade).

- [Abrir arquivo Figma](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K)
- [Apresentar modo claro](https://www.figma.com/proto/oTjmpIBgbA7OOYb9ZmMG9K?node-id=15-164&starting-point-node-id=15-164)
- [Apresentar modo escuro](https://www.figma.com/proto/oTjmpIBgbA7OOYb9ZmMG9K?node-id=16-1129&starting-point-node-id=16-1129)

## Organização e direção visual

O arquivo contém exatamente quatro páginas:

| Página | Conteúdo |
| --- | --- |
| Componentes e estilos — modo claro | Fundamentos e biblioteca; quadro `8:227` |
| Componentes e estilos — modo escuro | Os mesmos componentes resolvidos no tema escuro; quadro `12:164` |
| Páginas e fluxos — modo claro | 16 frames de telas e overlays; início `15:164` |
| Páginas e fluxos — modo escuro | Os mesmos 16 frames; início `16:1129` |

A direção aprovada combina estrutura técnica, atmosfera profunda no tema escuro e detalhes tecnológicos expressivos. A paleta **cacau, goiaba e pistache** foi aprovada pela pessoa usuária depois da exploração de alternativas. A base quente e a hierarquia tipográfica deixam o destaque cromático para ações, séries e informações prioritárias.

| Papel | Claro | Escuro |
| --- | --- | --- |
| Fundo | `#F5F0E7` | `#211A1C` |
| Superfície | `#FFFCF6` | `#2E2427` |
| Texto principal | `#29201F` | `#F5F0E7` |
| Texto secundário | `#73645F` | `#C2AFA8` |
| Ação goiaba | `#A83F4D` | `#EE8794` |
| Destaque pistache | `#707B2C` | `#D2DA8A` |

Tipografia: **Manrope** para títulos e métricas, **DM Sans** para interface e leitura, **IBM Plex Mono** para metadados. Foram criados nove estilos de texto. O alvo desta primeira versão é desktop, com telas principais de 1440 × 1024 e rolagem vertical; mobile e comportamento responsivo ainda precisam de desenho e validação.

As cinco referências informaram a exploração: [React Bits](https://www.reactbits.dev/c/backgrounds), [Aceternity UI](https://ui.aceternity.com/), [Magic UI](https://magicui.design/docs/components), [Motion Primitives](https://motion-primitives.com/docs) e [Codrops](https://tympanus.net/codrops/hub/). Nenhuma biblioteca foi instalada no frontend nesta etapa.

## Biblioteca compartilhada

Os dois temas usam os mesmos componentes, com variáveis semânticas em modos Claro/Escuro. Os masters ficam na primeira página; a página escura demonstra instâncias da mesma biblioteca.

São 13 famílias: Button, NavItem, Field, MetricCard, Badge, Notice, ContentState, AIInsight, TableRow, Sidebar, FilterBar, ConfirmDialog e Background / Dot Grid. As variantes incluem hover, foco, desabilitado, carregamento, vazio, erro, dados parciais, base pequena, denominador zero e insight indisponível/desatualizado.

Há 43 cores primitivas, 28 aliases semânticos de cor, 17 variáveis de espaçamento/raio e oito variáveis de apresentação. Cada página de fluxos contém 250 instâncias da biblioteca. Ainda não existe código de aplicação para associar via Code Connect.

## Jornadas desenhadas

| Jornada | O que pode ser revisado | PRD | Frame claro / escuro |
| --- | --- | --- | --- |
| Panorama | KPIs, comparação, série e insight contextual | WEB-01, WEB-07, IA-05 | `15:164` / `16:1129` |
| Receita | Preço-volume, municípios, bairro e limitações do recorte | WEB-02, WEB-07 | `15:331` / `16:1296` |
| Atendimento | Busca, UC, consumo, faturas e contexto de medidor/GD/rede/chamados | WEB-03 | `15:582` / `16:1547` |
| Inspeções | Fila, motivo, estimativa e evidências da suspeita | WEB-04 | `15:773` / `16:1738` |
| Ordens | Estado, resultado, cancelamento e exemplo de validação | WEB-05 | `16:640` / `16:1894` |
| Operação | Comparação de alimentadores, DEC/FEC e ausência de denominador | WEB-06 | `16:735` / `16:1989` |
| Assistente | Resposta em português, fundamento, ambiguidade, falta de evidência e recusa de escrita | IA-01 a IA-06 | `16:991` / `16:2245` |

Os 16 frames de cada tema incluem panorama, filtros, receita, recorte, busca de UC, UC, histórico da UC, fila, suspeita, ordens, ações da ordem, operação, alimentador, fundamento, chat e limites da IA. O menu liga as áreas; overlays permitem conferir contexto e retornar à jornada de origem. A troca de tema abre o frame correspondente no outro fluxo de apresentação.

Filtros e campos usam exemplos previamente definidos, identificados como não editáveis. As ações de ordens usam variáveis do Figma para simular alterações; não persistem em banco. Linhas sem detalhe demonstrável estão sinalizadas. Exportação/importação, perfis de acesso e memória de conversa não foram incluídos como diferenciais nesta versão.

## Backgrounds e movimento

No Figma há textura pontilhada e linhas de energia editáveis no panorama, além de transições nativas de hover, navegação e overlays. Hover usa Smart Animate de 160 ms; navegação e overlays usam Dissolve de 180 ms. Tabelas e gráficos mantêm leitura estável.

Na implementação, efeitos contínuos, reação ao cursor e eventual WebGL serão trabalho do frontend, após avaliar custo e legibilidade. O frontend deverá respeitar `prefers-reduced-motion`, oferecer estados sem movimento e implementar foco/teclado. O protótipo não comprova essas propriedades de execução.

## Dados e verificações

Todos os números e identificadores são **sintéticos**, sinalizados nas telas. Não foi usado dataset real nem dados pessoais. A demonstração de receita usa R$ 80.000 → R$ 76.500 e 100.000 → 90.000 kWh: variação de −R$ 3.500 (−4,38%). A decomposição ilustrativa fecha em −8.000 de volume + 5.000 de preço − 500 de interação. Os três municípios somam R$ 76.500; os dois bairros do município Alfa somam R$ 38.000. Esses valores não são diagnóstico do case nem fórmula final aprovada para a Gold.

A revisão confrontou as jornadas com os guias frontend/backend/IA e o dicionário ainda sem esquema real. Foram corrigidos destinos de recortes indisponíveis, retorno dos filtros, fundamento contextual, série de FEC e vencimento demonstrativo da fatura. O gráfico FEC foi compactado para preservar valores e bimestres na exportação, com escala alinhada à linha de base.

**Resultado da auditoria via Plugin API em 16/10/2026, por tema:** 16/16 frames alcançáveis a partir do panorama; 250 instâncias; 764 textos; zero destinos inexistentes, fontes ausentes, textos colapsados ou transbordamentos detectados em contêineres internos. Conteúdo abaixo da dobra em telas com rolagem não conta como transbordamento. Foram encontrados 201 destinos nativos por tema, incluindo reações herdadas dos componentes.

Para reproduzir a conferência, abrir cada página de fluxos pelo MCP, percorrer os destinos NODE das reações desde o panorama, conferir a existência dos destinos e comparar limites dos filhos aos contêineres, respeitando a rolagem. Conferir `hasMissingFont`, altura dos textos e o modo de cor explícito nos frames. Após qualquer mudança visual, exportar os frames afetados e inspecionar rótulos, recortes e alinhamento. Foram inspecionadas capturas da biblioteca, panoramas, receita, UC, operação, fila, assistente, filtros, ações de ordem, fundamento e FEC.

Os contrastes medidos nos aliases de texto principal/superfície, texto secundário/superfície e texto/botão foram, respectivamente, **15,53 / 5,52 / 5,89** no claro e **13,24 / 7,15 / 6,83** no escuro. Bordas de controle/superfície: 3,67 e 4,08. São verificações desses pares, não certificação de acessibilidade da aplicação inteira.

O player carregou e exibiu o panorama no navegador de validação. A sequência de cliques, atualização de textos por variáveis, scroll e transições no player ainda precisa de revisão manual; a conferência de conectividade foi estrutural. API, Gold, segurança da IA, persistência, responsividade e reconciliação de dados reais continuam pendentes.

Scripts auxiliares, capturas, respostas brutas do MCP e exploração temporária permanecem locais em `work/`. Este registro e os links do Figma são a documentação versionada da etapa.
