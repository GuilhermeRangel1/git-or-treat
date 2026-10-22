# Arquitetura do frontend

**Estado:** fundação e primeira fatia visual implementadas em 18/10/2026 na branch `feat/visual-frontend` (renomeada de `refactor/arquitetura-frontend`).

Em 21/10/2026, a DEV-03 acrescentou exploração funcional demonstrativa em `features/receita`: decoder do contrato 1.1.0, hook TanStack Query com cancelamento, filtros base/refinamentos na URL, diálogo de rascunho e componentes de resumo, decomposição, recortes e série. O retorno ao total preserva filtros base. A feature usa o transporte compartilhado e não importa `features/dev-contracts`. Confira [revisão e limites Gold](../plans/2026-10-21-dev03-evidence.md).
**Decisão:** [ADR-0001](../decisions/0001-arquitetura-frontend.md).
**Escopo de produto:** [PRD §5.2 e WEB/IA](../PRD.md). Os requisitos funcionais continuam pendentes.

## Limite da entrega

A fundação arquitetural foi concluída antes da etapa visual. A primeira fatia visual autorizada reproduz a sidebar e o topo do Panorama nos temas claro/escuro, com navegação mobile. O conteúdo do Panorama termina antes dos filtros: título, subtítulo e decoração SVG com movimento finito. A sidebar não inclui o rodapé demonstrativo; a linha de dados sintéticos e atualização ilustrativa também foi omitida.

Os títulos e subtítulos de Receita, UC 360, Inspeções, Ordens, Operação e Assistente também seguem os frames originais do Figma nos dois temas. Os rótulos superiores de UC 360 e Inspeções são Atendimento e Perdas; os nomes da navegação permanecem os mesmos. No Assistente, a abertura textual fica em um painel central de até 960 px, com superfície, borda e raio de 20 px do protótipo; não há exemplos, campo de envio ou funcionamento de chat. `title` e `section` nos metadados de rota distinguem título de página, contexto superior e rótulo do menu. O metadado `layout: "conversation"` seleciona as medidas próprias do Assistente: área desktop com margens de 32 px e cabeçalho de 48 px; painel 960 × 800 px em x=352/y=104 no viewport 1440 × 1024. No mobile 390 × 844, o painel mede 358 × 752 px em x=16/y=76. A altura de 800 px é um teto no desktop: o painel encolhe em janelas menores. A rota usa a altura dinâmica da janela (`100dvh`), cabeçalho sem encolhimento e conteúdo flexível com `min-height: 0`; somente o histórico tem rolagem. O futuro compositor deve ser um irmão do histórico, sem encolhimento, para ficar visível no rodapé do painel. Não há campo de prompt nesta etapa. Em janelas com altura de até 480 px, o cabeçalho interno do Assistente elimina o espaço reservado para preservar área de histórico. As outras rotas mantêm rolagem normal de página.

As demais funcionalidades permanecem sem conteúdo de negócio. Não há filtros, KPIs, gráficos, dados mockados, consultas, formulários operacionais ou chat. A entrega prepara a interface; não conclui requisitos funcionais do PRD.

## Estrutura e direção das dependências

```text
frontend/src/
  app/                 composição: rotas, provedores e testes de navegação
  layouts/             estrutura persistente, cabeçalho e sidebar
  features/            panorama, receita, uc360, inspecoes, ordens, operacao, assistente
  shared/
    api/               transporte HTTP e fábrica do QueryClient
    theme/             contexto, provedor e hook de tema
    ui/                marca, botão de ícone e alternância de tema
  styles/              entrada global e tokens compartilhados com Tailwind
  test/                preparação dos testes de componentes
  main.tsx             ponto de entrada
```

- `app` compõe layouts, funcionalidades e recursos compartilhados.
- `layouts` depende de seus componentes e de `shared`; recebe os itens de navegação por propriedade.
- Uma `feature` depende de seus próprios arquivos e de `shared`. Componentes de outra funcionalidade são acessados somente após extrair uma interface compartilhada pertinente.
- `shared` não importa funcionalidades, layouts ou a composição da aplicação.
- `styles` é uma fundação comum. `scripts/check-boundaries.mjs` verifica imports estáticos e dinâmicos literais reconhecidos pelo analisador TypeScript, relativos ou via `@/`.
- `shared/ui` contém apenas os componentes visuais reutilizados pelo layout. `shared/filters` e `shared/analytics` continuam adiados até existirem componentes e contratos concretos.

## Composição, navegação e tema

Em 22/10/2026, a correção responsiva DEV-05 alinhou `AppLayout` e `Header` ao padrão já presente no Panorama da DEV-02: largura disponível com teto de 1920 px, centralização e padding progressivo (`px-4`, `sm:px-6`, `lg:px-8`, `xl:px-12`). O limite anterior de 1184 px deixava a fila concentrada à esquerda em monitores largos. O layout de conversa mantém seu tratamento próprio. O cabeçalho global acompanha as margens do conteúdo. A correção foi conferida em 1440, 1920, 2560 e 390 px, sem merge da DEV-02.

`app/routes.ts` é o registro de caminhos, rótulos, metadados, ícones Lucide e componentes de entrada. `app/router.tsx` monta as rotas filhas em `AppLayout` com `Outlet`. A estrutura e seus estados locais permanecem montados ao navegar. Raiz e caminhos desconhecidos preservam o redirecionamento para Panorama.

As páginas não recriam sidebar, cabeçalho global ou provedores. O metadado `contentHeading` permite que Panorama e Assistente forneçam sua própria apresentação sem acoplar o layout à funcionalidade. O menu mobile usa `dialog` nativo, fecha ao navegar ou passar para desktop e oferece fechamento por botão e Escape, com retorno de foco ao acionador. Os metadados do assistente referenciam IA-05, acesso ao agente no portal. Os demais estados do agente continuam trabalho futuro.

O tema usa `data-theme` no elemento raiz e preferência local quando disponível, com fallback para o sistema. Falha de leitura/gravação no armazenamento não impede iniciar nem alternar o tema. O modo é aplicado antes da pintura da atualização React. Nenhuma informação de negócio é persistida nesse mecanismo.

## Estilização

React + TypeScript + Vite, Tailwind CSS 4 com `@tailwindcss/vite` e Lucide React são a base adotada.

`styles/globals.css` importa Tailwind e tokens. `@theme inline` conecta variáveis existentes a utilitários semânticos como `bg-canvas`, `bg-surface`, `text-content`, `text-muted` e `border-border`. A variante `dark:` acompanha `data-theme`, mantendo o tema selecionado pela pessoa.

Os blocos superiores das páginas padrão têm largura máxima de 810 px no desktop; os títulos usam sua largura natural e o subtítulo ocupa o bloco. Em 1440 × 1024, título e subtítulo começam em x=272/y=116 e x=272/y=164. No mobile, começam em x=16/y=84, com o subtítulo abaixo do título e intervalo de 8 px; as quebras de UC 360 e Ordens acompanham os respectivos frames. Medições via Playwright MCP foram comparadas aos metadados dos seis frames desktop/mobile, nos dois temas.

O CSS transitório de layout foi removido. Sidebar, cabeçalho e Panorama usam utilitários Tailwind e tokens semânticos; as fontes seguem o Figma: Manrope, DM Sans e IBM Plex Mono. O item ativo usa fundo neutro e barra goiaba. A sidebar desktop mede 224 px, seus itens têm 44 px e os controles de tema/menu têm 44 × 44 px; o menu mobile ocupa a tela e seus itens têm 48 px. O breakpoint do layout desktop é 1024 px.

Os ícones identificados no Figma são importados de `lucide-react`, sem arquivos SVG exportados para ícones. Os assets locais da marca preservam as versões clara/escura do Figma. A decoração do Panorama agora é um SVG React único, mantendo os dois traçados originais. No desktop, fica entre o texto de abertura e o alternador de tema; sua largura é responsiva até 320 px, na proporção original, e não altera a posição do texto ou dos controles. Os dez SVGs decorativos anteriormente importados foram removidos. A decoração é oculta de tecnologias assistivas, não recebe foco e não representa uma série de dados.

Referências consultadas via Figma MCP em 18/10/2026: [Panorama desktop claro](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=15-164), [escuro](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=16-1129), [mobile claro](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=195-3781) e [menu mobile](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=197-4744). A identidade original é a referência vigente.

## Estado: política para as próximas funcionalidades

| Estado | Responsabilidade |
| --- | --- |
| Filtros aplicados, período, comparação, paginação e ordenação | URL normalizada e validada pela funcionalidade; preservar somente parâmetros pertinentes ao navegar. |
| Dados recebidos, atualização e erro de consulta | TanStack Query; chaves incluem os parâmetros que alteram a resposta. |
| Formulário ainda não confirmado, menu e diálogo | Estado local do componente ou funcionalidade. |
| Tema | Provedor compartilhado e preferência local. |
| Mensagens e envio do assistente | Estado próprio do módulo, com retenção e contexto acordados com backend/IA. |

Além dos provedores de tema e cache, há controles locais de navegação e aparência. Ainda não há filtros, hooks de domínio, histórico de chat ou estado operacional. O QueryClient é estável por montagem dos provedores; retries automáticos de consultas e mutações ficam desativados por padrão. Cada funcionalidade deverá escolher atualização, expiração e tentativas com base em seu contrato. Nenhum provedor dispara requisições.

## Fronteira HTTP e contratos

### DEV-01 — verificação isolada de contratos

A rota `/dev/contratos`, documentada na [ADR-0004](../decisions/0004-contratos-analiticos-e-fonte-sintetica.md), existe somente em desenvolvimento. Sua feature usa o transporte existente, TanStack Query e um decoder da resposta de indicadores; filtros aplicados compõem a chave da consulta e requisições aceitam cancelamento. Ela não consta na navegação e sua importação é excluída do build de produção. As afirmações anteriores de ausência de consultas descrevem a fatia visual das páginas do produto; o diagnóstico DEV-01 é a primeira consulta sintética integrada.

O recorte aplicado da ferramenta fica na URL normalizada; o formulário mantém somente o rascunho ainda não confirmado. Links válidos restauram consulta e campos ao abrir/recarregar, e a navegação pelo histórico acompanha o recorte. Parâmetros inválidos impedem a consulta até a correção. Atualização em segundo plano mantém o resultado cacheado válido com aviso acessível, distinto do carregamento inicial.

O [catálogo de contratos](../contracts/analytics-api.md) descreve versão, disponibilidade, origem e pontos provisórios. Os schemas legados de `common.py` e contratos locais de IA não são prova de integração Gold. O decoder do diagnóstico aceita a versão sintética explícita; a futura integração com dados reais requer revisão do consumidor e das definições.

`shared/api/client.ts` usa Fetch e aceita `RequestInit`, inclusive `AbortSignal`. Lê o corpo uma única vez, distingue erro HTTP, rede, configuração e JSON inválido e preserva cancelamentos. Resposta vazia retorna `undefined`; o consumidor deve tipá-la como `void`. Um corpo string é tratado como JSON quando o chamador não fornece `Content-Type`; FormData mantém seu cabeçalho automático.

`apiClient<T>` expressa o tipo esperado em compilação; não valida o conteúdo recebido em execução. Cada funcionalidade deverá acordar DTOs e validação/adaptação com o backend antes de consumir dados. Os envelopes já propostos em `backend/app/schemas/common.py` e os contratos sintéticos no [guia de IA](../services/ai-agent.md) são referências em revisão, não autorização para apresentar placeholders como dados reais.

`VITE_API_URL` é uma URL pública do backend: fallback local somente em desenvolvimento; uma requisição fora desse modo exige configuração explícita. Não é necessário configurar API para abrir esta interface visual. Variáveis `VITE_*` são públicas e não recebem credenciais. Nenhuma rota do backend é consultada nesta etapa.

As próximas integrações devem preservar unidade, período, filtros, atualização, qualidade e indisponibilidade. Ausência não vira zero. Fórmulas oficiais, segurança, transições e idempotência permanecem responsabilidades do backend/Gold. A interface deverá refletir confirmação do servidor e vincular o insight ao mesmo recorte aplicado, sem apresentar resposta antiga como interpretação nova.

## Qualidade e evidências

TypeScript estrito, Oxlint, Prettier, verificação de fronteiras e Vitest/Testing Library estão disponíveis em scripts do [package.json](../../frontend/package.json) e executados na CI.

Os testes atuais verificam a fronteira HTTP, cancelamento, configuração, navegação entre sete áreas, persistência da estrutura e do tema e falha do armazenamento. A primeira fatia visual também é conferida em Chrome headless nos dois temas, em desktop e mobile, incluindo ausência de requisições de negócio e comportamento do menu. Esses testes não exercitam Gold, jornadas de negócio ou acessibilidade completa. As dimensões principais são comparadas ao Figma; a reprodução se limita à fatia autorizada.

## Referências consultadas em 18/10/2026

- [Tailwind com Vite](https://tailwindcss.com/docs/installation/using-vite) e [tokens](https://tailwindcss.com/docs/theme), Tailwind 4.
- [Layouts React Router](https://reactrouter.com/start/declarative/routing), React Router 7.
- [QueryClientProvider](https://tanstack.com/query/latest/docs/framework/react/reference/QueryClientProvider), TanStack Query 5.
- [Vitest](https://vitest.dev/guide/), Vitest 4; [Testing Library](https://testing-library.com/docs/react-testing-library/intro/).
- Versões resolvidas e reproduzíveis: `frontend/package-lock.json`.

### Verificação de zoom em 18/10/2026

- Playwright MCP: 24 comparações de posicionamento (seis páginas × desktop/mobile × claro/escuro), incluindo posição, altura, quebra de linha e largura do bloco de contexto. A rasterização dos glifos depende do navegador; a conferência não usa igualdade de bitmap.
- Zoom nativo da aba em Chromium isolado: 80%, 100%, 125%, 150%, 175%, 200%, 300% e 400%, em viewport inicial de 1280 × 800. Verificar sete rotas nos dois temas, ausência de rolagem horizontal/corte do título, acesso ao menu e área de histórico do Assistente. As páginas de conteúdo mantêm rolagem vertical quando necessária; o Assistente limita a rolagem ao histórico.
- Evidências locais e roteiros ficam em `work/visual-frontend/`, ignorado pelo Git. A extensão de teste existe somente no navegador isolado e não integra o frontend ou o perfil pessoal.
- Método baseado na documentação oficial de [extensões no Playwright](https://playwright.dev/docs/chrome-extensions) e [zoom da aba no Chromium](https://developer.chrome.com/docs/extensions/reference/api/tabs#method-setZoom). Nenhuma dependência nova de produto foi instalada.

### Movimento decorativo do Panorama — 18/10/2026

Aprovado na conversa e implementado em `features/panorama/PanoramaArtwork.tsx` e `panorama-artwork.css`. Referências: percurso de luz do [Animated Beam](https://magicui.design/docs/components/animated-beam) e iluminação suave do [Background Beams](https://ui.aceternity.com/components/background-beams). São referências de comportamento; nenhuma biblioteca foi adicionada.

As linhas em petróleo são desenhadas em aproximadamente 1,2 s. Pulsos goiaba percorrem as duas trilhas com rastro e pequeno intervalo; pontos próximos acendem em pistache conforme a distância ao percurso. A sequência inicial dura no máximo cerca de 3,73 s e repousa. A entrada do mouse após o término dispara apenas os pulsos, sem reiniciar uma sequência ativa e sem apresentar cursor de ação. Não há loop automático, dados, mensagens ou chamadas de rede associadas.

`prefers-reduced-motion: reduce` desativa todas as animações e mantém as linhas estáticas. O ornamento continua oculto abaixo do breakpoint desktop, incluindo reflow com zoom. Temas alteram as cores por CSS, sem remontar a animação. A única mudança de estado local ocorre ao repetir a sequência; não há temporizador ou loop JavaScript por frame.

Verificação: Playwright MCP para entrada, término, replay, bloqueio de replay durante execução, preferência reduzida, temas e mobile; inspeção visual do pulso e medição de `stroke-dashoffset` em diferentes instantes. Capturas e roteiros em `work/visual-frontend/`, ignorado pelo Git. Critérios funcionais de WEB-01/IA continuam pendentes.
