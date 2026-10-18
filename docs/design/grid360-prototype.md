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

O player carregou e exibiu o panorama no navegador de validação. Navegação, rolagem, estados principais e ciclo demonstrativo de ordens foram exercitados manualmente em 17/10/2026; foi encontrada uma regressão de cancelamento registrada abaixo. API, Gold, segurança da IA, persistência, responsividade e reconciliação de dados reais continuam pendentes.

Scripts auxiliares, capturas, respostas brutas do MCP e exploração temporária permanecem locais em `work/`. Este registro e os links do Figma são a documentação versionada da etapa.

## Checkup contra o PRD — 17/10/2026

Escopo: revisão de cobertura visual dos critérios WEB-01 a WEB-07 e IA-01 a IA-06, mais conferência manual do player. Este checkup orienta o fechamento do protótipo; não altera o estado funcional dos requisitos.

| ID | Cobertura visual observada | O que falta confirmar para fechar o protótipo |
| --- | --- | --- |
| WEB-01 | Panorama com KPIs, períodos comparáveis, série e insight; frames `15:164` / `16:1129`. | Conferir definição, unidade, atualização e filtros em cada indicador; manter explícitas as distinções faturado/pago e consumido/faturado. Os valores são sintéticos e não reconciliam com Gold. |
| WEB-02 | Receita com decomposição preço × volume, municípios e bairros; `15:331` / `16:1296`. A tabela mostra classe; a ressalva distingue reajuste homologado de preço médio observado. | A coluna classe e a ressalva são visíveis, mas filtros pré-definidos não permitem provar mudança dinâmica por classe. Base insuficiente precisa permanecer legível nos recortes. |
| WEB-03 | Busca e visão da UC, histórico e contexto de faturas, medidor, GD, rede e chamados; `15:582` / `16:1547`. A busca mostra aviso de UC não encontrada; a UC demonstrativa separa faturado/pago e explicita GD indisponível e cautela causal. | Aviso e cartões são exemplos estáticos: não há busca editável nem validação dinâmica de UC sem fatura/leitura ou medidor retirado. |
| WEB-04 | Fila ordenada, motivos, estimativa e detalhe da suspeita; `15:773` / `16:1738`. | Garantir que a estimativa e os indicadores usados estejam no detalhe e rotulados como ilustrativos; suspeita não pode parecer irregularidade confirmada. Regra final depende de Gold/decisão de negócio. |
| WEB-05 | Ordens, ações, resultado, cancelamento, sucesso e validação por resultado ausente; `16:640` / `16:1894`. Criação, atualização, resultado, “Manter ordem” e cancelamento foram percorridos no player. | Defeito reproduzido: depois de cancelar `OS-DEMO-001`, reabrir “Ações da ordem” mostra “Em análise · simulação” e permite “Atualizar estado”, desfazendo visualmente o cancelamento. Corrigir a transição antes de fechar o protótipo. Estado é simulado e não persiste. |
| WEB-06 | Comparação de alimentadores, evolução DEC/FEC e ausência de denominador; `16:735` / `16:1989`. | Preservar fórmula, população/denominador, janela e origem como dados a definir ou rótulos simplificados; não sugerir conformidade regulatória. |
| WEB-07 | Tela de filtros, contexto do recorte e aviso de insight desatualizado foram observados; campos identificam valores como ilustrativos e não editáveis. | Efeito de filtro em KPIs, gráficos e insight não é testável no player porque os controles são estáticos. |
| IA-01–03 | Chat em português testado com cenário numérico, pergunta ambígua sobre conta paga/faturada, esclarecimento, fundamento e pergunta de continuidade sem evidência; `16:991` / `16:2245`. | Exemplos trazem unidade, período, recorte, fonte sintética e ressalvas; não comprovam interpretação ampla nem resposta reconciliada com Gold. |
| IA-04–05 | Insight no panorama e assistente acessível no portal, com estados representados. | Conferir vínculo do insight aos filtros/período e caminho de atualização; deixar indisponibilidade/erro com nova tentativa claros. Nenhum modelo ou serviço real é comprovado pelo Figma. |
| IA-06 | Limites e recusa de pedidos fora do escopo estão representados. | Tratar a tela como explicação visual: somente leitura, esquema permitido e bloqueio de SQL precisam ser provados no backend, não pelo protótipo. |
| WEB-08–10 | Exportação, importação e perfis não incluídos, conforme a direção desta versão. | Permanecem fora do fechamento atual enquanto não forem selecionados como diferenciais. |

### Fechamento recomendado

1. Adicionar as versões mobile (informado pela pessoa usuária como trabalho em andamento) e verificar paridade de conteúdo e caminhos essenciais nos dois temas. O protótipo registrado hoje é desktop (1440 × 1024); o PRD não define breakpoints nem obriga um layout mobile, então essa dimensão é uma extensão de escopo acordada pela equipe.
2. Ligar cada estado crítico à tela/jornada em uma matriz: carregamento, vazio legítimo, parcial/desatualizado, erro e recuperação, base pequena/denominador zero e filtro alterado com insight pendente. A biblioteca contém variantes, mas isso não prova por si só que os caminhos estejam apresentados e alcançáveis.
3. Corrigir e repetir o ciclo de cancelamento de ordem; conferir estados de UC sem fatura/leitura e medidor retirado. A exploração dinâmica por classe e a relação filtro/insight dependem de controles executáveis ou da aplicação.
4. Fazer captura legível dos novos frames mobile e dos estados corrigidos. Conferir cortes, rolagem, alvos, foco visual, contraste e diferenças entre temas. Validar teclado, leitor de tela, reflow e movimento reduzido na aplicação quando ela existir.

### Evidência desta revisão

- Inspeção do player autenticado com a senha fornecida pela pessoa usuária: panorama claro e escuro carregaram; `Próximo quadro` abriu Receita; navegação lateral abriu Inspeções; `Investigar` abriu o detalhe; `Criar ordem` abriu Ordens e exibiu `OS-DEMO-001`.
- Captura visual do panorama em ambos os temas e dos frames de Receita, fila, suspeita e Ordens. Não foram alterados dados do arquivo.
- A auditoria estrutural prévia registrada acima encontrou 16/16 frames alcançáveis por tema e ausência de destinos inexistentes. Nesta passada não foi executada uma auditoria MCP nova; a sessão atual do Codex não expõe ferramentas Figma MCP.
- Os caminhos percorridos nesta revisão são simulações do player. Não validam busca real, persistência, API, Gold, permissões de IA nem conformidade de acessibilidade executável.

### Teste manual direto do player — 17/10/2026

- **Panorama e filtros:** panorama claro/escuro carregou; abrir filtros, ler recorte e confirmar devolveu ao panorama. Os valores do filtro são fixos e identificados como ilustrativos/não editáveis. O cartão de base pequena abriu fundamento com observação, interpretação, limitações e aviso de insight desatualizado. A tela também apresenta vazio legítimo (sem afirmar consumo zero), fonte incompleta, atualização e erro; “Tentar novamente” é transição demonstrativa.
- **Receita e UC:** Receita mostrou classe na tabela e ressalva tarifa homologada/preço observado. “Investigar município” abriu estado de base insuficiente. Busca de UC abriu `DEMO-0001`; detalhes separaram consumo/faturamento de pagamento, mostraram contexto de medidor, rede e chamado e marcaram GD indisponível. “Nova busca” retorna à tela com exemplo de UC inexistente; busca e estados continuam estáticos.
- **Inspeções e operação:** fila → suspeita → ordem demonstrativa percorrido. Detalhe da suspeita mantém ressalva de que suspeita não confirma irregularidade. Operação abriu detalhe de alimentador, séries DEC/FEC e tabela de dados com aviso de exemplos sintéticos/simplificados, sem resultado regulatório.
- **Ordens:** atualização de estado e registro de resultado exibiram sucesso simulado; exemplo de erro mostrou resultado obrigatório; “Manter ordem” retornou sem cancelar; confirmação cancelou `OS-DEMO-001`. **Falha reproduzível:** reabrir ações após cancelamento reapresenta status “Em análise · simulação”; “Atualizar estado” permite desfazer o cancelamento na lista.
- **Assistente:** pergunta de receita abriu resposta numérica com período, recorte e fonte sintética; ambiguidade em “conta de luz” pediu distinção entre faturado e pago e explicitou ausência de dado de pagamento. Pergunta sobre interrupções do alimentador AL-DEMO-01 respondeu “Não há evidência para responder”, sem inventar contagem nem interpretar ausência como zero.
- **Restauração:** botão “Reiniciar” do player retornou ao panorama inicial após as alterações simuladas.
- **Limites da passada:** validação foi por cliques e inspeção visual no player autenticado. A demonstração é estática/simulada: não valida serviços, API, Gold, persistência, permissões ou cálculo real. Mobile não está disponível no arquivo nesta passada. O player informa que compatibilidade com leitor de tela está desativada; teclado, foco executável, Escape, reflow e movimento reduzido não foram certificados. A sessão não expõe Figma MCP para uma nova auditoria estrutural ou edição do arquivo.
